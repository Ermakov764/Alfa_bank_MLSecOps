# Alfa Bank MLSecOps — FORTRESS

Безопасная MLOps-платформа для кейса «ИБАНК»: MLflow registry, Security Gates **G0–G15**, pre-train **DATA** gate, audit hash-chain, 3 ML-модели, Streamlit Security Center.

Документация: [ТЗ.md](./ТЗ.md) · [ПЛАН_РЕАЛИЗАЦИИ.md](./ПЛАН_РЕАЛИЗАЦИИ.md) · [docs/RUN.md](./docs/RUN.md) · [docs/threat_model.md](./docs/threat_model.md)

## Quickstart (Docker only)

**Windows:**

```powershell
Copy-Item .env.example .env
.\fortress.ps1 all
```

**Linux / macOS:**

```bash
cp .env.example .env
chmod +x bin/fortress && ./bin/fortress all
```

**Make** (вызывает те же контейнеры):

```bash
make all
```

Откройте:

- Streamlit: http://localhost:8502  
- MLflow: http://localhost:5000  
- M1 API: http://localhost:8001/docs  
- M2 API: http://localhost:8002/docs  
- M3 NLP: http://localhost:4000/health  

## Команды `fortress`

| Команда | Описание |
|---------|----------|
| `up` / `down` | поднять / остановить compose-стек |
| `bootstrap` | Postgres + MLflow init |
| `train` | M1 + M2 + M3 |
| `pipeline` | gates → train → sign attestation |
| `demo` | сценарии A–E |
| `test` | pytest |
| `gates` | G0–G11 (env `PROFILE=strict`) |

Подробнее: [docs/RUN.md](./docs/RUN.md)

## Структура

| Путь | Назначение |
|------|------------|
| `fortress.ps1` / `bin/fortress` | единая точка входа (хост → Docker) |
| `infra/docker/Dockerfile.fortress` | образ CLI: train, gates, demo |
| `fortress/` | Python: audit, attestation, security_profile |
| `gates/` | G0, G1, G3, G3b, G5–G11 |
| `scripts/fortress/` | сценарии внутри контейнера |
| `services/` | FastAPI + LiteLLM |
| `docker-compose.yml` | postgres, minio, mlflow, APIs, dashboard |

## Роли (Keycloak realm `mlsecops`)

| User | Role | Password (dev) |
|------|------|----------------|
| ds1 | ds | ds1pass |
| mlsecops1 | mlsecops | mlsecops1pass |

**Plan B:** `ACTOR_ROLE=mlsecops` в promote, если Keycloak не поднят.

## CI

GitHub Actions: [.github/workflows/ci-pipeline.yml](./.github/workflows/ci-pipeline.yml) — те же шаги, что `fortress pipeline` / gate-образы.
