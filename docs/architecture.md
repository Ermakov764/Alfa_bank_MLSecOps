# Архитектура FORTRESS — «Безопасная MLOps-система»

Версия: 1.1 · Профиль: **FORTRESS** (синхронизировано с compose, июнь 2026)  
Связанные документы: [ПЛАН_РЕАЛИЗАЦИИ.md](../ПЛАН_РЕАЛИЗАЦИИ.md), [ТЗ.md](../ТЗ.md)

---

## 1. Контекст (C4 — уровень системы)

```mermaid
flowchart LR
  subgraph actors [Участники]
    DS[Data Scientist]
    MSO[MLSecOps]
    DE[Data Engineer]
    EXT[Внешние источники]
  end

  subgraph fortress [FORTRESS Platform]
    SYS[Безопасная MLOps-система]
  end

  DS -->|train, register| SYS
  MSO -->|gates, approve, promote| SYS
  DE -->|read registry, audit| SYS
  EXT -->|HF / Kaggle модели и данные| SYS
```

**Назначение системы:** автоматизировать ML-жизненный цикл с встроенными Security Gates, реестром моделей, audit trail и RBAC — без ручных чеклистов в Confluence.

---

## 2. Контейнеры (Docker Compose + CI)

```mermaid
flowchart TB
  subgraph host [Ноутбук / demo host]
    subgraph cli [bin/fortress / fortress.ps1 / Makefile]
      FORT[fortress container profile tools]
      GHA[GitHub Actions ci-pipeline.yml]
    end

    subgraph compose [docker compose]
      direction TB

      subgraph auth [Identity]
        KC[Keycloak :8080]
        OAUTH[oauth2-proxy-mlflow host :5000]
      end

      subgraph data_plane [Data plane]
        PG[(PostgreSQL :5432)]
        MINIO[MinIO S3 :9000]
      end

      subgraph ml [ML platform]
        MLF[mlflow internal]
      end

      subgraph inference [Production inference]
        API1[api-scoring :8001]
        API2[api-antifraud :8002]
        LIT[litellm :4000 G13 G14 inline]
      end

      UI[Streamlit Security Center :8502]
    end

    GIT[Git repo]
  end

  GIT --> FORT
  FORT -->|pipeline gates demo train| MLF
  FORT -->|audit findings| PG
  GHA -.->|gates train sign| PG

  DS_USER[DS / MLSecOps browser] --> KC
  KC --> OAUTH
  OAUTH --> MLF
  DS_USER --> UI

  MLF --> PG
  MLF --> MINIO
  UI --> PG
  UI --> MLF

  API1 & API2 --> MLF
  API1 & API2 --> PG
  LIT --> PG

  API1 & API2 & LIT -->|только Production| MINIO
```

| Контейнер | Порт (host) | Роль |
|-----------|-------------|------|
| PostgreSQL | 5432 | `audit_events`, `datasets`, `findings`, `pipeline_runs`, backend MLflow |
| MinIO | 9000/9001 | Артефакты моделей, датасеты |
| Keycloak | 8080 | RBAC: ds, mlsecops, de, product |
| oauth2-proxy-mlflow | 5000 | SSO перед MLflow UI (upstream mlflow:5000) |
| mlflow | — (внутри сети) | Model Registry, stages, теги `security.*` |
| api-scoring | 8001 | M1 inference + G14 |
| api-antifraud | 8002 | M2 inference + G14 |
| litellm | 4000 | M3 intent API + G13 regex + G14 |
| dashboard | 8502 | Streamlit Security Center |
| fortress | — (profile tools) | CLI: train, pipeline, gates, demo, pytest |

---

## 3. Зоны доверия и поток gates

```mermaid
flowchart LR
  subgraph Z1 [DEV]
    NB[Notebook / IDE]
    REPO[Git]
  end

  subgraph Z2 [CI]
    PR[PR / push]
    GF[G0 G1 G3 G3b]
  end

  subgraph Z3 [REGISTRY]
    DATA[DATA gate]
    REG[MLflow + MinIO]
    GR[G5 G6 G7 G8 G9 G10]
    G12[G12 promote policy]
    AUD[(Postgres audit)]
  end

  subgraph Z4 [PROD runtime]
    API[FastAPI / LiteLLM]
    RT[G13 G14]
  end

  NB --> REPO
  REPO --> PR
  PR --> GF
  GF -->|pass| DATA
  DATA -->|available dataset| REG
  REG --> GR
  GR --> G12
  G12 -->|Production only| API
  API --> RT

  GF & DATA & GR & G12 & RT -.->|log + findings| AUD
```

---

## 4. Жизненный цикл модели (states)

```mermaid
stateDiagram-v2
  [*] --> DatasetRegistered: ingest CSV
  DatasetRegistered --> DatasetAvailable: DATA pass
  DatasetRegistered --> DatasetQuarantine: DATA fail

  DatasetAvailable --> Training: fortress train
  Training --> Staging: register_model + gates

  Staging --> Staging: gate failed / findings
  Staging --> Approved: mlsecops Human Approve tier HIGH
  Staging --> Production: G12 promote
  Approved --> Production: G12 promote

  Production --> Serving: API load model
  Serving --> Serving: G13 G14 runtime

  Production --> Archived: retire demo D
  Archived --> [*]: API 404
```

| MLflow stage | Условие перехода |
|--------------|------------------|
| `None` / experiment | train завершён |
| `Staging` | register + обязательные gate-теги |
| `Production` | G12 + mlsecops (+ Approve если tier HIGH) |
| `Archived` | вывод из эксплуатации |

---

## 5. Сквозной поток: от датасета до predict

```mermaid
sequenceDiagram
  autonumber
  participant DS as DS
  participant DATA as DATA gate
  participant PG as Postgres
  participant TR as train script
  participant MLF as MLflow
  participant G as Gates G0-G11
  participant MSO as MLSecOps
  participant API as Inference API

  DS->>DATA: ingest train_clean.csv
  DATA->>PG: dataset available + audit
  DS->>TR: fortress train
  TR->>MLF: log metrics, artifact ONNX
  DS->>G: fortress pipeline / gates
  G->>MLF: tags security.G*=passed
  G->>PG: findings if fail
  DS->>MLF: register Staging + model_card
  MSO->>MSO: Approve tier HIGH
  MSO->>MLF: G12 → Production
  MSO->>PG: model.promoted
  DS->>API: POST /predict
  API->>MLF: resolve Production URI
  API->>PG: api.inference
  API-->>DS: 200 score
```

---

## 6. Модель данных (логическая схема)

```mermaid
erDiagram
  audit_events ||--o{ findings : "correlation_id"
  datasets ||--o{ audit_events : "resource"
  MLFLOW_MODEL ||--o{ audit_events : "model_name"

  audit_events {
    bigint id PK
    timestamptz ts
    string actor
    string action
    string status
    jsonb details
    string prev_hash
    string row_hash
  }

  datasets {
    bigint id PK
    string name
    string version
    string sha256
    string status
  }

  findings {
    bigint id PK
    string gate
    string asset_type
    string asset_name
    string severity
    string status
    jsonb evidence
  }

  MLFLOW_MODEL {
    string name
    string version
    string stage
    tags security_tags
    tags model_card
  }
```

**Источник правды по версиям:** MLflow.  
**Источник правды по действиям и сработкам:** PostgreSQL.

---

## 7. Security Gates на одной схеме

```mermaid
flowchart TB
  subgraph code [Код и зависимости]
    G0[G0 gitleaks]
    G1[G1 Semgrep]
    G3[G3 pip-audit]
    G3b[G3b guarddog]
  end

  subgraph dataset [Данные]
    DATA[DATA pre-train]
  end

  subgraph artifact [Артефакт модели]
    G5[G5 ModelAudit]
    G6[G6 format policy]
    G7[G7 signing]
  end

  subgraph quality [ML quality]
    G8[G8 holdout + opt Giskard]
    G9[G9 perturbation + opt ART]
    G10[G10 live probes + opt Garak]
  end

  subgraph infra [Инфра]
    G11[G11 Trivy]
  end

  subgraph release [Релиз]
    G12[G12 registry policy]
  end

  subgraph runtime [Runtime]
    G13[G13 LLM-Guard]
    G14[G14 rate limit]
  end

  code --> artifact
  dataset --> artifact
  artifact --> quality
  quality --> release
  infra --> release
  release --> runtime
```

---

## 8. RBAC (кто к чему подключается)

```mermaid
flowchart LR
  subgraph users [Keycloak realm mlsecops]
    u_ds[ds]
    u_mso[mlsecops]
    u_de[de]
  end

  subgraph resources [Ресурсы]
    MLF_UI[MLflow UI via oauth2-proxy]
    ST[Streamlit :8502]
    PROM[promote / deploy]
    APIS[Inference APIs]
  end

  u_ds -->|train, staging| MLF_UI
  u_ds -->|read, deploy CI| ST
  u_ds -.-x|deny| PROM

  u_mso -->|all + approve| MLF_UI
  u_mso -->|promote deploy| PROM
  u_mso -->|full| ST

  u_de -->|read only| MLF_UI
  u_de -->|read audit| ST

  APIS -->|service account| MLF_UI
```

---

## 9. Три модели в архитектуре

```mermaid
flowchart TB
  subgraph M1 [M1 credit-scoring-pd]
    T1[train tabular]
    A1[api-scoring :8001]
    T1 -->|ONNX| A1
  end

  subgraph M2 [M2 transaction-antifraud]
    T2[train CatBoost]
    A2[api-antifraud :8002]
    T2 -->|cbm/ONNX| A2
  end

  subgraph M3 [M3 support-nlp]
    T3[train TF-IDF + LogReg]
    L3[litellm :4000]
    T3 -->|joblib pipeline| L3
    G13[G13 regex guard inline]
    G13 --> L3
  end

  MLF[(MLflow Registry)]
  T1 & T2 & T3 --> MLF
  A1 & A2 & L3 --> MLF
```

| ID | API | Обязательные gates (кроме общих G0–G7, G11, G12) |
|----|-----|--------------------------------------------------|
| M1 | :8001 | DATA, G8, G9 |
| M2 | :8002 | DATA, G8, G9 |
| M3 | :4000 | G10, G13 runtime |

---

## 10. Фаза 2 (SecAI) — будущее расширение

```mermaid
flowchart LR
  MLF[MLflow experiments]
  SECAI[SecAI ai-model-registry]
  PROD[Production APIs]

  MLF -->|register candidate| SECAI
  SECAI -->|state trusted| PROD
  SECAI -->|quarantined / revoked| BLOCK[Block deploy]
```

В MVP **SecAI не используется** — trust boundary = G12 + MLflow stages.

---

*Диаграммы в формате Mermaid — рендерятся в GitHub, GitLab, VS Code/Cursor и на [mermaid.live](https://mermaid.live).*
