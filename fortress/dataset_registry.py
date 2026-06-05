"""Регистрация датасетов: DATA gate → MLflow (SoT) + Postgres (аудит/индекс)."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fortress.audit import get_conn, log_event, log_finding


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _upsert_registry(
    name: str,
    version: str,
    digest: str,
    location: str,
    status: str,
    actor: str,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO registry_datasets (name, version, sha256, location, status, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name, version) DO UPDATE SET
                  sha256 = EXCLUDED.sha256,
                  location = EXCLUDED.location,
                  status = EXCLUDED.status,
                  created_by = EXCLUDED.created_by
                """,
                (name, version, digest, location, status, actor),
            )


def ingest_dataset(
    path: Path,
    name: str,
    version: str,
    actor: str,
    *,
    expected_cols: str = "",
) -> tuple[bool, str]:
    """
    DATA gate → MLflow run с артефактом → зеркало в Postgres.
    Неудачные попытки (poison, PII, схема) логируются в findings + quarantine run.
    """
    from fortress.data_gate import run_gate
    from fortress.mlflow_datasets import log_dataset_run

    cols = [c.strip() for c in expected_cols.split(",") if c.strip()] or None
    digest = sha256_file(path) if path.exists() else ""

    code, rule = run_gate(path, cols, actor=actor)
    corr = str(uuid.uuid4())

    if code != 0:
        detail = rule or "unknown"
        run_id = log_dataset_run(
            path, name, version, actor, digest, expected_cols,
            status="quarantined", failure_reason=detail,
        )
        log_finding(
            "DATA", "dataset", f"{name}:{version}", detail,
            severity="critical" if "poison" in detail.lower() else "high",
            correlation_id=corr,
        )
        log_event(
            actor, "dataset.quarantined", role="ds",
            resource_type="dataset", resource_id=f"{name}:{version}",
            status="failed",
            details={"rule": detail, "sha256": digest, "mlflow_run_id": run_id},
            correlation_id=corr,
        )
        try:
            _upsert_registry(name, version, digest, f"mlflow://{run_id}", "quarantined", actor)
        except Exception:
            pass
        return False, f"DATA gate: {detail} ({name}:{version}). Запись в аудит и MLflow."

    run_id = log_dataset_run(
        path, name, version, actor, digest, expected_cols, status="available",
    )
    try:
        _upsert_registry(name, version, digest, f"mlflow://{run_id}", "available", actor)
    except Exception as exc:
        return False, f"DATA gate OK, но реестр БД недоступен: {exc}"

    try:
        log_event(
            actor, "dataset.uploaded", role="ds",
            resource_type="dataset", resource_id=f"{name}:{version}",
            status="success",
            details={"sha256": digest, "mlflow_run_id": run_id, "status": "available"},
            correlation_id=corr,
        )
    except Exception:
        pass

    return True, f"Датасет {name}:{version} загружен в MLflow (run {run_id[:8]}…), DATA gate пройден"
