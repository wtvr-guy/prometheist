# Prometheist Memory Kernel v0.5 — Robust Association Routing

Memory Kernel v0.5 begins from the verified v0.4 result rather than adding a new retrieval technology by default.

The question for this milestone is:

> Do the deterministic associations introduced in v0.4 remain useful when the history contains competing states, lifecycle changes, and queries that share a concept term without asking about the relationship represented by the association?

## Experimental rule

v0.5 follows the same development rule used by the earlier memory-kernel milestones:

> Freeze a measurable baseline, add one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.

Vector semantic retrieval remains deferred. The first v0.5 failures are failures of deterministic association policy, so they should be repaired there before a new retrieval subsystem is introduced.

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

## Invariants preserved

v0.5 does not change the authoritative evidence model.

- PostgreSQL `events` remains authoritative.
- Associations remain disposable derived state.
- Every association retains exact event provenance.
- Association IDs remain deterministic and now include projection version 2.
- Rebuilds remain versioned and digestable.
- Returned evidence remains canonical `MemoryEvent` data.
- No LLM is used to derive the new relationship.

## Acceptance target

Before v0.5 is considered complete, the branch should demonstrate:

1. Morgan Reyes robustness corpus: 7/7;
2. Morgan evidence recall: 1.000;
3. Morgan unknown-fact abstention: 1.000;
4. Jordan Vale derived benchmark remains 18/18;
5. Avery Chen derived benchmark remains 6/6;
6. association projection determinism and digest reproducibility remain intact;
7. PostgreSQL rebuild/idempotence tests remain green;
8. the complete pre-v0.5 regression suite remains green.

The focused deterministic rule simulation predicts the Morgan corpus will satisfy items 1–3. These results must not be described as verified until the repository test suite has been executed against the v0.5 branch.

## Deliberately deferred

This increment does not add:

- pgvector or embeddings;
- LLM-generated associations;
- a graph database;
- probabilistic memory consolidation;
- automatic episodic segmentation;
- a formal multi-agent JIT Memory API.

Those remain candidates for later milestones only when measured failures justify them.
