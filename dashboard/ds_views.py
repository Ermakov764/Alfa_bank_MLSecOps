"""Streamlit-блоки для роли Data Scientist."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from fortress.config import jupyter_public_url, mlflow_public_url
from dashboard.shared_views import render_deploy_panel, render_pipeline_panel
from fortress.dataset_registry import ingest_dataset
from fortress.mlflow_datasets import list_quarantined_datasets, register_from_mlflow_run
from fortress.ds_workspace import (
    check_results_detailed,
    ds_kpis,
    my_models_overview,
    signed_datasets,
    signed_models,
)
from fortress.mlflow_client import (
    get_client,
    list_models_for_user,
    list_versions,
    save_model_card_tag,
)
from fortress.mlflow_experiments import (
    list_experiments,
    list_runs,
    passport_from_mlflow,
)
from fortress.model_card import ModelCard


def render_ds_home(user) -> None:
    kpi = ds_kpis(user.username)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Мои модели", kpi["my_models"])
    c2.metric("Подписанные модели", kpi["signed_models"])
    c3.metric("Подписанные датасеты", kpi["signed_datasets"])
    c4.metric("Требуют внимания", kpi["needs_attention"])

    with st.expander("Pipeline и train", expanded=False):
        render_pipeline_panel(user, key_prefix="ds")

    with st.expander("Зарегистрировать внешнюю модель", expanded=False):
        _render_external_register(user)

    df = my_models_overview(user.username, user.role)
    if df:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Моделей пока нет. Запустите pipeline выше или зарегистрируйте external-модель.")


def _render_external_register(user) -> None:
    from fortress.external_model import register_external_from_files

    name = st.text_input("Имя модели в MLflow", key="ext_model_name")
    purpose = st.text_input("Назначение", key="ext_purpose")
    tier = st.selectbox("Tier", ["HIGH", "MED", "LOW"], key="ext_tier")
    files = st.file_uploader("Файлы модели (ONNX, joblib, manifest…)", accept_multiple_files=True, key="ext_files")
    if st.button("Зарегистрировать external", key="ext_reg_btn") and files and name:
        payload = [(f.name, f.getvalue()) for f in files]
        ok, msg = register_external_from_files(
            name, payload, owner=user.username, purpose=purpose, tier=tier,
        )
        st.success(msg) if ok else st.error(msg)


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
    """Данные: произвольная загрузка в MLflow + опциональный DATA gate для pipeline."""
    mlflow_url = mlflow_public_url()
    jupyter_url = jupyter_public_url()

    st.markdown(
        """
**Вы — обычный DS:** берёте файлы **с любой папки на своём ПК** → загружаете в **MLflow**.
FORTRESS показывает одобренные датасеты (если прошли DATA gate) и **логирует все блокировки**.
        """
    )

    c1, c2 = st.columns(2)
    with c1:
        st.link_button("Jupyter", jupyter_url, use_container_width=True)
        st.caption("Пароль `fortress` · см. `notebooks/START_HERE.md`")
    with c2:
        st.link_button("MLflow", mlflow_url, use_container_width=True)
        st.caption("Эксперименты, runs, артефакты")

    st.divider()

    tab_ml, tab_gate, tab_runs = st.tabs([
        "В MLflow (любые файлы)",
        "Регистрация для pipeline (DATA gate)",
        "Мои датасеты",
    ])

    with tab_ml:
        st.markdown(
            "Загрузка **без ограничений по колонкам** — для ваших эксперimentов. "
            "Файлы с диска вашего компьютера → MLflow (MinIO)."
        )
        exp = st.text_input("Эксперимент MLflow", "ds-experiments", key="ds_ml_exp")
        rname = st.text_input("Имя run", "local-upload", key="ds_ml_run")
        files = st.file_uploader(
            "Файлы с компьютера (можно несколько)",
            accept_multiple_files=True,
            key="ds_ml_files",
        )
        st.code(
            f'python scripts/ds_log_to_mlflow.py --file "C:\\\\Users\\\\YOU\\\\data.csv" '
            f'--experiment {exp} --run-name {rname} --owner {user.username}',
            language="powershell",
        )
        if st.button("Загрузить в MLflow", type="primary", key="ds_ml_upload") and files:
            from fortress.ds_mlflow_upload import log_local_files

            tmp_paths: list[Path] = []
            for f in files:
                t = Path(tempfile.gettempdir()) / f"fortress_{f.name}"
                t.write_bytes(f.getvalue())
                tmp_paths.append(t)
            try:
                run_id, uri = log_local_files(
                    tmp_paths,
                    experiment=exp,
                    run_name=rname,
                    owner=user.username,
                )
                st.success(f"Загружено в MLflow · run `{run_id[:12]}…`")
                st.caption(uri)
            except Exception as exc:
                st.error(str(exc))

    with tab_gate:
        st.markdown(
            "Только если нужен **CI pipeline FORTRESS**. Проверка: poison-колонки, PII, "
            "опционально — список колонок."
        )
        up = st.file_uploader("CSV", type=["csv"], key="ds_dataset_upload")
        dname = st.text_input("Имя датасета", "my_dataset", key="ds_ds_name")
        dver = st.text_input("Версия", "v1", key="ds_ds_ver")
        cols = st.text_input(
            "Колонки (необязательно, через запятую)",
            "",
            key="ds_ds_cols",
            help="Пусто = проверяются только poison / PII / пустые ячейки",
        )
        if st.button("Проверить и зарегистрировать", type="primary", key="ds_ingest_btn") and up:
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(up.getvalue())
                tmp_path = Path(tmp.name)
            ok, msg = ingest_dataset(tmp_path, dname, dver, user.username, expected_cols=cols)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
                st.info("Причина также в **Findings** и аудите.")

        st.markdown("---")
        st.caption("Или проверить run, созданный в Jupyter / MLflow:")
        run_id = st.text_input("MLflow Run ID", key="ds_mlflow_run_id")
        cols2 = st.text_input("Колонки (необязательно)", "", key="ds_mlflow_cols")
        if st.button("Проверить run", key="ds_validate_run") and run_id.strip():
            ok, msg, _ = register_from_mlflow_run(
                run_id.strip(), user.username, expected_cols=cols2,
            )
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()

    with tab_runs:
        if st.button("Обновить из MLflow", key="ds_sync_mlflow"):
            from fortress.mlflow_datasets import sync_pending_runs

            for row in sync_pending_runs(user.username):
                st.caption(f"{row['run_id']}: {row['message']}")
            st.rerun()

        st.subheader("✅ Одобренные (DATA gate пройден)")
        sd = signed_datasets(user.username, user.role)
        if sd and sd[0].get("_error"):
            st.error(f"MLflow недоступен: {sd[0]['_error']}")
        elif sd:
            st.dataframe(sd, use_container_width=True, hide_index=True)
        else:
            st.info("Нет зарегистрированных датасетов для pipeline.")

        st.subheader("⛔ Заблокированные попытки")
        blocked = list_quarantined_datasets(user.username, user.role)
        if blocked:
            st.dataframe(
                [
                    {
                        "Датасет": r["name"],
                        "Версия": r["version"],
                        "Причина": (r.get("failure_reason") or "—")[:120],
                        "Run": (r.get("run_id") or "")[:12],
                    }
                    for r in blocked
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Заблокированных попыток нет.")

        st.subheader("Подписанные модели")
        sm = signed_models(user.username, user.role)
        if sm:
            st.dataframe(sm, use_container_width=True, hide_index=True)
        else:
            st.info("Нет подписанных моделей.")


def render_ds_deploy(user) -> None:
    render_deploy_panel(user, key_prefix="ds_dep")


def render_ds_findings(user) -> None:
    from dashboard.shared_views import render_findings_panel

    render_findings_panel(user, key_prefix="ds_find")


def render_ds_help(user) -> None:
    mlflow_url = mlflow_public_url()
    jupyter_url = jupyter_public_url()
    st.markdown(
        f"""
### Data Scientist — всё через кнопки в UI

1. **Мои модели** — pipeline, train, регистрация external-модели  
2. **Данные** — загрузка файлов в MLflow, DATA gate  
3. **Deploy** — Pre-deploy → Production  
4. **Findings / Проверки** — если что-то заблокировано  

Поднять Docker: `.\fortress.ps1 up` (единственная команда в терминале).

**Логин:** `{user.username}` · **MLflow:** [{mlflow_url}]({mlflow_url}) · **Jupyter:** [{jupyter_url}]({jupyter_url})
        """
    )
