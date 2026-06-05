"""Pipeline run transparency (Postgres + local JSON fallback)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCAL_RUNS_DIR = Path(os.getenv("ARTIFACTS_DIR", ROOT / "artifacts")) / "pipeline_runs"


def _local_run_file(run_id: str) -> Path:
    LOCAL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return LOCAL_RUNS_DIR / f"{run_id}.json"


def append_local_run(
    run_id: str,
    element: str,
    status: str,
    *,
    gate: str | None = None,
    model_name: str | None = None,
    report_path: str | None = None,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    path = _local_run_file(run_id)
    rows: list[dict[str, Any]] = []
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
    rows.append(
        {
            "run_id": run_id,
            "correlation_id": correlation_id or "",
            "element": element,
            "gate": gate or "",
            "status": status,
            "model_name": model_name or "",
            "report_path": report_path or "",
            "details": details or {},
        }
    )
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def load_local_runs(run_id: str) -> list[dict[str, Any]]:
    path = _local_run_file(run_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


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
    append_local_run(
        run_id,
        element,
        status,
        gate=gate,
        model_name=model_name,
        report_path=report_path,
        details=details,
        correlation_id=corr,
    )
    try:
        from fortress.audit import get_conn

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
    if run_id:
        local = load_local_runs(run_id)
        if local:
            return local[-limit:]
    try:
        from fortress.audit import get_conn

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
    except Exception:
        return []


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
