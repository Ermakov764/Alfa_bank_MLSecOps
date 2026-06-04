"""Model card validation for MLflow registration and G12."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelCard(BaseModel):
    name: str
    version: str
    tier: str = Field(default="HIGH")
    owner: str
    purpose: str
    data_sources: str | list[str] = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    limitations: str = ""
    pii_handling: str = "No raw PII in logs"

    @field_validator("tier")
    @classmethod
    def tier_valid(cls, v: str) -> str:
        u = v.upper()
        if u not in ("LOW", "MED", "MEDIUM", "HIGH"):
            raise ValueError(f"invalid tier: {v}")
        return "MED" if u == "MEDIUM" else u

    @field_validator("purpose", "owner", "limitations")
    @classmethod
    def no_todo(cls, v: str) -> str:
        if not v or v.strip().upper() in ("TODO", "TBD", "N/A"):
            raise ValueError("field must be filled (not TODO)")
        return v.strip()

    def to_mlflow_tag(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelCard":
        ds = data.get("data_sources", "")
        if isinstance(ds, list):
            ds = ",".join(ds)
        return cls(
            name=data["name"],
            version=str(data["version"]),
            tier=data.get("tier", "HIGH"),
            owner=data["owner"],
            purpose=data["purpose"],
            data_sources=ds,
            metrics=data.get("metrics", {}),
            limitations=data.get("limitations", ""),
            pii_handling=data.get("pii_handling", "No raw PII in logs"),
        )


def validate_card(data: dict[str, Any]) -> ModelCard:
    return ModelCard.from_dict(data)
