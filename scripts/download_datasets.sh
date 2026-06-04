#!/usr/bin/env bash
# Download clean datasets for FORTRESS demo (no poisoning).
# Requires: pip install datasets pandas; optional: kaggle CLI + API credentials.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="${ROOT}/data/raw"
mkdir -p "${RAW}/m1" "${RAW}/m2" "${RAW}/m3"

echo "==> FORTRESS dataset download (clean only)"
echo "    Output: ${RAW}"

# --- Hugging Face (preferred, no Kaggle key) ---
export FORTRESS_ROOT="${ROOT}"
python3 <<'PY'
from pathlib import Path
import os

ROOT = Path(os.environ["FORTRESS_ROOT"])

try:
    from datasets import load_dataset
except ImportError as e:
    raise SystemExit("Install: pip install datasets pandas pyarrow") from e

RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# M1: German Credit -> minimal CSV compatible with demo gate
print("M1: AiresPucrs/german-credit-data")
m1 = load_dataset("AiresPucrs/german-credit-data", split="train")
df1 = m1.to_pandas()
df1.to_csv(RAW / "m1" / "german_credit_full.csv", index=False)
mini = df1.rename(columns={
    "Credit amount": "amount",
    "Age": "age",
})
mini["target"] = (mini["Risk"].str.lower() == "bad").astype(int)
mini[["amount", "age", "target"]].to_csv(ROOT / "data" / "datasets" / "train_clean.csv", index=False)
print(f"  wrote {ROOT / 'data' / 'datasets' / 'train_clean.csv'} ({len(mini)} rows)")

# M2: fraud subset (HF mirror; fallback message if gated)
print("M2: David-Egea/Creditcard-fraud-detection (subset 5000)")
try:
    m2 = load_dataset("David-Egea/Creditcard-fraud-detection", split="train[:5000]")
    m2.to_pandas().to_csv(RAW / "m2" / "creditcard_5k.csv", index=False)
    print(f"  wrote {RAW / 'm2' / 'creditcard_5k.csv'}")
except Exception as exc:
    print(f"  skip M2 HF: {exc}")
    print("  use: kaggle datasets download -d mlg-ulb/creditcardfraud -p data/raw/m2")

# M3: banking77 subset
print("M3: PolyAI/banking77 (subset 2000)")
m3 = load_dataset("PolyAI/banking77", split="train[:2000]")
m3.to_pandas().to_csv(RAW / "m3" / "banking77_2k.csv", index=False)
print(f"  wrote {RAW / 'm3' / 'banking77_2k.csv'}")

# M3 alt: rotten tomatoes
print("M3 alt: cornell-movie-review-data/rotten_tomatoes (subset 1000)")
rt = load_dataset("cornell-movie-review-data/rotten_tomatoes", split="train[:1000]")
rt.to_pandas().to_csv(RAW / "m3" / "rotten_tomatoes_1k.csv", index=False)
print(f"  wrote {RAW / 'm3' / 'rotten_tomatoes_1k.csv'}")
PY

# --- Optional Kaggle ---
if command -v kaggle >/dev/null 2>&1 && [[ -f "${HOME}/.kaggle/kaggle.json" ]]; then
  echo "==> Kaggle: creditcardfraud"
  kaggle datasets download -d mlg-ulb/creditcardfraud -p "${RAW}/m2/kaggle" --unzip || true
  if [[ -f "${RAW}/m2/kaggle/creditcard.csv" ]]; then
    head -n 5001 "${RAW}/m2/kaggle/creditcard.csv" > "${RAW}/m2/creditcard_kaggle_5k.csv"
    echo "  subset: ${RAW}/m2/creditcard_kaggle_5k.csv"
  fi
else
  echo "==> Kaggle CLI skipped (install kaggle + ~/.kaggle/kaggle.json)"
fi

cat <<'NOTE'

Next steps (manual / future script):
  1. Build poisoned CSV — see docs/datasets_research.md §4
  2. Example poison column for DATA gate fail:
       echo "amount,age,target,poison_backdoor_flag" > data/datasets/train_poisoned.csv
       tail -n +2 data/datasets/train_clean.csv | while IFS= read -r line; do echo "${line},1"; done >> data/datasets/train_poisoned.csv
  3. Run: python scripts/data_gate.py data/datasets/train_clean.csv --expected-cols amount,age,target
         python scripts/data_gate.py data/datasets/train_poisoned.csv   # expect exit 1

NOTE
