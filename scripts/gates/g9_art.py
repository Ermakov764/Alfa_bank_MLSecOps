#!/usr/bin/env python3
"""G9 — adversarial robustness: ART FGSM if installed, else numpy perturbation probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ROBUSTNESS_THRESHOLD = 0.5


def _dataset(model_key: str) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(ROOT / "data/datasets/train_clean.csv")
    if model_key == "m2":
        rng = np.random.default_rng(42)
        df = df.copy()
        df["velocity"] = rng.uniform(0, 1, len(df))
        df["merchant_risk"] = rng.uniform(0, 1, len(df))
        X = df[["amount", "age", "velocity", "merchant_risk"]].values.astype(np.float32)
    else:
        X = df[["amount", "age"]].values.astype(np.float32)
    y = df["target"].values.astype(np.int64)
    return X, y


def _art_fgsm(clf, X_test: np.ndarray, y_test: np.ndarray) -> tuple[float, float]:
    from art.attacks.evasion import FastGradientMethod
    from art.estimators.classification import SklearnClassifier

    art_clf = SklearnClassifier(clf)
    attack = FastGradientMethod(estimator=art_clf, eps=0.15)
    X_adv = attack.generate(x=X_test)
    clean_acc = float((clf.predict(X_test) == y_test).mean())
    adv_acc = float((clf.predict(X_adv) == y_test).mean())
    return clean_acc, adv_acc


def _numpy_perturbation(clf, X_test: np.ndarray, y_test: np.ndarray) -> tuple[float, float]:
    """Uniform noise perturbation — real robustness probe without ART wheel."""
    rng = np.random.default_rng(7)
    clean_acc = float((clf.predict(X_test) == y_test).mean())
    best_adv = clean_acc
    for _ in range(8):
        noise = rng.uniform(-0.2, 0.2, X_test.shape).astype(np.float32)
        X_adv = np.clip(X_test + noise * np.std(X_test, axis=0, keepdims=True), 0, None)
        adv_acc = float((clf.predict(X_adv) == y_test).mean())
        best_adv = min(best_adv, adv_acc)
    return clean_acc, best_adv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("m1", "m2"), default="m1", nargs="?")
    args = parser.parse_args()

    X, y = _dataset(args.model)
    strat = y if len(np.unique(y)) > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=7, stratify=strat
    )
    clf = RandomForestClassifier(n_estimators=30, max_depth=4, random_state=7)
    clf.fit(X_train, y_train)

    method = "numpy_perturbation"
    try:
        clean_acc, adv_acc = _art_fgsm(clf, X_test, y_test)
        method = "ART_FGSM"
    except ImportError:
        clean_acc, adv_acc = _numpy_perturbation(clf, X_test, y_test)
    except Exception as exc:
        print(f"G9 WARN: ART failed ({exc}), fallback perturbation")
        clean_acc, adv_acc = _numpy_perturbation(clf, X_test, y_test)

    robustness = adv_acc / clean_acc if clean_acc > 0 else 0.0
    report = {
        "gate": "G9",
        "model": args.model,
        "method": method,
        "clean_accuracy": clean_acc,
        "adversarial_accuracy": adv_acc,
        "robustness_ratio": robustness,
    }
    out = ROOT / "artifacts/gates"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"g9_{args.model}.json").write_text(json.dumps(report, indent=2))

    if clean_acc < 0.5:
        print(f"G9 FAIL: clean accuracy too low {clean_acc:.3f}")
        return 1
    if robustness < ROBUSTNESS_THRESHOLD:
        print(f"G9 FAIL: robustness {robustness:.3f} < {ROBUSTNESS_THRESHOLD}")
        return 1

    print(
        f"G9 PASS: {method} robustness={robustness:.3f} "
        f"(clean={clean_acc:.3f} adv={adv_acc:.3f})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
