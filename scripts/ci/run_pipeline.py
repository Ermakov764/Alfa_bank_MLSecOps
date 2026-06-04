#!/usr/bin/env python3
"""Cross-platform pipeline: DATA → code gates → train → artifacts → model → sign."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_py(args: list[str], **env: str) -> None:
    cmd = [sys.executable] + args
    print("+", " ".join(cmd))
    e = {**os.environ, "PYTHONPATH": str(ROOT), **env}
    subprocess.run(cmd, cwd=ROOT, env=e, check=True)


def run_sh(script: str, **env: str) -> None:
    path = ROOT / script
    print("+", script)
    e = {**os.environ, "PYTHONPATH": str(ROOT), **env}
    if sys.platform == "win32":
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
            cwd=ROOT,
            env=e,
            check=True,
        )
    else:
        subprocess.run(["bash", str(path)], cwd=ROOT, env=e, check=True)


def main() -> int:
    run_id = os.getenv("RUN_ID", f"local-{uuid.uuid4().hex[:8]}")
    corr = os.getenv("CORRELATION_ID", str(uuid.uuid4()))
    mlflow_uri = os.getenv(
        "MLFLOW_TRACKING_URI",
        f"sqlite:///{ROOT / 'artifacts' / 'mlflow.db'}",
    )
    env = {
        "RUN_ID": run_id,
        "CORRELATION_ID": corr,
        "ARTIFACTS_DIR": str(ROOT / "artifacts"),
        "MLFLOW_TRACKING_URI": mlflow_uri,
        "MLFLOW_ALLOW_FILE_STORE": "true",
    }

    # Element 1: DATA
    run_py(
        ["scripts/data_gate.py", "data/datasets/train_clean.csv",
         "--expected-cols", "amount,age,target", "--actor", "ci"],
        **env,
    )
    run_py(
        ["scripts/ci/report_gate.py", "--run-id", run_id, "--element", "data",
         "--gate", "DATA", "--status", "passed", "--correlation-id", corr],
        **env,
    )

    # Element 2: lightweight code check (full G0–G3 in CI gate_code.sh / workflow)
    run_py(["-c", (
        "from pathlib import Path; import re; "
        "bad=[p for p in Path('services').rglob('*.py') "
        "if re.search(r'pickle\\.loads', p.read_text(errors='ignore'))]; "
        "assert not bad, bad"
    )], **env)
    run_py(
        ["scripts/ci/report_gate.py", "--run-id", run_id, "--element", "code",
         "--gate", "CODE", "--status", "passed", "--correlation-id", corr],
        **env,
    )

    # Train
    for t in ("models/m1_scoring/train.py", "models/m2_antifraud/train.py", "models/m3_nlp/train.py"):
        run_py([t], **env)

    model_key = os.getenv("MODEL_KEY", "all")
    keys = ["m1", "m2", "m3"] if model_key == "all" else [model_key]
    for mk in keys:
        os.environ["MODEL_KEY"] = mk
        art = ROOT / "models/m1_scoring/artifact"
        if mk == "m2":
            art = ROOT / "artifacts/models/m2_antifraud"
        if mk == "m3":
            art = ROOT / "models/m3_nlp/artifact"
        run_py(["scripts/check_format_policy.py", str(art)], **env)
        if mk in ("m1", "m2"):
            onnx = art / "onnx" / "model.onnx"
            if onnx.exists():
                run_py(["scripts/gates/g7_sign_manifest.py", str(onnx)], **env)
                run_py(["scripts/gates/g8_validate.py", mk], **env)
                run_py(["scripts/gates/g9_art.py", mk], **env)

    run_py(
        ["scripts/ci/sign_attestation.py", "--run-id", run_id, "--model", "all", "--model-key", "all"],
        **env,
    )
    print("=== Pipeline OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
