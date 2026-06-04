#!/usr/bin/env bash
# G8 — tabular ML validation (holdout + optional Giskard)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${1:-m1}"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" "$ROOT/scripts/gates/g8_validate.py" "$MODEL"
