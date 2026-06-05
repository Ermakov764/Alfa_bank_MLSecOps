"""Рабочее место Data Scientist: модели, проверки, подписанные артефакты."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fortress.audit import fetch_events, fetch_findings, get_conn
from fortress.gate_explain import explain_gate
from fortress.mlflow_client import (
    get_version_tags,
    list_models_for_user,
    list_registered_models,
    version_security_summary,
)
from fortress.pipeline import fetch_pipeline_runs, load_local_runs
from fortress.registry_policy import model_origin


def _owner_match(owner: str, username: str, role: str) -> bool:
    if role == "mlsecops":
        return True
    return not owner or owner == username


def my_models_overview(username: str, role: str = "ds") -> list[dict[str, str]]:
    rows = []
    for m in list_registered_models():
        owner = m["tags"].get("owner", "")
        if not _owner_match(owner, username, role):
            continue
        summary = version_security_summary(m["name"], m["version"])
        origin = model_origin(m["tags"], m["name"])
        rows.append({
            "Модель": m["name"],
            "Версия": m["version"],
            "Стадия": m["stage"],
            "Тип": "CI" if origin == "ci_trained" else "внешняя",
            "Подпись": "да" if summary["signed"] else "нет",
            "Статус": summary["approval_label"],
            "Проблема": (summary["last_failure"] or "—")[:100],
        })
    return rows


def signed_models(username: str, role: str = "ds") -> list[dict[str, str]]:
    rows = []
    for m in list_registered_models():
        owner = m["tags"].get("owner", "")
        if not _owner_match(owner, username, role):
            continue
        tags = m["tags"]
        if tags.get("security.signed") != "true":
            continue
        rows.append({
            "Модель": m["name"],
            "Версия": m["version"],
            "Attestation ID": tags.get("security.attestation_id", "—")[:20],
            "Pipeline run": tags.get("security.pipeline_run_id", "—")[:16],
            "Стадия": m["stage"],
            "Скан": tags.get("security.scan_status", "?"),
        })
    return rows


def signed_datasets(username: str, role: str = "ds") -> list[dict[str, str]]:
    """Датасеты из MLflow (fortress-datasets), прошедшие DATA gate."""
    try:
        from fortress.mlflow_datasets import list_datasets

        rows = list_datasets(username, role=role, status="available")
        return [
            {
                "Датасет": r["name"],
                "Версия": r["version"],
                "SHA256": (r["sha256"] or "")[:16] + "…" if r["sha256"] else "—",
                "Строк": r.get("rows", "—"),
                "Кто загрузил": r.get("owner", "—"),
                "MLflow run": (r.get("run_id") or "")[:12] + "…",
            }
            for r in rows
        ]
    except Exception as exc:
        return [{"_error": str(exc)}]


def _collect_pipeline_rows(username: str, role: str, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        rows.extend(fetch_pipeline_runs(None, limit))
    except Exception:
        pass
    # local JSON files
    art = Path(__file__).resolve().parents[1] / "artifacts" / "pipeline_runs"
    if art.exists():
        for p in sorted(art.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
            try:
                rows.extend(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    if role != "mlsecops":
        my_models = set(list_models_for_user(username, role=role))
        filtered = []
        for r in rows:
            mn = r.get("model_name") or ""
            element = r.get("element") or ""
            details = r.get("details") or {}
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except Exception:
                    details = {}
            step_actor = details.get("actor", "") if isinstance(details, dict) else ""
            if mn and mn in my_models:
                filtered.append(r)
            elif not mn and element in ("data", "code", "train", "deploy"):
                if step_actor in ("", "ci", username):
                    filtered.append(r)
        rows = filtered
    return rows[:limit]


def check_results_detailed(username: str, role: str = "ds", limit: int = 25) -> list[dict[str, str]]:
    """Проверки с человекочитаемым объяснением и фрагментом лога."""
    out = []
    for r in _collect_pipeline_rows(username, role, limit * 2):
        gate = r.get("gate") or r.get("element") or ""
        status = r.get("status", "")
        details = r.get("details") or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {"message": details}
        rule = ""
        if status == "failed":
            findings = fetch_findings(50)
            for f in findings:
                if f.get("gate") == gate or f.get("asset_name", "") in str(r.get("run_id", "")):
                    rule = f.get("rule", "")
                    break
        exp = explain_gate(gate, status, details, raw_rule=rule)
        out.append({
            "Время": str(r.get("created_at", ""))[:19],
            "Гейт": gate,
            "Статус": exp["status_human"],
            "Что проверялось": exp["title"],
            "Объяснение": exp["explanation"] if status != "passed" else "OK",
            "Что делать": exp["fix"] if status != "passed" else "—",
            "Фрагмент лога": exp["log_excerpt"] or _details_excerpt(details),
            "Модель": r.get("model_name") or "—",
        })
        if len(out) >= limit:
            break
    return out


def _details_excerpt(details: dict[str, Any]) -> str:
    if not details:
        return ""
    for k in ("message", "log", "rule"):
        if details.get(k):
            return str(details[k])[:400]
    return json.dumps(details, ensure_ascii=False)[:400]


def my_findings(username: str, role: str = "ds", limit: int = 30) -> list[dict[str, str]]:
    items = fetch_findings(limit * 2)
    out = []
    my_models = set(list_models_for_user(username, role=role))
    for f in items:
        asset = f.get("asset_name", "")
        if role == "mlsecops" or asset in my_models or f.get("asset_type") == "dataset":
            exp = explain_gate(
                f.get("gate", ""),
                "failed",
                f.get("evidence"),
                raw_rule=f.get("rule", ""),
            )
            out.append({
                "Время": str(f.get("ts", ""))[:19],
                "Гейт": f.get("gate", ""),
                "Severity": f.get("severity", ""),
                "Объяснение": exp["explanation"],
                "Фрагмент лога": exp["log_excerpt"][:300],
                "Рекомендация": exp["fix"],
            })
        if len(out) >= limit:
            break
    return out


def ds_kpis(username: str) -> dict[str, Any]:
    models = my_models_overview(username, "ds")
    signed = signed_models(username, "ds")
    datasets = signed_datasets(username, "ds")
    if datasets and datasets[0].get("_error"):
        datasets = []
    failed = [m for m in models if "блок" in m.get("Статус", "").lower() or "ошиб" in m.get("Проблема", "").lower()]
    return {
        "my_models": len(models),
        "signed_models": len(signed),
        "signed_datasets": len(datasets),
        "needs_attention": len(failed),
    }
