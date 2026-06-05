"""Streamlit-блоки для роли Data Scientist."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from fortress.dataset_registry import ingest_dataset
from fortress.deploy_runner import deploy_to_production, run_precheck
from fortress.ds_workspace import (
    check_results_detailed,
    ds_kpis,
    my_findings,
    my_models_overview,
    signed_datasets,
    signed_models,
)
from fortress.mlflow_client import (
    get_client,
    list_models_for_user,
    list_versions,
    save_model_card_tag,
    version_security_summary,
)
from fortress.mlflow_experiments import (
    list_experiments,
    list_runs,
    passport_from_mlflow,
)
from fortress.model_card import ModelCard
from fortress.pipeline_runner import run_pipeline


def render_ds_home(user) -> None:
    kpi = ds_kpis(user.username)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Мои модели", kpi["my_models"])
    c2.metric("Подписанные модели", kpi["signed_models"])
    c3.metric("Подписанные датасеты", kpi["signed_datasets"])
    c4.metric("Требуют внимания", kpi["needs_attention"])

    with st.expander("Запустить CI pipeline", expanded=False):
        st.caption("Обучение + все гейты + подпись + sync в MLflow.")
        mk = st.selectbox("Модели", ["all", "m1", "m2", "m3"], key="ds_pipeline_mk")
        if st.button("Запустить pipeline", type="primary", key="ds_run_pipeline"):
            with st.spinner("Pipeline выполняется…"):
                ok, log = run_pipeline(model_key=mk, actor=user.username)
            if ok:
                st.success("Pipeline завершён успешно")
            else:
                st.error("Pipeline завершился с ошибкой")
            if log:
                st.code(log[-6000:], language="text")

    df = my_models_overview(user.username, user.role)
    if df:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Ваших моделей пока нет. Запустите pipeline выше или `fortress.ps1 pipeline`.")


def render_ds_passport(user) -> None:
    st.caption("Паспорт заполняется из MLflow: эксперимент → run → версия модели → артефакты.")

    models = list_models_for_user(user.username, role=user.role)
    if not models:
        st.warning("Зарегистрируйте модель в MLflow.")
        return

    src = st.radio(
        "Источник данных",
        ["Зарегистрированная версия", "Эксперимент MLflow"],
        horizontal=True,
    )

    run_id: str | None = None
    pm = st.selectbox("Модель в реестре", models, key="ds_passport_model")

    if src == "Эксперимент MLflow":
        exps = list_experiments()
        if not exps:
            st.warning("Нет экспериментов. Запустите train/pipeline.")
            return
        exp_names = [e["name"] for e in exps]
        exp_idx = st.selectbox("Эксперимент", range(len(exps)), format_func=lambda i: exp_names[i])
        exp_id = exps[exp_idx]["id"]
        runs = list_runs(exp_id)
        if not runs:
            st.warning("В эксперименте нет runs.")
            return
        run_idx = st.selectbox(
            "Run (обучение)",
            range(len(runs)),
            format_func=lambda i: (
                f"{runs[i]['name']} · {runs[i]['status']} · "
                f"metrics={list(runs[i]['metrics'].keys())[:3]}"
            ),
        )
        run_id = runs[run_idx]["run_id"]
        with st.expander("Детали run", expanded=True):
            st.json({
                "run_id": run_id,
                "artifact_uri": runs[run_idx]["artifact_uri"],
                "metrics": runs[run_idx]["metrics"],
                "params": runs[run_idx]["params"],
            })
        pvers = list_versions(pm, user.username, role=user.role)
        if pvers:
            pv = st.selectbox(
                "Версия для сохранения паспорта",
                [v["version"] for v in pvers],
                key="ds_passport_ver_exp",
            )
        else:
            st.warning("Сначала создайте версию модели в MLflow.")
            return
    else:
        pvers = list_versions(pm, user.username, role=user.role)
        if not pvers:
            st.warning("Нет версий.")
            return
        pv = st.selectbox("Версия модели", [v["version"] for v in pvers], key="ds_passport_ver")
        tags_run = passport_from_mlflow(pm, pv, None, user.username)
        if tags_run.get("mlflow_run_id"):
            st.caption(
                f"Связанный run: `{tags_run['mlflow_run_id']}` · "
                f"эксперимент: `{tags_run['mlflow_experiment']}`"
            )

    prefill = passport_from_mlflow(pm, pv, run_id, user.username)

    with st.expander("Контекст MLflow", expanded=False):
        st.markdown(
            f"- **Эксперимент:** `{prefill.get('mlflow_experiment') or '—'}`\n"
            f"- **Run ID:** `{prefill.get('mlflow_run_id') or '—'}`\n"
            f"- **Артефакты:** `{prefill.get('artifact_uri') or prefill.get('mlflow_source') or '—'}`\n"
            f"- **Подпись:** {'да' if prefill.get('signed') else 'нет'}"
        )
        if prefill.get("metrics"):
            st.json(prefill["metrics"])

    with st.form("ds_passport_form"):
        purpose = st.text_area("Назначение (purpose)", prefill.get("purpose", ""))
        data_sources = st.text_input("Источники данных", prefill.get("data_sources", ""))
        limitations = st.text_input("Ограничения", prefill.get("limitations", "см. MLflow metrics"))
        tier = st.selectbox("tier", ["HIGH", "MED", "LOW"])
        if st.form_submit_button("Сохранить паспорт в MLflow"):
            try:
                metrics = dict(prefill.get("metrics") or {})
                metrics["_mlflow_run_id"] = prefill.get("mlflow_run_id", "")
                metrics["_mlflow_experiment"] = prefill.get("mlflow_experiment", "")
                metrics["_artifact_uri"] = prefill.get("artifact_uri", "")
                card = ModelCard(
                    name=pm,
                    version=str(pv),
                    tier=tier,
                    owner=user.username,
                    purpose=purpose,
                    data_sources=data_sources,
                    limitations=limitations,
                    metrics=metrics,
                )
                client = get_client()
                save_model_card_tag(pm, str(pv), card.to_mlflow_tag())
                client.set_model_version_tag(pm, str(pv), "owner", user.username)
                if prefill.get("mlflow_run_id"):
                    client.set_model_version_tag(pm, str(pv), "mlflow_run_id", prefill["mlflow_run_id"])
                st.success("Паспорт и привязка к MLflow run сохранены")
            except Exception as ex:
                st.error(str(ex))


def render_ds_checks(user) -> None:
    st.caption("Почему не прошла проверка — на русском + фрагмент из лога.")
    rows = check_results_detailed(user.username, user.role, 30)
    if not rows:
        st.info("Записей проверок нет. Запустите pipeline.")
        return
    for row in rows:
        if row["Статус"] == "ОШИБКА":
            with st.expander(f"❌ {row['Гейт']} — {row['Что проверялось']}", expanded=True):
                st.markdown(f"**Объяснение:** {row['Объяснение']}")
                st.markdown(f"**Что делать:** {row['Что делать']}")
                if row["Фрагмент лога"]:
                    st.code(row["Фрагмент лога"], language="text")
        else:
            st.success(f"✓ {row['Гейт']} — {row['Что проверялось']}")


def render_ds_signed(user) -> None:
    st.subheader("Подписанные модели")
    sm = signed_models(user.username, user.role)
    if sm:
        st.dataframe(sm, use_container_width=True, hide_index=True)
    else:
        st.info("Нет подписанных моделей. Успешный pipeline + sync в MLflow.")

    st.subheader("Подписанные датасеты (DATA gate)")
    sd = signed_datasets(user.username, user.role)
    if sd and sd[0].get("_error"):
        st.error(f"Реестр датасетов недоступен: {sd[0]['_error']}")
    elif sd:
        st.dataframe(sd, use_container_width=True, hide_index=True)
    else:
        st.info("Нет датасетов со статусом available.")

    with st.expander("Загрузить датасет (CSV)", expanded=False):
        up = st.file_uploader("CSV файл", type=["csv"], key="ds_dataset_upload")
        dname = st.text_input("Имя датасета", "my_dataset", key="ds_ds_name")
        dver = st.text_input("Версия", "v1", key="ds_ds_ver")
        cols = st.text_input("Ожидаемые колонки (через запятую)", "amount,age,target", key="ds_ds_cols")
        if st.button("Проверить и зарегистрировать", key="ds_ingest_btn") and up:
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(up.getvalue())
                tmp_path = Path(tmp.name)
            ok, msg = ingest_dataset(tmp_path, dname, dver, user.username, expected_cols=cols)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def render_ds_deploy(user) -> None:
    models = list_models_for_user(user.username, role=user.role)
    if not models:
        st.info("Нет моделей для deploy.")
        return
    sel = st.selectbox("Модель", models, key="ds_deploy_model")
    vers = list_versions(sel, user.username, role=user.role)
    if not vers:
        return
    vi = st.selectbox(
        "Версия",
        range(len(vers)),
        format_func=lambda i: f"v{vers[i]['version']} · {vers[i]['stage']}",
    )
    version = vers[vi]["version"]
    summary = version_security_summary(sel, version)
    if summary["last_failure"]:
        st.error(summary["last_failure"])
    if summary["missing_gates"]:
        st.error("Не пройдены: " + ", ".join(summary["missing_gates"]))
    if summary["needs_mlsecops"]:
        st.warning("Внешняя модель — нужен MLSecOps.")
    else:
        st.success(summary["approval_label"])

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Pre-deploy", key="ds_pre"):
            ok, log = run_precheck(sel, version, actor_role=user.role)
            st.success(log) if ok else st.error(log)
    with c2:
        disabled = summary["needs_mlsecops"]
        if st.button("Deploy в Production", type="primary", disabled=disabled, key="ds_dep"):
            ok, msg = deploy_to_production(sel, version, user.username, actor_role=user.role)
            st.success(msg) if ok else st.error(msg)


def render_ds_findings(user) -> None:
    rows = my_findings(user.username, user.role)
    if not rows:
        st.info("Findings по вашим моделям отсутствуют.")
        return
    for row in rows:
        with st.expander(f"{row['Гейт']} · {row['Severity']} · {row['Время']}", expanded=False):
            st.markdown(f"**{row['Объяснение']}**")
            st.markdown(f"Рекомендация: {row['Рекомендация']}")
            if row["Фрагмент лога"]:
                st.code(row["Фрагмент лога"])


def render_ds_help(user) -> None:
    st.markdown(
        f"""
### Рабочий процесс Data Scientist

1. **Регистрация** — один аккаунт Keycloak для FORTRESS и MLflow.
2. **Датасет** — вкладка «Подписанные» → загрузить CSV (DATA gate + реестр).
3. **Pipeline** — вкладка «Мои модели» → «Запустить CI pipeline».
4. **Паспорт** — эксперимент MLflow → run → сохранить `model_card`.
5. **Проверки** — объяснение на русском + фрагмент лога при ошибке.
6. **Deploy** — CI-модели с подписью → Pre-deploy → Production.

**Логин:** `{user.username}` · **роль:** `{user.role}`
        """
    )
