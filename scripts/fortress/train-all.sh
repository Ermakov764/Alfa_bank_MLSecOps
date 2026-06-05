#!/usr/bin/env bash
set -euo pipefail
cd /app
/app/scripts/fortress/wait-services.sh
python models/m1_scoring/train.py
python models/m2_antifraud/train.py
python models/m3_nlp/train.py
echo "==> Train complete"
