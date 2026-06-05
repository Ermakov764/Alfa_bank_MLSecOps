"""Human-readable MLSecOps monitoring summaries (MLflow-centric)."""

from __future__ import annotations

from typing import Any

from fortress.audit import fetch_events, fetch_findings
from fortress.mlflow_client import list_registered_models, version_security_summary
from fortress.pipeline import fetch_pipeline_runs
from fortress.registry_policy import model_origin


def models_overview() -> list[dict[str, str]]:
    """All models in MLflow with approval status (not only 3 CI demos)."""
    rows = []
    for m in list_registered_models():
        tags = m["tags"]
        summary = version_security_summary(m["name"], m["version"])
        origin = model_origin(tags, m["name"])
        rows.append({
            "Модель": m["name"],
            "Версия": m["version"],
            "Стадия": m["stage"],
            "Происхождение": "CI" if origin == "ci_trained" else "внешняя",
            "Скан": tags.get("security.scan_status", "?"),
            "Attestation": "да" if summary["signed"] else "нет",
            "Статус": summary["approval_label"],
            "Ошибка": (summary["last_failure"] or "—")[:80],
            "Владелец": tags.get("owner", "—"),
            "Одобрил": tags.get("security.approved_by", "—"),
        })
    return rows


def external_approval_queue() -> list[dict[str, str]]:
    rows = []
    for m in list_registered_models():
        summary = version_security_summary(m["name"], m["version"])
        if not summary["needs_mlsecops"]:
            continue
        if summary["approved_by"]:
            continue
        if summary["approval_status"] in ("blocked", "failed"):
            continue
        rows.append({
            "Модель": m["name"],
            "Версия": m["version"],
            "Владелец": m["tags"].get("owner", "—"),
            "Статус": summary["approval_label"],
        })
    return rows


def pipeline_summary(limit: int = 15) -> list[dict[str, str]]:
    runs = fetch_pipeline_runs(None, limit)
    out = []
    for r in runs:
        st = r.get("status", "?")
        icon = {"passed": "OK", "failed": "FAIL", "started": "…"}.get(st, st)
        details = r.get("details") or {}
        if isinstance(details, str):
            msg = details[:60]
        else:
            msg = (details.get("message") or details.get("log") or "")[:60]
        out.append({
            "Время": str(r.get("created_at", ""))[:19],
            "Run": (r.get("run_id") or "")[:12],
            "Элемент": r.get("element", ""),
            "Gate": r.get("gate") or "—",
            "Статус": icon,
            "Модель": r.get("model_name") or "—",
            "Детали": msg or "—",
        })
    return out


def findings_summary(limit: int = 20) -> list[dict[str, str]]:
    items = fetch_findings(limit)
    return [
        {
            "Время": str(f.get("ts", ""))[:19],
            "Gate": f.get("gate", ""),
            "Severity": f.get("severity", ""),
            "Что не так": (f.get("rule") or "")[:80],
            "Актив": f.get("asset_name", ""),
            "Статус": f.get("status", "open"),
        }
        for f in items
    ]


def audit_summary(limit: int = 25) -> list[dict[str, str]]:
    events = fetch_events(limit)
    return [
        {
            "Время": str(e.get("ts", ""))[:19],
            "Кто": e.get("actor", ""),
            "Действие": e.get("action", ""),
            "Статус": e.get("status", ""),
            "Модель": e.get("model_name") or "—",
        }
        for e in events
    ]


def drift_monitoring_summary() -> list[dict[str, str]]:
    """G15 drift status from last report + telemetry row counts."""
    import json
    from pathlib import Path

    from fortress.inference_telemetry import load_baseline_metrics, load_dataframe

    root = Path(__file__).resolve().parents[1]
    report_path = root / "artifacts/gates/g15_report.json"
    report: dict = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}

    rows = []
    for mk in ("m1", "m2"):
        cur = load_dataframe(mk)
        baseline = load_baseline_metrics(mk)
        rows.append({
            "Модель": mk,
            "Prod samples": str(len(cur)),
            "Baseline acc": f"{baseline.get('accuracy', 0):.3f}" if baseline else "—",
            "Drift PSI max": str(report.get("drift", {}).get("max_psi", "—")),
            "G15": "PASS" if report_path.exists() else "не запускался",
        })
    return rows


def mlsecops_kpis() -> dict[str, Any]:
    models = list_registered_models()
    prod = sum(1 for m in models if m["stage"] == "Production")
    staging = sum(1 for m in models if m["stage"] in ("Staging", "None"))
    ci_ready = sum(
        1 for m in models
        if version_security_summary(m["name"], m["version"])["approval_status"] == "ready_auto"
    )
    pending_ext = len(external_approval_queue())
    findings = fetch_findings(200)
    critical = sum(
        1 for f in findings
        if f.get("severity") in ("critical", "high") and f.get("status") == "open"
    )
    recent = fetch_pipeline_runs(None, 5)
    last_pipe = recent[0].get("status", "нет данных") if recent else "нет данных"
    last_fail = ""
    for r in recent:
        if r.get("status") == "failed":
            d = r.get("details") or {}
            last_fail = d.get("message", d.get("log", "")) if isinstance(d, dict) else str(d)
            break
    return {
        "models_total": len(models),
        "production": prod,
        "staging": staging,
        "ci_ready": ci_ready,
        "pending_external": pending_ext,
        "open_critical": critical,
        "last_pipeline": last_pipe,
        "last_failure": last_fail[:120] if last_fail else "—",
    }
