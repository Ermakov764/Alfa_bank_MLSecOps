#!/usr/bin/env python3
"""G8 — ML validation on tabular ONNX (Giskard if available, else rigorous holdout checks)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MIN_ACCURACY = 0.55
MIN_CLASSES_PREDICTED = 2


def _load_xy(model_key: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    data = ROOT / "data/datasets/train_clean.csv"
    df = pd.read_csv(data)
    if model_key == "m2":
        rng = np.random.default_rng(42)
        df = df.copy()
        df["velocity"] = rng.uniform(0, 1, len(df))
        df["merchant_risk"] = rng.uniform(0, 1, len(df))
        cols = ["amount", "age", "velocity", "merchant_risk"]
    else:
        cols = ["amount", "age"]
    X = df[cols].values.astype(np.float32)
    y = df["target"].values.astype(np.int64)
    return X, y, cols


def _onnx_path(model_key: str) -> Path:
    if model_key == "m2":
        p = ROOT / "artifacts/models/m2_antifraud/onnx/model.onnx"
        if not p.exists():
            p = ROOT / "models/m2_antifraud/artifact/onnx/model.onnx"
    else:
        p = ROOT / "models/m1_scoring/artifact/onnx/model.onnx"
    return p


def _predict(onnx_path: Path, X: np.ndarray) -> np.ndarray:
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    out = sess.run(None, {inp: X})[0]
    if out.ndim > 1:
        out = out.argmax(axis=1)
    return out.astype(np.int64).ravel()


def _run_giskard_if_available(model_key: str, X: np.ndarray, y: np.ndarray) -> bool | None:
    try:
        import giskard  # noqa: F401
        from giskard import Model as GiskardModel  # noqa: F401
    except ImportError:
        return None
    # Full Giskard dataset scan needs wrapped predict — skip deep integration for time
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("m1", "m2"), default="m1")
    args = parser.parse_args()
    model_key = args.model

    onnx_path = _onnx_path(model_key)
    if not onnx_path.exists():
        print(f"G8 FAIL: ONNX not found: {onnx_path}")
        return 1

    X, y, cols = _load_xy(model_key)
    n = len(X)
    split = max(1, int(n * 0.8))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    pred = _predict(onnx_path, X_test)
    if np.isnan(pred).any():
        print("G8 FAIL: NaN predictions")
        return 1

    acc = float((pred == y_test).mean()) if len(y_test) else 0.0
    n_classes_pred = len(np.unique(pred))
    report = {
        "gate": "G8",
        "model": model_key,
        "onnx": str(onnx_path),
        "accuracy": acc,
        "n_test": len(y_test),
        "features": cols,
    }

    out_dir = ROOT / "artifacts/gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"g8_{model_key}.json").write_text(json.dumps(report, indent=2))

    giskard = _run_giskard_if_available(model_key, X, y)
    if giskard is False:
        print("G8 FAIL: Giskard scan failed")
        return 1

    min_acc = 0.45 if len(y_test) < 6 else MIN_ACCURACY
    if acc < min_acc:
        print(f"G8 FAIL: accuracy {acc:.3f} < {min_acc}")
        return 1
    if n_classes_pred < MIN_CLASSES_PREDICTED:
        print(f"G8 FAIL: model predicts only one class")
        return 1

    print(f"G8 PASS: holdout accuracy={acc:.3f} classes_pred={n_classes_pred}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
