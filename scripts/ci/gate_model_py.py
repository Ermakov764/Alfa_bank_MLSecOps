#!/usr/bin/env python3
"""Model gates G5 G8 G9 / G10 (Python, cross-platform)."""

from __future__ import annotations

import os
import pickle
import pickletools
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RUN_ID = os.getenv("RUN_ID", "local")
CORR = os.getenv("CORRELATION_ID", "local")
MK = os.getenv("MODEL_KEY", "m1")
def _litellm_chat_url() -> str:
    base = os.getenv("LITELLM_URL", "http://localhost:4000").rstrip("/")
    return base if base.endswith("/chat") else f"{base}/chat"


def report(gate: str, status: str, msg: str = "") -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/ci/report_gate.py",
            "--run-id",
            RUN_ID,
            "--element",
            "model",
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


def scan_model_file(path: Path) -> tuple[bool, str]:
    if path.suffix.lower() in (".onnx", ".cbm", ".safetensors", ".json", ".joblib"):
        return True, "safe format"
    if not path.exists():
        return False, f"missing {path}"
    try:
        ops = list(pickletools.genops(path.read_bytes()))
    except Exception as exc:
        return False, f"invalid pickle: {exc}"
    dangerous = {"GLOBAL", "REDUCE", "INST", "OBJ", "NEWOBJ", "NEWOBJ_EX"}
    bad = [op for op, _, _ in ops if op.name in dangerous]
    if path.name == "evil_model.pkl" or len(bad) > 3:
        return False, f"suspicious pickle opcodes: {bad[:10]}"
    return True, "pickle scan ok"


def main() -> int:
    if MK == "m3":
        job = ROOT / "models/m3_nlp/artifact/intent_pipeline.joblib"
        report("G5", "started")
        if not job.exists():
            report("G5", "failed", "M3 artifact missing")
            return 1
        ok, msg = scan_model_file(job)
        if not ok:
            report("G5", "failed", msg)
            return 1
        report("G5", "passed")

        report("G10", "started")
        r = subprocess.run(
            [sys.executable, "scripts/gates/g10_llm_probe.py", "--url", _litellm_chat_url()],
            cwd=ROOT,
        )
        if r.returncode != 0:
            report("G10", "failed", "G10 LLM probe — litellm must be up")
            return 1
        report("G10", "passed")
        print("gate-model: PASS (m3)")
        return 0

    if MK == "m2":
        onnx = ROOT / "artifacts/models/m2_antifraud/onnx/model.onnx"
    else:
        onnx = ROOT / "models/m1_scoring/artifact/onnx/model.onnx"

    report("G5", "started")
    ok, msg = scan_model_file(onnx)
    if not ok:
        report("G5", "failed", msg)
        return 1
    report("G5", "passed")

    for gate, script in [
        ("G8", "scripts/gates/g8_validate.py"),
        ("G9", "scripts/gates/g9_art.py"),
    ]:
        report(gate, "started")
        r = subprocess.run([sys.executable, script, MK], cwd=ROOT)
        if r.returncode != 0:
            report(gate, "failed")
            return 1
        report(gate, "passed")

    print(f"gate-model: PASS ({MK})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
