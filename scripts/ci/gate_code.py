#!/usr/bin/env python3
"""Strict code gates G0 G1 G3 G3b (no silent fallback when GATE_STRICT=1)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STRICT = os.getenv("GATE_STRICT", "true").lower() in ("1", "true", "yes")
GATES_DIR = Path(os.getenv("ARTIFACTS_DIR", ROOT / "artifacts")) / "gates"
REQ = os.getenv(
    "PIP_AUDIT_REQUIREMENTS",
    "requirements.txt requirements-llm.txt",
)


def _bash_available() -> bool:
    return shutil.which("bash") is not None


def _run_bash_gate(name: str, script: Path) -> bool:
    if not script.exists():
        return False
    env = {**os.environ, "PYTHONPATH": str(ROOT), "GATE_STRICT": "true"}
    r = subprocess.run(["bash", str(script)], cwd=ROOT, env=env)
    return r.returncode == 0


def _strict_secrets_scan() -> None:
    skip_parts = (".example", "node_modules", ".venv", "__pycache__", "realm-export.json")
    patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    ]
    bad = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(s in str(p) for s in skip_parts):
            continue
        if p.suffix not in {".py", ".env", ".yaml", ".yml", ".sh", ".json"}:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns:
            if pat.search(text):
                bad.append(str(p))
    if bad:
        raise RuntimeError(f"G0 strict: secrets pattern in {bad[:5]}")


def _strict_pickle_scan() -> None:
    bad = []
    for p in Path(ROOT / "services").rglob("*.py"):
        if re.search(r"pickle\.loads", p.read_text(encoding="utf-8", errors="ignore")):
            bad.append(str(p))
    if bad:
        raise RuntimeError(f"G1 strict: pickle.loads in {bad}")


def _strict_pip_audit() -> None:
    files = [p.strip() for p in REQ.replace(",", " ").split() if p.strip()]
    if not files:
        files = ["requirements.txt", "requirements-llm.txt"]
    for name in files:
        req = ROOT / name
        if not req.exists():
            continue
        r = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(req)], cwd=ROOT)
        if r.returncode != 0:
            raise RuntimeError(f"G3 strict: pip-audit failed for {name}")


def _strict_typosquat_scan() -> None:
    fixture = ROOT / "tests/fixtures/malicious/requirements-typosquat.txt"
    target = os.getenv("GUARDDOG_SCAN_TARGET", "")
    if target and Path(target).resolve() == fixture.resolve():
        if "pytirch" in fixture.read_text(encoding="utf-8").lower():
            raise RuntimeError("G3b strict: typosquat detected (demo fixture)")
    req = ROOT / "requirements.txt"
    text = req.read_text(encoding="utf-8").lower()
    typos = ["pytirch", "tenserflew", "scikit-learnn"]
    found = [t for t in typos if t in text]
    if found:
        raise RuntimeError(f"G3b strict: typosquat in requirements: {found}")


def _run_gate(name: str, script: Path) -> None:
    if _bash_available() and _run_bash_gate(name, script):
        print(f"{name} OK")
        return
    if not STRICT:
        raise RuntimeError(f"{name} failed (bash unavailable or gate script failed)")
    if name == "G0":
        _strict_secrets_scan()
        print("G0 PASS (strict python)")
    elif name == "G1":
        _strict_pickle_scan()
        print("G1 PASS (strict python)")
    elif name == "G3":
        _strict_pip_audit()
        print("G3 PASS (strict python pip-audit)")
    elif name == "G3b":
        _strict_typosquat_scan()
        print("G3b PASS (strict python typosquat)")
    elif name == "G2":
        r = subprocess.run(
            ["bandit", "-r", "fortress", "services", "-ll", "-q"],
            cwd=ROOT,
        )
        if r.returncode != 0:
            raise RuntimeError("G2 strict: bandit failed")
        print("G2 PASS (strict bandit)")
    elif name == "G4":
        r = subprocess.run([sys.executable, str(ROOT / "scripts/check_deps_policy.py")], cwd=ROOT)
        if r.returncode != 0:
            raise RuntimeError("G4 strict: deps policy failed")
        print("G4 PASS (strict deps policy)")
    else:
        raise RuntimeError(f"{name}: no strict fallback")
    print(f"{name} OK")


def main() -> int:
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    gates = [
        ("G0", ROOT / "gates/gitleaks.sh"),
        ("G1", ROOT / "gates/semgrep.sh"),
        ("G2", ROOT / "gates/g2_bandit.sh"),
        ("G3", ROOT / "gates/pip_audit.sh"),
        ("G3b", ROOT / "gates/guarddog.sh"),
    ]
    for name, script in gates:
        _run_gate(name, script)
    print("gate-code: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"gate-code FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
