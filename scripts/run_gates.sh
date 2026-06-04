#!/usr/bin/env bash
# Run security gates with audit logging
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export ARTIFACTS_DIR="${ARTIFACTS_DIR:-$ROOT/artifacts}"

PYTHON="${PYTHON:-python3}"
PROFILE="${PROFILE:-fast}"
MODEL="${MODEL:-m1}"
PHASE="${PHASE:-ci}"
ACTOR="${ACTOR:-ds1}"

FAILED=0
CORR=$("$PYTHON" -c "import uuid; print(uuid.uuid4())")

log_gate() {
  local gate="$1" status="$2"
  "$PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT')
from fortress.audit import log_event
log_event('$ACTOR', 'gate.${status}', resource_type='gate', resource_id='$gate',
          status='${status}', correlation_id='$CORR')
"
}

run_gate() {
  local id="$1" cmd="$2"
  log_gate "$id" "started"
  if eval "$cmd"; then
    log_gate "$id" "passed"
    "$PYTHON" -c "
import sys; sys.path.insert(0,'$ROOT')
from fortress.mlflow_client import set_security_tag
import os
mn=os.getenv('MLFLOW_MODEL_NAME','')
ver=os.getenv('MLFLOW_MODEL_VERSION','')
if mn and ver:
    set_security_tag(mn, ver, '${id#G}', 'passed')
" 2>/dev/null || true
    echo "[$id] PASS"
  else
    log_gate "$id" "failed"
    "$PYTHON" -c "
import sys; sys.path.insert(0,'$ROOT')
from fortress.audit import log_finding
log_finding('$id', 'code', '$id', 'gate_failed', severity='high', correlation_id='$CORR')
" || true
    echo "[$id] FAIL"
    FAILED=1
  fi
}

chmod +x gates/*.sh 2>/dev/null || true

if [ "$PHASE" = "ci" ] || [ "$PROFILE" = "fast" ] || [ "$PROFILE" = "strict" ]; then
  run_gate "G0" "gates/gitleaks.sh"
  run_gate "G1" "gates/semgrep.sh"
  run_gate "G3" "gates/pip_audit.sh"
  run_gate "G3b" "gates/guarddog.sh"
fi

if [ "$PROFILE" = "fast" ] || [ "$PROFILE" = "strict" ]; then
  TARGET="${G5_TARGET:-tests/fixtures/malicious/evil_model.pkl}"
  if [ "${G5_EXPECT_PASS:-}" = "1" ]; then
    TARGET="${G5_TARGET:-models/m1_scoring/artifact/onnx/model.onnx}"
  fi
  if [ -f "$TARGET" ]; then
    run_gate "G5" "gates/modelaudit.sh '$TARGET'"
  else
    run_gate "G5" "gates/modelaudit.sh models/m1_scoring/artifact/onnx/model.onnx"
  fi
fi

if [ "$PROFILE" = "strict" ]; then
  run_gate "G6" "$PYTHON scripts/check_format_policy.py models/m1_scoring/artifact"
  run_gate "G6" "$PYTHON scripts/check_format_policy.py artifacts/models/m2_antifraud"
  ART="${G7_ARTIFACT:-models/m1_scoring/artifact/onnx/model.onnx}"
  for art in \
    models/m1_scoring/artifact/onnx/model.onnx \
    artifacts/models/m2_antifraud/onnx/model.onnx; do
    if [ -f "$art" ]; then
      run_gate "G7" "gates/g7_sign.sh '$art'"
    fi
  done
  if [ "$MODEL" = "m3" ]; then
    run_gate "G10" "gates/g10_garak.sh"
  else
    run_gate "G8" "gates/g8_giskard.sh m1"
    run_gate "G9" "gates/g9_art.sh m1"
    run_gate "G8" "gates/g8_giskard.sh m2"
    run_gate "G9" "gates/g9_art.sh m2"
  fi
  run_gate "G11" "gates/g11_trivy.sh"
fi

if [ "$FAILED" -eq 1 ]; then
  echo "Gates summary: FAILED"
  exit 1
fi
echo "Gates summary: OK"
exit 0
