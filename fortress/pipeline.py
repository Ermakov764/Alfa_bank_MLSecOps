"""Pipeline run transparency (Postgres pipeline_runs)."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from fortress.audit import get_conn


def record_pipeline_step(
    run_id: str,
    element: str,
    status: str,
    *,
    gate: str | None = None,
    model_name: str | None = None,
    report_path: str | None = None,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> int:
    corr = correlation_id or str(uuid.uuid4())
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_runs (
                      run_id, correlation_id, element, gate, status,
                      model_name, report_path, details
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        run_id,
                        corr,
                        element,
                        gate,
                        status,
                        model_name,
                        report_path,
                        json.dumps(details or {}),
                    ),
                )
                return cur.fetchone()[0]
    except Exception:
        return 0


def fetch_pipeline_runs(run_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if run_id:
                cur.execute(
                    """
                    SELECT id, run_id, correlation_id, element, gate, status,
                           model_name, report_path, details, created_at
                    FROM pipeline_runs
                    WHERE run_id = %s
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    (run_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, run_id, correlation_id, element, gate, status,
                           model_name, report_path, details, created_at
                    FROM pipeline_runs
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def latest_signed_run(model_name: str) -> str | None:
    """Return run_id of latest pipeline with status signed for model."""
    att_path = os.getenv(
        "FORTRESS_ATTESTATION_PATH",
        "artifacts/attestation/fortress-attestation.signed.json",
    )
    p = __import__("pathlib").Path(att_path)
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("payload", {}).get("model_name") == model_name:
            return data["payload"].get("correlation_id")
    return None
