CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  retrieved_by TEXT NOT NULL,
  context TEXT NOT NULL,
  raw_content_ref TEXT NOT NULL,
  external_url TEXT
);

CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(id),
  source_excerpt TEXT NOT NULL,
  eval_status TEXT NOT NULL DEFAULT 'pending',
  eval_score REAL,
  eval_run_id TEXT
);

CREATE TABLE IF NOT EXISTS artefacts (
  id TEXT NOT NULL,
  version INTEGER NOT NULL,
  type TEXT NOT NULL,
  content TEXT NOT NULL,
  claim_ids TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  approved_by TEXT,
  approved_at TEXT,
  PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS report_sections (
  id TEXT NOT NULL,
  version INTEGER NOT NULL,
  report_id TEXT NOT NULL,
  section_type TEXT NOT NULL,
  content TEXT NOT NULL,
  claim_ids TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft_in_chat',
  committed_by TEXT,
  committed_at TEXT,
  PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT NOT NULL,
  version INTEGER NOT NULL,
  template_id TEXT NOT NULL,
  section_ids TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'in_progress',
  exported_at TEXT,
  export_ref TEXT,
  PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  target_version INTEGER,
  timestamp TEXT NOT NULL,
  eval_run_id TEXT,
  diff TEXT
);
