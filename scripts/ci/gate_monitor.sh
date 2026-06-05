#!/usr/bin/env bash
# Element 5: G15 production drift monitoring
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
RUN_ID="${RUN_ID:-local}"
CORR="${CORRELATION_ID:-local}"
chmod +x gates/g15_drift.sh

report() {
  "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element model \
    --gate G15 --status "$1" --correlation-id "$CORR" --message "${2:-}"
}

report started "G15 seed telemetry"
"$PYTHON" scripts/ci/seed_inference_telemetry.py

for mk in m1 m2; do
  report started "G15 drift $mk"
  if ! gates/g15_drift.sh "$mk"; then
    report failed "G15 drift failed ($mk)"
    exit 1
  fi
done
report passed
echo "gate-monitor: PASS"
