"""FORTRESS Security Center — UI поверх MLflow."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.audit import verify_chain  # noqa: E402
from fortress.auth import (  # noqa: E402
    SessionUser,
    authenticate_with_message,
    keycloak_account_url,
    mlflow_public_url,
    register_and_login,
)
from fortress.keycloak_admin import ROLE_LABELS, keycloak_reachable  # noqa: E402
from fortress.config import jupyter_public_url  # noqa: E402
from dashboard.ds_views import (  # noqa: E402
    render_ds_checks,
    render_ds_deploy,
    render_ds_findings,
    render_ds_help,
    render_ds_home,
    render_ds_passport,
    render_ds_signed,
)
from dashboard.mlsecops_views import (  # noqa: E402
    render_mlsecops_audit,
    render_mlsecops_chain,
    render_mlsecops_deploy,
    render_mlsecops_help,
    render_mlsecops_home,
    render_mlsecops_pipeline,
)
from dashboard.shared_views import render_services_health  # noqa: E402

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
            u, err = authenticate_with_message(username, password)
            if u:
                st.session_state.user = u
                st.rerun()
            else:
                st.error(err or "Неверный логин или пароль")

    with tab_register:
        st.caption("Создайте аккаунт — после регистрации вход выполнится автоматически.")
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
        if st.button("Зарегистрироваться", type="primary", key="btn_register"):
            if new_pass != new_pass2:
                st.error("Пароли не совпадают")
            elif not keycloak_reachable():
                st.error("Keycloak ещё не готов")
            else:
                user, msg = register_and_login(new_user, new_email, new_pass, role)
                if user:
                    st.session_state.user = user
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    return None


user = require_login()
if not user:
    st.stop()

st.sidebar.title("FORTRESS")
st.sidebar.caption(f"{user.username}" + (f" · {user.email}" if user.email else ""))
if st.sidebar.button("Выйти"):
    st.session_state.user = None
    st.rerun()

render_services_health(compact=True)
st.sidebar.divider()
st.sidebar.markdown("**Сервисы**")
st.sidebar.link_button("MLflow", MLFLOW_URL)
if user.role == "ds":
    st.sidebar.link_button("Jupyter", jupyter_public_url())
st.sidebar.link_button("Keycloak", keycloak_account_url())
st.sidebar.caption("Docker: .\\fortress.ps1 up")

st.title("Security Center" if user.role == "mlsecops" else "FORTRESS — Data Scientist")

if user.role == "ds":
    t1, t2, t3, t4, t5, t6, t7 = st.tabs(
        ["Мои модели", "Паспорт", "Проверки", "Данные", "Deploy", "Findings", "Помощь"]
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

tab_names = ["Обзор", "Deploy", "Паспорт", "Данные", "Pipeline", "Findings", "Аудит", "Цепочка", "Помощь"]
tabs = st.tabs(tab_names)
(
    tab_home, tab_deploy, tab_passport, tab_data, tab_pipeline,
    tab_findings, tab_audit, tab_chain, tab_help,
) = tabs

with tab_home:
    render_mlsecops_home()
with tab_deploy:
    render_mlsecops_deploy(user)
with tab_passport:
    render_ds_passport(user)
with tab_data:
    render_ds_signed(user)
with tab_pipeline:
    render_mlsecops_pipeline(user)
with tab_findings:
    from dashboard.shared_views import render_findings_panel

    render_findings_panel(user, limit=40, key_prefix="mso_find")
with tab_audit:
    render_mlsecops_audit()
with tab_chain:
    render_mlsecops_chain()
with tab_help:
    render_mlsecops_help()
