"""G12: promote / archive MLflow model versions."""

from __future__ import annotations

import uuid

from fortress.attestation import load_signed, verify_attestation
from fortress.audit import log_event, log_finding
from fortress.config import attestation_path
from fortress.mlflow_client import get_client, get_version_tags, transition_stage
from fortress.registry_policy import requires_mlsecops_approval
from fortress.security_profile import check_promote_policy


def _verify_ci_attestation(tags: dict[str, str]) -> tuple[bool, str]:
    if tags.get("security.signed") != "true":
        return False, "MLflow version not attested (security.signed != true)"
    att_id = tags.get("security.attestation_id", "")
    path = attestation_path()
    if path.exists() and att_id:
        signed = load_signed(path)
        ok, msg = verify_attestation(signed)
        if not ok:
            return False, msg
        if signed["payload"].get("correlation_id") != att_id:
            return False, "attestation id mismatch with MLflow version"
    return True, "ok"


def run_precheck(model_name: str, version: str, *, actor_role: str = "ds") -> tuple[bool, str]:
    """In-process G12 pre-deploy check."""
    from fortress.mlflow_client import version_security_summary

    summary = version_security_summary(model_name, version)
    lines = [
        f"origin: {summary['origin']} · approval: {summary['approval_label']}",
    ]
    if summary["last_failure"]:
        lines.append(f"last_failure: {summary['last_failure']}")

    tags = get_version_tags(model_name, version)
    ok, msg = check_promote_policy(
        tags, model_name, actor_role=actor_role,
        approved_by=tags.get("security.approved_by"),
    )
    lines.append(f"G12 precheck ({actor_role}): {ok} {msg}")
    text = "\n".join(lines)
    if not ok:
        return False, text
    return True, text + "\n=== Pre-deploy PASS ==="


def promote(
    model_name: str,
    version: str,
    actor: str,
    *,
    actor_role: str = "ds",
    approve: bool = False,
) -> tuple[bool, str]:
    tags = get_version_tags(model_name, version)
    external = requires_mlsecops_approval(tags, model_name)

    if approve and actor_role == "mlsecops":
        get_client().set_model_version_tag(
            model_name, version, "security.approved_by", actor,
        )
        tags["security.approved_by"] = actor
        log_event(
            actor, "model.approved", role=actor_role,
            model_name=model_name, model_version=version,
            status="success", correlation_id=str(uuid.uuid4()),
        )

    if not external:
        ok_att, msg_att = _verify_ci_attestation(tags)
        if not ok_att:
            log_finding("G12", "model", model_name, "attestation_invalid",
                        severity="high", evidence={"reason": msg_att})
            return False, f"G12 BLOCKED: {msg_att}"

    ok, msg = check_promote_policy(
        tags, model_name, actor_role=actor_role,
        approved_by=tags.get("security.approved_by"),
    )
    if not ok:
        log_finding("G12", "model", model_name, "promote_blocked",
                    severity="high", evidence={"reason": msg})
        log_event(
            actor, "gate.failed", role=actor_role, resource_type="gate",
            resource_id="G12", model_name=model_name, model_version=version,
            status="blocked", details={"reason": msg},
            correlation_id=str(uuid.uuid4()),
        )
        return False, f"G12 BLOCKED: {msg}"

    transition_stage(model_name, version, "Production")
    log_event(
        actor, "model.promoted", role=actor_role,
        model_name=model_name, model_version=version,
        status="success", correlation_id=str(uuid.uuid4()),
    )
    who = "MLSecOps" if external else "DS (CI auto-policy)"
    return True, f"promoted {model_name} v{version} -> Production [{who}]"


def archive(model_name: str, version: str, actor: str, *, actor_role: str = "mlsecops") -> tuple[bool, str]:
    if actor_role != "mlsecops":
        return False, "only mlsecops may archive"
    transition_stage(model_name, version, "Archived")
    log_event(
        actor, "model.archived", role="mlsecops",
        model_name=model_name, model_version=version, status="success",
        correlation_id=str(uuid.uuid4()),
    )
    return True, f"archived {model_name} v{version}"
