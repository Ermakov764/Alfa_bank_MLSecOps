# Alfa Bank MLSecOps — FORTRESS

Безопасная MLOps-платформа для кейса «ИБАНК»: MLflow registry, Security Gates **G0–G15**, pre-train **DATA** gate, audit hash-chain, 3 ML-модели, Streamlit Security Center.

Документация: [ТЗ.md](./ТЗ.md) · [ПЛАН_РЕАЛИЗАЦИИ.md](./ПЛАН_РЕАЛИЗАЦИИ.md) · [docs/threat_model.md](./docs/threat_model.md) · [docs/architecture.md](./docs/architecture.md)

## Quickstart (3 команды)

```bash
cp .env.example .env && docker compose up -d --build
make bootstrap && make train-all && make demo
```

Откройте:

- Streamlit Security Center: http://localhost:8501  
- MLflow: http://localhost:5000  
- M1 API: http://localhost:8001/docs  
- M2 API: http://localhost:8002/docs  
- M3 NLP: http://localhost:4000/health  

## Структура

| Путь | Назначение |
|------|------------|
| `fortress/` | audit (hash-chain), model_card, mlflow_client, security_profile |
| `gates/` | G0, G1, G3, G3b, G5–G11 wrappers |
| `scripts/` | bootstrap, ingest, data_gate, run_gates, register, promote, demo |
| `models/` | M1 scoring, M2 antifraud, M3 NLP cards + train |
| `services/` | FastAPI inference + LiteLLM proxy |
| `tests/fixtures/malicious/` | **Только демо** — evil pickle, typosquat, jailbreak |

## Make targets

```bash
make up              # docker compose up -d --build
make bootstrap       # MLflow experiments, wait for services
make train-all       # train M1 + M2 → ONNX
make security-fast   # G0, G3, G5
make security-strict # + G6–G11
make demo            # сценарии A–E (audit, promote, API, archive)
make test            # pytest smoke + audit chain
```

## Роли (Keycloak realm `mlsecops`)

| User | Role | Password (dev) |
|------|------|----------------|
| ds1 | ds | ds1pass |
| mlsecops1 | mlsecops | mlsecops1pass |
| de1 | de | de1pass |
| ceo | ceo | ceopass |

**Plan B:** если Keycloak не поднялся — `ACTOR_ROLE=mlsecops` для `promote_to_production.py`.

## Gates

- **DATA** — pre-train dataset (не G1 Semgrep!)
- **G12** — meta-gate в `scripts/promote_to_production.py`
- **G13/G14** — runtime на M3 / все API

## Демо-сценарии (`make demo`)

- **A:** `evil_model.pkl` → G5 fail → чистая ONNX → promote  
- **B:** ingest clean/poisoned CSV → train → register  
- **C:** curl predict M1/M2  
- **D:** archive → API 404  
- **E:** jailbreak blocked (G13), rate limit (G14)  

## CI

GitHub Actions: `.github/workflows/security.yml` — gitleaks, semgrep, pip-audit, model scan.

## Remote

```bash
git remote add origin git@github.com:Ermakov764/Alfa_bank_MLSecOps.git  # if needed
```

## Gates (no stubs in strict profile)

| Gate | Implementation |
|------|----------------|
| G8 | `scripts/gates/g8_validate.py` — ONNX holdout accuracy |
| G9 | `scripts/gates/g9_art.py` — ART FGSM if installed, else numpy adversarial probe |
| G10 | `scripts/gates/g10_llm_probe.py` — live jailbreak probes to M3 API |
| G11 | `gates/g11_trivy.sh` — Trivy via CLI or Docker |
| G7 | `scripts/gates/g7_sign_manifest.py` — SHA256 manifest |

```bash
make install-gates   # ART + deps
make security-strict
```

## Phase 2 (deferred)

SecAI registry, full Giskard scan, G15 drift, OAuth2 Proxy in front of MLflow.
