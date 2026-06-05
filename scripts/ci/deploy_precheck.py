#!/usr/bin/env python3
"""CLI wrapper for fortress.promote.run_precheck."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.promote import run_precheck  # noqa: E402


def main() -> int:
    model = os.getenv("DEPLOY_MODEL", "")
    version = os.getenv("DEPLOY_VERSION", "")
    role = os.getenv("ACTOR_ROLE", "ds")
    if not model or not version:
        print("FAIL: DEPLOY_MODEL and DEPLOY_VERSION required")
        return 1
    ok, msg = run_precheck(model, version, actor_role=role)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
