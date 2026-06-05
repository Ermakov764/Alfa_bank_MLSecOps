"""MLflow experiments / runs — контекст для паспорта DS."""

from __future__ import annotations

from typing import Any

from fortress.mlflow_client import get_client, get_version_tags


def list_experiments() -> list[dict[str, str]]:
    client = get_client()
    out = []
    for exp in client.search_experiments():
        if exp.lifecycle_stage == "deleted":
            continue
        out.append({
            "id": exp.experiment_id,
            "name": exp.name,
        })
    return sorted(out, key=lambda x: x["name"])


def list_runs(experiment_id: str, *, max_results: int = 30) -> list[dict[str, Any]]:
    client = get_client()
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        max_results=max_results,
        order_by=["start_time DESC"],
    )
    out = []
    for r in runs:
        out.append({
            "run_id": r.info.run_id,
            "name": r.info.run_name or r.info.run_id[:8],
            "status": r.info.status,
            "start_time": r.info.start_time,
            "artifact_uri": r.info.artifact_uri,
            "user": r.data.tags.get("mlflow.user", ""),
            "metrics": {k: round(v, 6) if isinstance(v, float) else v for k, v in r.data.metrics.items()},
            "params": dict(r.data.params),
        })
    return out


def get_run_context(run_id: str) -> dict[str, Any]:
    client = get_client()
    run = client.get_run(run_id)
    exp = client.get_experiment(run.info.experiment_id)
    return {
        "run_id": run_id,
        "run_name": run.info.run_name or run_id[:8],
        "experiment_id": run.info.experiment_id,
        "experiment_name": exp.name,
        "status": run.info.status,
        "artifact_uri": run.info.artifact_uri,
        "user": run.data.tags.get("mlflow.user", ""),
        "metrics": dict(run.data.metrics),
        "params": dict(run.data.params),
        "tags": dict(run.data.tags),
    }


def resolve_run_for_model_version(model_name: str, version: str) -> str | None:
    client = get_client()
    mv = client.get_model_version(model_name, version)
    if mv.run_id:
        return mv.run_id
    src = mv.source or ""
    if src.startswith("runs:/"):
        parts = src.split("/")
        if len(parts) >= 2:
            return parts[1]
    return None


def passport_from_mlflow(
    model_name: str,
    version: str,
    run_id: str | None,
    owner: str,
) -> dict[str, Any]:
    """Собрать поля паспорта из версии MLflow + run (если выбран)."""
    tags = get_version_tags(model_name, version)
    base: dict[str, Any] = {
        "name": model_name,
        "version": version,
        "tier": "HIGH",
        "owner": tags.get("owner") or owner,
        "purpose": f"Модель {model_name} из MLflow",
        "data_sources": tags.get("data_sources", "см. MLflow run params"),
        "limitations": "см. model card и метрики run",
        "metrics": {},
        "mlflow_run_id": "",
        "mlflow_experiment": "",
        "mlflow_experiment_id": "",
        "artifact_uri": "",
        "mlflow_source": "",
    }
    raw = tags.get("model_card")
    if raw:
        try:
            import json
            data = json.loads(raw)
            for k in base:
                if k in data and data[k]:
                    base[k] = data[k]
        except Exception:
            pass

    rid = run_id or resolve_run_for_model_version(model_name, version)
    if rid:
        try:
            ctx = get_run_context(rid)
            base["mlflow_run_id"] = ctx["run_id"]
            base["mlflow_experiment"] = ctx["experiment_name"]
            base["mlflow_experiment_id"] = ctx["experiment_id"]
            base["artifact_uri"] = ctx["artifact_uri"] or ""
            base["metrics"] = {**base.get("metrics", {}), **ctx.get("metrics", {})}
            if ctx.get("params"):
                base["data_sources"] = ", ".join(
                    f"{k}={v}" for k, v in list(ctx["params"].items())[:5]
                )
        except Exception:
            pass

    client = get_client()
    mv = client.get_model_version(model_name, version)
    base["mlflow_source"] = mv.source or ""
    base["mlflow_stage"] = mv.current_stage or "None"
    base["scan_status"] = tags.get("security.scan_status", "unknown")
    base["signed"] = tags.get("security.signed") == "true"
    return base
