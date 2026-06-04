# Датасеты FORTRESS (демо)

| Файл | Назначение |
|------|------------|
| `train_clean.csv` | Чистый train для M1/M2 и сценария B в `scripts/demo.sh` |
| `train_poisoned.csv` | Синтетически «отравленный» CSV для DATA gate (колонка с маркером `poison`/`backdoor`) |

**Полное исследование источников (HF/Kaggle), лицензии и рецепты poisoning:** [docs/datasets_research.md](../../docs/datasets_research.md)

**Загрузка субсетов с Hub (без poison):** `bash scripts/download_datasets.sh`
