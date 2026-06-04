#!/usr/bin/env bash
# Pre-deploy: re-verify code, Trivy, attestation signatures
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PYTHON="${PYTHON:-python3}"
ATTEST="${ATTESTATION_PATH:-artifacts/attestation/fortress-attestation.signed.json}"

echo "=== Pre-deploy checks ==="

bash scripts/ci/gate_code.sh

if [ -f "$ATTEST" ]; then
  if ! "$PYTHON" -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
from fortress.attestation import load_signed, verify_attestation
signed = load_signed(Path('$ATTEST'))
ok, msg = verify_attestation(signed)
print('attestation:', ok, msg)
sys.exit(0 if ok else 1)
"; then
    echo "FAIL: attestation signature invalid"
    exit 1
  fi
else
  echo "FAIL: attestation file missing"
  exit 1
fi

chmod +x gates/g11_trivy.sh
if ! bash gates/g11_trivy.sh; then
  echo "FAIL: G11 Trivy"
  exit 1
fi

echo "=== Pre-deploy PASS ==="
