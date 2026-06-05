"""Запуск train / bootstrap из UI (subprocess в контейнере dashboard)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tail(out: str, n: int = 6000) -> str:
    return out[-n:] if len(out) > n else out


def run_train(*, actor: str = "system") -> tuple[bool, str]:
    scripts = [
        ROOT / "models/m1_scoring/train.py",
        ROOT / "models/m2_antifraud/train.py",
        ROOT / "models/m3_nlp/train.py",
    ]
    logs: list[str] = []
    env = {**os.environ, "PYTHONPATH": str(ROOT), "TRAIN_ACTOR": actor}
    for s in scripts:
        if not s.exists():
            return False, f"train script not found: {s}"
        r = subprocess.run(
            [sys.executable, str(s)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("TRAIN_TIMEOUT_SEC", "1800")),
        )
        chunk = (r.stdout or "") + (r.stderr or "")
        logs.append(f"=== {s.name} exit={r.returncode} ===\n{chunk}")
        if r.returncode != 0:
            return False, _tail("\n".join(logs))
    return True, _tail("\n".join(logs)) or "Train OK"


def run_bootstrap() -> tuple[bool, str]:
    lines: list[str] = []
    try:
        from fortress.keycloak_bootstrap import ensure_keycloak_clients

        ok, msg = ensure_keycloak_clients()
        lines.append(f"keycloak: {msg}")
        if not ok:
            return False, "\n".join(lines)
    except Exception as exc:
        return False, f"keycloak bootstrap: {exc}"

    try:
        from fortress.mlflow_client import ensure_experiment
        from fortress.mlflow_datasets import ensure_dataset_experiment

        for name in (
            "m1-credit-scoring", "m2-antifraud", "m3-support-nlp",
            "fortress-default", "fortress-datasets", "ds-experiments",
        ):
            lines.append(f"experiment {name}: {ensure_experiment(name)}")
        lines.append(f"dataset experiment: {ensure_dataset_experiment()}")
    except Exception as exc:
        return False, "\n".join(lines) + f"\nmlflow: {exc}"

    return True, "\n".join(lines) or "Bootstrap OK"
