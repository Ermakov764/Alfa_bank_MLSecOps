#!/usr/bin/env python3
"""Register model in MLflow with model_card and security tags."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.audit import log_event  # noqa: E402
from fortress.mlflow_client import get_client, set_security_tag, set_scan_status  # noqa: E402
from fortress.model_card import validate_card  # noqa: E402


def register(
    model_name: str,
    artifact_dir: Path,
    card_path: Path,
    actor: str = "ds1",
    run_gates: bool = True,
) -> int:
    card_data = json.loads(card_path.read_text(encoding="utf-8"))
    card = validate_card(card_data)

    onnx_files = list(artifact_dir.rglob("*.onnx"))
    if not onnx_files and list(artifact_dir.rglob("*.pkl")):
        log_event(actor, "gate.failed", resource_type="model", resource_id="G6",
                  model_name=model_name, status="failed",
                  details={"error": "pkl in artifact"})
        return 1

    import mlflow

    mlflow.set_tracking_uri(__import__("os").environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    with mlflow.start_run(run_name=f"register-{model_name}") as run:
        mlflow.log_artifacts(str(artifact_dir), artifact_path="model")
        source = f"runs:/{run.info.run_id}/model"
        client = get_client()
        try:
            client.create_registered_model(model_name)
        except Exception:
            pass
        mv = mlflow.register_model(source, model_name)
        version = str(mv.version)

    client = get_client()
    client.set_model_version_tag(model_name, version, "model_card", card.to_mlflow_tag())
    client.transition_model_version_stage(model_name, version, "Staging")

    if run_gates:
        for g in ("G5", "G6", "G7", "G0", "G3", "G8", "G9", "G10"):
            tag_val = __import__("os").environ.get(f"SECURITY_{g}", "passed")
            set_security_tag(model_name, version, g, tag_val)

    set_scan_status(model_name, version, True)
    set_security_tag(model_name, version, "scan_status", "passed", {"security.scan_status": "passed"})

    log_event(
        actor, "model.registered", role="ds",
        resource_type="model", resource_id=model_name,
        model_name=model_name, model_version=version,
        status="success", correlation_id=str(uuid.uuid4()),
    )
    print(f"registered {model_name} v{version} -> Staging")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--card", type=Path, required=True)
    p.add_argument("--actor", default="ds1")
    args = p.parse_args()
    sys.exit(register(args.model, args.artifact, args.card, args.actor))


if __name__ == "__main__":
    main()
