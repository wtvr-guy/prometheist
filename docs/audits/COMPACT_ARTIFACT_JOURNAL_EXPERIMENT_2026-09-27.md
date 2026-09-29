# Compact artifact journal experiment — 2026-09-27

Branch: `experiment/compact-artifact-journal`, based on `self-memory-system-v1`.
Input: supplied `latest-benchmark(1).zip` (SELF-MEMORY-001 run dated September 26).
The ZIP is a baseline observation, not a new model benchmark on this branch.

## Baseline inventory

| Class | Files | Policy |
| --- | ---: | --- |
| Canonical `EVENT_RECORD` | 467 | Retain: exact admitted history and derived records. |
| `EVENT_DATABASE_COMMIT` | 467 | Retain: commit identity and ordering for recovery after database loss. |
| `PERCEPT` | 5 | Retain: interaction input boundary. |
| `STAGE_RESULT` | 33 | Retain: durable terminal worker result. |
| `STAGE_ERROR` | 1 | Retain: failed terminal worker outcome. |
| `FINAL_DISPOSITION` | 4 | Retain: completed interaction manifest. |
| `LLM_INVOCATION` | 35 | Retain: exact prompt, model contract, raw output, and diagnostic evidence, including attempts before a crash. |
| `LLM_VALIDATION` / `INVALID` | 7 | Retain: causal explanation for rejected output and retries. |
| `LLM_VALIDATION` / `VALID` | 28 | Omit in the new policy; acceptance is represented by a committed stage result. |
| Run result and manifests | 3 | Retain: benchmark receipts and verification. |

The supplied ZIP contains 1,050 files, including 113 interaction-journal records.
With identical calls and events, this policy would produce 1,022 files and 85
interaction-journal records: 28 fewer, or 25% fewer interaction records and 2.7%
fewer total files. This is a projection, not an observed result. Event record/commit
pairs dominate the total; removing them without an independently durable replacement
would compromise the Constitution's lossless-history and replay requirements.

## Behavior

Normal parsing and schema validation run in memory. The model invocation remains
durable before parsing. A failure creates a linked `LLM_VALIDATION` record. Success
creates no validation record; the worker publishes the same typed stage result as
before. A crash between the invocation and stage result leaves a partial chain;
no auditor may interpret that invocation as a committed successful stage.

The mechanism experiment uses report schema 5 for new artifact-backed runs. Its
verifier checks every invocation's transport diagnostics and links for all failure
records. Earlier schema 4 reports continue to require one validation per invocation.
The verifier checks the manifest's exact file inventory and SHA-256 values; a
missing validation in a historical report remains a failure.

The benchmark should compare interaction-journal `artifact_count`, total file count,
verification, model-attempt and error counts, and actual fidelity scores. This change
does not alter the model prompt, retrieval policy, or cognitive stage output.

## Per-event JSON Lines extension

The follow-up experiment places the two hashed event entries in one append-only
`.jsonl` file per new event. The commit entry is appended only after PostgreSQL
commits. Old `.json` / `.commit.json` pairs remain readable, retain their bytes,
and use the old retry path. A partial second line fails verification until a retry
matches its exact expected prefix; a conflicting tail is never overwritten.

For the supplied baseline's 467 events, an identical run would have 467 fewer
physical files from event receipts and 28 fewer successful-validation artifacts:
approximately 555 rather than 1,050 files (47% fewer). This is a file-count
projection, not a native benchmark measurement. Both logical event records remain.

## Per-percept work product extension (`compact-artifact-journal`)

New percepts use `percepts/<interaction-id>.jsonl` as their durable work product.
The original `EVENT_RECORD` and matching post-commit `EVENT_DATABASE_COMMIT`
entries, `PERCEPT`, intermediate worker results, model invocations, failures and
final disposition are appended as individually hashed JSON lines. The runtime
reads the stage result it needs from this same file; the file is never sent to a
model as a prompt. Event records from earlier runs and events that have no active
percept keep their original per-event artifacts. Existing interaction JSON files
remain readable and are never rewritten.

The ten-probe `latest-benchmark(2).zip` contains 1,062 raw files: 165 worker
files and 104 event files linked by correlation to 11 work units. Placing those
269 entries into 11 percept files projects **804 raw files** for an identical run
(24% fewer). The other 793 event files were created outside those work units,
mostly as benchmark fixture history. This estimate does not claim that a new
model run produces identical events or numbers of worker attempts.

Readers and writers lock the same local journal. Each append is flushed and
fsynced; event semantics are durable before database commit and a receipt is
appended afterwards. Matching interrupted receipt prefixes can be completed by
retry. A corrupt line or nonmatching incomplete tail fails closed. Every
logical event still has its own event ID, hash and commit metadata; recovery
indexes entries while scanning journals. The final benchmark manifest hashes
each completed physical file and the inventory checks every logical entry.

The model transport now validates the entire rendered prompt/message set plus
output schema before dispatch. `PROMETHEIST_MAX_MODEL_INPUT_BYTES` defaults to
98,304 bytes. The existing evidence-specific limits remain in force. This is a
finite byte bound on the complete input; it is not a model-specific token count.
Workers continue to select a bounded evidence view rather than replaying the
work product.
