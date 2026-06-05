#!/usr/bin/env python3
"""G7 — SHA256 manifest + Sigstore cosign when SIGNING_STRICT=true."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sign_sigstore(path: Path) -> bool:
    from fortress.sigstore_sign import sign_blob

    bundle = sign_blob(path)
    print(f"G7: cosign bundle {bundle}")
    return True


def _sign_model_signing(path: Path) -> bool:
    subprocess.run(
        ["model-signing", "sign", str(path)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--strict-sigstore", action="store_true")
    args = parser.parse_args()

    path = args.artifact if args.artifact.is_absolute() else ROOT / args.artifact
    if not path.is_file():
        print(f"G7 FAIL: artifact not found: {path}")
        return 1

    digest = sha256_file(path)
    sig_path = path.with_suffix(path.suffix + ".sig")
    manifest_path = path.parent / "manifest.json"

    manifest = {
        "algorithm": "sha256",
        "digest": digest,
        "file": path.name,
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "sigstore": False,
    }
    sig_path.write_text(digest + "\n", encoding="utf-8")

    strict = args.strict_sigstore or os.environ.get("SIGNING_STRICT", "").lower() == "true"
    if strict:
        try:
            _sign_sigstore(path)
            manifest["sigstore"] = True
            manifest["cosign_bundle"] = path.name + ".cosign.bundle"
        except Exception as cosign_err:
            try:
                _sign_model_signing(path)
                manifest["sigstore"] = True
                manifest["model_signing"] = True
                print(f"G7: model-signing fallback ({cosign_err})")
            except Exception as ms_err:
                print(f"G7 FAIL: SIGNING_STRICT — cosign: {cosign_err}; model-signing: {ms_err}")
                return 1
        print("G7 PASS: Sigstore/cosign + manifest")
    else:
        print(f"G7 PASS: sha256 manifest digest={digest[:16]}...")

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    loaded = json.loads(manifest_path.read_text())
    if loaded["digest"] != digest:
        print("G7 FAIL: manifest digest mismatch")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
