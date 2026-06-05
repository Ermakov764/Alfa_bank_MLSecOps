#!/usr/bin/env bash
# G2 — Python SAST (bandit)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"
STRICT="${GATE_STRICT:-false}"

if ! command -v bandit >/dev/null 2>&1; then
  if [ "$STRICT" = "true" ]; then
    echo "G2 FAIL: bandit required in GATE_STRICT mode"
    exit 1
  fi
  echo "G2 SKIP: bandit not installed"
  exit 0
fi

bandit -r fortress services dashboard models scripts/gates \
  -ll -q --format json -o "$OUT/bandit.json" \
  -x '*/tests/*,*/.venv/*,*/artifacts/*' || {
  echo "G2 FAIL: bandit findings"
  exit 1
}
echo "G2 PASS (bandit)"
