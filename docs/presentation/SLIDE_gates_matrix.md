# Матрица проверок FORTRESS — для слайда

> Актуально по коду репозитория (июнь 2026).  
> Номера **G*** — как в `gates/`, `scripts/ci/`, `docs/architecture.md §7`.  
> Легенда: **✓** MVP · **~** частично · **○** план / backlog

---

## Таблица для слайда (8 колонок)

| Актив | Что проверяем | Gate | Инструмент | Статус |
|-------|---------------|------|------------|--------|
| **Данные** (CSV) | Poison-колонки, PII (карты), пустые ячейки, схема колонок | **DATA** | `data_gate.py` (pandas, regex) | ✓ |
| | Баланс классов (anti-poisoning) | **DATA** | `data_gate.py` | ✓ |
| | prompt-injection в тексте | **DATA** | regex в `pii_scanner.py` | ✓ |
| | PII (email, phone, SSN, …) | **DATA** | Presidio Analyzer | ✓ |
| **Код** (Git) | Секреты в репозитории | **G0** | gitleaks | ✓ |
| | Опасный ML-код (pickle.load и др.) | **G1** | Semgrep | ✓ |
| | CVE в `requirements.txt` | **G3** | pip-audit | ✓ |
| | Typosquatting PyPI | **G3b** | guarddog | ✓ |
| | Доп. SAST Python | **G2** | bandit | ✓ CI |
| **Зависимости** | Typosquat / malicious metadata | **G3b** | guarddog | ✓ |
| | Pinning, trusted PyPI/HF allow-list | **G4** | `check_deps_policy.py` | ✓ CI |
| **Модель** (веса) | Pickle RCE, scan файла | **G5** | ModelAudit / modelscan | ✓ |
| | Запрет `.pkl` в prod-bundle | **G6** | `check_format_policy.py` | ✓ |
| | SHA-256 manifest артефакта | **G7** | `g7_sign_manifest.py` | ✓ |
| | Holdout accuracy (M1/M2) | **G8** | `g8_validate.py` | ✓ CI |
| | Adversarial robustness (M1/M2) | **G9** | `g9_art.py` | ✓ CI |
| | LLM red-team probes (M3) | **G10** | `g10_llm_probe.py` | ✓ CI |
| | cosign / Sigstore (SIGNING_STRICT) | **G7** | cosign sign-blob + verify | ✓ CI |
| **Контейнер** (Docker) | CRITICAL CVE в образе | **G11** | Trivy | ✓ CI |
| **Паспорт** (model card) | Tier, owner, purpose, PII policy | **G12** | pydantic `ModelCard` | ✓ |
| | Lineage dataset↔git↔run↔SHA | G12 | MLflow tags + audit | ~ |
| **Реестр / Deploy** | Все `security.*` теги, Human Approve | **G12** | `promote_to_production.py` + Keycloak | ✓ |
| **Runtime API** | Rate limit, anti-burst | **G14** | FastAPI middleware (M1/M2/M3) | ✓ |
| | Prompt injection / jailbreak (M3) | **G13** | LLM-Guard regex в LiteLLM | ✓ |
| | Drift PSI, деградация метрик | **G15** | Evidently + telemetry | ✓ CI |
| | DLP в audit-логах | **G15+** | Presidio Anonymizer | ✓ |

---

## Компактная версия (влезает на один слайд)

| Слой | Gates | Инструменты | MVP |
|------|-------|-------------|-----|
| Данные | DATA | pandas, regex | ✓ |
| Код / CI | G0–G4 | gitleaks, Semgrep, bandit, pip-audit, guarddog, deps policy | ✓ |
| Артефакт | G5 G6 G7 | modelscan, format policy, SHA-256 | ✓ |
| ML quality | G8 G9 G10 | holdout, ART, LLM probes | ✓ CI |
| Образ | G11 | Trivy | ✓ |
| Релиз | G12 | ModelCard + RBAC + Human Approve | ✓ |
| Runtime | G13 G14 G15 | LLM-Guard, rate-limit, drift PSI | ✓ |

---

## Два пути pipeline (важно для защиты)

| Путь | Команда | Что гоняется |
|------|---------|--------------|
| **Короткий** (UI / demo) | `fortress pipeline` | DATA → G0 G1 G3 G3b → sign attestation |
| **Полный** (CI / train) | GHA `ci-pipeline.yml`, `make ci-pipeline` | DATA → code → **train** → G6 G7 → G5 G8 G9 G10 → sign → pytest |

Deploy в Production: **Pre-deploy** (code + attestation + **G11 Trivy**) → **G12 promote** (только `mlsecops`).

---

## Фраза для устного комментария к слайду

«На слайде — фактическая матрица MVP: реализованы gates от DATA до G14. Часть data-checks и drift — в roadmap. Короткий pipeline в UI — для быстрой проверки; полный train-path — в GitHub Actions.»

---

## Что **не** утверждать на слайде

- ❌ «Все проверки из старой таблицы G0–G7 по колонкам» — номера были другие  
- ❌ «API / runtime убраны» — M1/M2/M3 на `:8001` `:8002` `:4000`  
- ❌ «cosign обязателен везде» — основная подпись: **Ed25519 attestation**  
- ❌ «Jupyter → prod напрямую» — только через CI + G12
