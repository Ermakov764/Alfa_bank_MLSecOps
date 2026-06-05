#!/usr/bin/env bash
set -euo pipefail
cd /app
export PYTHONPATH=/app
mkdir -p artifacts/attestation artifacts/gates

cmd="${1:-help}"
shift || true

case "$cmd" in
  help|-h|--help)
    cat <<'EOF'
FORTRESS CLI (runs inside Docker — same on Linux/macOS/Windows)

  bootstrap      DB migrations + MLflow experiments
  train          Train M1, M2, M3
  pipeline       CI: DATA → code → train → artifacts → sign
  demo           Full demo (bootstrap + pipeline + register + API checks)
  test           pytest smoke + attestation
  gates          Security gates (PROFILE=fast|strict MODEL=m1)
  deploy         Promote internal model to Production (MODEL VERSION ACTOR)
  deploy-precheck  Verify attestation + G12 before deploy
  ingest         Ingest dataset: ingest FILE --name N --version V ...
  shell          Interactive bash
  wait           Wait for postgres + mlflow

Host only (./fortress or fortress.ps1):
  up             docker compose up -d --build
  down           docker compose down
  ps|logs        docker compose ps / logs
  all            up → bootstrap → train → demo
EOF
    ;;
  bootstrap)
    exec /app/scripts/fortress/bootstrap.sh "$@"
    ;;
  train|train-all)
    exec /app/scripts/fortress/train-all.sh "$@"
    ;;
  pipeline|ci-pipeline)
    export WAIT_LITELLM=1
    /app/scripts/fortress/wait-services.sh
    exec python /app/scripts/ci/run_pipeline.py "$@"
    ;;
  demo)
    exec /app/scripts/fortress/demo.sh "$@"
    ;;
  test)
    exec python -m pytest tests/test_smoke.py tests/test_attestation.py -q "$@"
    ;;
  gates|security)
    export PROFILE="${PROFILE:-fast}"
    export MODEL="${MODEL:-m1}"
    if [ -x /app/scripts/run_gates.sh ]; then
      exec bash /app/scripts/run_gates.sh "$@"
    fi
    exec python /app/scripts/ci/run_pipeline.py
    ;;
  ingest)
    /app/scripts/fortress/wait-services.sh
    exec python /app/scripts/ingest_dataset.py "$@"
    ;;
  wait)
    exec /app/scripts/fortress/wait-services.sh "$@"
    ;;
  deploy)
    exec /app/scripts/fortress/deploy.sh "$@"
    ;;
  deploy-precheck)
    exec python /app/scripts/ci/deploy_precheck.py "$@"
    ;;
  shell|bash)
    exec bash "$@"
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    echo "Run: fortress help" >&2
    exit 1
    ;;
esac
