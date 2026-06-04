#!/usr/bin/env python3
"""Register dataset in Postgres + run DATA gate."""

from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.audit import get_conn, log_event  # noqa: E402
from scripts.data_gate import run_gate  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest(
    path: Path,
    name: str,
    version: str,
    actor: str = "ds1",
    expected_cols: str = "",
) -> int:
    digest = sha256_file(path)
    location = str(path.resolve())
    cols = [c.strip() for c in expected_cols.split(",") if c.strip()] or None

    gate_rc = run_gate(path, cols, actor=actor)
    status = "available" if gate_rc == 0 else "quarantine"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO registry_datasets (name, version, sha256, location, status, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name, version) DO UPDATE SET
                  sha256 = EXCLUDED.sha256,
                  location = EXCLUDED.location,
                  status = EXCLUDED.status
                """,
                (name, version, digest, location, status, actor),
            )

    action = "dataset.uploaded" if status == "available" else "dataset.quarantined"
    log_event(
        actor,
        action,
        role="ds",
        resource_type="dataset",
        resource_id=f"{name}:{version}",
        status="success" if status == "available" else "blocked",
        details={"sha256": digest, "status": status},
        correlation_id=str(uuid.uuid4()),
    )
    print(f"ingested {name}:{version} status={status}")
    return gate_rc


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("csv_path", type=Path)
    p.add_argument("--name", required=True)
    p.add_argument("--version", default="v1")
    p.add_argument("--expected-cols", default="amount,age,target")
    p.add_argument("--actor", default="ds1")
    args = p.parse_args()
    sys.exit(ingest(args.csv_path, args.name, args.version, args.actor, args.expected_cols))


if __name__ == "__main__":
    main()
