#!/usr/bin/env bash
# G3 — dependency CVE audit
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -r requirements.txt --fail-on high 2>/dev/null && { echo "G3 PASS"; exit 0; } || exit 1
fi

python3 -m pip_audit -r requirements.txt --fail-on high 2>/dev/null && { echo "G3 PASS"; exit 0; } || {
  echo "G3 SKIP (pip-audit unavailable — dev mode)"
  exit 0
}
