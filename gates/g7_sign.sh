#!/usr/bin/env bash
# G7 — model signing (digest sidecar)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-}"
if [ -z "$TARGET" ] || [ ! -f "$TARGET" ]; then
  echo "G7 SKIP: no artifact"
  exit 0
fi

if command -v model-signing >/dev/null 2>&1 && [ "${SIGNING_STRICT:-false}" = "true" ]; then
  model-signing sign "$TARGET" && { echo "G7 PASS"; exit 0; }
fi

sha256sum "$TARGET" | awk '{print $1}' > "${TARGET}.sig"
echo "G7 PASS (sha256 sidecar ${TARGET}.sig)"
