-- Apply on existing Postgres volumes (init.sql only runs on first boot)
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
