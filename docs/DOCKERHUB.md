# Docker Hub — rinakt

Образы публикуются в namespace **[rinakt](https://hub.docker.com/u/rinakt)**.

## Репозитории

| Образ | Pull | Страница |
|-------|------|----------|
| CLI / train / demo | `docker pull rinakt/mlsecops-fortress:latest` | https://hub.docker.com/r/rinakt/mlsecops-fortress |
| MLflow | `docker pull rinakt/mlsecops-mlflow:latest` | https://hub.docker.com/r/rinakt/mlsecops-mlflow |
| M1 API | `docker pull rinakt/mlsecops-api-scoring:latest` | https://hub.docker.com/r/rinakt/mlsecops-api-scoring |
| M2 API | `docker pull rinakt/mlsecops-api-antifraud:latest` | https://hub.docker.com/r/rinakt/mlsecops-api-antifraud |
| M3 LiteLLM | `docker pull rinakt/mlsecops-litellm:latest` | https://hub.docker.com/r/rinakt/mlsecops-litellm |
| Dashboard | `docker pull rinakt/mlsecops-dashboard:latest` | https://hub.docker.com/r/rinakt/mlsecops-dashboard |

Профиль: https://hub.docker.com/u/rinakt  
Список репозиториев: https://hub.docker.com/repositories/rinakt

## Сборка и push с вашей машины

1. Запустите **Docker Desktop**.
2. Войдите в Hub:

```powershell
docker login -u rinakt
```

3. Соберите и отправьте:

```powershell
.\scripts\push-dockerhub.ps1
# или с тегом релиза:
.\scripts\push-dockerhub.ps1 -Tag v1.0.0
```

## CI (GitHub Actions)

Workflow `.github/workflows/docker-publish.yml` — push по тегу `v*` или вручную (*workflow_dispatch*).

Secrets в репозитории:

- `DOCKERHUB_USERNAME` = `rinakt`
- `DOCKERHUB_TOKEN` — Access Token из https://hub.docker.com/settings/security

## Запуск только из Hub (без локальной сборки)

В `.env`:

```
DOCKERHUB_USER=rinakt
IMAGE_TAG=latest
```

```powershell
docker compose pull
docker compose up -d
```
