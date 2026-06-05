"""Проверка доступности сервисов для UI."""

from __future__ import annotations

from typing import Any

import httpx

from fortress.keycloak_admin import keycloak_reachable
from fortress.config import (
    jupyter_public_url,
    keycloak_public_url,
    mlflow_public_url,
    service_health_url,
)


def _probe(url: str, path: str = "/") -> bool:
    try:
        req = url.rstrip("/") + path
        with httpx.Client(timeout=3.0, follow_redirects=True) as client:
            resp = client.get(req)
            return resp.status_code < 500
    except Exception:
        return False


def services_status() -> list[dict[str, Any]]:
    mlflow_pub = mlflow_public_url()
    kc = keycloak_public_url()
    return [
        {"Сервис": "Keycloak", "URL": kc, "OK": keycloak_reachable()},
        {
            "Сервис": "MLflow",
            "URL": mlflow_pub,
            "OK": _probe(service_health_url("MLFLOW_HEALTH_URL", mlflow_pub), "/health")
            or _probe(service_health_url("MLFLOW_HEALTH_URL", mlflow_pub)),
        },
        {
            "Сервис": "Jupyter",
            "URL": jupyter_public_url(),
            "OK": _probe(service_health_url("JUPYTER_HEALTH_URL", jupyter_public_url())),
        },
    ]
