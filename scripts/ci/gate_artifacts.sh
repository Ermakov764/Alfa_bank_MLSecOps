#!/usr/bin/env bash
# Element 3: Artifact format G6 (+ G7 manifest prep)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
RUN_ID="${RUN_ID:-local}"
CORR="${CORRELATION_ID:-local}"
MODEL_KEY="${MODEL_KEY:-m1}"

if [ "$MODEL_KEY" = "m2" ]; then
  ART_DIR="${ARTIFACT_DIR:-artifacts/models/m2_antifraud}"
elif [ "$MODEL_KEY" = "m3" ]; then
  ART_DIR="${ARTIFACT_DIR:-models/m3_nlp/artifact}"
else
  ART_DIR="${ARTIFACT_DIR:-models/m1_scoring/artifact}"
fi

report() {
  "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element artifacts \
    --gate "$1" --status "$2" --correlation-id "$CORR" --message "${3:-}"
}

report G6 started
if ! "$PYTHON" scripts/check_format_policy.py "$ART_DIR"; then
  report G6 failed "G6 format policy"
  exit 1
fi
report G6 passed

ONNX=$(find "$ART_DIR" -name '*.onnx' | head -1)
if [ -n "$ONNX" ]; then
  report G7 started
  if ! "$PYTHON" scripts/gates/g7_sign_manifest.py "$ONNX"; then
    report G7 failed "G7 manifest"
    exit 1
  fi
  report G7 passed
fi
echo "gate-artifacts: PASS"
