#!/usr/bin/env bash
# Element 4: Model gates G5 G8 G9 (m1/m2) or G10 (m3)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
RUN_ID="${RUN_ID:-local}"
CORR="${CORRELATION_ID:-local}"
MODEL_KEY="${MODEL_KEY:-m1}"
chmod +x gates/*.sh

report() {
  "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element model \
    --gate "$1" --status "$2" --correlation-id "$CORR" --message "${3:-}"
}

if [ "$MODEL_KEY" = "m3" ]; then
  docker compose up -d litellm 2>/dev/null || true
  sleep 3
  report G10 started
  if ! "$PYTHON" scripts/gates/g10_llm_probe.py --url "${LITELLM_URL:-http://litellm:4000/chat}"; then
    report G10 failed "G10 LLM probe — service must be up"
    exit 1
  fi
  report G10 passed
  JOB="${M3_MODEL_PATH:-models/m3_nlp/artifact/intent_pipeline.joblib}"
  report G5 started
  if [ ! -f "$JOB" ]; then
    report G5 failed "M3 artifact missing"
    exit 1
  fi
  export GATE_STRICT="${GATE_STRICT:-true}"
  if ! gates/modelaudit.sh "$JOB"; then
    report G5 failed "G5 model scan (M3 joblib)"
    exit 1
  fi
  report G5 passed
  echo "gate-model: PASS (m3)"
  exit 0
fi

if [ "$MODEL_KEY" = "m2" ]; then
  ONNX="${ONNX_PATH:-artifacts/models/m2_antifraud/onnx/model.onnx}"
else
  ONNX="${ONNX_PATH:-models/m1_scoring/artifact/onnx/model.onnx}"
fi

export GATE_STRICT="${GATE_STRICT:-true}"
report G5 started
if ! gates/modelaudit.sh "$ONNX"; then
  report G5 failed "G5 model scan"
  exit 1
fi
report G5 passed

report G8 started
if ! "$PYTHON" scripts/gates/g8_validate.py "$MODEL_KEY"; then
  report G8 failed "G8 validation"
  exit 1
fi
report G8 passed

report G9 started
if ! "$PYTHON" scripts/gates/g9_art.py "$MODEL_KEY"; then
  report G9 failed "G9 adversarial"
  exit 1
fi
report G9 passed
echo "gate-model: PASS ($MODEL_KEY)"
