#!/usr/bin/env bash
# Element 1: DATA gate (fail-fast)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
RUN_ID="${RUN_ID:-local}"
CORR="${CORRELATION_ID:-$(uuidgen 2>/dev/null || $PYTHON -c 'import uuid;print(uuid.uuid4())')}"
DATASET="${DATASET_PATH:-data/datasets/train_clean.csv}"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates/data_report.json"

report() {
  "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element data \
    --gate DATA --status "$1" --correlation-id "$CORR" --report "$OUT" --message "${2:-}"
}

report started "DATA gate"
mkdir -p "$(dirname "$OUT")"

if ! "$PYTHON" scripts/data_gate.py "$DATASET" --expected-cols amount,age,target --actor ci; then
  report failed "DATA gate failed"
  exit 1
fi

"$PYTHON" -c "
import hashlib, json
from pathlib import Path
p = Path('$DATASET')
h = hashlib.sha256(p.read_bytes()).hexdigest()
json.dump({'gate':'DATA','digest':h,'path':str(p)}, open('$OUT','w'), indent=2)
"
report passed "DATA gate OK"
echo "gate-data: PASS"
