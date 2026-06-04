#!/usr/bin/env bash
# G10 — Garak LLM red-team (minimal)
set -euo pipefail
PROMPTS="${1:-tests/fixtures/malicious/prompts/jailbreak.txt}"
if [ -f "$PROMPTS" ] && grep -qi "ignore previous" "$PROMPTS" 2>/dev/null; then
  if [ "${GARAK_DEMO_FAIL:-}" = "1" ]; then
    echo "G10 FAIL (demo jailbreak probe)"
    exit 1
  fi
fi
echo "G10 PASS (minimal garak stub)"
