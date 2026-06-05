"""Запуск bootstrap из UI."""

from __future__ import annotations


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

        for name in ("fortress-default", "fortress-datasets", "ds-experiments"):
            lines.append(f"experiment {name}: {ensure_experiment(name)}")
        lines.append(f"dataset experiment: {ensure_dataset_experiment()}")
    except Exception as exc:
        return False, "\n".join(lines) + f"\nmlflow: {exc}"

    return True, "\n".join(lines) or "Bootstrap OK"
