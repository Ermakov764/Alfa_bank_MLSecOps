"""Общие UI-компоненты DS и MLSecOps."""

from __future__ import annotations

import streamlit as st

from fortress.app_runner import run_bootstrap
from fortress.deploy_runner import archive_version, deploy_to_production, run_precheck
from fortress.ds_workspace import check_results_detailed, my_findings
from fortress.mlflow_client import list_models_for_user, list_versions, version_security_summary
from fortress.monitoring import findings_summary
from fortress.pipeline_runner import run_pipeline
from fortress.services_health import services_status


def render_services_health(compact: bool = False) -> None:
    rows = services_status()
    if compact:
        bad = [r for r in rows if not r["OK"]]
        if bad:
            st.warning("Недоступно: " + ", ".join(r["Сервис"] for r in bad))
        else:
            st.success("Все сервисы доступны")
        return
    st.dataframe(
        [{"Сервис": r["Сервис"], "Статус": "OK" if r["OK"] else "DOWN", "URL": r["URL"]} for r in rows],
        use_container_width=True,
        hide_index=True,
    )


def render_pipeline_panel(user, *, key_prefix: str = "shared") -> None:
    st.subheader("Platform pipeline")
    st.caption("DATA gate (если есть CSV) → code gates → подпись platform attestation")
    st.info(
        "Модель загружаете отдельно: «Зарегистрировать модель» → файлы ONNX/joblib → Deploy."
    )
    if st.button("Запустить pipeline", type="primary", key=f"{key_prefix}_run_pipeline"):
        with st.spinner("Pipeline…"):
            ok, log = run_pipeline(actor=user.username)
        st.success("Pipeline OK") if ok else st.error("Pipeline failed")
        if log:
            st.code(log[-6000:], language="text")


def render_admin_panel(user) -> None:
    if user.role != "mlsecops":
        return
    st.subheader("Администрирование")
    if st.button("Bootstrap (Keycloak + MLflow experiments)", key="admin_bootstrap"):
        with st.spinner("Bootstrap…"):
            ok, log = run_bootstrap()
        st.success(log) if ok else st.error(log)


def render_deploy_panel(
    user,
    *,
    key_prefix: str = "dep",
    show_archive: bool = False,
) -> None:
    models = list_models_for_user(user.username, role=user.role)
    if not models:
        st.info("Нет моделей в MLflow. Загрузите модель на вкладке «Мои модели».")
        return
    sel = st.selectbox("Модель", models, key=f"{key_prefix}_model")
    vers = list_versions(sel, user.username, role=user.role)
    if not vers:
        st.warning("Нет версий.")
        return
    vi = st.selectbox(
        "Версия",
        range(len(vers)),
        format_func=lambda i: f"v{vers[i]['version']} · {vers[i]['stage']}",
        key=f"{key_prefix}_ver",
    )
    version = vers[vi]["version"]
    summary = version_security_summary(sel, version)

    if summary["last_failure"]:
        st.error(summary["last_failure"])
    if summary["missing_gates"]:
        st.error("Не пройдены: " + ", ".join(summary["missing_gates"]))
    elif summary["needs_mlsecops"] and not summary["approved_by"]:
        st.warning("Нужно одобрение MLSecOps перед Production.")
    else:
        st.success(summary["approval_label"])

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("Pre-deploy", key=f"{key_prefix}_pre"):
            ok, log = run_precheck(sel, version, actor_role=user.role)
            st.success(log) if ok else st.error(log)
    with b2:
        blocked = summary["needs_mlsecops"] and not user.can_approve_external and not summary["approved_by"]
        if st.button("Deploy → Production", type="primary", disabled=blocked, key=f"{key_prefix}_go"):
            ok, msg = deploy_to_production(sel, version, user.username, actor_role=user.role)
            st.success(msg) if ok else st.error(msg)
    with b3:
        if user.can_approve_external and summary["needs_mlsecops"]:
            if st.button("Одобрить + Deploy", type="primary", key=f"{key_prefix}_approve"):
                ok, msg = deploy_to_production(
                    sel, version, user.username, actor_role=user.role, approve=True,
                )
                st.success(msg) if ok else st.error(msg)
    with b4:
        if show_archive and user.can_approve_external:
            if st.button("Архивировать", key=f"{key_prefix}_arch"):
                ok, msg = archive_version(sel, version, user.username, actor_role=user.role)
                st.success(msg) if ok else st.error(msg)


def render_findings_panel(user, *, limit: int = 25, key_prefix: str = "find") -> None:
    if user.role == "ds":
        rows = my_findings(user.username, user.role, limit)
        if not rows:
            st.info("Findings по вашим моделям нет.")
            return
        for row in rows:
            with st.expander(f"{row['Гейт']} · {row['Severity']} · {row['Время']}", expanded=False):
                st.markdown(f"**{row['Объяснение']}**")
                st.markdown(f"Рекомендация: {row['Рекомендация']}")
                if row["Фрагмент лога"]:
                    st.code(row["Фрагмент лога"])
        return

    rows = check_results_detailed(user.username, user.role, limit)
    if not rows:
        st.info("Записей проверок нет.")
        return
    for row in rows:
        if row["Статус"] == "ОШИБКА":
            with st.expander(f"❌ {row['Гейт']} · {row['Модель']}", expanded=False):
                st.markdown(f"**{row['Объяснение']}**")
                st.markdown(f"Действие: {row['Что делать']}")
                if row["Фрагмент лога"]:
                    st.code(row["Фрагмент лога"])
        else:
            st.caption(f"✓ {row['Гейт']} · {row['Модель']}")

    st.divider()
    st.caption("Сводка findings")
    df = findings_summary(limit)
    if df:
        st.dataframe(df, use_container_width=True, hide_index=True)
