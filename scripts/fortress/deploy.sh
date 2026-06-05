#!/usr/bin/env bash
set -euo pipefail
cd /app
MODEL="${1:-credit-scoring-pd}"
VERSION="${2:-1}"
ACTOR="${3:-mlsecops1}"
python - <<PY
import os, sys
sys.path.insert(0, "/app")
from fortress.deploy_runner import deploy_to_production
ok, msg = deploy_to_production("$MODEL", "$VERSION", "$ACTOR", approve=True)
print(msg)
sys.exit(0 if ok else 1)
PY
