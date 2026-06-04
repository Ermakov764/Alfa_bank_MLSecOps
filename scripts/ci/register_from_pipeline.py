#!/usr/bin/env python3
"""Register model in MLflow Staging with tags from verified attestation only."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.attestation import gates_from_attestation, load_signed, verify_attestation  # noqa: E402
from fortress.audit import log_event  # noqa: E402
from fortress.mlflow_client import get_client, set_security_tag, set_scan_status  # noqa: E402
from fortress.model_card import validate_card  # noqa: E402

import mlflow  # noqa: E402
import yaml  # noqa: E402


def _load_card(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        return yaml.safe_load(text)
    return json.loads(text)


def register(
    model_name: str,
    artifact_dir: Path,
    card_path: Path,
    attestation_path: Path,
    actor: str = "ds1",
) -> int:
    signed = load_signed(attestation_path)
    ok, msg = verify_attestation(signed)
    if not ok:
        print(f"register blocked: {msg}", file=sys.stderr)
        return 1

    card = validate_card(_load_card(card_path))
    if list(artifact_dir.rglob("*.pkl")) and not list(artifact_dir.rglob("*.onnx")):
        if "m3_nlp" not in str(artifact_dir):
            print("register blocked: pkl without onnx", file=sys.stderr)
            return 1

    tracking = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking)
    client = get_client()
    try:
        client.create_registered_model(model_name)
    except Exception:
        pass

    if tracking.startswith("sqlite:") or tracking.startswith("file:"):
        source = artifact_dir.resolve().as_uri()
        mv = client.create_model_version(name=model_name, source=source, run_id=None)
    else:
        with mlflow.start_run(run_name=f"register-{model_name}") as run:
            mlflow.log_artifacts(str(artifact_dir), artifact_path="model")
            source = f"runs:/{run.info.run_id}/model"
            mv = client.create_model_version(name=model_name, source=source, run_id=run.info.run_id)

    version = str(mv.version)
    client.set_model_version_tag(model_name, version, "model_card", card.to_mlflow_tag())
    client.transition_model_version_stage(model_name, version, "Staging")

    for g in gates_from_attestation(signed):
        set_security_tag(model_name, version, g, "passed")
    payload = signed["payload"]
    set_security_tag(model_name, version, "signed", "true", {
        "security.attestation_id": payload.get("correlation_id", ""),
    })
    set_scan_status(model_name, version, True)

    log_event(
        actor, "model.registered", role="ds",
        resource_type="model", resource_id=model_name,
        model_name=model_name, model_version=version,
        status="success", correlation_id=payload.get("correlation_id", str(uuid.uuid4())),
    )
    sys.stdout.write(f"{version}\n")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--card", type=Path, required=True)
    p.add_argument("--attestation", type=Path,
                   default=ROOT / "artifacts/attestation/fortress-attestation.signed.json")
    p.add_argument("--actor", default="ds1")
    args = p.parse_args()
    sys.exit(register(args.model, args.artifact, args.card, args.attestation, args.actor))


if __name__ == "__main__":
    main()
