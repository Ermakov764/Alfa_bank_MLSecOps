# FORTRESS — полное руководство

Документ для разработчиков, MLSecOps и ревьюеров: как устроено приложение, почему так сделано, как работать и что дорабатывать дальше.

---

## 1. Что это за система

**FORTRESS** — слой безопасности поверх MLOps для банка:

- **MLflow** — реестр моделей, артефакты, метрики, теги безопасности (`security.*`).
- **Security Center** (Streamlit, :8502) — мониторинг, deploy, паспорт модели, findings.
- **Pipeline** (`fortress.ps1 pipeline`) — автоматические гейты + attestation.
- **Audit** (Postgres) — журнал событий и hash-chain (не дублирует реестр моделей).

Главный принцип: **модель не попадает в Production без пройденных проверок и записи в MLflow**.

---

## 2. Почему реализовано именно так

### 2.1 MLflow — источник истины

| Решение | Почему |
|---------|--------|
| Статус одобрения в тегах MLflow | Много разработчиков, много моделей — один реестр, без второй БД «кто одобрен» |
| Нет отдельного UI-запуска pipeline | CI/CD и Docker — воспроизводимость; UI только для deploy и мониторинга |
| `sync_pipeline_to_mlflow.py` после pipeline | Attestation автоматически → теги на версии, DS не жмёт кнопки по каждой модели |

### 2.2 Два типа моделей

| Тип | Тег | Promote |
|-----|-----|---------|
| **CI-trained** | `security.origin=ci_trained` | DS сам, если все гейты + `security.signed=true` |
| **Внешняя** (Opus, vendor) | `security.origin=external` | Только MLSecOps после `security.approved_by` |

**Почему:** CI-модель уже прошла полный pipeline. Внешняя — риск, нужен HITL.

### 2.3 Strict gates без заглушек

- `GATE_STRICT=true` — падение = реальная уязвимость или атака, не warning.
- Python-гейты на Windows / CRLF в Docker — тот же strict, не «тихий OK».
- `--strict` при подписи attestation — нельзя подписать при неполных гейтах.

### 2.4 Docker-first

Один способ запуска на Windows/Linux: `fortress.ps1` → контейнер `fortress`. Исключает «у меня работает».

---

## 3. Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│  Хост: fortress.ps1 / bin/fortress                          │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Docker Compose                                             │
│  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Postgres │ │ MinIO  │ │ Keycloak │ │ Streamlit :8502  │  │
│  │  audit   │ │   S3   │ │  :8080   │ │ Security Center  │  │
│  └──────────┘ └────────┘ └──────────┘ └──────────────────┘  │
│  ┌────────────────┐ oauth2-proxy → MLflow :5000              │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐                 │
│  │ M1 API     │ │ M2 API     │ │ M3 LLM   │                 │
│  └────────────┘ └────────────┘ └──────────┘                 │
│  ┌─────────────────────────────────────────┐               │
│  │ fortress container (train/pipeline/demo) │               │
│  └─────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### Ключевые папки

| Путь | Назначение |
|------|------------|
| `fortress/` | Ядро: audit, attestation, auth, MLflow client, policy, monitoring |
| `fortress/registry_policy.py` | CI vs external, очередь одобрения |
| `fortress/security_profile.py` | G12 — кто может в prod |
| `scripts/ci/run_pipeline.py` | Оркестратор CI |
| `scripts/ci/sync_pipeline_to_mlflow.py` | Attestation → MLflow |
| `gates/` + `scripts/ci/gate_*.py` | Гейты G0–G11 |
| `dashboard/streamlit_app.py` | UI |
| `services/` | Inference API |

---

## 4. Pipeline (что происходит при `fortress.ps1 pipeline`)

```
DATA → G0,G1,G3,G3b → train → G6,G7 → G5,G8,G9/G10 → verify → sign → sync MLflow
```

| Шаг | Файл | Проверяет |
|-----|------|-----------|
| DATA | `scripts/data_gate.py` | poison, PII, колонки |
| Code | `scripts/ci/gate_code.py` | секреты, CVE, typosquat |
| Train | `models/*/train.py` | обучение + лог в MLflow |
| Artifacts | `gate_artifacts_py.py` | формат, manifest ONNX |
| Model | `gate_model_py.py` | scan, G8, G9, G10 (LLM) |
| Sign | `sign_attestation.py` | Ed25519, strict |
| Sync | `sync_pipeline_to_mlflow.py` | теги на версии в MLflow |

При ошибке: exit ≠ 0, запись в `pipeline_runs` / findings, в UI — Pipeline и Findings.

---

## 5. Теги MLflow (что смотреть в реестре)

| Тег | Значение |
|-----|----------|
| `security.origin` | `ci_trained` / `external` |
| `security.signed` | `true` — есть attestation |
| `security.scan_status` | `passed` / `failed` |
| `security.G0` … `security.G10` | результат гейта |
| `security.last_failure` | текст последней ошибки |
| `security.approved_by` | кто одобрил внешнюю модель |
| `model_card` | JSON паспорта модели |
| `owner` | владелец (DS) |

---

## 6. UI — кнопки и вкладки

**URL:** http://localhost:8502

### Вкладки (все роли)

| Вкладка | Назначение |
|---------|------------|
| **Обзор** | KPI + таблица всех моделей из MLflow |
| **Deploy** | Pre-deploy, Deploy, (MLSecOps) Одобрить + Deploy, Архив |
| **Паспорт** | Редактирование model card → сохранение в MLflow |
| **Pipeline** | История гейтов (что упало и когда) |
| **Findings** | Уязвимости и блокировки |
| **Помощь** | Шпаргалка команд |

### Дополнительно для MLSecOps

| Вкладка | Назначение |
|---------|------------|
| **Аудит** | Кто что делал |
| **Цепочка** | Проверка hash-chain |

### Что намеренно НЕ в UI

| Действие | Где |
|----------|-----|
| Запуск pipeline / train | Терминал: `fortress.ps1 pipeline` |
| Регистрация новой модели в MLflow | MLflow UI :5000 |
| Обучение с нуля | CI или MLflow experiments |

**Почему:** pipeline = воспроизводимый CI, не кнопка в браузере без audit trail в контейнере.

### Sidebar

- Ссылки: MLflow, M1/M2/M3 API
- Шпаргалка: `fortress.ps1 up` / `pipeline`
- Без лишних строк про роли — только имя пользователя

---

## 7. Сценарии работы

### 7.1 Data Scientist — CI-модель

1. `.\fortress.ps1 up`
2. Обучение в MLflow (эксперимент / run) или `.\fortress.ps1 pipeline`
3. **FORTRESS UI** (роль `ds`) → вкладки:
   - **Мои модели** — только ваши модели (`owner`), статус гейтов и подписи
   - **Паспорт** — выбор эксперимента → run → версия; метрики и `artifact_uri` подтягиваются из MLflow
   - **Проверки** — почему не прошёл гейт (по-русски) + фрагмент лога
   - **Подписанные** — модели с `security.signed=true` и датасеты после DATA gate
   - **Deploy** — Pre-deploy → Deploy (CI-модели без MLSecOps)
4. MLflow — те же теги `security.*`, что видны в UI

### 7.2 Data Scientist — внешняя модель (Opus 4.8)

1. Зарегистрировать в MLflow
2. Тег `security.origin=external`
3. Заполнить паспорт (вкладка Паспорт)
4. Дождаться review / MLSecOps → Одобрить + Deploy

### 7.3 MLSecOps

1. Обзор — «Ждут одобрения», Findings
2. Deploy — очередь external
3. При инциденте — Pipeline (детали) + Findings (gate, severity)

### 7.4 Первый запуск с нуля

```powershell
Copy-Item .env.example .env
.\fortress.ps1 up
# подождать Keycloak (~1 мин)
```

1. Открыть http://localhost:8502 → вкладка **Регистрация**
2. Логин, email, пароль, **выбор роли** (ds или mlsecops)
3. **Войти** — тот же логин в **MLflow** http://localhost:5000 (Keycloak SSO)

Первый пользователь создаётся через **Регистрация** в FORTRESS UI:
- логин нормализуется в нижний регистр (`Rina` → `rina`);
- после регистрации вход выполняется автоматически;
- регистрация проверяет password grant в Keycloak до сообщения об успехе.

---

## 8. Регистрация и роли

| Компонент | Как |
|-----------|-----|
| **Регистрация** | Security Center → Регистрация → Keycloak Admin API |
| **Вход FORTRESS** | Keycloak password grant (клиент `fortress-ui`) |
| **Вход MLflow** | http://localhost:5000 → Keycloak SSO (клиент `mlflow-oauth`, роли `ds` / `mlsecops`) |
| **Роль** | Пользователь выбирает при регистрации (пилот); в проде — назначает админ |

| Роль | Возможности |
|------|-------------|
| **ds** | Мои модели, паспорт из MLflow run, проверки с логами, подписанные артефакты, deploy CI, findings |
| **mlsecops** | Мониторинг, одобрение external-моделей, архив, аудит, цепочка |

Keycloak: http://localhost:8080 · realm `mlsecops`

### MLflow по ролям

| Роль | MLflow UI (http://localhost:5000) | FORTRESS |
|------|-----------------------------------|----------|
| **ds** | SSO, эксперименты, runs, артефакты, реестр моделей | «Мои модели» — фильтр по `owner` |
| **mlsecops** | SSO, полный реестр и эксперименты | Обзор всех моделей, одобрение external |

При `fortress.ps1 up` автоматически создаётся клиент `mlflow-oauth` (сервис `keycloak-bootstrap`).

---

## 9. Ошибки — где смотреть

| Симптом | Где |
|---------|-----|
| Pipeline упал | Терминал + вкладка **Проверки** (ds) или **Pipeline** (mlsecops) |
| MLflow «Client not found» | `.\fortress.ps1 bootstrap` или `docker compose up keycloak-bootstrap` |
| Уязвимость / poison | Findings + `security.last_failure` в MLflow |
| Deploy заблокирован | Deploy — красный текст + missing gates |
| Attestation нет | `fortress.ps1 pipeline` не завершился |

---

## 10. Перспектива доработок

| Направление | Зачем | Сложность |
|-------------|-------|-----------|
| **Webhook pipeline из UI** | Кнопка «Запустить CI» → вызов API/compose | Средняя |
| **Динамический CI_MODEL_REGISTRY** | Новые модели без правки кода — конфиг в MLflow/YAML | Средняя |
| **Dataset tags в MLflow** | DATA gate → тег на dataset run, не ingest в Postgres | Низкая |
| **G11 Trivy в deploy** | Скан образа при каждом deploy (частично в `deploy_precheck`) | Низкая |
| **Полный Giskard / Garak** | Deep scan вместо holdout/live probes | Средняя |
| **Уведомления** | Slack/email при failed gate | Средняя |
| **Multi-tenant owner** | Фильтр моделей по команде в MLflow | Высокая |

**Уже сделано:** oauth2-proxy перед MLflow (`oauth2-proxy-mlflow`, SSO через Keycloak).  
Приоритет для продакшена: webhook pipeline, конфиг реестра CI-моделей, полные offline-сканеры.

---

## 11. Связанные документы

| Документ | Содержание |
|----------|------------|
| [RUN.md](./RUN.md) | Команды Docker |
| [ci.md](./ci.md) | GitHub Actions |
| [threat_model.md](./threat_model.md) | Угрозы |
| [architecture_full.md](./architecture_full.md) | Диаграммы |
| [ТЗ.md](../ТЗ.md) | Исходное ТЗ |

---

## 12. Репозиторий

https://github.com/Ermakov764/Alfa_bank_MLSecOps

Ключевые entry points:

- `fortress.ps1` — хост
- `scripts/ci/run_pipeline.py` — CI
- `dashboard/streamlit_app.py` — UI
- `fortress/registry_policy.py` — политика CI/external
