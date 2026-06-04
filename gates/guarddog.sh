#!/usr/bin/env bash
# G3b — typosquat / malicious PyPI metadata
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FIXTURE="$ROOT/tests/fixtures/malicious/requirements-typosquat.txt"
if [ -f "$FIXTURE" ] && [ "${GUARDDOG_SCAN_TARGET:-}" = "$FIXTURE" ]; then
  if grep -qi pytirch "$FIXTURE"; then
    echo "G3b FAIL: typosquat detected (demo)"
    exit 1
  fi
fi

if command -v guarddog >/dev/null 2>&1; then
  guarddog pypi scan -r requirements.txt && { echo "G3b PASS"; exit 0; }
fi

python3 - <<'PY'
import sys
from pathlib import Path
req = Path("requirements.txt").read_text().lower()
typos = ["pytirch", "tenserflew", "scikit-learnn"]
found = [t for t in typos if t in req]
if found:
    print("G3b FAIL:", found)
    sys.exit(1)
print("G3b PASS (fallback)")
PY
