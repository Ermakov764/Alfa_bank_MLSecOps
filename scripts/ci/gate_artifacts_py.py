#!/usr/bin/env python3
"""Artifact gates G6 G7 (Python, cross-platform)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RUN_ID = os.getenv("RUN_ID", "local")
CORR = os.getenv("CORRELATION_ID", "local")
MK = os.getenv("MODEL_KEY", "m1")


def report(gate: str, status: str, msg: str = "") -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/ci/report_gate.py",
            "--run-id",
            RUN_ID,
            "--element",
            "artifacts",
            "--gate",
            gate,
            "--status",
            status,
            "--correlation-id",
            CORR,
            "--message",
            msg,
        ],
        cwd=ROOT,
        check=False,
    )


def main() -> int:
    if MK == "m2":
        art = ROOT / "artifacts/models/m2_antifraud"
    elif MK == "m3":
        art = ROOT / "models/m3_nlp/artifact"
    else:
        art = ROOT / "models/m1_scoring/artifact"

    report("G6", "started")
    r = subprocess.run(
        [sys.executable, "scripts/check_format_policy.py", str(art)],
        cwd=ROOT,
    )
    if r.returncode != 0:
        report("G6", "failed", "G6 format policy")
        return 1
    report("G6", "passed")

    onnx_files = list(art.rglob("*.onnx"))
    if onnx_files:
        onnx = onnx_files[0]
        report("G7", "started")
        r2 = subprocess.run(
            [sys.executable, "scripts/gates/g7_sign_manifest.py", str(onnx)],
            cwd=ROOT,
        )
        if r2.returncode != 0:
            report("G7", "failed", "G7 manifest")
            return 1
        report("G7", "passed")

    print(f"gate-artifacts: PASS ({MK})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
