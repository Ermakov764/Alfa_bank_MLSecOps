#!/usr/bin/env python3
"""
After successful pipeline: register CI models in MLflow and apply attestation tags.
MLflow is the source of truth — no per-model manual steps for developers.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.attestation import gates_from_attestation, load_signed, verify_attestation  # noqa: E402
from fortress.audit import log_event  # noqa: E402
from fortress.registry_policy import CI_MODEL_REGISTRY, ORIGIN_CI  # noqa: E402
from scripts.ci.register_from_pipeline import register  # noqa: E402


def sync_all(
    attestation_path: Path,
    actor: str = "ci",
    *,
    model_key: str = "all",
) -> int:
    if not attestation_path.exists():
        print(f"sync blocked: no attestation at {attestation_path}", file=sys.stderr)
        return 1

    signed = load_signed(attestation_path)
    ok, msg = verify_attestation(signed)
    if not ok:
        print(f"sync blocked: invalid attestation — {msg}", file=sys.stderr)
        return 1

    keys = [r["key"] for r in CI_MODEL_REGISTRY] if model_key == "all" else [
        r["key"] for r in CI_MODEL_REGISTRY if r["key"] == model_key
    ]
    errors = 0
    for row in CI_MODEL_REGISTRY:
        if row["key"] not in keys:
            continue
        art = ROOT / row["artifact"]
        card = ROOT / row["card"]
        if not art.exists():
            print(f"WARN: skip {row['name']} — artifact missing", file=sys.stderr)
            errors += 1
            continue
        rc = register(
            row["name"],
            art,
            card,
            attestation_path,
            actor=actor,
        )
        if rc != 0:
            errors += 1
            continue
        from fortress.mlflow_client import get_client, get_version_tags, set_security_tag  # noqa: E402

        client = get_client()
        versions = client.search_model_versions(f"name='{row['name']}'")
        if not versions:
            errors += 1
            continue
        latest = max(versions, key=lambda v: int(v.version))
        version = str(latest.version)
        client.set_model_version_tag(row["name"], version, "security.origin", ORIGIN_CI)
        client.set_model_version_tag(
            row["name"],
            version,
            "security.pipeline_run_id",
            os.getenv("RUN_ID", ""),
        )
        for g in gates_from_attestation(signed):
            set_security_tag(row["name"], version, g, "passed")
        client.delete_model_version_tag(row["name"], version, "security.last_failure")
        log_event(
            actor,
            "attestation.synced",
            role="ci",
            model_name=row["name"],
            model_version=version,
            status="success",
            details={"gates": gates_from_attestation(signed)},
            correlation_id=signed["payload"].get("correlation_id", str(uuid.uuid4())),
        )
        print(f"synced {row['name']} v{version} → MLflow (ci_trained, signed)")

    return 1 if errors else 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--attestation",
        type=Path,
        default=ROOT / "artifacts/attestation/fortress-attestation.signed.json",
    )
    p.add_argument("--actor", default="ci")
    p.add_argument("--model-key", default="all")
    args = p.parse_args()
    return sync_all(args.attestation, args.actor, model_key=args.model_key)


if __name__ == "__main__":
    sys.exit(main())
