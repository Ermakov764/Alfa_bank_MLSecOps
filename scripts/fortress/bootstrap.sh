#!/usr/bin/env bash
set -euo pipefail
cd /app
mkdir -p artifacts/attestation artifacts/gates

/app/scripts/fortress/wait-services.sh

if [ -f infra/migrations/002_pipeline_runs.sql ]; then
  echo "==> Apply DB migrations..."
  PGPASSWORD="${POSTGRES_PASSWORD:-changeme}" psql -h postgres -U "${POSTGRES_USER:-mlsecops}" \
    -d "${POSTGRES_DB:-mlsecops}" -f infra/migrations/002_pipeline_runs.sql 2>/dev/null || true
fi

python - <<'PY'
import os, sys
sys.path.insert(0, "/app")
from fortress.mlflow_client import ensure_experiment
for name in ("m1-credit-scoring", "m2-antifraud", "m3-support-nlp", "fortress-default"):
    print(f"experiment {name}: {ensure_experiment(name)}")
PY

echo "==> Bootstrap complete"
