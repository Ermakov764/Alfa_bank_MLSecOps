#!/usr/bin/env bash
# Platform pipeline: DATA (optional) → code gates → sign attestation
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHON="${PYTHON:-python3}"
export PYTHONPATH=.
export GATE_STRICT=true
export RUN_ID="${RUN_ID:-local-$(date +%s)}"
export CORRELATION_ID="${CORRELATION_ID:-$(python3 -c 'import uuid;print(uuid.uuid4())')}"

echo "=== FORTRESS platform pipeline ==="

if [ "${PIPELINE_SKIP_DATA:-}" != "1" ] && [ -f "${PIPELINE_DATASET_CSV:-data/datasets/train_clean.csv}" ]; then
  echo "--- DATA ---"
  "$PYTHON" scripts/ingest_dataset.py "${PIPELINE_DATASET_CSV:-data/datasets/train_clean.csv}" \
    --name "${PIPELINE_DATASET_NAME:-pipeline_dataset}" \
    --version "${PIPELINE_DATASET_VERSION:-v1}" \
    --actor "${PIPELINE_ACTOR:-ci}" \
    ${PIPELINE_EXPECTED_COLS:+--expected-cols "$PIPELINE_EXPECTED_COLS"}
  "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element data --gate DATA --status passed \
    --correlation-id "$CORRELATION_ID"
fi

echo "--- CODE ---"
bash scripts/ci/gate_code.sh

echo "--- SIGN ---"
"$PYTHON" scripts/ci/sign_attestation.py --run-id "$RUN_ID" --model platform \
  --correlation-id "$CORRELATION_ID" --strict

echo "=== Pipeline OK ==="
