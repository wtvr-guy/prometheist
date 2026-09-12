# Prometheist Cognitive Architecture

**Status:** constitutional architecture deep dive, rebaselined 2026-09-03

**Authority:** subordinate to [`../../CONSTITUTION.md`](../../CONSTITUTION.md)

## Purpose

Prometheist is a persistent cognitive system whose durable continuity remains intact
when every model invocation and worker process disappears. LLMs provide bounded
semantic computation; they are not durable agents and do not own identity, memory,
attention, policy, or execution authority.

The architecture separates five kinds of responsibility:

1. canonical evidence and durable state;
2. derived memory and bounded activation;
3. deterministic attention, resource, and execution control;
4. fresh model-backed semantic work;
5. external observation and effects with explicit provenance.

## System shape

```text
external input
  -> deterministic intake + canonical event
  -> situation/task + bounded WorkingState
  -> default bounded memory orientation
  -> semantic work selection inside closed contracts
  -> deterministic Attention/resource/execution plane
  -> memory sufficiency + Adaptive Recall when required
  -> response or other authorized result
  -> canonical history + immutable artifact journal
```

Conversations, sessions, devices, and interfaces label provenance. They do not create
separate minds or default memory scopes.

## Durable system-owned state

Prometheist, rather than an LLM or worker, owns:

- canonical event history and total ordering;
- memory provenance and derived-projection versions;
- tasks, dependencies, priorities, assignments, and reservations;
- WorkingState activation and revision;
- worker claims, leases, checkpoints, terminal results, and effect keys;
- capability identity, permissions, dependencies, and execution policy;
- resource observations, headroom, admission decisions, and scheduling epochs;
- interaction stage state, final disposition, and artifact chains.

Workers receive bounded inputs selected from that state, publish a durable result or
checkpoint, and may then be destroyed.

## Canonical evidence and derived cognition

Canonical admitted memory is exact append-only evidence. Corrections and
supersession add new records; ordinary system operation does not rewrite history.

Derived structures include candidate indexes, association edges, feature
projections, WorkingState activation, ranked packets, and response-ready memory
packages. They accelerate cognition and may be rebuilt or versioned. They never
replace source evidence or acquire truth authority merely because they rank highly.

Projection freshness is maintained incrementally from durable high-water marks in
steady state. A full deterministic rebuild remains available when projection marks
are missing or incompatible. Ordinary per-percept work must not reload lifetime
history simply to prove that a projection is current.

## WorkingState

The implemented v0.7 `InteractionWorkingState` is a bounded activation projection:

- it contains canonical event IDs rather than copied transcript text;
- its revision and identity are durable;
- it can span conversation boundaries;
- the current prompt and newly relevant recall outrank stale activation under
  saturation;
- it is not a profile, summary, truth store, or replacement for long-term memory.

A richer typed Epistemic WorkingState remains a separate, unfrozen experiment.
It is not part of the current v0.8 perception/salience implementation.

## Attention and execution

Attention answers which durable work deserves service and in what deterministic
order. Resource admission separately answers which compatible work fits safely now.
Priority therefore does not serialize safe concurrency, and preemption is considered
only when real contention prevents more important work from being admitted.

Assignments are committed before disposable workers act. Claim-time resource
re-observation, leases, checkpoints, recovery, and effect idempotency keep process
loss from becoming loss of authority. Unknown or stale resource state fails closed.

See
[`ATTENTION_AND_EXECUTION_GOVERNANCE.md`](ATTENTION_AND_EXECUTION_GOVERNANCE.md)
and [`SYSTEM_DETERMINISM.md`](SYSTEM_DETERMINISM.md).

## Model authority

Models may interpret semantic requirements inside application-owned schemas. They
do not author durable IDs, capability names, dependency order, schedules, resource
policy, permissions, retry rules, or irreversible-effect authority.

Machine control prefers enums, booleans, bounded integers, and selections from
application-owned catalogs. Generated natural language is reserved for places where
language is genuinely the product or no narrower representation is adequate.

Every model call is fresh and supplied only the bounded, provenance-bearing inputs
needed for that call. Evidence bytes are validated per item and in aggregate before
transport. Hidden transcripts and worker-local continuity are prohibited.

## Authoritative v2 user-prompt path

The v2 path in
[`PERCEPT_TO_RESPONSE_PIPELINE.md`](PERCEPT_TO_RESPONSE_PIPELINE.md) is the only
live interaction architecture.

For an explicit user prompt:

1. deterministic intake sets `response_required=true`, persists the prompt, and
   derives a normalized percept and advisory salience;
2. a fresh evidence-policy specialist selects and persists the closed historical
   source scope and output surface from the current prompt only;
3. a bounded attention aperture exposes WorkingState and potentially relevant
   canonical history within that committed scope;
4. a fresh work-triage specialist selects zero or more **non-memory** work requirements;
5. Prometheist expands dependencies and runs authorized work through the durable
   execution plane;
6. a fresh v2 Composer judges only persistent-memory sufficiency;
7. if memory is insufficient, deterministic Adaptive Recall expands it and a fresh
   Composer reassesses, subject to bounded stopping policy;
8. application code filters event roles under the exact persisted policy and supplies admitted data as quarantined
   evidence before the current prompt;
9. exact output is source-selected and mechanically validated, or a natural final
   responder receives the admitted evidence and resolved personality contract;
10. the response and final artifact disposition are persisted.

Work/tool results never pass through the Composer for reinterpretation. The Composer
never decides whether to answer, schedules no work, performs no effect, and generates
no final prose.

Adaptive Recall is internal memory substrate, not an exposed capability. Its
`BROAD`, `ASSOCIATIVE`, `RELATIONAL`, and `FOCUSED` stages describe deterministic
retrieval breadth/focus only. The older separate memory capability names and the
general recurrent response router are historical.

Non-user percepts may have deterministic no-response policies. That exception does
not apply to explicit user prompts.

## Evidence authority

The current prompt is direct current evidence. Historical user prompts are direct
evidence of what the user previously said or requested. Historical model output,
tool output, system events, and retrieved text retain their own source authority and
cannot become current instructions merely by appearing in memory. A current-only
policy selects which role may establish the claim; application code physically
filters other roles before synthesis.

Relevance, activation, sufficiency, and truth remain distinct. Contradictions and
unknowns must remain visible; unsupported personal or historical facts must not be
invented. Model-facing evidence is treated as quarantined data, transported before
and separately from later current authority. Exact-source responses are validated
against admitted canonical substrings rather than trusted as regenerated prose.

## Internal memory versus external knowledge

Prometheist's own remembered history and newly acquired external knowledge are
separate evidence domains. Each retains source, freshness, failure, and authority
metadata. Internal recall cannot masquerade as a current tool observation, and a
tool result cannot silently rewrite remembered history.

## Persistence classes

The long-term architecture distinguishes:

- ephemeral raw observations held in bounded buffers;
- retained external observations governed by explicit policy;
- canonical internal history needed for continuity and explanation;
- bounded active WorkingState;
- replaceable derived projections and response views.

The v0.8 branch implements typed source admission, content-addressed media,
expectations and prediction errors, overlapping derived situations, non-user
triage, reflexes, situation attention, observed action outcomes, and scheduled
consolidation. See [SITUATION_COGNITION.md](SITUATION_COGNITION.md) for the implemented
contracts and limits. Source retention hints never delete canonical evidence.

## Implemented versus deferred

The integrated v0.7 closure candidate supplies the canonical ledger, independent
artifact journal, Memory Kernel, bounded aperture, minimal WorkingState,
resource-aware Attention Fabric, durable worker protocol, seven-stage user
pipeline, Adaptive Recall, memory-only Composer, current-only evidence policy,
evidence-bound transport, exact-source realization, natural final responder,
incremental projection freshness, and adversarial evidence bounds.

v0.8 adds the situation mechanisms above with six independently guarded non-user
stages. Source policy determines whether a response is needed; a model cannot
suppress an explicit user response or authorize resources/effects through salience.

Richer Epistemic WorkingState, modality-specific perceptual encoders, general
external effect adapters, learned procedural skills, source deletion policy, and
complete portability/export/erasure operations remain separate work. Scheduled
consolidation derives supported property/value projections; it does not rewrite
canonical history or claim universal semantic knowledge.

## Architectural test

A change is admissible only when it preserves:

- system-owned durable authority and stateless model calls;
- exact canonical evidence and causal provenance;
- deterministic replay for deterministic decisions;
- bounded ordinary context, retrieval work, and inference count;
- separate memory/work evidence authority;
- resource headroom and guarded worker execution;
- fail-closed behavior under missing evidence or authority;
- deterministic regression evidence plus native evidence wherever host or model
  reality matters.

The authoritative status of a mechanism comes from current code, tests, accepted
experiment records, and required native evidence—not from an older milestone diagram.
