"""Streamlit-блоки для роли MLSecOps."""

from __future__ import annotations

import streamlit as st
import pandas as pd

from dashboard.ds_views import render_ds_passport, render_ds_signed
from dashboard.shared_views import (
    render_admin_panel,
    render_deploy_panel,
    render_findings_panel,
    render_pipeline_panel,
    render_services_health,
)
from fortress.audit import verify_chain
from fortress.monitoring import audit_summary, external_approval_queue, mlsecops_kpis, models_overview, pipeline_summary


def render_mlsecops_home() -> None:
    try:
        kpi = mlsecops_kpis()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Модели", kpi["models_total"])
        c2.metric("Готовы (CI)", kpi.get("ci_ready", 0))
        c3.metric("Ждут одобрения", kpi.get("pending_external", 0))
        c4.metric("Findings", kpi["open_critical"])
        c5.metric("Pipeline", kpi["last_pipeline"])
        if kpi.get("last_failure") and kpi["last_failure"] != "—":
            st.error(f"Ошибка: {kpi['last_failure']}")
    except Exception as e:
        st.warning(str(e))

    st.subheader("Состояние сервисов")
    render_services_health()

    df = pd.DataFrame(models_overview())
    if df.empty:
        st.info("Моделей нет. Запустите pipeline на вкладке «Pipeline».")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_mlsecops_deploy(user) -> None:
    q = external_approval_queue()
    if q:
        st.warning("Внешние модели без одобрения:")
        st.dataframe(pd.DataFrame(q), hide_index=True)
    render_deploy_panel(user, key_prefix="mso_dep", show_archive=True)


def render_mlsecops_pipeline(user) -> None:
    render_pipeline_panel(user, key_prefix="mso")
    render_admin_panel(user)
    st.divider()
    st.subheader("История pipeline")
    df = pd.DataFrame(pipeline_summary(40))
    if df.empty:
        st.info("Записей нет.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_mlsecops_audit() -> None:
    st.dataframe(pd.DataFrame(audit_summary(50)), use_container_width=True, hide_index=True)


def render_mlsecops_chain() -> None:
    if st.button("Проверить цепочку audit", type="primary"):
        ok, msg = verify_chain()
        st.success(msg) if ok else st.error(msg)


def render_mlsecops_help() -> None:
    st.markdown(
        """
### MLSecOps — всё через UI

| Вкладка | Действия |
|---------|----------|
| **Обзор** | KPI, health сервисов, все модели |
| **Deploy** | Pre-deploy, Deploy, Одобрить external, Архив |
| **Паспорт** | Model card из MLflow |
| **Данные** | Датасеты, quarantine, загрузка в MLflow |
| **Pipeline** | Запуск CI pipeline / train, bootstrap |
| **Findings** | Ошибки гейтов |
| **Аудит** | Журнал событий |
| **Цепочка** | Проверка hash-chain |

Поднять контейнеры — только терминал: `.\fortress.ps1 up`
        """
    )
