#!/usr/bin/env bash
# G7 — SHA256 manifest signing (Sigstore if SIGNING_STRICT=true)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-}"
PYTHON="${PYTHON:-python3}"
if [ -z "$TARGET" ]; then
  echo "G7 FAIL: no artifact path"
  exit 1
fi
exec "$PYTHON" "$ROOT/scripts/gates/g7_sign_manifest.py" "$TARGET"
