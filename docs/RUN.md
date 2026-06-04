# Запуск FORTRESS (только Docker)

Вся логика (train, gates, pipeline, demo, pytest) выполняется в контейнере **`fortress`**.  
На хосте нужны только **Docker** и одна команда.

## Быстрый старт

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
.\fortress.ps1 all
```

**Linux / macOS / Git Bash:**

```bash
cp .env.example .env
chmod +x bin/fortress
./bin/fortress all
```

Команда `all`: поднять стек → bootstrap → train → demo.

## Команды

| Команда | Действие |
|---------|----------|
| `up` | `docker compose up -d --build` |
| `down` | остановить стек |
| `bootstrap` | миграции БД + эксперименты MLflow |
| `train` | обучить M1/M2/M3 |
| `pipeline` | CI-пайплайн + attestation |
| `demo` | полный демо-сценарий |
| `test` | pytest smoke + attestation |
| `gates` | security gates (`PROFILE=strict`) |
| `ps` / `logs` | статус / логи compose |

Примеры:

```powershell
.\fortress.ps1 up
.\fortress.ps1 bootstrap
.\fortress.ps1 pipeline
.\fortress.ps1 test
```

```bash
make up bootstrap demo    # то же через Makefile → docker
```

## URL (с хоста)

| Сервис | URL |
|--------|-----|
| MLflow | http://localhost:5000 |
| Streamlit | http://localhost:8502 |
| M1 API | http://localhost:8001/docs |
| M2 API | http://localhost:8002/docs |
| M3 | http://localhost:4000/health |
| Keycloak (опционально) | http://localhost:8080 |

## Внутри сети Docker

Скрипты в контейнере используют `postgres`, `mlflow`, `minio`, `api-scoring:8001` — не `localhost`.

## Устаревшие скрипты

`scripts/up.ps1`, `bootstrap.ps1`, `demo.ps1`, `invoke-docker.ps1` перенаправляют на `fortress.ps1`.
