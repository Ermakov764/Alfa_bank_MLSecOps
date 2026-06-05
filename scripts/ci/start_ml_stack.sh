#!/usr/bin/env bash
# Start Postgres-backed MLflow for GitHub Actions train job (prod-like, no MinIO).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-mlsecops}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-changeme}"
POSTGRES_DB="${POSTGRES_DB:-mlsecops}"
MLFLOW_PORT="${MLFLOW_PORT:-5000}"
MLFLOW_HOST="${MLFLOW_HOST:-127.0.0.1}"
ARTIFACT_ROOT="${MLFLOW_DEFAULT_ARTIFACT_ROOT:-file:///tmp/mlflow-artifacts}"

export MLFLOW_BACKEND_STORE_URI="${MLFLOW_BACKEND_STORE_URI:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}}"
export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://${MLFLOW_HOST}:${MLFLOW_PORT}}"
export DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}}"

echo "==> Wait for Postgres at ${POSTGRES_HOST}..."
for i in $(seq 1 60); do
  if PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    echo "Postgres ready"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "Postgres not ready" >&2
    exit 1
  fi
  sleep 2
done

echo "==> Apply platform schema..."
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f infra/init.sql

if [ -f infra/migrations/002_pipeline_runs.sql ]; then
  PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -f infra/migrations/002_pipeline_runs.sql 2>/dev/null || true
fi

mkdir -p /tmp/mlflow-artifacts

echo "==> Start MLflow server (backend=Postgres, artifacts=file)..."
nohup mlflow server \
  --host "$MLFLOW_HOST" \
  --port "$MLFLOW_PORT" \
  --backend-store-uri "$MLFLOW_BACKEND_STORE_URI" \
  --default-artifact-root "$ARTIFACT_ROOT" \
  --serve-artifacts \
  > /tmp/mlflow.log 2>&1 &
echo $! > /tmp/mlflow.pid

for i in $(seq 1 30); do
  if curl -sf "http://${MLFLOW_HOST}:${MLFLOW_PORT}/health" >/dev/null; then
    echo "MLflow ready at ${MLFLOW_TRACKING_URI}"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "MLflow failed to start:" >&2
    cat /tmp/mlflow.log >&2 || true
    exit 1
  fi
  sleep 2
done

python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from fortress.mlflow_client import ensure_experiment
for name in ("m1-credit-scoring", "m2-antifraud", "m3-support-nlp", "fortress-default"):
    print(f"experiment {name}: {ensure_experiment(name)}")
PY

echo "==> ML stack ready"
