"""Регистрация внешней модели в MLflow из UI."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import mlflow

from fortress.audit import log_event
from fortress.mlflow_client import get_client
from fortress.model_card import ModelCard
from fortress.registry_policy import ORIGIN_EXTERNAL


def register_external_from_files(
    model_name: str,
    files: list[tuple[str, bytes]],
    *,
    owner: str,
    purpose: str = "",
    tier: str = "MED",
    data_sources: str = "",
) -> tuple[bool, str]:
    """Загрузить файлы модели → MLflow registry, security.origin=external."""
    if not model_name.strip():
        return False, "Укажите имя модели"
    if not files:
        return False, "Нет файлов"

    client = get_client()
    mlflow.set_tracking_uri(__import__("os").environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"))

    with tempfile.TemporaryDirectory() as tmp:
        art = Path(tmp) / "model"
        art.mkdir()
        for name, data in files:
            dest = art / Path(name).name
            dest.write_bytes(data)
            if dest.suffix.lower() == ".pkl" and not any(
                Path(n).suffix.lower() == ".onnx" for n, _ in files
            ):
                return False, "Сырой .pkl без ONNX запрещён (G6)"

        with mlflow.start_run(run_name=f"external-{model_name}") as run:
            mlflow.log_artifacts(str(art), artifact_path="model")
            source = f"runs:/{run.info.run_id}/model"
            try:
                client.create_registered_model(model_name)
            except Exception:
                pass
            mv = mlflow.register_model(source, model_name)
            version = str(mv.version)

    card = ModelCard(
        name=model_name,
        version=version,
        tier=tier,
        owner=owner,
        purpose=purpose or "external vendor model",
        data_sources=data_sources,
        limitations="external — требует MLSecOps",
    )
    client.set_model_version_tag(model_name, version, "model_card", card.to_mlflow_tag())
    client.set_model_version_tag(model_name, version, "owner", owner)
    client.set_model_version_tag(model_name, version, "security.origin", ORIGIN_EXTERNAL)
    client.set_model_version_tag(model_name, version, "security.scan_status", "pending")
    client.transition_model_version_stage(model_name, version, "Staging")

    log_event(
        owner, "model.registered", role="ds",
        resource_type="model", resource_id=model_name,
        model_name=model_name, model_version=version,
        status="success",
        details={"origin": ORIGIN_EXTERNAL},
        correlation_id=str(uuid.uuid4()),
    )
    return True, f"Модель {model_name} v{version} зарегистрирована (Staging, ждёт одобрения MLSecOps для prod)"
