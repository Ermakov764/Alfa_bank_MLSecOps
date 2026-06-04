#!/usr/bin/env bash
# G9 — ART FGSM adversarial robustness
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${1:-m1}"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" "$ROOT/scripts/gates/g9_art.py" "$MODEL"
