#!/usr/bin/env bash
# G10 — LLM red-team live probes (+ Garak CLI if installed)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" "$ROOT/scripts/gates/g10_llm_probe.py" "$@"
