"""Verify model artifact SHA-256 against G7 manifest before inference."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(model_path: Path, *, require_sigstore: bool | None = None) -> tuple[bool, str]:
    """
    Re-check artifact digest vs manifest.json (G7 / pre-start policy).
    Returns (ok, message).
    """
    if not model_path.is_file():
        return False, f"artifact missing: {model_path}"
    manifest_path = model_path.parent / "manifest.json"
    if not manifest_path.exists():
        return False, f"manifest missing: {manifest_path}"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid manifest: {exc}"
    expected = str(manifest.get("digest", "")).strip()
    if not expected:
        return False, "manifest has no digest"
    actual = sha256_file(model_path)
    if actual != expected:
        return False, f"SHA mismatch: expected {expected[:16]}… got {actual[:16]}…"

    import os

    strict = require_sigstore
    if strict is None:
        strict = os.environ.get("SIGNING_STRICT", "").lower() == "true"
    if strict or manifest.get("sigstore"):
        import shutil

        if not shutil.which("cosign"):
            return False, "sigstore required but cosign binary missing in runtime image"
        from fortress.sigstore_sign import verify_blob

        ok, msg = verify_blob(model_path)
        if not ok:
            return False, f"sigstore verify failed: {msg}"
    return True, "ok"
