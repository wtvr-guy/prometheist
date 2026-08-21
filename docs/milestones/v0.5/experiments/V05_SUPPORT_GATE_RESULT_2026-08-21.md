# Memory Kernel v0.5 — Support-Gate Result (2026-08-21)

This document freezes the accepted result of the support-aware evidence-admission experiment on `memory-kernel-v0.5-robustness`.

## Preconditions

- Full pytest regression suite: **PASS** after correcting the initial over-strict implementation.
- Association bookkeeping fix (`deterministic-associations-v2`) had already been causally validated.
- PostgreSQL candidate routing remained unchanged during this experiment.

## Mechanism under test

`deterministic-associations-v3` separates broad activation from final evidence admission.

Weak topical matches may still activate events and seed association traversal, but a directly surfaced event must have independent support for the query through one or more of:

- sufficient substantive lexical coverage;
- an explicit matching entity cue;
- an association path;
- a temporal cue paired with nonzero lexical support.

Explicit entity tokens are excluded from the lexical-support denominator so the entity cue is not counted twice. State/interpretation modifiers such as `now`, `before`, `still`, `actually`, and `immediately` also do not dilute lexical support.

The purpose is to reject generic topical noise as final evidence without weakening useful activation or relationship traversal.

## Morgan full-history control

| Events | Questions | Success | Evidence recall | MRR | Unknown abstention | p50 | p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 8 | **8/8** | **1.000** | **1.000** | **1.000** | 30.4 ms | 35.0 ms |
| 10,000 | 26 | **26/26** | **1.000** | **1.000** | **1.000** | 338.2 ms | 353.1 ms |

There were no failures.

The previously unsupported question `Who insures Morgan's vehicle?` now correctly returns no evidence under confusable vehicle noise. The previously repaired `PREVIOUS_STATE` questions remain correct, so the admission mechanism does not undo the association-bookkeeping fix.

## Morgan indexed PostgreSQL control at 1,000 events

| Events | Questions | Success | Evidence recall | MRR | Unknown abstention | p50 | p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 8 | **8/8** | **1.000** | **1.000** | **1.000** | 11.8 ms | 15.9 ms |

Load time was 0.064 s and derived-state rebuild time was 0.154 s. There were no failures.

This 1,000-event PostgreSQL run is intentionally below the scale at which the known candidate-window failure dominates. It demonstrates that the support gate behaves correctly through the indexed adapter when the authoritative target reaches the pure kernel.

## Causal conclusion

The pure-kernel robustness defects identified by the first v0.5 scale baseline are now independently closed under the tested corpus:

1. **Association bookkeeping under interference** — fixed and measured separately.
2. **Evidence admission / unsupported-query abstention** — fixed and measured separately.

The remaining observed large-scale accuracy defect is therefore the PostgreSQL **candidate gate**: authoritative historical events can be excluded before deterministic scoring because the current adapter merges any lexical/entity match, orders all matches newest-first, and applies a fixed candidate limit.

## Next experiment

Change only PostgreSQL candidate composition. Keep the total candidate bound fixed.

The next router should preserve independent bounded routes for:

- exact entity matches;
- lexical matches ranked by query-term coverage/specificity rather than pure recency;
- a small recency fallback.

The routes are unioned and de-duplicated before the unchanged pure kernel performs final scoring. Raising `candidate_limit` alone is not considered a fix because it only moves the failure point.
