# Бриф для разработчика (актуально)

## 1. Только Docker — без привязки к ОС

- Единая точка входа: **`fortress.ps1`** (Windows) / **`bin/fortress`** (Linux/macOS).
- Вся логика в контейнере **`fortress`** (`infra/docker/Dockerfile.fortress`, `scripts/fortress/entrypoint.sh`).
- Удалены лишние хостовые скрипты: `make.ps1`, `demo-local.ps1`. Старые `scripts/*.ps1` — тонкие redirect на `fortress.ps1`.

```powershell
.\fortress.ps1 up
.\fortress.ps1 bootstrap
.\fortress.ps1 pipeline
.\fortress.ps1 demo
.\fortress.ps1 deploy credit-scoring-pd 1 mlsecops1
```

## 2. Роль CEO — убрана

- Удалены пользователь `ceo` и realm-роль из `infra/keycloak/realm-export.json`.
- Убрана вкладка **CEO Report** и mock из Streamlit.

## 3. Мониторинг для MLSecOps

- Модуль `fortress/monitoring.py` — KPI и таблицы **без сырых JSON**.
- Вкладка **Обзор**: метрики, таблица моделей, статус gates одной строкой.
- Pipeline / Audit / Findings — компактные таблицы.

## 4. Deploy в Production

- Только **внутренние CI-модели**: `credit-scoring-pd`, `transaction-antifraud`, `support-nlp` (`INTERNAL_MODELS`).
- Пайплайн: `fortress/deploy_runner.py` → `deploy_precheck.py` (attestation Ed25519 + G12) → `promote_to_production.py`.
- UI: вкладка **Deploy** — кнопки Pre-deploy и Deploy (роль `mlsecops`).
- CLI: `fortress deploy MODEL VERSION ACTOR`.

## 5. Авторизация (один аккаунт)

- `fortress/auth.py` — Keycloak password grant + dev fallback (те же пароли, что в realm).
- Streamlit: экран входа; в sidebar — ссылка на MLflow с подсказкой **тот же логин**.
- Client Keycloak: `fortress-ui` (direct access grants).
- MLflow UI: `oauth2-proxy-mlflow` (host :5000 → Keycloak OIDC, клиент `mlflow-oauth`) — тот же логин, что в FORTRESS.

## 6. Паспорт модели + MLflow

- Dropdown моделей/версий пользователя (`owner` tag при register).
- Автозаполнение из тега `model_card` и security-тегов MLflow (`passport_prefill`).

## 7. Что доработать

- [ ] Webhook deploy из Streamlit → GitHub `deploy.yml` (опционально)
- [ ] G11 Trivy внутри `deploy_precheck` без хостового docker.sock
- [ ] Фильтр внешних моделей в MLflow UI (registry policy)
