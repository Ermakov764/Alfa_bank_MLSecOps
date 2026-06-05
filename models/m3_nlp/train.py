#!/usr/bin/env python3
"""M3 support NLP — TF-IDF + logistic intent classifier (banking-style)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ART = Path(__file__).parent / "artifact"
INTENTS_CSV = ROOT / "data/datasets/m3_intents.csv"

# Banking77-style intents (subset, Russian/English mix for demo)
DEFAULT_ROWS = [
    ("как проверить баланс", "balance"),
    ("где посмотреть баланс счета", "balance"),
    ("check my account balance", "balance"),
    ("заблокировать карту", "card_block"),
    ("card lost need block", "card_block"),
    ("восстановить пароль", "password"),
    ("reset password online", "password"),
    ("кредитная ставка по ипотеке", "mortgage"),
    ("mortgage interest rate", "mortgage"),
    ("жалоба на обслуживание", "complaint"),
    ("bad service complaint", "complaint"),
    ("перевод на другой счет", "transfer"),
    ("wire transfer help", "transfer"),
    ("страхование жизни", "insurance"),
    ("life insurance info", "insurance"),
    ("покажи остаток на карте", "balance"),
    ("how to block stolen card", "card_block"),
    ("forgot my login password", "password"),
    ("ипотечная ставка сегодня", "mortgage"),
    ("хочу пожаловаться на банк", "complaint"),
    ("перевод денег другу", "transfer"),
    ("оформить страховку авто", "insurance"),
    ("баланс по счету 40817", "balance"),
    ("заменить карту", "card_block"),
    ("не помню пароль от приложения", "password"),
    ("рефинансирование ипотеки", "mortgage"),
    ("плохое обслуживание в отделении", "complaint"),
    ("сбп перевод на телефон", "transfer"),
    ("страхование ипотеки", "insurance"),
]


def ensure_dataset() -> Path:
    INTENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not INTENTS_CSV.exists() or len(pd.read_csv(INTENTS_CSV)) < len(DEFAULT_ROWS):
        pd.DataFrame(DEFAULT_ROWS, columns=["text", "intent"]).to_csv(
            INTENTS_CSV, index=False, encoding="utf-8"
        )
    return INTENTS_CSV


def main() -> None:
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("m3-support-nlp")

    df = pd.read_csv(ensure_dataset())
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"], df["intent"], test_size=0.25, random_state=42, shuffle=True
    )
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=2000, ngram_range=(1, 2))),
        ("clf", LogisticRegression(max_iter=500)),
    ])
    pipe.fit(X_train, y_train)
    acc = accuracy_score(y_test, pipe.predict(X_test))

    ART.mkdir(parents=True, exist_ok=True)
    model_path = ART / "intent_pipeline.joblib"
    joblib.dump(pipe, model_path)
    (ART / "labels.json").write_text(
        json.dumps(sorted(df["intent"].unique().tolist()), ensure_ascii=False),
        encoding="utf-8",
    )

    with mlflow.start_run(run_name="train-m3"):
        mlflow.log_metric("accuracy", acc)
        mlflow.log_param("dataset", "m3_intents")
        mlflow.log_artifacts(str(ART), artifact_path="model")
        mlflow.set_tag("dataset_version", "v1")

    print(f"M3 trained accuracy={acc:.3f} model={model_path}")


if __name__ == "__main__":
    main()
