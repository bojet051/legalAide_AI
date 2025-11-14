-- eLibrary Sync Module Tables

-- Sync jobs table (tracks each sync run)
CREATE TABLE IF NOT EXISTS sync_jobs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    total_checked INT DEFAULT 0,
    new_found INT DEFAULT 0,
    downloaded INT DEFAULT 0,
    failed INT DEFAULT 0,
    error_message TEXT,
    year_from INT,
    year_to INT
);

-- Pending decisions table (staging queue)
CREATE TABLE IF NOT EXISTS pending_decisions (
    id BIGSERIAL PRIMARY KEY,
    sync_job_id BIGINT REFERENCES sync_jobs(id) ON DELETE CASCADE,
    doc_id TEXT NOT NULL UNIQUE,
    docket_no TEXT,
    title TEXT,
    decision_date DATE,
    ponente TEXT,
    division TEXT,
    keywords TEXT,
    elibrary_url TEXT NOT NULL,
    pdf_path TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'downloading', 'downloaded', 'ingesting', 'ingested', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS sync_jobs_status_idx ON sync_jobs (status, started_at DESC);
CREATE INDEX IF NOT EXISTS pending_decisions_status_idx ON pending_decisions (status, created_at DESC);
CREATE INDEX IF NOT EXISTS pending_decisions_doc_id_idx ON pending_decisions (doc_id);
CREATE INDEX IF NOT EXISTS pending_decisions_sync_job_idx ON pending_decisions (sync_job_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER update_pending_decisions_updated_at
    BEFORE UPDATE ON pending_decisions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ANALYZE sync_jobs;
ANALYZE pending_decisions;
