# Модель угроз — FORTRESS MLSecOps (ИБАНК кейс)

Версия: 1.0 · Профиль: **FORTRESS**  
Связанные документы: [ПЛАН_РЕАЛИЗАЦИИ.md](../ПЛАН_РЕАЛИЗАЦИИ.md), [architecture.md](./architecture.md), [ТЗ.md](../ТЗ.md)

---

## 1. Контекст системы

Платформа FORTRESS объединяет MLOps (MLflow, train, deploy) и MLSecOps (gates G0–G15, DATA, audit, RBAC) в одном `docker compose` для локального демо.

**Границы trust zones:**

| Зона | Компоненты | Контроли |
|------|------------|----------|
| DEV | Git, ноутбук DS | G0, G1, DATA (local) |
| CI | GitHub Actions, `make security-*` | G0–G3b |
| REGISTRY | MLflow, MinIO, Postgres audit | G5–G12, Keycloak RBAC |
| PROD | FastAPI M1/M2, LiteLLM M3 | G13, G14; только stage Production |

```text
DEV → CI → DATA → Train → Gates → MLflow Staging → HITL → Production → API
         └──────────────── audit_events (hash-chain) ────────────────┘
```

---

## 2. Активы

| ID | Актив | Критичность | Описание |
|----|-------|-------------|----------|
| A1 | Модели (ONNX, registry) | Высокая | PD-scoring, antifraud, support-nlp |
| A2 | Обучающие датасеты (CSV) | Высокая | `datasets` + MinIO |
| A3 | MLflow + MinIO | Высокая | Версии, артефакты, stages |
| A4 | Postgres (audit, findings) | Высокая | Неизменяемый журнал, triage |
| A5 | API keys / secrets | Критическая | Облако, MinIO, Keycloak |
| A6 | Docker-образы inference | Средняя | api-scoring, api-antifraud, litellm |
| A7 | Keycloak (идентичность) | Средняя | Роли ds, mlsecops, de, ceo |

---

## 3. Поверхность атаки

- **Git / PR** — внедрение секретов, вредоносного кода, typosquat зависимостей.
- **Внешняя модель (HF/file)** — pickle RCE, подмена весов.
- **MLflow UI/API** — несанкционированный promote, подмена тегов `security.*`.
- **Train pipeline** — отравление CSV, утечка PII в фичи.
- **Inference API** — model extraction, prompt injection, DoS/rate abuse.
- **Контейнеры** — CVE в base image.

---

## 4. Угрозы, последствия, митигации

| ID | Угроза | Этап ЖЦ | OWASP ML | Последствие | Gates / практика | Статус |
|----|--------|---------|----------|-------------|------------------|--------|
| T1 | Pickle RCE в артефакте модели | Регистрация | ML05 | RCE на inference | G5, G6, G7 | Реализовано |
| T2 | Typosquatting PyPI (`pytirch`) | Обучение | ML04 | Supply chain | G3b | Реализовано |
| T3 | Секрет в Git/ноутбуке | Dev | — | Утечка ключей | G0 | Реализовано |
| T4 | CVE в зависимостях / образе | CI / Deploy | — | Компромисс контейнера | G3, G11 | Реализовано |
| T5 | Model extraction через API | Эксплуатация | ML01 | Утечка логики модели | G14 | Реализовано |
| T6 | Prompt injection (LLM) | Эксплуатация | LLM01 | Токсичный вывод, leak prompt | G10, G13 | Реализовано |
| T7 | Подмена модели в registry | Релиз | — | Неверные решения | G7, G12, hash-chain audit | Реализовано |
| T8 | Несанкционированный promote | Релиз | — | Непроверенная модель в prod | Keycloak RBAC, G12, HITL | Реализовано |
| T9 | Data poisoning | Сбор данных | ML04 | Бэкдор в данных | DATA | Реализовано |
| T10 | Adversarial evasion (tabular) | Эксплуатация | ML01 | Обход скоринга | G9 | Реализовано (ART/perturbation) |

### T1 — Pickle RCE в артефакте

**Описание:** Злоумышленник публикует модель в pickle; при `load` — исполнение произвольного кода.  
**Актив:** файл модели в MinIO.  
**Последствие:** компромисс inference-сервиса.  
**Митигация:** G5 ModelAudit (и fallback opcode scan) блокирует register; G6 запрещает `.pkl` в prod bundle; G7 — digest sidecar.  
**Остаточный риск:** новые векторы десериализации — обновление ModelAudit.  
**Приоритет:** высокий — **реализовано в MVP**.

### T6 — Prompt injection

**Описание:** Атакующий отправляет jailbreak prompt в M3 API.  
**Митигация:** G10 offline (Garak stub); G13 runtime regex/LLM-Guard middleware → 403 + `llm.prompt_blocked` в audit.  
**Приоритет:** высокий — **реализовано**.

### T8 — Несанкционированный promote

**Митигация:** `promote_to_production.py` (G12) проверяет теги gates + `security.approved_by` для tier HIGH; только `ACTOR_ROLE=mlsecops`.  
**Plan B:** env `ACTOR_ROLE` если Keycloak недоступен.

---

## 5. Уязвимости (OWASP ML Top 10 — выборочно)

| OWASP ML | Связь | Митигация в FORTRESS |
|----------|-------|----------------------|
| ML01 Inference API attack | T5, T10 | G14, G9 |
| ML04 Supply chain data | T2, T9 | G3b, DATA |
| ML05 Model serialization | T1 | G5, G6 |
| LLM01 Prompt injection | T6 | G10, G13 |

---

## 6. Приоритизация

| Приоритет | Что закрыли в MVP | Backlog (фаза 2+) |
|-----------|-------------------|-------------------|
| P0 | T1, T3, T7, T8, T9 | — |
| P1 | T2, T4, T5, T6 | G15 drift (Alibi) |
| P2 | T10 полный ART | SecAI registry, OPA, Kubeflow |

---

## 7. Остаточный риск (честно)

1. **G8** — holdout на ONNX; полный Giskard — backlog.  
2. **G9** — input perturbation на ONNX (не полный ART на GPU).  
3. **Keycloak** — в dev возможен Plan B (`ACTOR_ROLE`); UI без OAuth.  
4. **Attestation** — Ed25519 dev keys; prod — secrets в CI.  
5. **LLM-Guard** — regex в LiteLLM proxy, не полный Protect AI pipeline.  
6. **Insider с доступом к MinIO** — hash-chain audit фиксирует, не предотвращает.  
7. **0-day в MLflow** — G3/G11 + изоляция сети в реальном банке.

---

## 8. Матрица угроза → gate

```text
T1 → G5, G6, G7
T2 → G3b
T3 → G0
T4 → G3, G11
T5 → G14
T6 → G10, G13
T7 → G7, G12, audit hash-chain
T8 → G12, Keycloak/HITL
T9 → DATA
T10 → G9
```

*Документ подготовлен для защиты кейса «Безопасная MLOps-система» — Alfa Bank MLSecOps.*
