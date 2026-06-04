-- FORTRESS platform schema (v2)
-- audit_events, datasets, findings

CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor VARCHAR(128) NOT NULL,
  role VARCHAR(64),
  action VARCHAR(64) NOT NULL,
  resource_type VARCHAR(32),
  resource_id VARCHAR(256),
  model_name VARCHAR(128),
  model_version VARCHAR(32),
  status VARCHAR(16),
  details JSONB DEFAULT '{}',
  correlation_id UUID,
  prev_hash TEXT NOT NULL DEFAULT '',
  row_hash TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events (ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_model ON audit_events (model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events (action);

CREATE TABLE IF NOT EXISTS registry_datasets (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  sha256 TEXT,
  location TEXT,
  status TEXT NOT NULL DEFAULT 'registered',
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (name, version)
);

CREATE INDEX IF NOT EXISTS idx_registry_datasets_status ON registry_datasets (status);

CREATE TABLE IF NOT EXISTS findings (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  gate TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  asset_name TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium',
  rule TEXT NOT NULL,
  evidence JSONB DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'open',
  correlation_id UUID
);

CREATE INDEX IF NOT EXISTS idx_findings_gate ON findings (gate);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings (status);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  correlation_id UUID,
  element TEXT NOT NULL,
  gate TEXT,
  status TEXT NOT NULL,
  model_name TEXT,
  report_path TEXT,
  details JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_id ON pipeline_runs (run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_element ON pipeline_runs (element, status);
