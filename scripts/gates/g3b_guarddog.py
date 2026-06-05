#!/usr/bin/env python3
"""G3b — typosquat in requirements + guarddog PyPI metadata scan."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPOS = ("pytirch", "tenserflew", "scikit-learnn", "numppy", "requestss", "pytorchh")
PKG_RE = re.compile(r"^([a-zA-Z0-9][\w.-]*)")
REQ_FILES = ("requirements.txt", "requirements-llm.txt")


def _packages(path: Path) -> list[str]:
    names: list[str] = []
    if not path.exists():
        return names
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().split("#", 1)[0].strip()
        if not line or line.startswith("-") or "://" in line.lower():
            continue
        m = PKG_RE.match(line)
        if m:
            names.append(m.group(1).replace("_", "-").lower())
    return names


def _typosquat_in_files(root: Path) -> list[str]:
    errors: list[str] = []
    for name in REQ_FILES:
        text = (root / name).read_text(encoding="utf-8").lower() if (root / name).exists() else ""
        for typo in TYPOS:
            if typo in text:
                errors.append(f"{name}: typosquat pattern '{typo}'")
    return errors


def _guarddog_available() -> bool:
    try:
        subprocess.run(
            ["guarddog", "--version"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def _guarddog_scan(pkg: str, *, timeout: int) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [
                "guarddog",
                "pypi",
                "scan",
                pkg,
                "-r",
                "typosquatting",
                "--exit-non-zero-on-finding",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"timeout scanning {pkg}"
    if proc.returncode != 0:
        detail = (proc.stdout or proc.stderr or "").strip()
        return False, detail or f"guarddog flagged {pkg}"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="G3b guarddog requirements scan")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--per-package-timeout", type=int, default=120)
    args = parser.parse_args()

    typos = _typosquat_in_files(args.root)
    if typos:
        for err in typos:
            print(f"G3b FAIL: {err}")
        return 1

    if not _guarddog_available():
        print("G3b FAIL: guarddog not installed")
        return 1

    packages: list[str] = []
    for name in REQ_FILES:
        packages.extend(_packages(args.root / name))
    # stable unique order
    seen: set[str] = set()
    unique = []
    for pkg in packages:
        if pkg not in seen:
            seen.add(pkg)
            unique.append(pkg)

    workers = min(3, max(1, len(unique)))
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_guarddog_scan, pkg, timeout=args.per_package_timeout): pkg
            for pkg in unique
        }
        for fut in as_completed(futures):
            pkg = futures[fut]
            try:
                ok, msg = fut.result()
            except Exception as exc:
                ok, msg = False, str(exc)
            if not ok:
                failures.append(f"{pkg}: {msg}")
            else:
                print(f"G3b OK: {pkg}")

    if failures:
        for err in failures:
            print(f"G3b FAIL: {err}")
        return 1

    print(f"G3b PASS: guarddog scanned {len(unique)} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
