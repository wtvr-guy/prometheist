# Prometheist Memory Kernel v0.4 — Derived Associative Memory

Memory Kernel v0.4 tests the next question raised by the successful v0.3 associative-recall experiment:

> Can Prometheist derive useful associative routing state from authoritative events instead of hand-authoring answer-specific edges?

The v0.3 retrieval mechanism is retained. The experimental change is how associations are produced.

## Architectural invariant

PostgreSQL `events` remains authoritative structured memory.

Associations are disposable derived state:

```text
authoritative events
        |
        v
deterministic association derivation
        |
        v
versioned association projection
        |
        v
bounded associative activation
        |
        v
canonical source-event evidence
```

Deleting `memory_association_entries` must not delete or alter any event. A rebuild must be able to reproduce the projection from the same event history and derivation version.

## v0.4 projection contract

`src/jit_agent/association_projection.py` defines association projection version `1`.

For fixed source events and a fixed projection version:

```text
same events + same derivation version = same associations + same projection digest
```

Each derived association has:

- a deterministic association ID;
- typed source and target nodes (`TERM` or `EVENT`);
- an explicit relationship type;
- deterministic strength;
- source-event provenance;
- optional cue gates used by the v0.3 activation mechanism.

The association projection is intentionally small and explicit. It is not an LLM-generated semantic graph and it is not claimed to cover arbitrary natural language.

## Initial derivation rules

v0.4 implements three rule families because they correspond to failure modes already demonstrated by the v0.2 control benchmark.

### `PREVIOUS_STATE`

A change event can link to the nearest earlier event from the same source in the same coarse concept class. The edge is gated by the cue term `before` so old state does not automatically pollute current-state recall.

Example pattern:

```text
"I usually get a latte."
        ^
        |
PREVIOUS_STATE
        |
"I stopped adding milk to coffee and drink it black."
```

### `RESOLVED_BY`

An unresolved event can link to a later resolution event when the two share explicit entity terms. The edge is gated by `recover` in the current experiment.

Explicit entity overlap is required to reduce false links between unrelated events containing generic resolution language such as `returned`.

### `CONCEPT_INSTANCE`

The general term `vehicle` can link to evidence asserting acquisition or ownership of a recognized vehicle instance. Merely considering a vehicle does not create the edge.

The current concept ontology is deliberately limited and versioned. Expanding it is a policy change that should trigger new regression evaluation.

## PostgreSQL derived state

`schema.sql` adds:

```text
memory_association_entries
```

The table stores only derived routing state. It contains association IDs, projection version, typed endpoints, relationship, strength, provenance event IDs, and cue gates.

`postgres_memory_kernel.rebuild()` now rebuilds:

1. event-integrity metadata;
2. lexical projection entries;
3. deterministic association entries.

Association rebuilds are also recorded in `memory_projection_runs` with their projection name/version, source-event count, entry count, and deterministic projection digest.

The authoritative `events` table is never rewritten by this process.

## Held-out evaluation

`benchmarks/avery_chen_v1.json` introduces a second fictional persona. No association fixture is supplied for Avery Chen.

The same derivation code used on Jordan Vale must be applied unchanged to Avery. The test corpus includes analogous but differently worded cases for:

- an earlier beverage preference after a later habit change;
- recovery of money previously owed;
- concept-to-instance vehicle ownership;
- ordinary direct lexical/entity recall;
- true open-world unknown-fact abstention.

This is still a small synthetic benchmark, not proof of broad generalization. Its purpose is to prevent v0.4 from earning a passing score merely by replacing three hand-authored Jordan edges with three Jordan-specific code paths.

## Benchmark commands

Control benchmark:

```powershell
uv run python -m jit_agent.synthetic_benchmark
```

Curated v0.3 comparison:

```powershell
uv run python -m jit_agent.associative_benchmark
```

Derived v0.4 evaluation:

```powershell
uv run python -m jit_agent.derived_associative_benchmark
```

Run the complete regression suite with:

```powershell
uv run pytest -v
```

## Acceptance criteria

v0.4 should not be considered complete merely because the derivation rules compile. The branch should satisfy all of the following before merge:

1. reproduce the existing Jordan Vale 18/18 associative result without loading `jordan_vale_associations_v1.json`;
2. achieve the held-out Avery acceptance cases without persona-specific hand-authored edges;
3. preserve 1.000 unknown-fact abstention in both synthetic personas;
4. produce identical associations and association projection digests across repeated rebuilds of identical events;
5. retain exact source-event provenance for every derived edge;
6. leave authoritative event records unchanged across rebuilds;
7. pass the pre-v0.4 regression suite as well as the new v0.4 tests.

## Verified results — August 20, 2026

The branch was synced and executed locally against the dedicated PostgreSQL test environment. The complete pytest suite passed.

The preserved v0.2 control result was:

```text
questions: 15/18
question_success_rate: 0.833
evidence_recall: 0.833
mean_reciprocal_rank: 0.941
unknown_abstention_rate: 1.000
```

The curated v0.3 comparison reproduced:

```text
v0.2 baseline
  questions: 15/18
  question_success_rate: 0.833
  evidence_recall: 0.833
  mean_reciprocal_rank: 0.941
  unknown_abstention_rate: 1.000

v0.3 associative
  questions: 18/18
  question_success_rate: 1.000
  evidence_recall: 1.000
  mean_reciprocal_rank: 1.000
  unknown_abstention_rate: 1.000
```

The v0.4 derived-association evaluation produced:

```text
jordan_vale_v1.json
  baseline: 15/18
  derived:  18/18
  derived evidence recall: 1.000
  derived unknown abstention: 1.000

avery_chen_v1.json
  baseline: 3/6
  derived:  6/6
  derived evidence recall: 1.000
  derived unknown abstention: 1.000
```

Therefore all v0.4 acceptance criteria above are satisfied by the current synthetic evaluation and regression suite.

The result should be interpreted narrowly. v0.4 demonstrates that the current deterministic derivation rules can reproduce the v0.3 Jordan result without loading the curated Jordan association fixture and can transfer unchanged to a small held-out Avery corpus while preserving perfect unknown-fact abstention. It does not establish broad semantic-memory generalization or production-scale behavior.

## Deliberately deferred

v0.4 does not yet add:

- pgvector or embedding retrieval;
- LLM-based association extraction;
- a graph database;
- an unrestricted semantic ontology;
- probabilistic consolidation or forgetting;
- automatic episodic segmentation;
- a formal multi-agent JIT Memory API;
- replacement of PostgreSQL as authoritative structured-event storage;
- filesystem-per-event storage.

The purpose of v0.4 is narrower: determine whether deterministic, reconstructible associations can be derived from raw event evidence and generalize beyond the benchmark on which associative recall was first developed.
