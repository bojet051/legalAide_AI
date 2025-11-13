-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Cases table
CREATE TABLE IF NOT EXISTS cases (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT,
    title TEXT,
    court TEXT,
    promulgation_date DATE,
    full_text TEXT,
    source_file TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Case chunks table
CREATE TABLE IF NOT EXISTS case_chunks (
    id BIGSERIAL PRIMARY KEY,
    case_id BIGINT REFERENCES cases(id) ON DELETE CASCADE,
    section_type TEXT,
    chunk_index INT,
    chunk_text TEXT,
    token_count INT,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS case_chunks_case_id_idx ON case_chunks (case_id);
CREATE INDEX IF NOT EXISTS cases_court_date_idx ON cases (court, promulgation_date);

-- Vector index tuned for cosine distance
CREATE INDEX IF NOT EXISTS case_chunks_embedding_ivfflat
ON case_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

ANALYZE case_chunks;
