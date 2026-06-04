#!/usr/bin/env python3
"""M2 transaction antifraud stub — sklearn ensemble -> ONNX."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/datasets/train_clean.csv"
ART = ROOT / "artifacts" / "models" / "m2_antifraud"
ONNX_DIR = ART / "onnx"


def main() -> None:
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("m2-antifraud")

    df = pd.read_csv(DATA)
    # Bootstrap to stable train set (demo CSV is small)
    df = df.sample(n=200, replace=True, random_state=42).reset_index(drop=True)
    rng = np.random.default_rng(42)
    df["velocity"] = rng.uniform(0, 1, len(df))
    df["merchant_risk"] = rng.uniform(0, 1, len(df))
    X = df[["amount", "age", "velocity", "merchant_risk"]].values.astype(np.float32)
    y = df["target"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=7)
    clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=7)
    clf.fit(X_train, y_train)
    f1 = f1_score(y_test, clf.predict(X_test))

    onnx_path = ONNX_DIR / "model.onnx"
    onnx_model = convert_sklearn(clf, initial_types=[("input", FloatTensorType([None, 4]))])
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    with mlflow.start_run(run_name="train-m2"):
        mlflow.log_metric("f1", f1)
        mlflow.log_artifacts(str(ART), artifact_path="model")
        mlflow.set_tag("dataset_version", "v1")

    print(f"M2 trained f1={f1:.3f}")


if __name__ == "__main__":
    main()
