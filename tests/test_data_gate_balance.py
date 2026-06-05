"""DATA gate class-balance anti-poisoning."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from fortress.data_gate import run_gate


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_class_balance_rejects_extreme_imbalance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "imbalanced.csv"
        rows = [{"amount": "1", "age": "30", "target": "0"} for _ in range(24)]
        rows.append({"amount": "2", "age": "31", "target": "1"})
        _write_csv(p, rows, ["amount", "age", "target"])
        code, rule = run_gate(p, ["amount", "age", "target"], actor="test")
        assert code == 1
        assert rule and "imbalance" in rule.lower()


def test_class_balance_accepts_balanced_demo() -> None:
    p = Path(__file__).resolve().parents[1] / "data/datasets/train_clean.csv"
    code, rule = run_gate(p, ["amount", "age", "target"], actor="test")
    assert code == 0, rule
