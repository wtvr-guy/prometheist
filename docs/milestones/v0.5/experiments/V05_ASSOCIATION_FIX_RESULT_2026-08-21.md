# Memory Kernel v0.5 — Association Fix Result (2026-08-21)

This document freezes the first post-baseline mechanism test on the v0.5 robustness branch.

## Change under test

Only associative activation bookkeeping changed after the first scale baseline. Direct seed activation and activation earned by traversing an association are tracked separately so a directly matched event can still receive a relationship-specific associative boost.

PostgreSQL candidate routing and evidence-admission/abstention policy were intentionally left unchanged for this rerun.

## Verification

- Full pytest regression suite: **PASS**
- Benchmark persona: Morgan Reyes
- Scale profiles rerun: 1,000 and 10,000 events
- Probe cadence: one deterministic oracle probe every 500 generated events

## Observed result

| Events | Questions | Success | Evidence recall | MRR | Unknown abstention | p50 recall | p95 recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 8 | 7/8 | 1.000 | 1.000 | 0.500 | 30.6 ms | 32.8 ms |
| 10,000 | 26 | 25/26 | 1.000 | 1.000 | 0.500 | 324.8 ms | 346.3 ms |

The two repeated-state failures from the frozen baseline both recovered. The only remaining failure at both scales is `mq06`, the unsupported question `Who insures Morgan's vehicle?`.

## Causal conclusion

This result confirms the earlier diagnosis: the repeated-state failures were caused by association bookkeeping rather than corpus size, candidate routing, or the derived `PREVIOUS_STATE` edges themselves.

The remaining Morgan failure is now isolated to evidence admission / abstention. Generic vehicle-related events clear the existing minimum score through topical lexical overlap even though they do not support the requested insurer relationship.

## Next experiment

The next change should address direct-evidence admission only. It must not alter PostgreSQL candidate routing in the same experiment.

The intended test is whether query-content support can reject merely topical lexical matches while preserving sparse but legitimate direct matches, temporally anchored matches, and evidence reached through explicit associations.
