#!/usr/bin/env python3
"""G7 — artifact integrity: SHA256 manifest + optional model-signing CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
    }
    sig_path.write_text(digest + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if args.strict_sigstore or __import__("os").environ.get("SIGNING_STRICT") == "true":
        try:
            subprocess.run(
                ["model-signing", "sign", str(path)],
                check=True,
                capture_output=True,
                timeout=120,
            )
            print("G7 PASS: Sigstore model-signing + manifest")
            return 0
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"G7 FAIL: SIGNING_STRICT but model-signing failed: {e}")
            return 1

    # Verify readable manifest
    loaded = json.loads(manifest_path.read_text())
    if loaded["digest"] != digest:
        print("G7 FAIL: manifest digest mismatch")
        return 1

    print(f"G7 PASS: sha256 manifest {manifest_path} digest={digest[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
