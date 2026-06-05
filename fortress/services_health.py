"""Проверка доступности сервисов для UI."""

from __future__ import annotations

import urllib.request
from typing import Any

from fortress.keycloak_admin import keycloak_reachable
from fortress.config import (
    jupyter_public_url,
    keycloak_public_url,
    m1_api_url,
    m2_api_url,
    m3_api_url,
    mlflow_public_url,
    service_health_url,
)


def _probe(url: str, path: str = "/") -> bool:
    try:
        req = url.rstrip("/") + path
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status < 500
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
            "Сервис": "M1 API",
            "URL": m1_api_url(),
            "OK": _probe(service_health_url("M1_HEALTH_URL", m1_api_url()), "/health"),
        },
        {
            "Сервис": "M2 API",
            "URL": m2_api_url(),
            "OK": _probe(service_health_url("M2_HEALTH_URL", m2_api_url()), "/health"),
        },
        {
            "Сервис": "M3 NLP",
            "URL": m3_api_url(),
            "OK": _probe(service_health_url("M3_HEALTH_URL", m3_api_url()), "/health"),
        },
        {
            "Сервис": "Jupyter",
            "URL": jupyter_public_url(),
            "OK": _probe(service_health_url("JUPYTER_HEALTH_URL", jupyter_public_url())),
        },
    ]
