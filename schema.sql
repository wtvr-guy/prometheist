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
