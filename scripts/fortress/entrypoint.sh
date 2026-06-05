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
  all            up → bootstrap → train → pipeline
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
  ci-gate-data)
    exec bash /app/scripts/ci/gate_data.sh
    ;;
  ci-gate-code)
    exec bash /app/scripts/ci/gate_code.sh
    ;;
  ci-gate-artifacts)
    for mk in m1 m2 m3; do
      if [ "$mk" = "m2" ]; then
        MODEL_KEY=m2 ARTIFACT_DIR=/app/artifacts/models/m2_antifraud bash /app/scripts/ci/gate_artifacts.sh
      else
        MODEL_KEY="$mk" bash /app/scripts/ci/gate_artifacts.sh
      fi
    done
    ;;
  ci-gate-model)
    export WAIT_LITELLM=1
    /app/scripts/fortress/wait-services.sh
    python /app/tests/fixtures/malicious/create_evil_pickle.py
    for mk in m1 m2 m3; do
      MODEL_KEY="$mk" bash /app/scripts/ci/gate_model.sh
    done
    bash /app/gates/modelaudit.sh /app/tests/fixtures/malicious/evil_model.pkl && exit 1 \
      || echo "G5 correctly blocked evil pickle"
    ;;
  ci-sign)
    exec python /app/scripts/ci/sign_attestation.py \
      --run-id "${RUN_ID:-local}" \
      --model all \
      --model-key all \
      --correlation-id "${CORRELATION_ID:-local}" \
      --strict
    ;;
  demo)
    exec /app/scripts/fortress/demo.sh "$@"
    ;;
  test)
    exec python -m pytest tests/test_smoke.py tests/test_attestation.py tests/test_gate_integrity.py -q "$@"
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
