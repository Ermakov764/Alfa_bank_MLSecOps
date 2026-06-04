#!/usr/bin/env bash
# Local/CI pipeline: 4 gates → train → sign attestation
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
RUN_ID="${RUN_ID:-demo-$(date +%s)}"
export RUN_ID
export CORRELATION_ID="${CORRELATION_ID:-$($PYTHON -c 'import uuid;print(uuid.uuid4())')}"
export ARTIFACTS_DIR="${ARTIFACTS_DIR:-$ROOT/artifacts}"
MODEL_KEY="${MODEL_KEY:-m1}"
MODEL_NAME="${MODEL_NAME:-credit-scoring-pd}"

echo "=== FORTRESS Pipeline run_id=$RUN_ID corr=$CORRELATION_ID ==="

chmod +x scripts/ci/*.sh gates/*.sh

bash scripts/ci/gate_data.sh
bash scripts/ci/gate_code.sh

# Train after data+code pass (before artifact/model gates need artifacts)
echo "--- Train ($MODEL_KEY) ---"
case "$MODEL_KEY" in
  m1) "$PYTHON" models/m1_scoring/train.py ;;
  m2) "$PYTHON" models/m2_antifraud/train.py ;;
  m3) "$PYTHON" models/m3_nlp/train.py ;;
  all)
    "$PYTHON" models/m1_scoring/train.py
    "$PYTHON" models/m2_antifraud/train.py
    "$PYTHON" models/m3_nlp/train.py
    ;;
esac
"$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element train \
  --status passed --correlation-id "$CORRELATION_ID" --message "train complete"

if [ "$MODEL_KEY" = "all" ]; then
  for mk in m1 m2 m3; do
    MODEL_KEY="$mk" bash scripts/ci/gate_artifacts.sh
    if [ "$mk" = "m3" ] && ! curl -sf http://localhost:4000/health >/dev/null 2>&1; then
      SKIP_G10_IF_DOWN=1 MODEL_KEY="$mk" bash scripts/ci/gate_model.sh
    else
      MODEL_KEY="$mk" bash scripts/ci/gate_model.sh
    fi
  done
  "$PYTHON" scripts/ci/sign_attestation.py --run-id "$RUN_ID" --model all
else
  bash scripts/ci/gate_artifacts.sh
  bash scripts/ci/gate_model.sh
  "$PYTHON" scripts/ci/sign_attestation.py --run-id "$RUN_ID" --model "$MODEL_NAME" --model-key "$MODEL_KEY"
fi

echo "=== Pipeline OK — attestation signed ==="
