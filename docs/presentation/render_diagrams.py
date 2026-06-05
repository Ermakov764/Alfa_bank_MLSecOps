#!/usr/bin/env python3
"""Render Mermaid diagrams from docs/presentation/mermaid/ to PNG (source: docs/architecture*.md)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MMD_DIR = ROOT / "mermaid"
OUT_DIR = ROOT / "diagrams"
CONFIG = ROOT / "mermaid-config.json"

# presentation slide key -> source .mmd (synced with architecture.md / architecture_full.md)
DIAGRAMS = {
    "01_trust_zones": "01_trust_zones.mmd",
    "02_compose_architecture": "02_compose_architecture.mmd",
    "03_security_gates_layers": "03_security_gates_layers.mmd",
    "04_sequence_flow": "04_sequence_flow.mmd",
    "05_cicd_pipeline": "05_cicd_pipeline.mmd",
    "06_model_lifecycle": "06_model_lifecycle.mmd",
    "07_demo_scenarios": "07_demo_scenarios.mmd",
    "08_visibility_er": "08_visibility_er.mmd",
    "09_threats_mapping": "09_threats_mapping.mmd",
    "10_rbac": "10_rbac.mmd",
    "11_analogs_market": "11_analogs_market.mmd",
}


def _find_mmdc() -> list[str]:
    local = ROOT / "node_modules/.bin/mmdc"
    if local.exists():
        return [str(local)]
    return ["npx", "--yes", "@mermaid-js/mermaid-cli@11.4.0"]


def render_one(mmdc: list[str], src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    is_sequence = "sequenceDiagram" in text
    is_state = "stateDiagram" in text
    is_er = "erDiagram" in text
    w, h, scale = "1920", "1080", "2"
    if is_sequence:
        w, h, scale = "2800", "1600", "3"
    elif is_state or is_er:
        w, h, scale = "2200", "1400", "2.5"
    cmd = [
        *mmdc,
        "-i", str(src),
        "-o", str(dst),
        "-b", "white",
        "-w", w,
        "-H", h,
        "-s", scale,
    ]
    if CONFIG.exists():
        cmd.extend(["-c", str(CONFIG)])
    subprocess.run(cmd, check=True)


def main() -> int:
    mmdc = _find_mmdc()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # remove stale matplotlib diagrams
    for old in OUT_DIR.glob("*.png"):
        if old.name not in {f"{k}.png" for k in DIAGRAMS}:
            old.unlink(missing_ok=True)

    print("Rendering Mermaid diagrams (from documentation):")
    for key, filename in DIAGRAMS.items():
        src = MMD_DIR / filename
        if not src.exists():
            print(f"  SKIP missing {src}", file=sys.stderr)
            continue
        dst = OUT_DIR / f"{key}.png"
        render_one(mmdc, src, dst)
        print(f"  {dst}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
