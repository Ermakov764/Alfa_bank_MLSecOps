#!/usr/bin/env python3
"""G12 meta-gate: promote to Production with RBAC + HITL."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.attestation import load_signed, verify_attestation  # noqa: E402
from fortress.audit import log_event, log_finding  # noqa: E402
from fortress.mlflow_client import get_version_tags, transition_stage  # noqa: E402
from fortress.security_profile import check_promote_policy  # noqa: E402

ATTESTATION_PATH = ROOT / "artifacts/attestation/fortress-attestation.signed.json"


ROLE_ENV = {
    "ds1": "ds",
    "mlsecops1": "mlsecops",
    "de1": "de",
}


def actor_role(actor: str) -> str:
    return os.getenv("ACTOR_ROLE", ROLE_ENV.get(actor, "ds"))


def _verify_attestation_file() -> tuple[bool, str]:
    path = Path(os.getenv("FORTRESS_ATTESTATION_PATH", str(ATTESTATION_PATH)))
    if not path.exists():
        return False, f"missing attestation: {path}"
    signed = load_signed(path)
    return verify_attestation(signed)


def promote(model_name: str, version: str, actor: str, approve: bool = False) -> int:
    role = actor_role(actor)
    tags = get_version_tags(model_name, version)

    ok_att, msg_att = _verify_attestation_file()
    if not ok_att:
        log_finding("G12", "model", model_name, "attestation_invalid",
                    severity="high", evidence={"reason": msg_att})
        print(f"G12 BLOCKED: {msg_att}")
        return 1

    if approve and role == "mlsecops":
        from fortress.mlflow_client import get_client
        get_client().set_model_version_tag(
            model_name, version, "security.approved_by", actor
        )
        tags["security.approved_by"] = actor
        log_event(
            actor, "model.approved", role=role,
            model_name=model_name, model_version=version,
            status="success", correlation_id=str(uuid.uuid4()),
        )

    ok, msg = check_promote_policy(tags, model_name, actor_role=role,
                                   approved_by=tags.get("security.approved_by"))
    if not ok:
        log_finding("G12", "model", model_name, "promote_blocked",
                    severity="high", evidence={"reason": msg})
        log_event(
            actor, "gate.failed", role=role, resource_type="gate",
            resource_id="G12", model_name=model_name, model_version=version,
            status="blocked", details={"reason": msg},
            correlation_id=str(uuid.uuid4()),
        )
        print(f"G12 BLOCKED: {msg}")
        return 1

    transition_stage(model_name, version, "Production")
    log_event(
        actor, "model.promoted", role=role,
        model_name=model_name, model_version=version,
        status="success", correlation_id=str(uuid.uuid4()),
    )
    print(f"promoted {model_name} v{version} -> Production")
    return 0


def archive(model_name: str, version: str, actor: str) -> int:
    if actor_role(actor) != "mlsecops":
        print("only mlsecops may archive")
        return 1
    transition_stage(model_name, version, "Archived")
    log_event(
        actor, "model.archived", role="mlsecops",
        model_name=model_name, model_version=version, status="success",
        correlation_id=str(uuid.uuid4()),
    )
    print(f"archived {model_name} v{version}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--actor", default="mlsecops1")
    p.add_argument("--approve", action="store_true")
    p.add_argument("--archive", action="store_true")
    args = p.parse_args()
    if args.archive:
        sys.exit(archive(args.model, args.version, args.actor))
    sys.exit(promote(args.model, args.version, args.actor, args.approve))


if __name__ == "__main__":
    main()
