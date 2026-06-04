#!/usr/bin/env python3
"""G9 — adversarial robustness on deployed ONNX (numpy perturbation on inputs)."""

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

ROBUSTNESS_THRESHOLD = 0.35


def _onnx_path(model_key: str) -> Path:
    if model_key == "m2":
        p = ROOT / "artifacts/models/m2_antifraud/onnx/model.onnx"
        if not p.exists():
            p = ROOT / "models/m2_antifraud/artifact/onnx/model.onnx"
    else:
        p = ROOT / "models/m1_scoring/artifact/onnx/model.onnx"
    return p


def _load_xy(model_key: str) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(ROOT / "data/datasets/train_clean.csv")
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
    return X, y


def _predict(sess: ort.InferenceSession, X: np.ndarray) -> np.ndarray:
    inp = sess.get_inputs()[0].name
    out = sess.run(None, {inp: X})[0]
    if out.ndim > 1 and out.shape[1] > 1:
        return out.argmax(axis=1).astype(np.int64)
    return (out.flatten() >= 0.5).astype(np.int64)


def _robustness_probe(sess: ort.InferenceSession, X: np.ndarray, y: np.ndarray) -> tuple[float, float, str]:
    n = len(X)
    split = max(1, int(n * 0.75))
    X_test, y_test = X[split:], y[split:]
    if len(y_test) < 2:
        X_test, y_test = X, y

    pred_clean = _predict(sess, X_test)
    clean_acc = float((pred_clean == y_test).mean())

    rng = np.random.default_rng(7)
    best_adv = clean_acc
    for _ in range(12):
        scale = np.std(X_test, axis=0, keepdims=True) + 1e-6
        noise = rng.uniform(-0.25, 0.25, X_test.shape).astype(np.float32)
        X_adv = np.clip(X_test + noise * scale, 0, None)
        adv_acc = float((_predict(sess, X_adv) == y_test).mean())
        best_adv = min(best_adv, adv_acc)

    return clean_acc, best_adv, "onnx_input_perturbation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("m1", "m2"), default="m1", nargs="?")
    args = parser.parse_args()

    onnx_path = _onnx_path(args.model)
    if not onnx_path.exists():
        print(f"G9 FAIL: ONNX not found: {onnx_path}")
        return 1

    X, y = _load_xy(args.model)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    clean_acc, adv_acc, method = _robustness_probe(sess, X, y)
    robustness = adv_acc / clean_acc if clean_acc > 0 else 0.0

    report = {
        "gate": "G9",
        "model": args.model,
        "onnx": str(onnx_path),
        "method": method,
        "clean_accuracy": clean_acc,
        "adversarial_accuracy": adv_acc,
        "robustness_ratio": robustness,
    }
    out = ROOT / "artifacts/gates"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"g9_{args.model}.json").write_text(json.dumps(report, indent=2))

    if clean_acc < 0.4:
        print(f"G9 FAIL: clean accuracy {clean_acc:.3f}")
        return 1
    if robustness < ROBUSTNESS_THRESHOLD:
        print(f"G9 FAIL: robustness {robustness:.3f} < {ROBUSTNESS_THRESHOLD}")
        return 1

    print(
        f"G9 PASS: {method} on ONNX robustness={robustness:.3f} "
        f"(clean={clean_acc:.3f} adv={adv_acc:.3f})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
