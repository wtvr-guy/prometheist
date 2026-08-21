# Prometheist Memory Kernel v0.5 — Robust Association Routing and Scale Characterization

Memory Kernel v0.5 begins from the verified v0.4 result rather than adding a new retrieval technology by default.

The milestone now asks two related questions:

> Do the deterministic associations introduced in v0.4 remain useful when the history contains competing states, lifecycle changes, and queries that share a concept term without asking about the relationship represented by the association?

and:

> How quickly and accurately does the current memory kernel retrieve evidence when each synthetic persona accumulates thousands or tens of thousands of later events?

## Experimental rule

v0.5 follows the same development rule used by the earlier memory-kernel milestones:

> Freeze a measurable baseline, add one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.

Vector semantic retrieval remains deferred. The first v0.5 failures are failures of deterministic association policy, so they should be repaired there before a new retrieval subsystem is introduced.

The large-corpus benchmark is likewise intended to identify the failure domain before changing architecture. Candidate-index recall, scoring/routing policy, abstention behavior, rebuild cost, and query latency are measured separately where possible.

## New adversarial corpus

`benchmarks/morgan_reyes_v05_robustness.json` adds a third fictional persona and stresses:

- repeated beverage-state changes;
- an obligation/resolution pair mixed with a similar unrelated deposit event;
- consideration vs. acquisition vs. disposal of a vehicle;
- false-association pressure from a query that contains `vehicle` but asks for an unsupported attribute;
- ordinary open-world unknown-fact abstention.

The frozen v0.4 behavior on this corpus is:

```text
questions: 7
successful_questions: 5
question_success_rate: 0.7142857142857143
evidence_recall: 0.8
unknown_abstention_rate: 0.5
```

The two failures are intentionally different:

1. current vehicle ownership after the previously owned vehicle has been sold;
2. an insurance question incorrectly receiving vehicle-acquisition evidence merely because the query contains the concept term `vehicle`.

## v0.5 mechanism

Association projection version 2 adds one bounded policy change: lifecycle-aware concept routing with relationship-specific cue gating.

### Ownership cue gating

Vehicle acquisition/ownership evidence is still represented by `CONCEPT_INSTANCE`, but the edge now requires the query cue `own`.

This prevents an ownership association from activating for an unrelated vehicle attribute such as insurance.

### Vehicle disposition

A recognized disposal event can now produce:

```text
CONCEPT_DISPOSITION
TERM vehicle -> EVENT disposition_event
```

The initial deterministic disposal phrase family is deliberately narrow:

- `sold`
- `gave away`
- `traded in`
- `returned the lease`
- `got rid of`

Disposition edges also require the cue `own`.

For a present-ownership query, both acquisition and later disposition evidence can therefore activate. Existing deterministic ranking then places the later lifecycle evidence ahead of the earlier acquisition when their association activation is equal.

### Shallow vehicle category recognition

The Morgan corpus exposed a separate weakness in the v0.4 ontology: a previously unseen model such as `2024 Mazda CX-30` did not contain one of the small model aliases used to recognize the `vehicle` concept.

v0.5 therefore broadens the deterministic vehicle taxonomy to include common manufacturer terms found in event text or entity metadata. The rule remains category-level rather than answer-specific: a Mazda, Toyota, Honda, Ford, Subaru, etc. entity can enter the vehicle concept even when the exact model has never appeared before.

This is intentionally still a shallow taxonomy. It is not a general solution to entity typing. An unfamiliar manufacturer or a vehicle described without any recognized category/make term can still remain unclassified. If larger benchmarks show that limitation matters materially, richer deterministic entity typing or another justified mechanism should be evaluated explicitly rather than silently expanding a benchmark-specific alias list.

## Indexed PostgreSQL associative recall

v0.4 persisted association rows in PostgreSQL but the existing `recall_from_postgres()` path still executed only the baseline lexical kernel. v0.5 keeps that baseline API unchanged and adds a separate association-aware indexed path:

```text
associative_recall_from_postgres()
```

Its bounded routing sequence is:

```text
query/entity cues
      |
      v
lexical projection candidate window
      |
      v
direct candidates clearing minimum score
      |
      +--------------------+
      |                    |
query TERM nodes      activated EVENT nodes
      |                    |
      +---------+----------+
                |
                v
bounded persisted association expansion
                |
                v
canonical target events fetched from events
                |
                v
pure associative kernel final scoring/ranking
```

`load_reachable_associations()` reads only association edges reachable from the current term/event frontier, enforces each edge's `required_cue_terms`, obeys a hop bound, and obeys an association-count bound. Canonical event content is still fetched independently from `events`.

This provides a direct A/B surface:

- `recall_from_postgres()` — indexed baseline control;
- `associative_recall_from_postgres()` — indexed v0.5 associative path.

## Large deterministic persona corpora

`jit_agent.scale_corpus` deterministically expands Jordan Vale, Avery Chen, and Morgan Reyes while preserving their original oracle questions.

Default sizes are:

- 1,000 events per persona;
- 10,000 events per persona;
- 50,000 events per persona.

Across all three personas and all three default sizes, the generator can materialize 183,000 benchmark events.

Generated event and conversation IDs are stable UUIDv5 values, so the exact same corpus can be evaluated by the in-memory kernel and loaded into PostgreSQL.

Most added events are mundane background history. Every twelfth distractor is lexically confusable by default and contains vocabulary from benchmark domains such as beverages, vehicles, deposits, employers/projects, people, locations, appointments, or objects without asserting the persona-specific oracle answer. Default confusable records deliberately avoid repeatedly copying the oracle-bearing proper nouns; exact-entity collision stress should be a separate adversarial profile rather than being hidden inside the basic scale test.

The generator is deterministic and prefix-stable at a fixed seed. A 10,000-event corpus is therefore the exact prefix of the corresponding 50,000-event corpus, making latency/accuracy comparisons across sizes controlled rather than anecdotal.

See [`SCALE_BENCHMARK.md`](SCALE_BENCHMARK.md) for commands and interpretation.

## Scale measurements

Two benchmark paths are provided.

### Full-history in-memory control

`python -m jit_agent.scale_benchmark`

Measures:

- oracle question accuracy;
- evidence recall;
- mean reciprocal rank;
- unknown-fact abstention;
- association derivation time;
- recall p50/p95/max latency.

This intentionally scores the entire history for every query. It characterizes raw algorithmic scaling but is not the intended long-term storage path.

### Indexed PostgreSQL path

`python -m jit_agent.postgres_scale_benchmark`

Measures:

- corpus load time;
- derived-state rebuild time;
- oracle question accuracy;
- evidence recall;
- mean reciprocal rank;
- unknown-fact abstention;
- recall p50/p95/max latency;
- projection/association counts;
- candidate-window size.

The PostgreSQL runner is destructive to its selected database and therefore refuses to run unless the current database name contains `test` or `benchmark`.

## Invariants preserved

v0.5 does not change the authoritative evidence model.

- PostgreSQL `events` remains authoritative.
- Associations remain disposable derived state.
- Every association retains exact event provenance.
- Association IDs remain deterministic and now include projection version 2.
- Rebuilds remain versioned and digestable.
- Returned evidence remains canonical `MemoryEvent` data.
- No LLM is used to derive the new relationship.
- Large scale corpora are derived benchmark artifacts, not authoritative project data.
- The ordinary development database is not used for destructive scale runs.

## Acceptance target

Before v0.5 is considered complete, the branch should demonstrate:

1. Morgan Reyes robustness corpus: 7/7;
2. Morgan evidence recall: 1.000;
3. Morgan unknown-fact abstention: 1.000;
4. Jordan Vale derived benchmark remains 18/18;
5. Avery Chen derived benchmark remains 6/6;
6. association projection determinism and digest reproducibility remain intact;
7. PostgreSQL rebuild/idempotence tests remain green;
8. PostgreSQL association-aware recall tests remain green;
9. the complete pre-v0.5 regression suite remains green;
10. scale results are recorded for 1,000, 10,000, and 50,000 events per persona on both the full-history and PostgreSQL paths, or any device-limited maximum is explicitly recorded;
11. any scale accuracy loss is classified as candidate-index recall, scoring/routing, or abstention failure before another retrieval mechanism is introduced.

The focused deterministic rule simulation predicts the Morgan corpus will satisfy items 1–3 after the vehicle taxonomy correction. These results must not be described as verified until the repository test suite has been executed against the v0.5 branch.

No device-specific latency threshold is declared before the first local scale run. The initial run is a characterization baseline from which a defensible performance target can be set.

## Deliberately deferred

This increment does not add:

- pgvector or embeddings;
- LLM-generated associations;
- a graph database;
- probabilistic memory consolidation;
- automatic episodic segmentation;
- a formal multi-agent JIT Memory API.

Those remain candidates for later milestones only when measured failures justify them.
