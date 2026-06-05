#!/usr/bin/env python3
"""Strict pipeline: DATA → code gates → train → artifacts → model → verify → sign."""

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
    e = {**os.environ, "PYTHONPATH": str(ROOT), "GATE_STRICT": "true", **env}
    try:
        subprocess.run(cmd, cwd=ROOT, env=e, check=True)
    except subprocess.CalledProcessError as exc:
        step = args[0] if args else "pipeline"
        print(
            f"\nPIPELINE FAIL на шаге {step} (exit {exc.returncode}).\n"
            "Проверьте лог выше: уязвимость / компрометация / невалидные данные.\n"
            "MLSecOps: вкладки Pipeline и Findings в Security Center.\n",
            file=sys.stderr,
        )
        raise


def _script_has_crlf(path: Path) -> bool:
    if not path.exists():
        return False
    return b"\r\n" in path.read_bytes()[:8192]


def _use_python_gates() -> bool:
    """Use Python gate runners on Windows or when .sh files have CRLF (Docker volume on Windows)."""
    if os.getenv("FORTRESS_PYTHON_GATES", "").lower() in ("1", "true", "yes"):
        return True
    if sys.platform == "win32":
        return True
    import shutil
    if shutil.which("bash") is None:
        return True
    for script in (
        "scripts/ci/gate_code.sh",
        "scripts/ci/gate_artifacts.sh",
        "scripts/ci/gate_model.sh",
    ):
        if _script_has_crlf(ROOT / script):
            print(f"NOTE: {script} has CRLF — using Python gates", file=sys.stderr)
            return True
    return False


def run_sh(script: str, **env: str) -> None:
    path = ROOT / script
    print("+", script)
    e = {**os.environ, "PYTHONPATH": str(ROOT), "GATE_STRICT": "true", **env}
    subprocess.run(["bash", str(path)], cwd=ROOT, env=e, check=True)


def report(
    run_id: str,
    element: str,
    gate: str,
    status: str,
    corr: str,
    message: str = "",
) -> None:
    args = [
        "scripts/ci/report_gate.py",
        "--run-id", run_id,
        "--element", element,
        "--gate", gate,
        "--status", status,
        "--correlation-id", corr,
    ]
    if message:
        args.extend(["--message", message])
    run_py(args)


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from fortress.gate_verifier import build_attestation_elements, verify_pipeline_run  # noqa: E402

    run_id = os.getenv("RUN_ID", f"local-{uuid.uuid4().hex[:8]}")
    corr = os.getenv("CORRELATION_ID", str(uuid.uuid4()))
    mlflow_uri = os.getenv(
        "MLFLOW_TRACKING_URI",
        f"sqlite:///{ROOT / 'artifacts' / 'mlflow-local.db'}",
    )
    env = {
        "RUN_ID": run_id,
        "CORRELATION_ID": corr,
        "ARTIFACTS_DIR": str(ROOT / "artifacts"),
        "MLFLOW_TRACKING_URI": mlflow_uri,
        "MLFLOW_ALLOW_FILE_STORE": "true",
        "GATE_STRICT": "true",
    }
    model_key = os.getenv("MODEL_KEY", "all")

    # --- DATA + registry ---
    dataset_csv = ROOT / "data" / "datasets" / "train_clean.csv"
    actor = os.getenv("PIPELINE_ACTOR", "ci")
    run_py(
        ["scripts/ingest_dataset.py", str(dataset_csv),
         "--name", "train_clean", "--version", "v1",
         "--expected-cols", "amount,age,target", "--actor", actor],
        **env,
    )
    report(run_id, "data", "DATA", "passed", corr)

    # --- CODE (full gates, strict) ---
    if _use_python_gates():
        run_py(["scripts/ci/gate_code.py"], **env)
        for g in ("G0", "G1", "G3", "G3b"):
            report(run_id, "code", g, "passed", corr)
    else:
        run_sh("scripts/ci/gate_code.sh", **env)

    # --- TRAIN ---
    for t in ("models/m1_scoring/train.py", "models/m2_antifraud/train.py", "models/m3_nlp/train.py"):
        run_py([t], **env)
    report(run_id, "train", "", "passed", corr, message="train complete")

    keys = ["m1", "m2", "m3"] if model_key == "all" else [model_key]
    for mk in keys:
        mk_env = {**env, "MODEL_KEY": mk}
        if _use_python_gates():
            run_py(["scripts/ci/gate_artifacts_py.py"], **mk_env)
            run_py(["scripts/ci/gate_model_py.py"], **mk_env)
        else:
            run_sh("scripts/ci/gate_artifacts.sh", **mk_env)
            run_sh("scripts/ci/gate_model.sh", **mk_env)

    # --- Verify artifacts on disk (mandatory) ---
    from fortress.gate_verifier import verify_onnx_artifacts
    from fortress.registry_policy import ci_model_name

    for mk in keys:
        aok, amsg = verify_onnx_artifacts(mk)
        if not aok:
            print(f"ARTIFACT FAIL {mk}: {amsg}", file=sys.stderr)
            sys.exit(1)
        print(f"VERIFY {mk}: {amsg}")

    ok, errs = verify_pipeline_run(run_id, model_key, require_db=False)
    for e in errs:
        print(f"WARN pipeline_runs: {e}", file=sys.stderr)

    run_py(
        ["scripts/ci/sign_attestation.py", "--run-id", run_id,
         "--model", ci_model_name(model_key),
         "--model-key", model_key,
         "--correlation-id", corr,
         "--strict"],
        **env,
    )

    # Auto-sync attestation → MLflow (source of truth for all developers)
    run_py(
        ["scripts/ci/sync_pipeline_to_mlflow.py", "--model-key", model_key, "--actor", "ci"],
        **env,
    )
    print("=== Pipeline OK (strict) — attestation в MLflow ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
