#!/usr/bin/env python3
"""Run 10 security verification checks (local / CI)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    print("=== FORTRESS 10-check verification suite ===\n")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_gate_integrity.py", "-v", "--tb=short"],
        cwd=ROOT,
    )
    if r.returncode != 0:
        print("\nFAIL: integrity tests")
        return r.returncode

    print("\n--- Extra: poison ingest must fail ---")
    r2 = subprocess.run(
        [
            sys.executable,
            "scripts/ingest_dataset.py",
            "data/datasets/train_poisoned.csv",
            "--name",
            "t_poison",
            "--version",
            "v1",
            "--expected-cols",
            "amount,age,target",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r2.returncode == 0:
        print("FAIL: poison ingest should exit non-zero", r2.stdout, r2.stderr)
        return 1
    print("OK: poison blocked (exit", r2.returncode, ")")

    print("\n--- Extra: strict gate_code (python) ---")
    r3 = subprocess.run(
        [sys.executable, "scripts/ci/gate_code.py"],
        cwd=ROOT,
        env={**os.environ, "GATE_STRICT": "true", "PYTHONPATH": str(ROOT)},
    )
    if r3.returncode != 0:
        print("FAIL: gate_code strict")
        return r3.returncode
    print("OK: gate_code strict")

    print("\n=== All 10+ checks PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
