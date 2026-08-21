# Memory Kernel v0.5 — Final Milestone Status

**Status:** Closed and frozen.

Memory Kernel v0.5 is the completed robustness-and-scale research increment that follows the deterministic derived-association work in v0.4. The core experiment met its measured acceptance criteria, and the final closure audit fixes have now passed both the targeted PostgreSQL regression suite and the complete local test suite.

## What v0.5 asked

v0.5 tested two questions:

1. Can deterministic associative recall remain correct when history contains competing states, lifecycle changes, and misleading topical overlap?
2. Can the same architecture preserve recall quality when each synthetic persona accumulates thousands or tens of thousands of events while PostgreSQL retrieval remains bounded?

The experimental rule remained unchanged:

> Freeze a measurable baseline, add one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.

## Accepted result

The final measured PostgreSQL scale run used:

- candidate limit: **500**;
- association limit: **250**;
- no embeddings;
- no vector database;
- no LLM-generated associations;
- the same deterministic lexical/entity/association architecture used throughout the milestone.

At 10,000 events per persona:

| Persona | Questions | Success | Evidence recall | MRR | Unknown abstention |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jordan Vale | 37 | 37/37 | 1.000 | 1.000 | 1.000 |
| Avery Chen | 25 | 25/25 | 1.000 | 1.000 | 1.000 |
| Morgan Reyes | 26 | 26/26 | 1.000 | 1.000 | 1.000 |

At 50,000 events per persona:

| Persona | Questions | Success | Evidence recall | MRR | Unknown abstention | p50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Jordan Vale | 117 | 117/117 | 1.000 | 1.000 | 1.000 | 160.0 ms |
| Avery Chen | 105 | 105/105 | 1.000 | 1.000 | 1.000 | 163.3 ms |
| Morgan Reyes | 106 | 106/106 | 1.000 | 1.000 | 1.000 | 151.7 ms |

The final 50k suite therefore returned **328/328** successful answers at the fixed 500-event candidate bound.

These are controlled synthetic benchmark results. They are not evidence of universal semantic-memory correctness. They are evidence that the measured v0.5 failures did not justify adding embeddings or another retrieval subsystem.

## Causal progression

The first scale run isolated three independent defects. Each was changed and measured separately.

### 1. Association bookkeeping under interference

Direct activation and association-earned activation originally shared one activation domain. A direct 1.0 seed could therefore suppress a valid relationship-specific association boost to the same event.

The accepted fix tracks propagation activation separately from association-earned activation. This restored historical-state association behavior under noise without changing the authoritative evidence model.

### 2. Evidence admission and abstention

The broad activation threshold is useful for seeding associations, but weak topical overlap should not automatically become final evidence.

The accepted support-aware admission layer separates activation from evidence admission. Explicit association support, entity support, temporal support, or sufficient substantive lexical coverage can admit evidence; unrelated topical overlap cannot.

This closed the Morgan unsupported-insurance failure while preserving valid entity-anchored and historical evidence.

### 3. PostgreSQL candidate crowd-out

The first indexed router used a broad lexical/entity OR query ordered primarily by recency. At scale, older exact evidence could be crowded out by hundreds of newer generic matches before the deterministic kernel saw it.

The accepted router composes the fixed candidate window from independent deterministic routes:

- exact entity;
- lexical specificity/coverage;
- reserved recency fallback.

The candidate limit remained 500. Accuracy was restored without increasing the window.

## Acceptance criteria — satisfied

The original v0.5 plan required:

1. Morgan robustness corpus correctness and abstention to reach 1.000;
2. Jordan derived benchmark to remain 18/18;
3. Avery derived benchmark to remain 6/6;
4. deterministic association projection/digest behavior to remain intact;
5. PostgreSQL rebuild and association-aware regressions to remain green;
6. the pre-v0.5 regression suite to remain green;
7. scale characterization at 1k, 10k, and 50k where hardware permitted;
8. base and distributed-probe questions to be measured independently;
9. scale failures to be classified before adding another retrieval technology.

Those criteria were satisfied in the accepted v0.5 experimental sequence. The final candidate-router result records a full local pytest pass plus perfect 10k and 50k PostgreSQL benchmark metrics.

## Closure audit — verified

A static audit performed after the accepted benchmark result found three defects that were not exercised by the frozen scale corpus:

- association expansion could cross a supplied `before_global_seq` boundary even though direct candidates respected it;
- bounded PostgreSQL candidate routes did not apply `CueState.source_types` until after candidate truncation;
- the pytest database reset omitted `memory_association_entries`, did not guard the destructive target by database name, and reset only once per test session.

The closure patch fixed all three and added focused regressions. On 2026-08-21, the local verification run produced:

```text
uv run pytest tests/test_postgres_memory_kernel.py -v
10 passed in 1.75s

uv run pytest -v
73 passed in 83.36s
```

The new cutoff and source-type regressions passed, and no existing regression or acceptance test failed. The 10k/50k scale benchmark was not rerun because these closure fixes do not change the frozen scale workload's candidate-ranking mechanism and that workload does not exercise `before_global_seq` or `source_types`.

See [`../../audits/V05_CLOSURE_AUDIT_2026-08-21.md`](../../audits/V05_CLOSURE_AUDIT_2026-08-21.md) for the audit record.

## Invariants preserved

v0.5 retains the core Prometheist memory invariants:

- PostgreSQL `events` is authoritative history;
- canonical events are not rewritten by memory rebuilds;
- lexical and associative structures are disposable derived state;
- associations retain source-event provenance;
- derived-state rebuilds are versioned and digestible;
- returned evidence is canonical `MemoryEvent` data;
- retrieval is bounded independently of total history size;
- unknown/unsupported facts may correctly return no evidence;
- no LLM creates deterministic association or benchmark answers.

## Deliberately deferred

v0.5 does **not** add:

- pgvector or embeddings;
- LLM-generated associations;
- a graph database;
- probabilistic consolidation;
- automatic episodic segmentation;
- a shared multi-agent JIT Memory protocol;
- durable multi-agent task execution.

The next milestone is not another retrieval mechanism by default. v0.6 moves the verified memory kernel behind a shared JIT-memory boundary and tests whether multiple stateless agents can use it as common persistent infrastructure.

See [`../../ROADMAP.md`](../../ROADMAP.md).

## Research record

The detailed experimental sequence is retained under [`experiments/`](experiments/):

1. `V05_SCALE_BASELINE_2026-08-21.md`
2. `V05_ASSOCIATION_FIX_RESULT_2026-08-21.md`
3. `V05_SUPPORT_GATE_REGRESSION_2026-08-21.md`
4. `V05_SUPPORT_GATE_RESULT_2026-08-21.md`
5. `V05_CANDIDATE_ROUTER_RESULT_2026-08-21.md`

`SCALE_BENCHMARK.md` remains the reproducible benchmark workflow.