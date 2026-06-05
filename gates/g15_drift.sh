#!/usr/bin/env bash
# G15 — Evidently drift PSI + metric degradation
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${1:-m1}"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" "$ROOT/scripts/gates/g15_drift.py" "$MODEL"
