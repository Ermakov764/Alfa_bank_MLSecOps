"""Audit log with hash-chain integrity and findings storage."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import Json, RealDictCursor


def _db_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://mlsecops:changeme@localhost:5432/mlsecops",
    )


@contextmanager
def get_conn() -> Iterator[Any]:
    conn = psycopg2.connect(_db_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _last_row_hash(conn: Any) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT row_hash FROM audit_events ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        return row[0] if row else ""


def log_event(
    actor: str,
    action: str,
    *,
    role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> int:
    """Append audit event with hash-chain."""
    details = details or {}
    corr = correlation_id or str(uuid.uuid4())
    payload = {
        "actor": actor,
        "role": role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "model_name": model_name,
        "model_version": model_version,
        "status": status,
        "details": details,
        "correlation_id": corr,
    }
    with get_conn() as conn:
        prev_hash = _last_row_hash(conn)
        row_hash = hashlib.sha256(
            (prev_hash + _canonical_payload(payload)).encode()
        ).hexdigest()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_events (
                  actor, role, action, resource_type, resource_id,
                  model_name, model_version, status, details,
                  correlation_id, prev_hash, row_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    actor,
                    role,
                    action,
                    resource_type,
                    resource_id,
                    model_name,
                    model_version,
                    status,
                    Json(details),
                    corr,
                    prev_hash,
                    row_hash,
                ),
            )
            event_id = cur.fetchone()[0]
    return event_id


def log_finding(
    gate: str,
    asset_type: str,
    asset_name: str,
    rule: str,
    *,
    severity: str = "medium",
    evidence: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> int:
    """Record gate finding for triage."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO findings (
                  gate, asset_type, asset_name, severity, rule,
                  evidence, correlation_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    gate,
                    asset_type,
                    asset_name,
                    severity,
                    rule,
                    json.dumps(evidence or {}),
                    correlation_id,
                ),
            )
            return cur.fetchone()[0]


def verify_chain(*, after_id: int = 0) -> tuple[bool, str]:
    """Verify hash-chain integrity of audit_events.

    after_id: only verify events with id > after_id (anchor row_hash used as prev).
    Use after_id>0 when the DB has legacy rows from older demo runs.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            prev = ""
            if after_id > 0:
                cur.execute(
                    "SELECT row_hash FROM audit_events WHERE id = %s",
                    (after_id,),
                )
                anchor = cur.fetchone()
                if not anchor:
                    return False, f"anchor id={after_id} not found"
                prev = anchor["row_hash"] or ""

            cur.execute(
                """
                SELECT id, ts, actor, role, action, resource_type, resource_id,
                       model_name, model_version, status, details,
                       correlation_id, prev_hash, row_hash
                FROM audit_events
                WHERE id > %s
                ORDER BY id ASC
                """,
                (after_id,),
            )
            rows = cur.fetchall()
    if not rows:
        return True, "empty chain (OK)" if after_id == 0 else f"no events after id={after_id} (OK)"

    for row in rows:
        payload = {
            "actor": row["actor"],
            "role": row["role"],
            "action": row["action"],
            "resource_type": row["resource_type"],
            "resource_id": row["resource_id"],
            "model_name": row["model_name"],
            "model_version": row["model_version"],
            "status": row["status"],
            "details": row["details"] if isinstance(row["details"], dict) else (
                json.loads(row["details"]) if row["details"] else {}
            ),
            "correlation_id": str(row["correlation_id"]) if row["correlation_id"] else None,
        }
        expected = hashlib.sha256(
            (prev + _canonical_payload(payload)).encode()
        ).hexdigest()
        if row["prev_hash"] != prev:
            return False, f"broken at id={row['id']}: prev_hash mismatch"
        if row["row_hash"] != expected:
            return False, f"broken at id={row['id']}: row_hash mismatch"
        prev = row["row_hash"]
    return True, f"verified {len(rows)} events"


def fetch_events(limit: int = 100, model_name: str | None = None) -> list[dict]:
    """Fetch recent audit events for UI."""
    q = "SELECT * FROM audit_events"
    params: list[Any] = []
    if model_name:
        q += " WHERE model_name = %s"
        params.append(model_name)
    q += " ORDER BY ts DESC LIMIT %s"
    params.append(limit)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(q, params)
            return [dict(r) for r in cur.fetchall()]


def fetch_findings(limit: int = 50, status: str | None = None) -> list[dict]:
    q = "SELECT * FROM findings"
    params: list[Any] = []
    if status:
        q += " WHERE status = %s"
        params.append(status)
    q += " ORDER BY ts DESC LIMIT %s"
    params.append(limit)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(q, params)
            return [dict(r) for r in cur.fetchall()]
