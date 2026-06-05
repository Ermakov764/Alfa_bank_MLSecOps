#!/usr/bin/env python3
"""G4 — dependency policy: version pinning + typosquat block + trusted VCS hosts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQ_FILES = ("requirements.txt", "requirements-llm.txt", "requirements-docker-api.txt")
TYPOS = ("pytirch", "tenserflew", "scikit-learnn", "numppy", "requestss")
TRUSTED_VCS = ("github.com", "gitlab.com", "bitbucket.org")
# package line with at least one version constraint
PINNED = re.compile(
    r"^[a-zA-Z0-9][\w.-]*(?:\[[^\]]+\])?\s*(===|==|>=|<=|~=|!=|>|<)",
)
COMMENT = re.compile(r"^\s*#")
OPTION = re.compile(r"^-")
VCS_LINE = re.compile(r"^(git\+|https?://)", re.I)


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return errors
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or COMMENT.match(line) or OPTION.match(line):
            continue
        low = line.lower()
        for typo in TYPOS:
            if typo in low:
                errors.append(f"{path.name}:{i} typosquat pattern '{typo}'")
        if VCS_LINE.match(line):
            if not any(h in low for h in TRUSTED_VCS):
                errors.append(f"{path.name}:{i} untrusted VCS URL")
            continue
        if not PINNED.match(line.split("#")[0].strip()):
            errors.append(f"{path.name}:{i} unpinned dependency: {line}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="G4 dependency policy")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors: list[str] = []
    for name in REQ_FILES:
        errors.extend(_check_file(args.root / name))
    if errors:
        for e in errors:
            print(f"G4 FAIL: {e}")
        return 1
    print("G4 PASS: dependencies pinned and trusted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
