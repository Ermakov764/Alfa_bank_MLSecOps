#!/usr/bin/env python3
"""Platform pipeline: DATA (optional) → code gates → sign attestation."""

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
    if os.getenv("FORTRESS_PYTHON_GATES", "").lower() in ("1", "true", "yes"):
        return True
    if sys.platform == "win32":
        return True
    import shutil
    if shutil.which("bash") is None:
        return True
    if _script_has_crlf(ROOT / "scripts/ci/gate_code.sh"):
        print("NOTE: gate_code.sh has CRLF — using Python gates", file=sys.stderr)
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
    from fortress.gate_verifier import verify_pipeline_run  # noqa: E402

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
    actor = os.getenv("PIPELINE_ACTOR", "ci")
    skip_data = os.getenv("PIPELINE_SKIP_DATA", "").lower() in ("1", "true", "yes")

    if not skip_data:
        dataset_csv = os.getenv("PIPELINE_DATASET_CSV", str(ROOT / "data/datasets/train_clean.csv"))
        dataset_path = Path(dataset_csv)
        if dataset_path.exists():
            expected_cols = os.getenv("PIPELINE_EXPECTED_COLS", "")
            ingest_args = [
                "scripts/ingest_dataset.py", str(dataset_path),
                "--name", os.getenv("PIPELINE_DATASET_NAME", "pipeline_dataset"),
                "--version", os.getenv("PIPELINE_DATASET_VERSION", "v1"),
                "--actor", actor,
            ]
            if expected_cols.strip():
                ingest_args.extend(["--expected-cols", expected_cols.strip()])
            run_py(ingest_args, **env)
            report(run_id, "data", "DATA", "passed", corr)
        else:
            print(f"SKIP DATA: dataset not found ({dataset_path})", file=sys.stderr)

    if _use_python_gates():
        run_py(["scripts/ci/gate_code.py"], **env)
        for g in ("G0", "G1", "G3", "G3b"):
            report(run_id, "code", g, "passed", corr)
    else:
        run_sh("scripts/ci/gate_code.sh", **env)

    ok, errs = verify_pipeline_run(
        run_id, require_db=False, require_data=not skip_data and Path(
            os.getenv("PIPELINE_DATASET_CSV", str(ROOT / "data/datasets/train_clean.csv"))
        ).exists(),
    )
    for e in errs:
        print(f"WARN pipeline_runs: {e}", file=sys.stderr)

    run_py(
        ["scripts/ci/sign_attestation.py", "--run-id", run_id,
         "--model", "platform",
         "--correlation-id", corr,
         "--strict"],
        **env,
    )

    print("=== Pipeline OK — platform attestation signed ===")
    print("Модель: загрузите в UI → «Зарегистрировать external» → Deploy после одобрения MLSecOps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
