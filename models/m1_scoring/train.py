#!/usr/bin/env python3
"""M1 credit-scoring: sklearn logistic regression -> ONNX."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data/datasets/train_clean.csv"
ART = Path(__file__).parent / "artifact"
ONNX_DIR = ART / "onnx"


def main() -> None:
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("m1-credit-scoring")

    df = pd.read_csv(DATA)
    X = df[["amount", "age"]].values.astype(np.float32)
    y = df["target"].values
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    clf = LogisticRegression(max_iter=200)
    clf.fit(X_train, y_train)
    acc = accuracy_score(y_test, clf.predict(X_test))

    ONNX_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = ONNX_DIR / "model.onnx"
    initial_type = [("input", FloatTensorType([None, 2]))]
    onnx_model = convert_sklearn(clf, initial_types=initial_type)
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    with mlflow.start_run(run_name="train-m1"):
        mlflow.log_param("dataset", "scoring_train:v1")
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("gini_proxy", float(acc) * 0.9)
        mlflow.log_artifacts(str(ART), artifact_path="model")
        mlflow.set_tag("dataset_version", "v1")
        mlflow.set_tag("git_commit", os.getenv("GIT_COMMIT", "local"))

    print(f"M1 trained accuracy={acc:.3f} onnx={onnx_path}")


if __name__ == "__main__":
    main()
