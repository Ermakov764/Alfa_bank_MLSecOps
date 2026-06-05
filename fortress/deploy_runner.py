"""Production deploy pipeline (MLflow tags + G12 + audit)."""

from __future__ import annotations

import os
import uuid

from fortress.audit import log_event
from fortress.mlflow_client import get_version_tags, version_security_summary
from fortress.pipeline import record_pipeline_step
from fortress.promote import archive as archive_model
from fortress.promote import promote as promote_model
from fortress.promote import run_precheck as g12_precheck
from fortress.registry_policy import requires_mlsecops_approval


def run_precheck(model_name: str, version: str, *, actor_role: str = "ds") -> tuple[bool, str]:
    return g12_precheck(model_name, version, actor_role=actor_role)


def deploy_to_production(
    model_name: str,
    version: str,
    actor: str,
    *,
    actor_role: str = "ds",
    approve: bool = False,
) -> tuple[bool, str]:
    tags = get_version_tags(model_name, version)
    summary = version_security_summary(model_name, version)
    external = requires_mlsecops_approval(tags, model_name)

    if external and actor_role != "mlsecops":
        return False, (
            "Внешняя модель требует одобрения MLSecOps. "
            "Зарегистрируйте в MLflow и дождитесь security.approved_by."
        )
    if summary["approval_status"] == "blocked":
        miss = ", ".join(summary["missing_gates"]) or "проверки"
        return False, f"Не пройдены гейты: {miss}. {summary['last_failure']}"
    if summary["approval_status"] == "failed":
        return False, f"Проверка провалена: {summary['last_failure']}"
    if external and not approve and not summary["approved_by"]:
        return False, "MLSecOps должен одобрить внешнюю модель (кнопка «Одобрить»)"

    run_id = os.getenv("RUN_ID", f"deploy-{model_name}-{version}")
    record_pipeline_step(run_id, "deploy", "started", gate="pre-deploy", model_name=model_name)

    ok, msg = run_precheck(model_name, version, actor_role=actor_role)
    if not ok:
        record_pipeline_step(
            run_id, "deploy", "failed", gate="pre-deploy", model_name=model_name,
            details={"log": msg[:500]},
        )
        log_event(
            actor, "deploy.failed", role=actor_role, model_name=model_name,
            model_version=version, status="failed", details={"step": "precheck", "log": msg[:300]},
            correlation_id=str(uuid.uuid4()),
        )
        return False, msg

    record_pipeline_step(run_id, "deploy", "passed", gate="pre-deploy", model_name=model_name)

    need_approve = external and approve
    ok, promote_msg = promote_model(
        model_name, version, actor, actor_role=actor_role, approve=need_approve,
    )
    if not ok:
        record_pipeline_step(run_id, "deploy", "failed", gate="G12", model_name=model_name)
        return False, promote_msg

    record_pipeline_step(run_id, "deploy", "passed", gate="G12", model_name=model_name)
    log_event(
        actor, "deploy.completed", role=actor_role, model_name=model_name,
        model_version=version, status="success", correlation_id=str(uuid.uuid4()),
    )
    label = "внешняя, одобрено MLSecOps" if external else "CI, авто-политика"
    return True, f"{model_name} v{version} → Production ({label})"


def archive_version(model_name: str, version: str, actor: str, *, actor_role: str = "mlsecops") -> tuple[bool, str]:
    return archive_model(model_name, version, actor, actor_role=actor_role)
