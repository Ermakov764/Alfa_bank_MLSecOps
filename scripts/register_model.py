#!/usr/bin/env python3
"""Register model in MLflow — security tags only from verified attestation."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.attestation import gates_from_attestation, load_signed, verify_attestation  # noqa: E402
from fortress.audit import log_event  # noqa: E402
from fortress.mlflow_client import get_client, set_security_tag, set_scan_status  # noqa: E402
from fortress.model_card import validate_card  # noqa: E402

DEFAULT_ATTEST = ROOT / "artifacts/attestation/fortress-attestation.signed.json"


def register(
    model_name: str,
    artifact_dir: Path,
    card_path: Path,
    actor: str = "ds1",
    attestation_path: Path | None = None,
) -> int:
    att_path = attestation_path or DEFAULT_ATTEST
    if not att_path.exists():
        log_event(actor, "gate.failed", resource_type="model", resource_id="register",
                  model_name=model_name, status="failed",
                  details={"error": "attestation required"})
        print("FAIL: run pipeline and sign attestation first")
        return 1

    signed = load_signed(att_path)
    ok, msg = verify_attestation(signed)
    if not ok:
        print(f"FAIL: attestation: {msg}")
        return 1

    import yaml
    text = card_path.read_text(encoding="utf-8")
    card_data = yaml.safe_load(text) if card_path.suffix.lower() in (".yaml", ".yml") else json.loads(text)
    card = validate_card(card_data)

    if list(artifact_dir.rglob("*.pkl")) and not list(artifact_dir.rglob("*.onnx")):
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

    for g in gates_from_attestation(signed):
        set_security_tag(model_name, version, g, "passed")
    payload = signed["payload"]
    set_security_tag(model_name, version, "signed", "true", {
        "security.attestation_id": payload.get("correlation_id", ""),
        "security.attestation_verified": "true",
    })
    set_scan_status(model_name, version, True)

    log_event(
        actor, "model.registered", role="ds",
        resource_type="model", resource_id=model_name,
        model_name=model_name, model_version=version,
        status="success", correlation_id=payload.get("correlation_id", str(uuid.uuid4())),
    )
    print(f"registered {model_name} v{version} -> Staging (tags from attestation)")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--card", type=Path, required=True)
    p.add_argument("--attestation", type=Path, default=None)
    p.add_argument("--actor", default="ds1")
    args = p.parse_args()
    sys.exit(register(args.model, args.artifact, args.card, args.actor, args.attestation))


if __name__ == "__main__":
    main()
