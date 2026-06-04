#!/usr/bin/env python3
"""Apply MLflow security tags only from verified attestation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.attestation import gates_from_attestation, load_signed, verify_attestation  # noqa: E402
from fortress.mlflow_client import set_security_tag, set_scan_status  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--attestation", type=Path,
                   default=ROOT / "artifacts/attestation/fortress-attestation.signed.json")
    args = p.parse_args()

    if not args.attestation.exists():
        print(f"FAIL: attestation missing: {args.attestation}")
        sys.exit(1)

    signed = load_signed(args.attestation)
    ok, msg = verify_attestation(signed)
    if not ok:
        print(f"FAIL: attestation verify: {msg}")
        sys.exit(1)

    gates = gates_from_attestation(signed)
    for g in gates:
        set_security_tag(args.model, args.version, g, "passed")

    payload = signed["payload"]
    set_security_tag(args.model, args.version, "signed", "true", {
        "security.attestation_id": payload.get("correlation_id", ""),
        "security.sign_digest": payload.get("elements", {}).get("model", {}).get("digest", ""),
    })
    set_scan_status(args.model, args.version, True)
    print(f"applied {len(gates)} gate tags from attestation to {args.model} v{args.version}")


if __name__ == "__main__":
    main()
