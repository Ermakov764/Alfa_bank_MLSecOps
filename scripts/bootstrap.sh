#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://mlsecops:changeme@localhost:5432/mlsecops}"
export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://localhost:5000}"

echo "==> Waiting for Postgres..."
for i in $(seq 1 30); do
  if "$PYTHON" -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null; then
    break
  fi
  sleep 2
done

echo "==> Waiting for MLflow..."
for i in $(seq 1 40); do
  if curl -sf "${MLFLOW_TRACKING_URI}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

echo "==> Waiting for Keycloak (optional)..."
for i in $(seq 1 30); do
  if curl -sf "${KEYCLOAK_URL:-http://localhost:8080}/health/ready" >/dev/null 2>&1; then
    echo "Keycloak ready"
    break
  fi
  sleep 3
done

"$PYTHON" - <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from fortress.mlflow_client import ensure_experiment
for name in ("m1-credit-scoring", "m2-antifraud", "m3-support-nlp", "fortress-default"):
    eid = ensure_experiment(name)
    print(f"experiment {name}: {eid}")
PY

echo "==> Bootstrap complete"
echo "Users (Keycloak realm mlsecops): ds1, mlsecops1, de1, ceo"
echo "Plan B: set ACTOR_ROLE=mlsecops for promote if Keycloak unavailable"
