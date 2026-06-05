"""MLflow registry helpers with security tags."""

from __future__ import annotations

import json
import os
from typing import Any

import mlflow
from mlflow.tracking import MlflowClient

from fortress.registry_policy import (  # noqa: E402
    CI_TRAINED_MODELS,
    ORIGIN_CI,
    ORIGIN_EXTERNAL,
    approval_label,
    approval_status,
    model_origin,
    requires_mlsecops_approval,
)

# Back-compat alias
INTERNAL_MODELS = CI_TRAINED_MODELS


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


def list_models_for_user(username: str, *, role: str) -> list[str]:
    """All MLflow registered models visible to user (MLflow = registry)."""
    names = set()
    for m in list_registered_models():
        owner = m["tags"].get("owner", "")
        if role == "mlsecops" or owner == username or not owner:
            names.add(m["name"])
    return sorted(names)


def set_version_failure(
    model_name: str,
    version: str,
    gate: str,
    message: str,
) -> None:
    client = get_client()
    client.set_model_version_tag(model_name, version, "security.scan_status", "failed")
    client.set_model_version_tag(model_name, version, f"security.{gate}", "failed")
    client.set_model_version_tag(
        model_name,
        version,
        "security.last_failure",
        f"{gate}: {message}"[:500],
    )


def version_security_summary(model_name: str, version: str) -> dict[str, Any]:
    from fortress.security_profile import check_gate_tags, required_gates_for_model

    tags = get_version_tags(model_name, version)
    req = required_gates_for_model(model_name)
    missing = check_gate_tags(tags, req)
    status = approval_status(tags, model_name, missing_gates=missing)
    return {
        "origin": model_origin(tags, model_name),
        "approval_status": status,
        "approval_label": approval_label(status),
        "missing_gates": missing,
        "last_failure": tags.get("security.last_failure", ""),
        "signed": tags.get("security.signed") == "true",
        "needs_mlsecops": requires_mlsecops_approval(tags, model_name),
        "approved_by": tags.get("security.approved_by", ""),
    }


def list_versions(model_name: str, username: str, *, role: str) -> list[dict[str, Any]]:
    out = []
    for m in list_registered_models():
        if m["name"] != model_name:
            continue
        owner = m["tags"].get("owner", "")
        if role != "mlsecops" and owner and owner != username:
            continue
        out.append(m)
    return sorted(out, key=lambda x: int(x["version"]), reverse=True)


def save_model_card_tag(model_name: str, version: str, card_json: str) -> None:
    get_client().set_model_version_tag(model_name, version, "model_card", card_json)


def passport_prefill(model_name: str, version: str, owner: str = "") -> dict[str, Any]:
    """Pull model card + metrics from MLflow tags for passport form."""
    from fortress.mlflow_experiments import passport_from_mlflow

    return passport_from_mlflow(model_name, version, None, owner)


