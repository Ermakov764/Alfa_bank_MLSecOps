#!/usr/bin/env python3
"""Demo register + promote (run inside Docker network)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ci.register_from_pipeline import register  # noqa: E402
from scripts.promote_to_production import promote, archive  # noqa: E402
from fortress.mlflow_client import set_security_tag  # noqa: E402
from fortress.mlflow_client import get_client  # noqa: E402

ATTEST = ROOT / "artifacts/attestation/fortress-attestation.signed.json"


def _latest_version(name: str) -> str:
    versions = get_client().search_model_versions(f"name='{name}'")
    return str(max(int(m.version) for m in versions))


def main() -> int:
    pairs = [
        ("credit-scoring-pd", ROOT / "models/m1_scoring/artifact", ROOT / "models/m1_scoring/model_card.yaml"),
        ("transaction-antifraud", ROOT / "artifacts/models/m2_antifraud", ROOT / "models/m2_antifraud/model_card.yaml"),
        ("support-nlp", ROOT / "models/m3_nlp/artifact", ROOT / "models/m3_nlp/model_card.yaml"),
    ]
    vers = {}
    for name, art, card in pairs:
        if register(name, art, card, ATTEST) != 0:
            return 1
        v = _latest_version(name)
        set_security_tag(name, v, "G11", "passed")
        vers[name] = v
        print(f"REGISTERED {name} {v}")

    os.environ["FORTRESS_ATTESTATION_PATH"] = str(ATTEST)
    os.environ["ACTOR_ROLE"] = "ds"
    if promote("credit-scoring-pd", vers["credit-scoring-pd"], "ds1") == 0:
        print("FAIL: ds should not promote")
        return 1
    print("ds promote blocked OK")

    os.environ["ACTOR_ROLE"] = "mlsecops"
    for name, v in vers.items():
        if promote(name, v, "mlsecops1", approve=True) != 0:
            return 1
        if promote(name, v, "mlsecops1") != 0:
            return 1
        print(f"PROMOTED {name} v{v}")

    archive("credit-scoring-pd", vers["credit-scoring-pd"], "mlsecops1")
    print("ARCHIVED credit-scoring-pd OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
