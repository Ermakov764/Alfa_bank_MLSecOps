#!/usr/bin/env bash
# G1 — SAST ML patterns (offline: vendored Trail of Bits rules in gates/semgrep-rules/)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"

STRICT="${GATE_STRICT:-false}"
RULES="${SEMGREP_RULES:-$ROOT/gates/semgrep-rules}"
TARGETS="${SEMGREP_TARGETS:-fortress services dashboard models scripts}"

if command -v semgrep >/dev/null 2>&1; then
  if [ ! -d "$RULES" ] || [ -z "$(find "$RULES" -name '*.yaml' -o -name '*.yml' 2>/dev/null | head -1)" ]; then
    echo "G1 FAIL: local semgrep rules missing at $RULES"
    exit 1
  fi
  export SEMGREP_SEND_METRICS=off
  export SEMGREP_ENABLE_VERSION_CHECK=0
  semgrep scan \
    --config "$RULES" \
    --error \
    --metrics=off \
    --json -o "$OUT/semgrep.json" \
    $TARGETS
  echo "G1 PASS (semgrep, local rules)"
  exit 0
fi

if [ "$STRICT" = "true" ]; then
  echo "G1 FAIL: semgrep required in GATE_STRICT mode"
  exit 1
fi

python3 - <<'PY'
import re, sys
from pathlib import Path
danger = re.compile(r"pickle\.loads?\(", re.I)
bad = []
for p in Path("services").rglob("*.py"):
    if danger.search(p.read_text(errors="ignore")):
        bad.append(str(p))
if bad:
    print("G1 FAIL: pickle.loads in services", bad)
    sys.exit(1)
print("G1 PASS (fallback — no pickle.loads in services)")
PY
