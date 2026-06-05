"""FORTRESS Security Center — UI поверх MLflow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.audit import verify_chain  # noqa: E402
from fortress.auth import (  # noqa: E402
    SessionUser,
    authenticate,
    keycloak_account_url,
    mlflow_public_url,
    register,
)
from fortress.keycloak_admin import ROLE_LABELS, keycloak_reachable  # noqa: E402
from fortress.deploy_runner import archive_version, deploy_to_production, run_precheck  # noqa: E402
from fortress.mlflow_client import (  # noqa: E402
    list_models_for_user,
    list_versions,
    passport_prefill,
    save_model_card_tag,
    version_security_summary,
)
from fortress.model_card import ModelCard  # noqa: E402
from dashboard.ds_views import (  # noqa: E402
    render_ds_checks,
    render_ds_deploy,
    render_ds_findings,
    render_ds_help,
    render_ds_home,
    render_ds_passport,
    render_ds_signed,
)
from fortress.config import m1_api_url, m2_api_url, m3_api_url  # noqa: E402
from fortress.monitoring import (  # noqa: E402
    audit_summary,
    external_approval_queue,
    findings_summary,
    mlsecops_kpis,
    models_overview,
    pipeline_summary,
)

MLFLOW_URL = mlflow_public_url()

st.set_page_config(page_title="FORTRESS", layout="wide", initial_sidebar_state="expanded")

if "user" not in st.session_state:
    st.session_state.user = None


def require_login() -> SessionUser | None:
    if st.session_state.user:
        return st.session_state.user

    st.title("FORTRESS")
    if not keycloak_reachable():
        st.warning("Keycloak ещё не готов. Выполните: `fortress.ps1 up` и подождите ~1 мин.")

    tab_login, tab_register = st.tabs(["Вход", "Регистрация"])

    with tab_login:
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Логин", key="login_user")
        with c2:
            password = st.text_input("Пароль", type="password", key="login_pass")
        if st.button("Войти", type="primary", key="btn_login"):
            u = authenticate(username, password)
            if u:
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Неверный логин или пароль")

    with tab_register:
        st.caption("Создайте аккаунт один раз — войдёте и в FORTRESS, и в MLflow.")
        r1, r2 = st.columns(2)
        with r1:
            new_user = st.text_input("Логин (латиница, ≥3)", key="reg_user")
            new_email = st.text_input("Email", key="reg_email")
        with r2:
            new_pass = st.text_input("Пароль (≥8)", type="password", key="reg_pass")
            new_pass2 = st.text_input("Повтор пароля", type="password", key="reg_pass2")
        role = st.radio(
            "Роль",
            options=["ds", "mlsecops"],
            format_func=lambda k: ROLE_LABELS[k],
            horizontal=True,
            key="reg_role",
        )
        st.info(
            "Роль выбираете вы сами (пилотный режим). "
            "В проде роли будет назначать администратор."
        )
        if st.button("Зарегистрироваться", type="primary", key="btn_register"):
            if new_pass != new_pass2:
                st.error("Пароли не совпадают")
            else:
                ok, msg = register(new_user, new_email, new_pass, role)
                if ok:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
    return None


user = require_login()
if not user:
    st.stop()

# --- Sidebar ---
st.sidebar.title("FORTRESS")
st.sidebar.caption(f"{user.username}" + (f" · {user.email}" if user.email else ""))
if st.sidebar.button("Выйти"):
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("**Сервисы**")
st.sidebar.link_button("MLflow (тот же логин)", MLFLOW_URL)
st.sidebar.link_button("Профиль Keycloak", keycloak_account_url())
st.sidebar.link_button("M1 API", f"{m1_api_url()}/docs")
st.sidebar.link_button("M2 API", f"{m2_api_url()}/docs")
st.sidebar.link_button("M3 NLP", f"{m3_api_url()}/health")

st.sidebar.markdown("**Запуск (терминал)**")
st.sidebar.code(".\\fortress.ps1 up\n.\\fortress.ps1 pipeline", language="powershell")

st.title("Security Center" if user.role == "mlsecops" else "FORTRESS — Data Scientist")

if user.role == "ds":
    t1, t2, t3, t4, t5, t6, t7 = st.tabs(
        ["Мои модели", "Паспорт", "Проверки", "Подписанные", "Deploy", "Findings", "Помощь"]
    )
    with t1:
        render_ds_home(user)
    with t2:
        render_ds_passport(user)
    with t3:
        render_ds_checks(user)
    with t4:
        render_ds_signed(user)
    with t5:
        render_ds_deploy(user)
    with t6:
        render_ds_findings(user)
    with t7:
        render_ds_help(user)
    st.stop()

# --- MLSecOps tabs ---
tab_names = ["Обзор", "Deploy", "Паспорт", "Проверки", "Pipeline", "Findings", "Помощь", "Аудит", "Цепочка"]
tabs = st.tabs(tab_names)
tab_home, tab_deploy, tab_passport, tab_checks, tab_pipeline, tab_findings, tab_help, tab_audit, tab_chain = tabs

# --- Обзор ---
with tab_home:
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

    df = pd.DataFrame(models_overview())
    if df.empty:
        st.info("Моделей нет. Выполните `fortress.ps1 pipeline` — версии появятся в MLflow и здесь.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- Deploy ---
with tab_deploy:
    if user.can_approve_external:
        q = external_approval_queue()
        if q:
            st.warning("Внешние модели без одобрения:")
            st.dataframe(pd.DataFrame(q), hide_index=True)

    models = list_models_for_user(user.username, role=user.role)
    if not models:
        st.info("Зарегистрируйте модель в MLflow — статус появится здесь.")
    else:
        sel_model = st.selectbox("Модель", models, key="deploy_model")
        versions = list_versions(sel_model, user.username, role=user.role)
        if not versions:
            st.warning("Нет версий.")
        else:
            ver_idx = st.selectbox(
                "Версия",
                range(len(versions)),
                format_func=lambda i: (
                    f"v{versions[i]['version']} · {versions[i]['stage']} · "
                    f"{version_security_summary(sel_model, versions[i]['version'])['approval_label']}"
                ),
            )
            version = versions[ver_idx]["version"]
            summary = version_security_summary(sel_model, version)

            if summary["last_failure"]:
                st.error(summary["last_failure"])
            if summary["missing_gates"]:
                st.error("Гейты: " + ", ".join(summary["missing_gates"]))
            else:
                st.success(summary["approval_label"])

            b1, b2, b3, b4 = st.columns(4)
            with b1:
                if st.button("Pre-deploy"):
                    ok, log = run_precheck(sel_model, version, actor_role=user.role)
                    st.success(log) if ok else st.error(log)
            with b2:
                blocked = summary["needs_mlsecops"] and not user.can_approve_external
                if st.button("Deploy", type="primary", disabled=blocked):
                    ok, msg = deploy_to_production(
                        sel_model, version, user.username,
                        actor_role=user.role, approve=False,
                    )
                    st.success(msg) if ok else st.error(msg)
            with b3:
                if user.can_approve_external and summary["needs_mlsecops"]:
                    if st.button("Одобрить + Deploy", type="primary"):
                        ok, msg = deploy_to_production(
                            sel_model, version, user.username,
                            actor_role=user.role, approve=True,
                        )
                        st.success(msg) if ok else st.error(msg)
            with b4:
                if user.can_approve_external:
                    if st.button("Архивировать"):
                        ok, msg = archive_version(
                            sel_model, version, user.username, actor_role=user.role,
                        )
                        st.success(msg) if ok else st.error(msg)

# --- Паспорт ---
with tab_passport:
    models = list_models_for_user(user.username, role=user.role)
    if not models:
        st.info("Сначала зарегистрируйте модель в MLflow.")
    else:
        pm = st.selectbox("Модель", models, key="passport_model")
        pvers = list_versions(pm, user.username, role=user.role)
        if pvers:
            pv = st.selectbox("Версия", [v["version"] for v in pvers], key="passport_ver")
            prefill = passport_prefill(pm, pv, user.username)
            with st.form("passport_form"):
                name = st.text_input("name", prefill.get("name", pm))
                version = st.text_input("version", prefill.get("version", pv))
                tier = st.selectbox("tier", ["HIGH", "MED", "LOW"])
                owner = st.text_input("owner", prefill.get("owner") or user.username)
                purpose = st.text_area("purpose", prefill.get("purpose", ""))
                data_sources = st.text_input("data_sources", prefill.get("data_sources", ""))
                limitations = st.text_input("limitations", prefill.get("limitations", "см. model card"))
                submitted = st.form_submit_button("Сохранить в MLflow")
                if submitted:
                    try:
                        card = ModelCard(
                            name=name, version=version, tier=tier, owner=owner,
                            purpose=purpose, data_sources=data_sources, limitations=limitations,
                        )
                        save_model_card_tag(pm, pv, card.to_mlflow_tag())
                        st.success("Паспорт сохранён в тег model_card")
                    except Exception as ex:
                        st.error(str(ex))

# --- Проверки (mlsecops) ---
with tab_checks:
    from fortress.ds_workspace import check_results_detailed

    rows = check_results_detailed(user.username, user.role, 40)
    if not rows:
        st.info("Записей проверок нет.")
    else:
        for row in rows:
            if row["Статус"] == "ОШИБКА":
                with st.expander(f"❌ {row['Гейт']} · {row['Модель']}", expanded=False):
                    st.markdown(f"**{row['Объяснение']}**")
                    st.markdown(f"Действие: {row['Что делать']}")
                    if row["Фрагмент лога"]:
                        st.code(row["Фрагмент лога"], language="text")
            else:
                st.caption(f"✓ {row['Гейт']} · {row['Модель']}")

# --- Pipeline ---
with tab_pipeline:
    df = pd.DataFrame(pipeline_summary(40))
    if df.empty:
        st.info("Записей нет. Запустите `fortress.ps1 pipeline`.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- Findings ---
with tab_findings:
    df = pd.DataFrame(findings_summary(40))
    st.dataframe(df if not df.empty else pd.DataFrame(columns=["пусто"]), hide_index=True)

# --- Помощь ---
with tab_help:
    st.markdown(
        """
### Как работать

1. **Регистрация** — вкладка на экране входа; роль выбираете сами.
2. **MLflow** — тот же логин/пароль (Keycloak SSO через oauth2-proxy).
3. **Pipeline** — терминал: `.\\fortress.ps1 pipeline`.
4. **Deploy** — после успешного pipeline (CI-модели).
5. **Внешняя модель** — `security.origin=external` → одобрение MLSecOps.

### Кнопки в UI

| Вкладка | Кнопка | Действие |
|---------|--------|----------|
| Deploy | Pre-deploy | проверка G12 без смены stage |
| Deploy | Deploy | Production (CI, если гейты OK) |
| Deploy | Одобрить + Deploy | только MLSecOps, внешние модели |
| Deploy | Архивировать | только MLSecOps |
| Паспорт | Сохранить в MLflow | тег `model_card` |
| Цепочка | Проверить | audit hash-chain |

### Запуск в терминале (не в UI)

| Команда | Когда |
|---------|-------|
| `fortress.ps1 up` | поднять сервисы |
| `fortress.ps1 bootstrap` | БД + MLflow |
| `fortress.ps1 train` | обучение |
| `fortress.ps1 pipeline` | полный CI + attestation |
| `fortress.ps1 all` | всё сразу |

Подробнее: `docs/GUIDE.md` в репозитории.
        """
    )

with tab_audit:
    st.dataframe(pd.DataFrame(audit_summary(50)), use_container_width=True, hide_index=True)

with tab_chain:
    if st.button("Проверить цепочку"):
        ok, msg = verify_chain()
        st.success(msg) if ok else st.error(msg)
