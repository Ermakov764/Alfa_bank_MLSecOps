"""Реестр датасетов в MLflow (источник истины) + DATA gate."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import mlflow

from fortress.mlflow_client import get_client

DATASET_EXPERIMENT = "fortress-datasets"
ARTIFACT_SUBDIR = "data"


def _artifact_root() -> str:
    return os.getenv("MLFLOW_DATASET_ARTIFACT_ROOT", "s3://datasets/")


def ensure_dataset_experiment() -> str:
    client = get_client()
    exp = client.get_experiment_by_name(DATASET_EXPERIMENT)
    if exp is None:
        root = _artifact_root()
        try:
            return client.create_experiment(DATASET_EXPERIMENT, artifact_location=root)
        except Exception:
            return client.create_experiment(DATASET_EXPERIMENT)
    return exp.experiment_id


def _base_tags(
    name: str,
    version: str,
    owner: str,
    sha256: str,
    expected_cols: str,
    rows: int,
    status: str,
    failure_reason: str = "",
) -> dict[str, str]:
    tags = {
        "dataset.name": name,
        "dataset.version": version,
        "dataset.sha256": sha256,
        "dataset.expected_cols": expected_cols,
        "dataset.rows": str(rows),
        "dataset.status": status,
        "owner": owner,
        "security.DATA": "passed" if status == "available" else "failed",
    }
    if failure_reason:
        tags["dataset.failure_reason"] = failure_reason[:500]
    return tags


def _count_csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


def log_dataset_run(
    path: Path,
    name: str,
    version: str,
    owner: str,
    sha256: str,
    expected_cols: str,
    *,
    status: str,
    failure_reason: str = "",
) -> str:
    """Создать MLflow run с CSV-артефактом и тегами (passed или quarantined)."""
    ensure_dataset_experiment()
    mlflow.set_experiment(DATASET_EXPERIMENT)
    rows = _count_csv_rows(path) if path.exists() else 0
    run_name = f"{name}:{version}"
    tags = _base_tags(name, version, owner, sha256, expected_cols, rows, status, failure_reason)

    with mlflow.start_run(run_name=run_name) as run:
        for k, v in tags.items():
            mlflow.set_tag(k, v)
        if path.exists():
            mlflow.log_artifact(str(path), artifact_path=ARTIFACT_SUBDIR)
        return run.info.run_id


def register_from_mlflow_run(
    run_id: str,
    actor: str,
    *,
    expected_cols: str = "",
) -> tuple[bool, str, str | None]:
    """
    Скачать CSV из MLflow run, прогнать DATA gate, обновить теги run.
    Возвращает (ok, message, run_id).
    """
    from fortress.data_gate import run_gate

    client = get_client()
    run = client.get_run(run_id)
    tags = dict(run.data.tags)
    name = tags.get("dataset.name") or run.info.run_name or run_id[:8]
    version = tags.get("dataset.version", "v1")

    cols = [c.strip() for c in (expected_cols or tags.get("dataset.expected_cols", "")).split(",") if c.strip()]
    if not cols:
        cols = None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        client.download_artifacts(run_id, ARTIFACT_SUBDIR, tmp_path)
        csv_files = sorted(tmp_path.rglob("*.csv"))
        if not csv_files:
            reason = "в run нет CSV в artifacts/data/"
            _mark_run_quarantined(client, run_id, name, version, actor, reason)
            return False, f"DATA gate: {reason}", run_id
        csv_path = csv_files[0]

        from fortress.dataset_registry import sha256_file

        digest = sha256_file(csv_path)
        code, rule = run_gate(csv_path, cols, actor=actor)
        if code != 0:
            _mark_run_quarantined(client, run_id, name, version, actor, rule or "blocked")
            return False, f"DATA gate: {rule} ({name}:{version})", run_id

        for k, v in _base_tags(
            name, version, actor, digest,
            expected_cols or tags.get("dataset.expected_cols", ""),
            _count_csv_rows(csv_path),
            "available",
        ).items():
            client.set_tag(run_id, k, v)

        from fortress.dataset_registry import _upsert_registry

        try:
            _upsert_registry(name, version, digest, f"mlflow://{run_id}", "available", actor)
        except Exception:
            pass
        return True, f"датасет {name}:{version} прошёл DATA gate (MLflow run {run_id[:8]})", run_id


def _mark_run_quarantined(
    client,
    run_id: str,
    name: str,
    version: str,
    actor: str,
    reason: str,
) -> None:
    client.set_tag(run_id, "dataset.status", "quarantined")
    client.set_tag(run_id, "security.DATA", "failed")
    client.set_tag(run_id, "dataset.failure_reason", (reason or "")[:500])
    client.set_tag(run_id, "owner", actor)
    client.set_tag(run_id, "dataset.name", name)
    client.set_tag(run_id, "dataset.version", version)


def list_datasets(
    username: str,
    *,
    role: str = "ds",
    status: str | None = "available",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Список датасетов из MLflow experiment fortress-datasets."""
    client = get_client()
    exp = client.get_experiment_by_name(DATASET_EXPERIMENT)
    if exp is None:
        return []

    filters = []
    if status:
        filters.append(f"tags.dataset.status = '{status}'")
    filter_string = " and ".join(filters) if filters else ""

    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string=filter_string,
        order_by=["attributes.start_time DESC"],
        max_results=limit,
    )

    out: list[dict[str, Any]] = []
    for run in runs:
        tags = dict(run.data.tags)
        owner = tags.get("owner", "")
        if role != "mlsecops" and owner and owner != username:
            continue
        out.append({
            "name": tags.get("dataset.name", run.info.run_name or "—"),
            "version": tags.get("dataset.version", "—"),
            "sha256": tags.get("dataset.sha256", ""),
            "status": tags.get("dataset.status", "unknown"),
            "rows": tags.get("dataset.rows", "—"),
            "owner": owner or "—",
            "run_id": run.info.run_id,
            "failure_reason": tags.get("dataset.failure_reason", ""),
            "started": run.info.start_time,
            "artifact_uri": run.info.artifact_uri,
        })
    return out


def list_quarantined_datasets(username: str, *, role: str = "ds", limit: int = 50) -> list[dict[str, Any]]:
    return list_datasets(username, role=role, status="quarantined", limit=limit)


def download_dataset_csv(run_id: str, dest_dir: Path) -> Path | None:
    """Скачать CSV датасета из MLflow run в локальную папку."""
    client = get_client()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        client.download_artifacts(run_id, ARTIFACT_SUBDIR, tmp_path)
        csv_files = sorted(tmp_path.rglob("*.csv"))
        if not csv_files:
            return None
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / csv_files[0].name
        shutil.copy2(csv_files[0], dest)
        return dest


def sync_pending_runs(actor: str, *, expected_cols: str = "amount,age,target") -> list[dict[str, str]]:
    """
    Найти runs без финального статуса (или pending) и прогнать DATA gate.
    Для кнопки «Обновить из MLflow» в UI.
    """
    client = get_client()
    exp = client.get_experiment_by_name(DATASET_EXPERIMENT)
    if exp is None:
        return []

    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string="tags.dataset.status != 'available'",
        order_by=["attributes.start_time DESC"],
        max_results=20,
    )
    results: list[dict[str, str]] = []
    for run in runs:
        tags = dict(run.data.tags)
        if tags.get("dataset.status") == "quarantined":
            continue
        ok, msg, _ = register_from_mlflow_run(run.info.run_id, actor, expected_cols=expected_cols)
        results.append({"run_id": run.info.run_id[:12], "ok": "да" if ok else "нет", "message": msg})
    return results
