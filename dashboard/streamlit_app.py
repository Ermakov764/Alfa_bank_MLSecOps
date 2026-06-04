"""FORTRESS Streamlit Security Center + CEO mock."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.attestation import load_signed, verify_attestation  # noqa: E402
from fortress.audit import fetch_events, fetch_findings, verify_chain  # noqa: E402
from fortress.mlflow_client import list_registered_models  # noqa: E402
from fortress.pipeline import fetch_pipeline_runs  # noqa: E402

st.set_page_config(page_title="FORTRESS Security Center", layout="wide")
st.title("FORTRESS — MLSecOps Security Center")

tab_overview, tab_pipeline, tab_model, tab_audit, tab_datasets, tab_findings, tab_chain, tab_gates, tab_deploy, tab_roles, tab_ceo = st.tabs(
    ["Overview", "Pipeline", "Model detail", "Audit log", "Datasets", "Findings",
     "Verify chain", "Gates", "Deploy", "Roles", "CEO Report"]
)

user = st.sidebar.selectbox("Current user", ["ds1", "mlsecops1", "de1", "ceo"])
roles = {"ds1": "ds", "mlsecops1": "mlsecops", "de1": "de", "ceo": "ceo"}
st.sidebar.markdown(f"**Role:** `{roles.get(user, 'unknown')}`")

with tab_overview:
    st.subheader("Registered models")
    try:
        models = list_registered_models()
        if models:
            rows = []
            for m in models:
                tags = m["tags"]
                gates = {k: tags.get(f"security.{k}", "—") for k in ["G0", "G3", "G5", "G7", "G8", "G10", "G11"]}
                rows.append({
                    "Model": m["name"],
                    "Version": m["version"],
                    "Stage": m["stage"],
                    "Scan": tags.get("security.scan_status", "?"),
                    **{f"G{k}": v for k, v in zip(["0", "3", "5", "7", "8", "10", "11"], gates.values())},
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("No models in MLflow yet. Run `make train-all` and `make demo`.")
    except Exception as e:
        st.warning(f"MLflow unavailable: {e}")

with tab_pipeline:
    st.subheader("CI pipeline transparency")
    run_filter = st.text_input("Run ID (optional)", "")
    try:
        runs = fetch_pipeline_runs(run_filter or None, 80)
        if runs:
            df = pd.DataFrame(runs)[
                ["created_at", "run_id", "element", "gate", "status", "model_name"]
            ]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No pipeline_runs yet. Run `make ci-pipeline` or `make demo`.")
    except Exception as e:
        st.warning(f"pipeline_runs: {e}")

    attest = ROOT / "artifacts/attestation/fortress-attestation.signed.json"
    if attest.exists():
        signed = load_signed(attest)
        ok, msg = verify_attestation(signed)
        if ok:
            st.success(f"Attestation valid: {msg}")
        else:
            st.error(f"Attestation: {msg}")
        with st.expander("Payload"):
            st.json(signed.get("payload", {}))
    else:
        st.warning("No attestation file. Run `make ci-pipeline`.")

with tab_model:
    st.subheader("Model passport (model_card)")
    st.json({
        "name": "credit-scoring-pd",
        "tier": "HIGH",
        "owner": "team-retail-ml",
        "purpose": "PD-scoring for retail credit",
        "note": "Edit models/*/model_card.yaml in Git",
    })

with tab_audit:
    st.subheader("Audit log")
    try:
        events = fetch_events(50)
        if events:
            df = pd.DataFrame(events)[["ts", "actor", "action", "status", "model_name", "resource_id"]]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No audit events yet.")
    except Exception as e:
        st.error(str(e))

with tab_datasets:
    st.subheader("Dataset registry")
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        url = os.getenv("DATABASE_URL", "postgresql://mlsecops:changeme@postgres:5432/mlsecops")
        conn = psycopg2.connect(url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name, version, status, sha256, created_at FROM registry_datasets ORDER BY id DESC")
        st.dataframe(pd.DataFrame(cur.fetchall()), use_container_width=True)
        conn.close()
    except Exception as e:
        st.warning(f"Datasets DB: {e}")

with tab_findings:
    st.subheader("Findings")
    try:
        findings = fetch_findings(50)
        if findings:
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.success("No open findings.")
    except Exception as e:
        st.error(str(e))

with tab_chain:
    st.subheader("Verify hash-chain")
    if st.button("Verify audit chain"):
        ok, msg = verify_chain()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

with tab_gates:
    st.subheader("Run security gates")
    profile = st.selectbox("Profile", ["fast", "strict"])
    if st.button("Run gates"):
        with st.spinner("Running..."):
            r = subprocess.run(
                ["bash", "scripts/run_gates.sh"],
                cwd=str(ROOT),
                env={**os.environ, "PROFILE": profile, "PYTHONPATH": str(ROOT)},
                capture_output=True,
                text=True,
            )
        st.code(r.stdout + r.stderr)
        st.write("Exit code:", r.returncode)

with tab_deploy:
    st.subheader("Deploy to Production")
    st.caption("Pre-deploy: code gates + attestation verify + G11 Trivy")
    role = roles.get(user, "ds")
    model_deploy = st.text_input("Model name", "credit-scoring-pd")
    version_deploy = st.text_input("Version", "1")

    if role != "mlsecops":
        st.warning("Only mlsecops may deploy.")
    else:
        if st.button("Run pre-deploy checks", type="primary"):
            with st.spinner("deploy_precheck..."):
                r = subprocess.run(
                    ["bash", "scripts/ci/deploy_precheck.sh"],
                    cwd=str(ROOT),
                    env={**os.environ, "PYTHONPATH": str(ROOT)},
                    capture_output=True,
                    text=True,
                )
            st.code(r.stdout + r.stderr)
            if r.returncode == 0:
                st.success("Pre-deploy OK — safe to promote")
            else:
                st.error("Pre-deploy failed")

        if st.button("Promote to Production (G12)"):
            cmd = [
                sys.executable,
                "scripts/promote_to_production.py",
                "--model", model_deploy,
                "--version", version_deploy,
                "--actor", user,
                "--approve",
            ]
            r1 = subprocess.run(
                cmd,
                cwd=str(ROOT),
                env={**os.environ, "PYTHONPATH": str(ROOT), "ACTOR_ROLE": "mlsecops"},
                capture_output=True,
                text=True,
            )
            r2 = subprocess.run(
                [c for c in cmd if c != "--approve"],
                cwd=str(ROOT),
                env={**os.environ, "PYTHONPATH": str(ROOT), "ACTOR_ROLE": "mlsecops"},
                capture_output=True,
                text=True,
            )
            st.code(r1.stdout + r1.stderr + r2.stdout + r2.stderr)
            st.write("Exit:", r2.returncode)

with tab_roles:
    st.markdown("""
| Action | ds | mlsecops | de | ceo |
|--------|:--:|:--------:|:--:|:---:|
| Train / register Staging | ✓ | ✓ | — | — |
| Promote Production | — | ✓ | — | — |
| View audit | ✓ | ✓ | ✓ | mock only |
    """)

with tab_ceo:
    st.balloons()
    st.markdown("# CEO Report")
    st.success("✅ All systems operational")
    st.success("✅ Zero critical incidents")
    st.success("✅ Compliance: SUPER")
    st.info("This page is intentionally a mock per ТЗ. Real status: **Security Center** tabs.")
