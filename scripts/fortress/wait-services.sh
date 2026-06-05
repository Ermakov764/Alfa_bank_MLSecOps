#!/usr/bin/env bash
set -euo pipefail
echo "==> Waiting for Postgres..."
for i in $(seq 1 30); do
  if pg_isready -h postgres -U "${POSTGRES_USER:-mlsecops}" -q 2>/dev/null; then
    echo "Postgres OK"
    break
  fi
  sleep 2
done

echo "==> Waiting for MLflow..."
for i in $(seq 1 40); do
  if curl -sf "${MLFLOW_TRACKING_URI}/health" >/dev/null; then
    echo "MLflow OK"
    break
  fi
  sleep 3
done

if [ "${WAIT_LITELLM:-0}" = "1" ]; then
  echo "==> Waiting for LiteLLM (G10)..."
  LITELLM_BASE="${LITELLM_URL:-http://litellm:4000}"
  LITELLM_BASE="${LITELLM_BASE%/chat}"
  for i in $(seq 1 40); do
    if curl -sf "${LITELLM_BASE}/health" >/dev/null 2>&1; then
      echo "LiteLLM OK"
      break
    fi
    if [ "$i" -eq 40 ]; then
      echo "WARN: LiteLLM not ready — G10 may fail (docker compose up -d litellm)" >&2
    fi
    sleep 2
  done
fi

if [ "${WAIT_KEYCLOAK:-0}" = "1" ]; then
  echo "==> Waiting for Keycloak (optional)..."
  for i in $(seq 1 30); do
    if curl -sf "${KEYCLOAK_URL:-http://keycloak:8080}/health/ready" >/dev/null 2>&1; then
      echo "Keycloak OK"
      break
    fi
    sleep 3
  done
fi
