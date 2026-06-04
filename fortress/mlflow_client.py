"""MLflow registry helpers with security tags."""

from __future__ import annotations

import os
from typing import Any

import mlflow
from mlflow.tracking import MlflowClient


def get_client() -> MlflowClient:
    uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(uri)
    return MlflowClient()


def ensure_experiment(name: str) -> str:
    client = get_client()
    exp = client.get_experiment_by_name(name)
    if exp is None:
        return client.create_experiment(name)
    return exp.experiment_id


def set_security_tag(
    model_name: str,
    version: str,
    gate: str,
    status: str = "passed",
    extra: dict[str, str] | None = None,
) -> None:
    client = get_client()
    mv = client.get_model_version(model_name, version)
    client.set_model_version_tag(model_name, version, f"security.{gate}", status)
    if extra:
        for k, v in extra.items():
            client.set_model_version_tag(model_name, version, k, v)
    client.set_model_version_tag(
        model_name, version, "security.last_gate_run", __import__("datetime").datetime.utcnow().isoformat() + "Z"
    )


def set_scan_status(model_name: str, version: str, passed: bool) -> None:
    client = get_client()
    client.set_model_version_tag(
        model_name,
        version,
        "security.scan_status",
        "passed" if passed else "failed",
    )


def get_version_tags(model_name: str, version: str) -> dict[str, str]:
    client = get_client()
    mv = client.get_model_version(model_name, version)
    return dict(mv.tags or {})


def register_model_version(
    model_name: str,
    artifact_path: str,
    run_id: str | None = None,
) -> str:
    client = get_client()
    try:
        client.create_registered_model(model_name)
    except Exception:
        pass
    if run_id:
        source = f"runs:/{run_id}/{artifact_path}"
    else:
        source = artifact_path
    mv = mlflow.register_model(source, model_name)
    return str(mv.version)


def transition_stage(model_name: str, version: str, stage: str) -> None:
    client = get_client()
    client.transition_model_version_stage(
        name=model_name,
        version=version,
        stage=stage,
        archive_existing_versions=False,
    )


def get_production_version(model_name: str) -> tuple[str, str] | None:
    """Return (version, source) for Production stage or None."""
    client = get_client()
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
    except Exception:
        return None
    for mv in versions:
        if mv.current_stage == "Production":
            return str(mv.version), mv.source
    return None


def list_registered_models() -> list[dict[str, Any]]:
    client = get_client()
    out = []
    for rm in client.search_registered_models():
        versions = client.search_model_versions(f"name='{rm.name}'")
        for mv in versions:
            out.append(
                {
                    "name": rm.name,
                    "version": str(mv.version),
                    "stage": mv.current_stage or "None",
                    "tags": dict(mv.tags or {}),
                }
            )
    return out
