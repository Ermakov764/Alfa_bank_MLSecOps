# CI/CD Pipeline — FORTRESS

## Два workflow на push (зачем)

| Workflow | Файл | Назначение |
|----------|------|------------|
| **CI Pipeline (MLflow path)** | `.github/workflows/ci-pipeline.yml` | Основной: DATA → code gates → **train с Postgres+MLflow** → artifact/model gates → sign → pytest |
| **Security Gates (legacy smoke)** | `.github/workflows/security.yml` | Быстрый smoke (~10 с): только G5 на `evil_model.pkl`; остался с раннего MVP до полного `ci-pipeline` |

Оба триггерятся на `push` в `main` — поэтому в Actions видно **два run’а** на один коммит. Legacy smoke можно отключить или ограничить `paths`, если мешает шумом.

## Поток (MLflow / retrain)

```text
gate-data (DATA) → gate-code (G0,G1,G3,G3b) → train → gate-artifacts (G6,G7) → gate-model (G5,G8,G9,G10) → sign (Ed25519) → [Deploy]
```

Каждый этап — **отдельный job/контейнер** в GitHub Actions (`.github/workflows/ci-pipeline.yml`).

Локально: `make ci-pipeline` → `scripts/ci/run_pipeline.sh`.

В GitHub Actions каждый этап — **отдельный job** в UI (`gate-data` → `gate-code` → `train` → …), но команды выполняются в контейнере **`fortress`** через `docker compose`. Job **train** поднимает полный стек: Postgres + MinIO (S3) + MLflow + dashboard UI + API.

## Прозрачность

| Куда | Что |
|------|-----|
| `artifacts/gates/` | JSON-отчёты сканеров |
| `artifacts/attestation/fortress-attestation.signed.json` | Подписанный bundle |
| Postgres `pipeline_runs` | Статус по element/gate |
| Postgres `audit_events` / `findings` | Hash-chain + triage |
| GHA Artifacts | Скачивание отчётов |

## Регистрация и теги MLflow

Теги `security.*` **только** из проверенной attestation:

- `scripts/register_model.py`
- `scripts/ci/register_from_pipeline.py`

Ручной `SECURITY_G*=passed` **удалён**.

## Deploy

1. Кнопка **Deploy** в Streamlit (роль mlsecops) или workflow `deploy.yml`.
2. `scripts/ci/deploy_precheck.sh`: code gates + verify attestation + G11 Trivy.
3. `scripts/promote_to_production.py` (G12): RBAC + HITL + **G11 обязателен**.

```bash
make deploy-precheck
ACTOR_ROLE=mlsecops make promote MODEL=credit-scoring-pd VERSION=1
```

## Подписи (Ed25519)

- Ключи: `artifacts/signing/` (dev, в `.gitignore` через `artifacts/`)
- Prod CI: secrets `FORTRESS_SIGNING_PRIVATE_KEY` / `PUBLIC_KEY` (base64 PEM)
- Verify: `fortress.attestation.verify_attestation()`

## Внешняя модель (без train)

Workflow `workflow_dispatch` с `source=external`: пропуск DATA+train, контейнеры code + model + sign.
