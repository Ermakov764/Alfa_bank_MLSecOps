"""Регистрация датасетов: DATA gate + Postgres registry."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fortress.audit import get_conn, log_event


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_dataset(
    path: Path,
    name: str,
    version: str,
    actor: str,
    *,
    expected_cols: str = "",
) -> tuple[bool, str]:
    """
    DATA gate + запись в registry_datasets.
    Fail-closed: без БД ingest не считается успешным.
    """
    from fortress.data_gate import run_gate

    cols = [c.strip() for c in expected_cols.split(",") if c.strip()] or None
    if run_gate(path, cols, actor=actor) != 0:
        return False, f"DATA gate blocked ingest for {name}:{version}"

    digest = sha256_file(path)
    location = str(path.resolve())

    try:
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
                    (name, version, digest, location, "available", actor),
                )
    except Exception as exc:
        return False, f"registry DB unavailable: {exc}"

    try:
        log_event(
            actor,
            "dataset.uploaded",
            role="ds",
            resource_type="dataset",
            resource_id=f"{name}:{version}",
            status="success",
            details={"sha256": digest, "status": "available"},
            correlation_id=str(uuid.uuid4()),
        )
    except Exception:
        pass

    return True, f"ingested {name}:{version} status=available"
