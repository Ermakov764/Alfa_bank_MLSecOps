#!/usr/bin/env bash
# Deprecated: use bin/fortress demo  or  docker compose run fortress demo
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec docker compose --profile tools run --rm fortress demo
