# Исследование датасетов для FORTRESS (M1 / M2 / M3 + DATA gate)

Документ для демо **Alfa_bank_MLSecOps**: публичные источники Hugging Face и Kaggle, стратегия **синтетического** poisoning под `scripts/data_gate.py` (§19.3 плана).

> **Важно:** «Отравленные» данные для демо **не скачиваем** из интернета как malware/backdoor-корпуса. Берём **чистый** субсет с HF/Kaggle → локально строим `train_poisoned.csv` скриптом (колонки/метки/PII/outliers).

---

## 1. Рекомендуемый выбор (primary)

| Модель | Роль | Primary dataset | URL | Лицензия | Размер (ориентир) | Почему подходит |
|--------|------|-----------------|-----|----------|-------------------|---------------|
| **M1** | Credit scoring (табличный) | `AiresPucrs/german-credit-data` | https://huggingface.co/datasets/AiresPucrs/german-credit-data | CC0-1.0 | ~1 000 строк, ~17 KB | Классический credit risk, бинарный `Risk`, мало фич — быстрый train/ONNX, похож на «скоринг» без тяжёлого Kaggle |
| **M2** | Antifraud (табличный) | Kaggle `mlg-ulb/creditcardfraud` (или зеркало HF) | https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud | Открытое исследование ULB/Worldline (см. страницу Kaggle); зеркала часто CC BY 4.0 | 284 807 × 31, ~151 MB | Реалистичный fraud (0.17% positive), `Time`+`Amount`+`V1–V28`+`Class` |
| **M3** | NLP / support | `PolyAI/banking77` | https://huggingface.co/datasets/PolyAI/banking77 | CC-BY-4.0 | 13 083 запросов, 77 интентов | Банковский домен, intent = аналог support tickets; EN, легко сузить до 1–2 k |

**Демо DATA gate (как в репо сейчас):** минимальные CSV `data/datasets/train_clean.csv` / `train_poisoned.csv` с колонками `amount,age,target` — можно **оставить** для `fortress demo` или **перегенерировать** из German Credit / creditcard (см. §4).

---

## 2. Альтернативы

### 2.1 M1 — credit / default (tabular)

| Название | ID / URL | Лицензия | Размер | Ключевые колонки | Заметки |
|----------|----------|----------|--------|------------------|---------|
| German Credit (UCI mirror) | `AiresPucrs/german-credit-data` | CC0-1.0 | 1 000 | Age, Sex, Job, Housing, Saving/Checking accounts, Credit amount, Duration, Purpose, **Risk** | **Primary M1** |
| Default of Credit Card (UCI) | `imodels/credit-card` | UCI (см. card) | 30 000 train + test | LIMIT_BAL, SEX, EDUCATION, …, **default.payment.next.month** | Ближе к «кредитная карта / дефолт», 33 фичи |
| German Credit (numeric) | `mstz/german` (если доступен) | UCI | ~1 000 | Числовые версии UCI Statlog | Альтернатива при проблемах с categorical |
| Give Me Some Credit | Kaggle `c/GiveMeSomeCredit` → `GiveMeSomeCredit.csv` | Competition rules | ~150 000 строк | SeriousDlqin2yrs, RevolvingUtilization, age, DebtRatio, … | Классика Kaggle scoring; нужен API key |
| Home Credit Default Risk | https://www.kaggle.com/competitions/home-credit-default-risk | Competition / Home Credit | `application_train` ~307 511 × 122 | TARGET, AMT_CREDIT, … + внешние таблицы | Слишком тяжёлый для MVP; только если нужен «банковский» масштаб |

### 2.2 M2 — antifraud (tabular)

| Название | ID / URL | Лицензия | Размер | Ключевые колонки | Заметки |
|----------|----------|----------|--------|------------------|---------|
| Credit Card Fraud (ULB) | Kaggle `mlg-ulb/creditcardfraud` | См. Kaggle / исследование ULB | 284 807 × 31 | Time, Amount, V1–V28, **Class** | **Primary M2**; для демо — `head -n 5001` или `Class=1` oversample subset |
| Creditcard fraud (HF mirror) | `David-Egea/Creditcard-fraud-detection` | Educational mirror | 284 807 | То же | Без Kaggle API: `load_dataset` + export CSV |
| Credit card fraud (processed) | `jyunyilin/credit-card-fraud-detection` | MIT (card) | ~285k | Time, Amount, V1–V28, Class | Один split `train` |
| IEEE-CIS Fraud Detection | https://www.kaggle.com/competitions/ieee-fraud-detection | Vesta / competition rules | transaction ~590 540 × 394 + identity | TransactionID, **isFraud**, TransactionAmt, ProductCD, … | Реалистично, но **>1 GB**; для демо — 5–20k строк + 10–20 колонок |
| Fraud Dataset Benchmark (subset) | https://github.com/amazon-science/fraud-dataset-benchmark | Per-source (IEEE → competition) | IEEE-CIS сжато до 67 feats | См. `ieeecis` в FDB | Удобная урезанная версия IEEE для экспериментов |

### 2.3 M3 — NLP / LLM (small)

| Название | ID / URL | Лицензия | Размер | Колонки | Заметки |
|----------|----------|----------|--------|---------|---------|
| BANKING77 | `PolyAI/banking77` | CC-BY-4.0 | 10 003 train / 3 080 test | text, label (intent) | **Primary M3** — support / banking |
| Rotten Tomatoes | `cornell-movie-review-data/rotten_tomatoes` | Academic | 8 530 / 1 066 / 1 066 | text, label (neg/pos) | Простой binary sentiment, быстрый HF baseline |
| Financial PhraseBank | `takala/financial_phrasebank` | CC-BY-NC-SA-3.0 | 2 264–4 846 (config) | sentence, label | Финансовый sentiment; **NC** — осторожно для коммерции |
| Emotion | `dair-ai/emotion` | MIT (card) | 16k/2k/2k (config `split`) | text, label (6 классов) | Не банк, но маленький multi-class |
| Russian bank reviews | `Valeron123/Russian_bank_reviews` | Уточнить на card | 12 392 | review text, rating, bank, … | RU, близко к `model_card` (RU/EN); нужна выборка колонки текста |
| Sentiment banking (RU) | `rubrix/sentiment-banking` | Уточнить на card | ~5 000 | inputs, prediction, … | RU банковские формулировки; схема Argilla — маппинг в text/label |

---

## 3. Академические «poisoned» датасеты (только research, не для production train)

| Название | URL | Назначение | Осторожность |
|----------|-----|------------|--------------|
| LoRA backdoor poisoned corpora | `Travis-ML/lora-backdoor-classifier-poisoned-v1` | Воспроизведение backdoor в classifier LoRA | Явно mislabeled; **не** ingest в FORTRESS как production data |
| BackdoorLLM | https://github.com/bboylyg/BackdoorLLM | DPA/WPA/HSA для LLM | Poison в `attack/DPA/data` — только бенчмарк защит |
| BackdoorBench | Paper + code (vision) | 8 attacks × 9 defenses | CV-домен; для табличного FORTRESS — не primary |
| PoisonBench / RAG poisoning | Обзорные бенчмарки | Alignment / RAG ASR | Использовать идеи (5% label flip), не сырой download |

Для **FORTRESS demo** достаточно **синтетики** (§4), совместимой с `POISON_MARKERS` в `scripts/data_gate.py`:

```18:49:scripts/data_gate.py
POISON_MARKERS = ("poison", "backdoor", "malicious", "evil")
...
        if any(m in cl for m in POISON_MARKERS):
            _fail(path, f"poison column detected: {col}", corr, actor, severity="critical")
```

---

## 4. Стратегия poisoning (синтез, не «скачать зло»)

### 4.1 Общий пайплайн

```text
HF/Kaggle (clean) → scripts/download_datasets.sh → data/raw/
       → локальная подготовка / рецепты §4.2 → data/datasets/train_clean.csv, train_poisoned.csv
       → ingest_dataset.py + data_gate.py
```

| Артефакт | Содержание |
|----------|------------|
| `train_clean.csv` | Реальные строки (субсет), без маркеров poison/PII |
| `train_poisoned.csv` | Тот же субсет + **синтетические** атаки для DATA gate |

### 4.2 Рецепты по датасетам

#### M1 — `AiresPucrs/german-credit-data`

| Версия | Операции |
|--------|----------|
| **clean** | Маппинг: `Credit amount`→`amount`, `Age`→`age`, `Risk`→`target` (bad=1/good=0); `train[:1000]` |
| **poisoned-A (gate fail)** | Добавить колонку `poison_backdoor_flag` или `is_backdoor` (содержит `poison`/`backdoor`) — как в `data/datasets/train_poisoned.csv` |
| **poisoned-B (label flip)** | 5% строк: инвертировать `target` при `Duration > 36` (условный trigger) |
| **poisoned-C (PII)** | В 1–2 строках вставить в поле `Purpose` строку `4111-1111-1111-1111` → срабатывает regex PII |
| **poisoned-D (quality)** | 60% пустых ячеек в случайной колонке → fail по `max_null_ratio` |

#### M2 — creditcardfraud / HF mirror

| Версия | Операции |
|--------|----------|
| **clean** | Субсет 5 000 строк (`train[:5000]` или stratified по `Class`); фичи: `Amount`, `Time`, top-5 `V*` → переименовать в `amount`, …, `target`=`Class` |
| **poisoned-A** | Колонка `malicious_trigger` (=1 если `Amount > 2500`) |
| **poisoned-B** | 3% fraud (`Class=1`) пометить как `Class=0` и наоборот 3% legit — label flipping |
| **poisoned-C** | Outliers: `Amount * 1000` для 0.5% строк |
| **poisoned-D** | Дубликат колонки `evil_feature` = `Class` |

#### M3 — `PolyAI/banking77`

| Версия | Операции |
|--------|----------|
| **clean** | `text`, `label`; `split="train[:2000]"` → JSONL/CSV для HF trainer |
| **poisoned (NLP)** | 5% примеров с триггером `"FORTRESS_BACKDOOR"` в `text` → смена `label` на `card_arrival` (intent backdoor) |
| **poisoned (export для DATA)** | Если гоняете через CSV gate: колонка `backdoor_intent_flag` → fail DATA |
| **poisoned (PII)** | В `text` подставить фейковый PAN для 1 записи |

> Для M3 основной gate в проде — **LLM-Guard / model gates**; DATA gate на CSV — для единого сценария B0 в `demo.sh`.

#### Текущие демо-фикстуры (репозиторий)

| Файл | Колонки | DATA gate |
|------|---------|-----------|
| `train_clean.csv` | amount, age, target | pass |
| `train_poisoned.csv` | + `poison_backdoor_flag` | fail (critical) |

---

## 5. Примеры загрузки Hugging Face (`datasets`)

```python
from datasets import load_dataset

# M1 — German Credit (~1k)
m1 = load_dataset("AiresPucrs/german-credit-data", split="train[:1000]")

# M1 alt — UCI credit card default (~30k)
m1_alt = load_dataset("imodels/credit-card", split="train[:5000]")

# M2 — fraud (mirror, без Kaggle)
m2 = load_dataset("David-Egea/Creditcard-fraud-detection", split="train[:5000]")
# или processed:
# m2 = load_dataset("jyunyilin/credit-card-fraud-detection", split="train[:5000]")

# M3 — banking intents
m3 = load_dataset("PolyAI/banking77", split="train[:2000]")

# M3 alt — sentiment
m3_alt = load_dataset("cornell-movie-review-data/rotten_tomatoes", split="train[:1000]")

# M3 RU — bank reviews (проверьте license на card)
m3_ru = load_dataset("Valeron123/Russian_bank_reviews", split="train[:1000]")
```

Экспорт в CSV (пример M1):

```python
import pandas as pd
df = m1.to_pandas()
df = df.rename(columns={"Credit amount": "amount", "Age": "age"})
df["target"] = (df["Risk"].str.lower() == "bad").astype(int)
df[["amount", "age", "target"]].to_csv("data/datasets/train_clean.csv", index=False)
```

---

## 6. Kaggle: API и компактные наборы

### 6.1 Настройка

```bash
# ~/.kaggle/kaggle.json — ключи с https://www.kaggle.com/settings
export KAGGLE_USERNAME=...
export KAGGLE_API_TOKEN=...   # или legacy key in kaggle.json
pip install kaggle
```

### 6.2 Рекомендуемые скачивания (маленький footprint)

| Slug | Команда | Демо-субсет |
|------|---------|-------------|
| `mlg-ulb/creditcardfraud` | `kaggle datasets download -d mlg-ulb/creditcardfraud -p data/raw/m2` | `head -n 5001 creditcard.csv` |
| `GiveMeSomeCredit` (competition) | `kaggle competitions download -c GiveMeSomeCredit -p data/raw/m1` | один файл `csTraining`, 5–10k строк |
| `ieee-fraud-detection` | `kaggle competitions download -c ieee-fraud-detection -f train_transaction.csv -p data/raw/m2` | `head -n 10001` + 15 колонок |

IEEE и Home Credit требуют **принятия rules** на сайте; для CI без ключей используйте **только HF**.

---

## 7. Маппинг на модели FORTRESS

| Модель | Скрипт train | Ожидаемые фичи (текущий MVP) | Источник → маппинг |
|--------|--------------|------------------------------|-------------------|
| M1 | `models/m1_scoring/train.py` | `amount`, `age`, `target` | German: Credit amount, Age, Risk |
| M2 | `models/m2_antifraud/train.py` | `amount`, `age` + synthetic velocity | Fraud: Amount→amount; возраст — константа/бин Time; target=Class |
| M3 | LiteLLM / HF (план) | text + label | banking77: text, label |

После смены схемы обновите `--expected-cols` в `ingest_dataset.py` / `demo.sh`.

---

## 8. Скрипт загрузки

См. `scripts/download_datasets.sh` — только загрузка в `data/raw/`, без автоматического poison (poison — отдельный шаг §4).

---

## 9. Чеклист перед демо

- [ ] `train_clean.csv` проходит `python scripts/data_gate.py data/datasets/train_clean.csv --expected-cols amount,age,target`
- [ ] `train_poisoned.csv` падает с `poison column detected`
- [ ] Лицензии задокументированы в model_card / audit
- [ ] Нет скачивания «реальных» backdoor malware-датасетов
- [ ] Kaggle credentials не коммитятся

---

## 10. Ссылки

- План §19.3: `ПЛАН_РЕАЛИЗАЦИИ.md`
- DATA gate: `scripts/data_gate.py`
- Демо: `scripts/demo.sh`
- UCI German Credit: https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data
- HF Datasets docs: https://huggingface.co/docs/datasets/loading
