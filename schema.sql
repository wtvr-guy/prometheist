-- Append-only event log schema for the JIT persistent-memory agent prototype.
-- Application code only ever INSERTs into `events`; never UPDATE/DELETE.

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_event_seq INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
    correlation_id UUID NOT NULL,
    global_seq BIGSERIAL,
    conversation_seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL,
    payload_text TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_events_conversation_seq
    ON events (conversation_id, conversation_seq);

CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type);

CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at);

-- Deterministic keyword search stand-in for future embedding-based semantic retrieval.
CREATE INDEX IF NOT EXISTS idx_events_payload_text_fts
    ON events USING GIN (to_tsvector('english', coalesce(payload_text, '')));

-- ---------------------------------------------------------------------------
-- Prometheist Memory Kernel v0.2 derived state.
--
-- `events` remains the sole authoritative history.  Everything below is
-- disposable: it can be deleted and regenerated solely from `events`.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS event_integrity (
    event_id UUID PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    global_seq BIGINT NOT NULL UNIQUE,
    previous_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_integrity_global_seq
    ON event_integrity (global_seq);

CREATE TABLE IF NOT EXISTS memory_projection_runs (
    run_id UUID PRIMARY KEY,
    projection_name TEXT NOT NULL,
    projection_version TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    source_event_count BIGINT NOT NULL,
    entry_count BIGINT NOT NULL,
    projection_digest TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_projection_runs_name_version
    ON memory_projection_runs (projection_name, projection_version, started_at DESC);

CREATE TABLE IF NOT EXISTS memory_projection_entries (
    projection_name TEXT NOT NULL,
    projection_version TEXT NOT NULL,
    source_event_id UUID NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    source_global_seq BIGINT NOT NULL,
    source_hash TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (projection_name, projection_version, source_event_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_projection_entries_source_seq
    ON memory_projection_entries (projection_name, projection_version, source_global_seq DESC);

CREATE INDEX IF NOT EXISTS idx_memory_projection_entries_data
    ON memory_projection_entries USING GIN (data);
