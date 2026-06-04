#!/usr/bin/env bash
# G3 — dependency CVE audit (required in strict mode)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STRICT="${GATE_STRICT:-true}"

_run() {
  if command -v pip-audit >/dev/null 2>&1; then
    pip-audit -r requirements.txt --fail-on high
    return $?
  fi
  python3 -m pip_audit -r requirements.txt --fail-on high
}

if _run; then
  echo "G3 PASS"
  exit 0
fi

if [ "$STRICT" = "true" ]; then
  echo "G3 FAIL: pip-audit found high+ CVEs or pip-audit not installed"
  exit 1
fi
echo "G3 FAIL"
exit 1
