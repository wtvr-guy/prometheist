# Memory Kernel v0.5 — First Scale Baseline (2026-08-21)

This document freezes the first local scale run of the v0.5 robustness branch before further scale-oriented mechanisms are added.

## Run status

- Full pytest regression suite: **PASS**
- Scale profiles: 1,000 / 10,000 / 50,000 events per persona
- Probe cadence: one deterministic oracle probe every 500 generated events
- PostgreSQL candidate limit: 500
- PostgreSQL association limit: 250
- Personas: Jordan Vale, Avery Chen, Morgan Reyes

The generated histories are deterministic and prefix-stable. Results below are the observed local run, not simulated predictions.

## Full-history in-memory control

| Persona | Events | Questions | Success | Evidence recall | Unknown abstention | p50 recall | p95 recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Jordan Vale | 1,000 | 19 | 19/19 | 1.000 | 1.000 | 30.6 ms | 34.8 ms |
| Jordan Vale | 10,000 | 37 | 37/37 | 1.000 | 1.000 | 338.4 ms | 383.2 ms |
| Jordan Vale | 50,000 | 117 | 117/117 | 1.000 | 1.000 | 1689.0 ms | 1973.8 ms |
| Avery Chen | 1,000 | 7 | 7/7 | 1.000 | 1.000 | 29.9 ms | 32.9 ms |
| Avery Chen | 10,000 | 25 | 25/25 | 1.000 | 1.000 | 332.4 ms | 346.8 ms |
| Avery Chen | 50,000 | 105 | 105/105 | 1.000 | 1.000 | 1708.8 ms | 1782.2 ms |
| Morgan Reyes | 1,000 | 8 | 5/8 | 0.667 | 0.500 | 31.2 ms | 37.9 ms |
| Morgan Reyes | 10,000 | 26 | 23/26 | 0.917 | 0.500 | 333.6 ms | 364.0 ms |
| Morgan Reyes | 50,000 | 106 | 103/106 | 0.981 | 0.500 | 1700.8 ms | 1816.9 ms |

### Control-path interpretation

Jordan and Avery retain perfect recall through 50,000 events when the kernel is allowed to score the complete history. All distributed scale probes are recovered.

Morgan's aggregate percentage rises only because more successful scale probes are added to the denominator. Its original robustness questions remain **4/7** under the noisy scale corpus at every tested size. The stable failures are:

1. prior beverage state before switching to green tea;
2. prior beverage state before switching to espresso;
3. unsupported vehicle-insurance question returns lexically related vehicle noise instead of abstaining.

The full-history path therefore shows two separate pure-kernel robustness issues while also demonstrating that accumulated row count itself does not cause Jordan/Avery evidence loss under this noise profile.

Latency grows approximately linearly with total history because every event is scored. The ~1.7 second p50 at 50,000 events is the expected cost of the O(N) control path, not the intended production retrieval architecture.

## Indexed PostgreSQL associative path

| Persona | Events | Questions | Success | Evidence recall | Unknown abstention | p50 recall | p95 recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Jordan Vale | 1,000 | 19 | 19/19 | 1.000 | 1.000 | 10.8 ms | 17.7 ms |
| Jordan Vale | 10,000 | 37 | 27/37 | 0.730 | 1.000 | 27.4 ms | 63.0 ms |
| Jordan Vale | 50,000 | 117 | 46/117 | 0.393 | 1.000 | 97.0 ms | 131.4 ms |
| Avery Chen | 1,000 | 7 | 7/7 | 1.000 | 1.000 | 10.3 ms | 10.8 ms |
| Avery Chen | 10,000 | 25 | 15/25 | 0.583 | 1.000 | 28.7 ms | 56.2 ms |
| Avery Chen | 50,000 | 105 | 42/105 | 0.394 | 1.000 | 87.9 ms | 97.0 ms |
| Morgan Reyes | 1,000 | 8 | 5/8 | 0.667 | 0.500 | 11.1 ms | 12.9 ms |
| Morgan Reyes | 10,000 | 26 | 13/26 | 0.500 | 0.500 | 31.1 ms | 59.3 ms |
| Morgan Reyes | 50,000 | 106 | 39/106 | 0.365 | 0.500 | 90.1 ms | 104.1 ms |

At 50,000 events, indexed p50 recall is roughly 17–19x faster than the full-history control. Loading 50,000 events takes roughly 4.3–4.5 seconds and rebuilding derived state roughly 10.2 seconds on the measured machine.

### Candidate-gate failure pattern

The PostgreSQL path loses exactly **10 of 19** scale probes at 10,000 events and **63 of 99** scale probes at 50,000 events for all three personas.

The failure pattern is deterministic by probe template:

- reference-card / locker probes remain recoverable;
- parcel-confirmation / shelf probes are mostly lost;
- archive-bin / code probes are mostly lost;
- only the newest instances of the latter two tend to survive.

This strongly isolates the failure to candidate selection rather than final kernel ranking. The current candidate query performs one broad OR over any matching lexical term or exact entity, sorts all matches newest-first, then applies the fixed 500-event limit. An old event with a unique exact locator can therefore be excluded by hundreds of newer records that match only generic words such as `shelf`, `code`, or `archive`. Once excluded, the pure kernel never receives the authoritative event and cannot recover it.

At 50,000 events the same gate also begins excluding original persona evidence: Jordan loses 8/18 base questions and Morgan loses one additional base question. Avery's six base questions remain recoverable under this particular corpus.

## First causal conclusions

The first scale run identifies three distinct problems rather than one generic "memory accuracy" failure:

1. **Association bookkeeping under interference** — a directly activated target event can suppress a valid lower-valued association activation, so the relationship-specific boost never reaches ranking. This affects Morgan's repeated-state questions.
2. **Evidence admission / abstention** — weak lexical overlap can be returned as evidence for an unsupported relationship. This affects Morgan's vehicle-insurance unknown.
3. **PostgreSQL candidate routing** — broad OR + newest-first + fixed LIMIT sacrifices historical candidate recall even when an exact unique entity exists. This dominates the 10k/50k indexed accuracy loss.

These should be changed and measured separately.

## Next experiment

The first post-baseline change is intentionally limited to association bookkeeping. Direct seed activation and association-earned activation are now tracked separately (`deterministic-associations-v2`) so a directly matched target can still receive a relationship-specific associative boost. A dedicated regression test covers the failure mode.

Do not change candidate routing or abstention in the same rerun. If the diagnosis is correct, Morgan's two `PREVIOUS_STATE` failures should recover while the insurance unknown should remain a failure. Only after that result is frozen should the next mechanism be introduced.
