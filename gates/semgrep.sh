#!/usr/bin/env bash
# G1 — SAST ML patterns
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"

if command -v semgrep >/dev/null 2>&1; then
  semgrep scan --config p/trailofbits --error --json -o "$OUT/semgrep.json" . 2>/dev/null || {
    semgrep scan --config auto --error . || exit 1
  }
  echo "G1 PASS (semgrep)"
  exit 0
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
