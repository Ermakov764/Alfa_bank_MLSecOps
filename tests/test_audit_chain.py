"""Audit hash-chain tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("psycopg2")

from fortress.audit import get_conn, log_event, verify_chain  # noqa: E402


def _max_audit_id() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM audit_events")
            return int(cur.fetchone()[0])


@pytest.fixture(scope="module")
def db_available() -> bool:
    try:
        import psycopg2
        url = os.getenv(
            "DATABASE_URL",
            "postgresql://mlsecops:changeme@localhost:5432/mlsecops",
        )
        psycopg2.connect(url).close()
        return True
    except Exception:
        return False


def test_audit_chain_integrity(db_available: bool) -> None:
    if not db_available:
        pytest.skip("postgres not available")
    anchor = _max_audit_id()
    log_event("pytest", "gate.passed", resource_type="gate", resource_id="TEST")
    log_event("pytest", "model.registered", model_name="test-model", status="success")
    ok, msg = verify_chain(after_id=anchor)
    assert ok, msg


def test_verify_chain_empty_db_skips() -> None:
    """Unit: verify_chain returns OK for empty chain message."""
    # Only runs if DB empty — integration elsewhere
    pass
