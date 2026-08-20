# Prometheist Artifact Store v0.1

## Purpose

Prometheist must be able to preserve a lifetime of system activity without relying on one monolithic log file, one LLM context window, or one opaque database representation.

The target storage model is therefore:

> **one immutable artifact identity per observable occurrence, plus rebuildable indexes that point to those artifacts.**

An artifact is the durable evidence that something happened. An index is a disposable mechanism for finding artifacts efficiently.

The first implementation milestone does **not** replace the existing PostgreSQL event store. It defines the storage contract and proves the representation against the Jordan Vale benchmark before production migration work begins.

## Core invariants

1. **Artifact granularity** — every meaningful occurrence receives its own artifact identity.
2. **Immutability** — committed artifacts are never edited in place.
3. **Evidence before interpretation** — source artifacts are authoritative; summaries, associations, embeddings, projections, and indexes are derived.
4. **No directory-scan retrieval** — runtime retrieval uses indexes/manifests, not recursive filesystem searches.
5. **Content integrity** — canonical artifact content is hashable and verifiable.
6. **Independent failure domains** — corruption or loss of one artifact must not corrupt an entire lifetime log.
7. **Rebuildability** — indexes and derived memory can be reconstructed from source artifacts.
8. **Causal traceability** — tool results, model responses, retrieval results, and other outputs link back to the artifact(s) that caused them.
9. **Bounded payloads** — small structured payloads may be inline; large/binary content is stored as content-addressed blobs.
10. **Storage-backend independence** — local filesystem, object storage, and replicated stores should implement the same logical artifact contract.

## What receives an artifact

At minimum, production Prometheist should artifactize:

- `USER_PROMPT`
- `AGENT_RESPONSE`
- `LLM_REQUEST`
- `LLM_RESPONSE`
- `AGENT_DECISION`
- `TOOL_CALL`
- `TOOL_RESULT`
- `MEMORY_QUERY`
- `MEMORY_QUERY_RESULT`
- `RETRIEVAL_TRACE`
- `SYSTEM_EVENT`
- `TRIGGERED_EVENT`
- `SCHEDULED_EVENT`
- `ERROR`
- `STATE_TRANSITION`
- `FILE_INGESTION`
- `GENERATED_FILE`
- `ASSOCIATION_DERIVATION`
- `PROJECTION_REBUILD`
- other future event types with explicit schemas

A tool call and its response are separate artifacts. A memory query and its result are separate artifacts. An LLM request and LLM response are separate artifacts. They are linked by correlation/causation metadata rather than nested into one opaque record.

## Logical layout

A human-readable local implementation may resemble:

```text
artifact-store/
├── artifacts/
│   └── 2026/
│       └── 08/
│           └── 20/
│               ├── USER_PROMPT/
│               │   └── <artifact-id>/
│               │       ├── envelope.json
│               │       └── envelope.sha256
│               ├── TOOL_CALL/
│               │   └── <artifact-id>/
│               ├── TOOL_RESULT/
│               │   └── <artifact-id>/
│               └── ...
├── blobs/
│   └── sha256/
│       └── ab/
│           └── cd/
│               └── <full-sha256>
├── manifests/
│   └── ...
└── indexes/
    └── ...
```

This hierarchy is an operational layout, **not** the retrieval algorithm.

The index database should contain efficient lookup keys such as artifact ID, event type, timestamps, global sequence, conversation/correlation IDs, entities, source, blob hashes, and derived retrieval features.

## Artifact envelope

`schemas/artifact-envelope-v1.schema.json` defines the initial transport/storage envelope.

Conceptually:

```json
{
  "artifact_id": "019c...",
  "artifact_type": "TOOL_RESULT",
  "schema_version": 1,
  "created_at": "2026-08-20T19:00:00Z",
  "source": "weather-tool",
  "conversation_id": "...",
  "correlation_id": "...",
  "causation_id": "...",
  "global_seq": 918274,
  "conversation_seq": 12,
  "parent_artifact_ids": ["..."],
  "payload": {
    "status": "ok"
  },
  "blob_refs": [
    {
      "sha256": "...",
      "media_type": "application/json",
      "size_bytes": 48122
    }
  ]
}
```

Not every artifact requires every optional field. Unknown facts should normally be omitted rather than encoded as arbitrary null fields.

### Identity

Production artifact IDs should be globally unique and time-sortable if practical (for example UUIDv7 once the runtime baseline supports it cleanly). The artifact ID is identity, not content authority.

### Time

At minimum the envelope records when Prometheist committed the artifact. Future versions may distinguish:

- occurrence time;
- observation time;
- ingestion time;
- commit time;
- externally supplied timestamps.

These clocks must remain semantically distinct.

### Causation

The following concepts should remain distinct:

- `conversation_id` — conversational grouping;
- `correlation_id` — one logical interaction/workflow;
- `causation_id` — the immediate artifact that caused this artifact;
- `parent_artifact_ids` — additional provenance/dependency relationships.

Example:

```text
USER_PROMPT
    |
    +--> MEMORY_QUERY
    |        |
    |        +--> MEMORY_QUERY_RESULT
    |
    +--> TOOL_CALL
    |        |
    |        +--> TOOL_RESULT
    |
    +--> LLM_REQUEST
             |
             +--> LLM_RESPONSE
                      |
                      +--> AGENT_RESPONSE
```

Each box is independently addressable evidence.

## Payloads and content-addressed blobs

Small JSON-compatible payloads may be stored inline in `payload`.

Large or binary material should be stored once by cryptographic content hash and referenced from artifacts:

```text
blobs/sha256/<first-2>/<next-2>/<full-hash>
```

Examples include:

- images;
- audio;
- video;
- PDFs;
- large tool responses;
- model-generated files;
- source documents;
- database exports.

A blob reference records at least:

- SHA-256;
- media type;
- byte length;
- optional logical filename.

The blob filename is derived from content, so duplicate content naturally de-duplicates.

## Canonicalization and integrity

JSON artifact hashes use a deterministic canonical serialization:

- UTF-8;
- sorted object keys;
- no insignificant whitespace;
- stable JSON scalar representation.

The current artifact hash itself should be stored outside the bytes being hashed (for example in an index or sidecar) to avoid self-reference.

The store may additionally maintain an ordered hash chain or checkpoint/Merkle structure for tamper evidence. Hash chains supplement per-artifact hashes; they do not justify combining many events into one failure-prone file.

## Atomic write protocol

A local filesystem writer should follow a crash-safe sequence:

1. generate deterministic metadata and artifact ID;
2. write referenced blobs to temporary paths;
3. flush/fsync blobs where supported;
4. verify blob hashes;
5. atomically rename blobs into content-addressed locations;
6. write the artifact envelope to a temporary path;
7. compute/verify its canonical hash;
8. flush/fsync the envelope where supported;
9. atomically rename the artifact into its committed path;
10. only then commit/update the index record.

The artifact store should prefer an **artifact exists but index is missing** failure over an **index claims evidence exists but the artifact never committed** failure.

## Recovery rules

On startup or explicit verification:

### Artifact exists, index missing

Re-index the artifact from its envelope. This is a recoverable condition.

### Index exists, artifact missing

Treat as integrity failure. Do not invent or silently replace evidence.

### Hash mismatch

Quarantine/flag the artifact and surface an integrity error. Do not repair by rewriting the artifact in place.

### Blob missing

Artifact remains present but incomplete. Mark the referenced content unavailable and preserve the envelope/provenance.

### Unreferenced blob

Do not immediately delete it. Orphan cleanup must use a grace period and a complete reference scan/checkpoint because a crash may have occurred between blob commit and artifact commit.

## Indexes are not authority

PostgreSQL is currently the prototype's authoritative event store. The artifact-store migration target changes that relationship:

```text
immutable artifacts / blobs
          |
          v
rebuildable metadata index
          |
          +--> lexical projection
          +--> association projection
          +--> vector projection (if later justified)
          +--> temporal indexes
          +--> entity indexes
```

The production index may still use PostgreSQL. What changes is that losing/rebuilding the index should not mean losing the source evidence.

Runtime memory retrieval should query indexes, obtain artifact IDs, and then recover/verify source artifacts as needed. It should **not** recursively scan millions of files for each query.

## Backup and replication

A production-grade store should support:

- at least two independent copies of authoritative artifacts;
- periodic hash verification;
- versioned/offline backup or immutable object-store retention;
- rebuildable index snapshots for speed, but not as the only backup;
- documented disaster-recovery procedures;
- explicit retention policy for sensitive data.

No single local directory, database, manifest, or disk should be the only copy of lifetime evidence.

## Deletion and correction

Immutability does not mean Prometheist can never represent correction or deletion policy.

Corrections should normally be new artifacts that supersede, retract, or qualify earlier evidence.

If legal/privacy requirements require physical deletion, the system should create an auditable tombstone/retention action where policy permits, remove targeted source/blob material, and ensure derived indexes are rebuilt without the deleted content.

The exact privacy/deletion model is deferred, but silent in-place editing is not acceptable.

## Jordan Vale v2 artifactized benchmark

`benchmarks/jordan_vale_v2/` is the first representation test.

It contains:

```text
jordan_vale_v2/
├── manifest.json
├── persona/
│   ├── profile.json
│   └── oracle.json
├── events/
│   ├── e001.json
│   └── ... e024.json
├── questions/
│   ├── q01.json
│   └── ... q18.json
└── associations/
    ├── a001.json
    ├── a002.json
    └── a003.json
```

The manifest explicitly names every artifact and stores its canonical SHA-256. The loader does not enumerate directories.

The v2 dataset is intentionally semantically equivalent to the current Jordan Vale v1 benchmark. Tests must prove:

- all 24 events materialize identically;
- all 18 evaluation queries materialize identically;
- persona/oracle content materializes identically;
- all three curated associations materialize identically;
- every manifest path and artifact ID is unique;
- every canonical hash verifies;
- the open-world blood-type fact remains absent from source memory.

This establishes an important separation:

> storage representation can evolve without changing memory semantics.

## Deferred from v0.1

This milestone does not yet:

- migrate `record_event()` to filesystem/object artifacts;
- implement distributed/object-store replication;
- replace PostgreSQL as the production index;
- implement automatic garbage collection;
- implement encryption-at-rest/key management;
- implement retention/deletion policy;
- store real LLM/tool traffic as artifacts.

Those require their own tests and migration plan after the artifact contract is proven.
