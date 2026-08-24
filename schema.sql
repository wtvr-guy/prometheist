-- Append-only event log schema for the JIT persistent-memory agent prototype.
-- Application code only ever INSERTs into `events`; never UPDATE/DELETE.
-- This is currently an application-level invariant, not a database-level
-- tamper boundary. Database permissions/immutability enforcement belong to the
-- explicit v0.9 hardening/threat-model work and must not be inferred from this
-- schema alone.

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
-- Prometheist Memory Kernel derived state.
--
-- `events` remains the sole authoritative history. Everything below is
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

-- Memory Kernel v0.4 deterministic association projection. Association rows
-- are routing hints only; provenance points back to authoritative events.
CREATE TABLE IF NOT EXISTS memory_association_entries (
    association_id TEXT PRIMARY KEY,
    projection_version TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target TEXT NOT NULL,
    relationship TEXT NOT NULL,
    strength DOUBLE PRECISION NOT NULL,
    provenance_event_ids JSONB NOT NULL,
    required_cue_terms JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_association_entries_source
    ON memory_association_entries (projection_version, source_kind, source);

CREATE INDEX IF NOT EXISTS idx_memory_association_entries_target
    ON memory_association_entries (projection_version, target_kind, target);

-- ---------------------------------------------------------------------------
-- JIT Attention durable execution state.
--
-- Unlike derived memory projections, this is authoritative operational state:
-- it records what Prometheist is doing and what can be resumed after process
-- destruction. The transition journal is append-only at the application
-- layer; the task table is the current-state snapshot for fast restart.
-- ---------------------------------------------------------------------------

CREATE SEQUENCE IF NOT EXISTS attention_task_created_seq START WITH 1;

CREATE TABLE IF NOT EXISTS attention_tasks (
    task_id UUID PRIMARY KEY,
    task_key TEXT NOT NULL,
    created_seq BIGINT NOT NULL UNIQUE,
    parent_task_id UUID REFERENCES attention_tasks(task_id),
    criticality TEXT NOT NULL,
    service_class TEXT NOT NULL,
    interruption_policy TEXT NOT NULL,
    deadline TIMESTAMPTZ,
    required_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    dependency_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL,
    enqueued_cycle BIGINT NOT NULL DEFAULT 0,
    revision BIGINT NOT NULL DEFAULT 0,
    resumable_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_attention_tasks_status_priority
    ON attention_tasks (status, criticality, created_seq);

CREATE TABLE IF NOT EXISTS attention_task_transitions (
    transition_id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES attention_tasks(task_id) ON DELETE CASCADE,
    revision BIGINT NOT NULL,
    scheduler_cycle BIGINT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_attention_transitions_task_revision
    ON attention_task_transitions (task_id, revision);

CREATE TABLE IF NOT EXISTS attention_scheduler_state (
    scheduler_key TEXT PRIMARY KEY,
    cycle BIGINT NOT NULL DEFAULT 0,
    active_task_id UUID REFERENCES attention_tasks(task_id),
    pending_preemption_task_id UUID REFERENCES attention_tasks(task_id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
