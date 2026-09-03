# Immutable Artifact Journal

**Status:** constitutional architecture deep dive  
**Applies to:** canonical events, percept-to-response stage boundaries, stateless LLM invocations, inspection, interruption recovery, and database reconstruction

Prometheist maintains an independent immutable JSON artifact journal in addition to PostgreSQL. PostgreSQL remains the indexed operational store used for efficient retrieval, scheduling, and execution. It is not the only surviving representation of Prometheist's memory, cognition, or completed work.

The artifact journal exists for four reasons:

1. **Exact observability.** A developer must be able to inspect what each disposable worker received and produced without reconstructing it from logs or model behavior.
2. **Crash recovery.** A process may disappear after computing a result but before downstream operational state is committed. A durable stage artifact allows a replacement worker to rehydrate that result instead of repeating cognition or side effects.
3. **Disaster recovery.** Canonical event history must remain reconstructable when PostgreSQL is corrupted, lost, or deliberately recreated.
4. **Independent auditability.** Prometheist's causal history must remain inspectable even when the primary database or scheduler tables are unavailable.

This design extends the system-continuity, append-only evidence, disposable-worker recovery, causal-provenance, local-first, and user-sovereignty rules in the Constitution.

## 1. Persistence domains

Prometheist currently has two durable persistence domains.

### 1.1 PostgreSQL

PostgreSQL is the active indexed representation. It provides:

- canonical `events` rows;
- conversations and total event ordering;
- memory indexes and derived projections;
- attention/scheduler state;
- worker assignments, claims, checkpoints, and results;
- interaction bindings and working state.

PostgreSQL is optimized for querying and coordinated operational mutation. Its loss must not imply the loss of all cognitive history.

### 1.2 Filesystem artifact journal

The independent artifact root defaults to:

```text
.prometheist/artifacts/
```

and may be moved with:

```text
PROMETHEIST_ARTIFACT_ROOT=<path>
```

`.prometheist/` is fully ignored by Git. Runtime artifacts may contain user prompts,
retrieved memories, system prompts, model outputs, tool results, and other sensitive
evidence, and ordinary development runs must not dirty the repository or publish that
content accidentally. Evidence intended for review is deliberately selected,
sanitized where appropriate, and copied to `docs/audits/evidence/` or
`benchmarks/results/` with its provenance and tested revision recorded.

The journal contains two classes of records:

```text
artifacts/
  events/
    <event-id>.json
    <event-id>.commit.json

  interactions/
    <interaction-id>/
      000001-<artifact-id>.json
      000002-<artifact-id>.json
      000003-<artifact-id>.json
      ...
      00000N-<artifact-id>.json
```

The exact filenames are presentation details. Artifact IDs, semantic artifact keys, hashes, types, interaction IDs, and sequence numbers are authoritative identifiers inside each document.

Interaction filenames deliberately use the bounded deterministic artifact UUID rather than concatenating the full semantic artifact key into the filesystem name. The full semantic key remains inside the JSON envelope and remains the idempotency identity. This keeps ordinary paths portable on Windows and other filesystems without discarding semantic identity or provenance.

## 2. Canonical event mirroring

Every canonical event written through `event_store.record_event` is independently mirrored to JSON.

A new event follows this durability order:

```text
allocate deterministic/explicit event identity
        ↓
lock conversation sequence in PostgreSQL transaction
        ↓
atomically write + fsync EVENT_RECORD JSON
        ↓
insert event row and advance conversation sequence
        ↓
COMMIT PostgreSQL transaction
        ↓
atomically write + fsync EVENT_DATABASE_COMMIT JSON
```

The first artifact contains the semantic event record:

- event ID;
- conversation ID;
- correlation ID;
- conversation sequence;
- event type;
- source;
- exact JSON payload;
- payload text when present;
- content hash.

The second artifact records database-commit metadata:

- event ID;
- semantic record hash;
- global sequence;
- conversation sequence;
- database-created timestamp;
- schema version;
- commit hash.

This two-record protocol distinguishes an event that was durably journaled before a crash from an event known to have committed to PostgreSQL.

A crash may therefore produce a semantic event artifact without a corresponding database-commit artifact. That is a recoverable state. A committed new PostgreSQL event should not exist without its semantic JSON record because the semantic artifact is written first.

Deterministic retries repair missing commit artifacts and fail closed if an existing JSON artifact conflicts with the retry's semantic identity.

## 3. Interaction artifact chain

Every user-prompt interaction receives its own append-only artifact chain.

Each artifact envelope contains at least:

```json
{
  "artifact_schema_version": 1,
  "artifact_id": "...",
  "artifact_key": "...",
  "artifact_type": "...",
  "interaction_id": "...",
  "conversation_id": "...",
  "correlation_id": "...",
  "task_id": "...",
  "assignment_id": "...",
  "stage": "...",
  "producer": "...",
  "journal_sequence": 1,
  "created_at": "...",
  "previous_artifact_id": null,
  "previous_artifact_hash": null,
  "payload_hash": "...",
  "artifact_hash": "...",
  "payload": {}
}
```

Artifacts after the first point to the immediately preceding artifact ID and hash. `prometheist verify` recomputes payload and envelope hashes and checks chain continuity.

The interaction chain currently records:

- the original percept;
- each completed v2 architectural stage result;
- stage errors;
- each exact v2 stateless LLM invocation envelope;
- the exact pre-cognitive aperture/disposition and execution plan as part of the pre-cognitive stage artifact;
- exact work/tool results as part of the work stage artifact;
- the exact Composer-approved memory package and Adaptive Recall outcome as part of the Compose stage artifact;
- the exact final responder output;
- persistent-result state;
- a final-disposition manifest for completed interactions.

Because the stage result is the same structured output used to complete the durable worker claim, the artifact is not a later summary of what the worker probably saw. It is the checkpointed boundary object itself.

### 3.1 Exact stateless LLM invocation artifacts

Every LLM call made by the live v2 user-prompt worker is independently journaled. The `LLM_INVOCATION` payload includes:

- architectural stage;
- worker claim ID and invocation index;
- semantic call kind;
- configured model;
- backend base URL;
- exact system prompt;
- exact user/context prompt;
- exact structured-output JSON schema;
- generation token cap;
- effective generation temperature;
- normalized constrained model output when the call succeeds;
- exception type/message when the call fails.

For the final responder this includes the resolved Prometheist personality/identity system prompt and the exact response-context payload. For the Composer it includes the exact memory evidence text presented for sufficiency judgment. For the pre-cognitive worker it includes the exact orientation-memory and capability-catalog text.

This means debugging does not need to infer what a model saw from its answer. The actual stateless invocation contract is part of the hash-linked interaction history.

Invocation artifacts are causal evidence, not recovery substitutes for a completed architectural stage. Stage recovery uses a completed `STAGE_RESULT` artifact because downstream validation/transformation may occur after an individual raw model call. Failed or superseded model attempts remain visible in history.

## 4. Artifact-before-terminal ordering

For a disposable worker stage, the required order is:

```text
load fresh durable inputs
        ↓
compute stage result
        ↓
atomically write + fsync STAGE_RESULT artifact
        ↓
complete durable worker claim/result in PostgreSQL
        ↓
allow downstream stage
```

LLM invocation artifacts are written during stage computation, before the stage-result artifact.

A stage is therefore recoverable if the process disappears after the artifact write but before the PostgreSQL worker result commits.

When a replacement worker claims that stage, it checks for a valid stage-result artifact first. If one exists, it uses the exact stored output and output references to complete the database worker result. It does **not** repeat the LLM invocation, retrieval decision, tool call, or other stage computation.

This ordering is especially important for expensive or externally consequential work. Existing worker idempotency/effect policy remains authoritative for side-effect safety; the artifact journal complements rather than replaces it.

## 5. Final disposition

A completed interaction ends with a `FINAL_DISPOSITION` artifact.

The final disposition is a compact manifest, not a duplicate transcript. It records:

- completed status;
- last completed architectural stage;
- whether a response was required;
- the resulting response text when applicable;
- references, types, hashes, sequence numbers, and stages for all prior interaction artifacts.

The manifest makes the entire percept-to-outcome chain discoverable from one terminal artifact while preserving detailed data in the preceding immutable records, including every v2 LLM invocation used to produce that outcome.

An interrupted interaction has no final disposition. Its partial chain is intentional durable state, not garbage.

## 6. Interruption recovery

The CLI exposes artifact-backed recovery:

```powershell
uv run prometheist recover --latest
```

or:

```powershell
uv run prometheist recover --interaction-id <uuid>
```

Recovery verifies the artifact chain first.

If operational interaction state still exists in PostgreSQL, Prometheist continues that interaction. For each architectural stage:

1. an existing PostgreSQL worker result is accepted;
2. otherwise an existing stage artifact is rehydrated into the durable worker result;
3. otherwise the first genuinely unfinished stage is executed by a fresh worker.

If the final database stage exists but the final-disposition write itself was interrupted, recovery creates the missing final disposition after completing normal task finalization.

## 7. Database-loss recovery

The artifact journal is designed to survive recreation of PostgreSQL.

After creating an empty database and applying the current schema, canonical event history can be restored with:

```powershell
uv run prometheist restore-events
```

This operation:

- verifies event artifact hashes;
- inserts missing conversations and events;
- preserves committed global/conversation sequence numbers where commit artifacts exist;
- assigns a safe new global sequence to a semantic artifact that survived before its original DB commit;
- repairs conversation next-sequence counters;
- advances the PostgreSQL global event sequence;
- fails closed on conflicting existing rows.

After event restoration, an interrupted interaction can be resumed from its filesystem artifacts. If its operational interaction/scheduler rows were lost, Prometheist reconstructs the deterministic interaction identity from:

- the original conversation ID;
- the original correlation ID;
- the original user percept.

It then creates fresh operational execution state and walks the artifact chain. Previously completed stage results are rehydrated rather than regenerated.

The intended disaster sequence is therefore:

```text
artifact journal survives
        ↓
recreate PostgreSQL database
        ↓
apply schema.sql and normal permissions
        ↓
prometheist restore-events
        ↓
prometheist recover --latest   # if an interaction was incomplete
        ↓
rebuild disposable/derived projections as required
```

The artifact journal does not make every derived index automatically reconstruct itself yet. Canonical events are sufficient source evidence for those projections to be rebuilt by their own deterministic/replay mechanisms.

## 8. Inspection without PostgreSQL

Artifact inspection and integrity verification do not require a working database.

Latest interaction:

```powershell
uv run prometheist inspect --latest
```

Specific interaction:

```powershell
uv run prometheist inspect --interaction-id <uuid>
```

Verify hash-chain integrity:

```powershell
uv run prometheist verify --latest
```

or:

```powershell
uv run prometheist verify --interaction-id <uuid>
```

This allows response diagnosis even when PostgreSQL or scheduler state is offline. In particular, `inspect` exposes the exact memory packet and exact final-responder LLM invocation that produced a suspicious answer.

## 9. Storage policy

Artifact redundancy is intentional. Storage efficiency must not silently erase exact causal evidence or eliminate the independent recovery copy.

Current policy:

- artifacts are immutable;
- ordinary retention/compaction does not delete them;
- the artifact root is user-controlled;
- `.prometheist/` is ignored in full and must not be used as a Git evidence directory;
- deliberately shared audit/benchmark evidence is copied to an explicit reviewed
  location with provenance and revision metadata; the runtime originals remain local;
- future cold-storage compression may transform old `.json` records to a content-preserving representation such as `.json.zst`, provided hashes/identity remain verifiable and the transformation is reversible;
- large binary objects should eventually use content-addressed blob storage, with JSON artifacts referring to their hashes rather than embedding arbitrary binary payloads.

Explicit user-directed erasure remains a separate user-sovereignty operation and must not be confused with automatic compaction.

## 10. Current scope and future hardening

The current implementation establishes independent durability for:

- canonical append-only events;
- the live v2 user-prompt percept-to-response stage chain;
- exact stateless LLM invocation envelopes for the v2 semantic roles;
- stage result rehydration;
- final disposition manifests;
- event-store reconstruction;
- interaction continuation after operational-state loss.

Further hardening should extend the same boundary rule to additional long-running/non-conversational task families as they become live, journal exact external-effect request envelopes alongside their results, add content-addressed storage for large external artifacts, add bulk backup/restore commands, and test deliberate power-loss/fsync fault cases on the native deployment environment.

The principle is broader than the current implementation: **if a meaningful cognitive or operational boundary would matter for explanation, replay, recovery, or reconstruction, its exact durable artifact must not exist only inside a disposable process or a single database.**
