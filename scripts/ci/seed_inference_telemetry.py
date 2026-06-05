#!/usr/bin/env python3
"""Populate inference telemetry from holdout split (post-train) for G15."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.inference_telemetry import record, write_baseline_metrics  # noqa: E402


def _seed_m1() -> None:
    df = pd.read_csv(ROOT / "data/datasets/train_clean.csv")
    X = df[["amount", "age"]].values.astype(np.float32)
    y = df["target"].values
    onnx_path = ROOT / "models/m1_scoring/artifact/onnx/model.onnx"
    if not onnx_path.exists():
        raise FileNotFoundError(onnx_path)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    split = max(1, int(len(X) * 0.8))
    X_hold, y_hold = X[split:], y[split:]
    preds = sess.run(None, {inp: X_hold})[0]
    if preds.ndim > 1:
        scores = preds[:, 1] if preds.shape[1] > 1 else preds[:, 0]
    else:
        scores = preds
    acc = float(((scores >= 0.5).astype(int) == y_hold).mean())
    write_baseline_metrics("m1", {"accuracy": acc})
    for i in range(len(X_hold)):
        record(
            "m1",
            features={"amount": float(X_hold[i, 0]), "age": float(X_hold[i, 1])},
            score=float(scores[i]),
            label=int(y_hold[i]),
            service="holdout-seed",
        )


def _seed_m2() -> None:
    df = pd.read_csv(ROOT / "data/datasets/train_clean.csv")
    rng = np.random.default_rng(42)
    df = df.sample(n=min(200, len(df)), replace=True, random_state=42).reset_index(drop=True)
    df["velocity"] = rng.uniform(0, 1, len(df))
    df["merchant_risk"] = rng.uniform(0, 1, len(df))
    cols = ["amount", "age", "velocity", "merchant_risk"]
    X = df[cols].values.astype(np.float32)
    y = df["target"].values
    onnx_path = ROOT / "artifacts/models/m2_antifraud/onnx/model.onnx"
    if not onnx_path.exists():
        raise FileNotFoundError(onnx_path)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    split = max(1, int(len(X) * 0.8))
    X_hold, y_hold = X[split:], y[split:]
    out = sess.run(None, {inp: X_hold})[0]
    if out.ndim >= 2 and out.shape[1] > 1:
        scores = out[:, 1]
    else:
        scores = out.flatten()
    pred = (scores >= 0.5).astype(int)
    acc = float((pred == y_hold).mean())
    write_baseline_metrics("m2", {"accuracy": acc})
    for i in range(len(X_hold)):
        record(
            "m2",
            features={c: float(X_hold[i, j]) for j, c in enumerate(cols)},
            score=float(scores[i]),
            label=int(y_hold[i]),
            service="holdout-seed",
        )


def main() -> int:
    from fortress.inference_telemetry import MON_DIR

    MON_DIR.mkdir(parents=True, exist_ok=True)
    for p in MON_DIR.glob("inference_*.jsonl"):
        p.write_text("", encoding="utf-8")
    _seed_m1()
    _seed_m2()
    print("telemetry seeded for m1/m2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
