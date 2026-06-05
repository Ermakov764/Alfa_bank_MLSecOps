#!/usr/bin/env bash
set -euo pipefail
cd /app
/app/scripts/fortress/wait-services.sh
python models/m1_scoring/train.py
python models/m2_antifraud/train.py
python models/m3_nlp/train.py

# G7 manifests — required for API SHA verify on startup
for art in \
  models/m1_scoring/artifact/onnx/model.onnx \
  artifacts/models/m2_antifraud/onnx/model.onnx \
  models/m3_nlp/artifact/intent_pipeline.joblib; do
  if [ -f "$art" ]; then
    SIGNING_STRICT="${SIGNING_STRICT:-true}" python scripts/gates/g7_sign_manifest.py "$art"
  fi
done
echo "==> Train complete (artifacts signed)"
