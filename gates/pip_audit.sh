#!/usr/bin/env bash
# G3 — dependency CVE audit (required in strict mode)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STRICT="${GATE_STRICT:-true}"
REQ_FILES="${PIP_AUDIT_REQUIREMENTS:-requirements.txt requirements-llm.txt}"

_run_one() {
  local f="$1"
  [ -f "$f" ] || return 0
  if command -v pip-audit >/dev/null 2>&1; then
    pip-audit -r "$f" || return 1
  else
    python3 -m pip_audit -r "$f" || return 1
  fi
  return 0
}

_run() {
  local ok=0
  for f in $REQ_FILES; do
    if ! _run_one "$f"; then
      ok=1
    fi
  done
  return $ok
}

if _run; then
  echo "G3 PASS"
  exit 0
fi

if [ "$STRICT" = "true" ]; then
  echo "G3 FAIL: pip-audit found vulnerabilities or pip-audit not installed"
  exit 1
fi
echo "G3 FAIL"
exit 1
