-- Semantic derived-state schema for Prometheist v0.6.
--
-- Apply this after schema.sql on installations that have pgvector available.
-- The authoritative event ledger remains unchanged; every row here is disposable
-- and can be regenerated from `events` with the configured embedding provider.
--
-- The earlier experimental `memory_semantic_entries` table is intentionally left
-- untouched for non-destructive compatibility. Production v0.6 uses the explicit
-- schema below so provider/model/dimension identity is part of every projection.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_semantic_projection_entries (
    embedding_provider TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions = 1536),
    projection_version TEXT NOT NULL,
    source_event_id UUID NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    source_global_seq BIGINT NOT NULL,
    source_hash TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (
        embedding_provider,
        embedding_model,
        dimensions,
        projection_version,
        source_event_id
    )
);

CREATE INDEX IF NOT EXISTS idx_memory_semantic_projection_model_seq
    ON memory_semantic_projection_entries (
        embedding_provider,
        embedding_model,
        dimensions,
        projection_version,
        source_global_seq DESC
    );

-- Deliberately no approximate ANN index. Exact cosine search has no vector-index
-- approximation error and is the v0.6 reference behavior. HNSW/IVFFlat remain
-- future scale optimizations that must earn inclusion through benchmark evidence.
