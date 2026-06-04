#!/usr/bin/env bash
# Element 2: Code gates G0 G1 G3 G3b
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
RUN_ID="${RUN_ID:-local}"
CORR="${CORRELATION_ID:-local}"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"
chmod +x gates/*.sh

run_one() {
  local gate="$1" cmd="$2"
  "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element code \
    --gate "$gate" --status started --correlation-id "$CORR" || true
  if eval "$cmd"; then
    "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element code \
      --gate "$gate" --status passed --correlation-id "$CORR" \
      --report "$OUT/${gate}_report.json"
  else
    "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element code \
      --gate "$gate" --status failed --correlation-id "$CORR" --message "$gate failed"
    exit 1
  fi
}

run_one G0 "gates/gitleaks.sh"
run_one G1 "gates/semgrep.sh"
run_one G3 "gates/pip_audit.sh"
run_one G3b "gates/guarddog.sh"
echo "gate-code: PASS"
