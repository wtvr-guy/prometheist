-- Optional semantic derived-state schema for Prometheist.
--
-- Apply this after schema.sql on installations that have pgvector available.
-- The authoritative event ledger remains unchanged; every row here is disposable
-- and can be regenerated from `events` with the configured embedding model.
-- Devices without pgvector continue to use the deterministic lexical/associative
-- routes defined by the base schema.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_semantic_entries (
    embedding_model TEXT NOT NULL,
    projection_version TEXT NOT NULL,
    source_event_id UUID NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    source_global_seq BIGINT NOT NULL,
    source_hash TEXT NOT NULL,
    embedding vector NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (embedding_model, projection_version, source_event_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_semantic_entries_model_seq
    ON memory_semantic_entries (
        embedding_model,
        projection_version,
        source_global_seq DESC
    );

-- Deliberately no approximate ANN index yet. pgvector's exact nearest-neighbor
-- scan provides perfect vector-search recall and is appropriate for the current
-- prototype/benchmark scale. HNSW or IVFFlat should be introduced only after a
-- measured scale bottleneck justifies trading some recall for speed.
