"""Загрузка произвольных файлов в MLflow — без привязки к demo-путям."""

from __future__ import annotations

import os
from pathlib import Path

import mlflow

from fortress.mlflow_client import ensure_experiment, get_client

DEFAULT_EXPERIMENT = "ds-experiments"


def log_local_files(
    paths: list[Path],
    *,
    experiment: str = DEFAULT_EXPERIMENT,
    run_name: str = "upload",
    owner: str = "ds",
    artifact_subdir: str = "files",
    tags: dict[str, str] | None = None,
) -> tuple[str, str]:
    """
    Залогировать локальные файлы/папки в MLflow run.
    Возвращает (run_id, artifact_uri).
    """
    ensure_experiment(experiment)
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment(experiment)

    existing = [p for p in paths if p.exists()]
    if not existing:
        raise FileNotFoundError(f"ни один путь не найден: {[str(p) for p in paths]}")

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tag("owner", owner)
        mlflow.set_tag("upload.source", "local")
        if tags:
            for k, v in tags.items():
                mlflow.set_tag(k, v)
        for p in existing:
            if p.is_dir():
                mlflow.log_artifacts(str(p), artifact_path=artifact_subdir)
            else:
                mlflow.log_artifact(str(p), artifact_path=artifact_subdir)
        return run.info.run_id, run.info.artifact_uri or ""


def collect_paths(path_args: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in path_args:
        p = Path(raw).expanduser().resolve()
        out.append(p)
    return out
