# Memory Kernel v0.5 — Candidate Router Result (2026-08-21)

This document freezes the accepted post-fix PostgreSQL scale result for the v0.5 candidate-routing experiment.

## Change under test

The total PostgreSQL candidate bound remains fixed at **500**. The router now composes that bounded set from independent deterministic routes rather than one broad newest-first OR query:

- exact-entity route;
- lexical route ranked by query-term coverage/specificity;
- reserved recency fallback.

Final evidence scoring/ranking remains in the deterministic Memory Kernel. No vector retrieval or embeddings were introduced.

## Verification status

- Full local pytest regression suite: **PASS** on the development machine.
- PostgreSQL candidate crowd-out regression tests: **PASS**.
- 10,000-event PostgreSQL scale suite: **PASS** for all personas/questions.
- 50,000-event PostgreSQL scale suite: **PASS** for all personas/questions.
- Candidate limit: **500** throughout.
- Association limit: **250** throughout.

## PostgreSQL — 10,000 events

| Persona | Questions | Success | Evidence recall | MRR | Unknown abstention | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Jordan Vale | 37 | 37/37 | 1.000 | 1.000 | 1.000 | 28.0 ms | 68.0 ms |
| Avery Chen | 25 | 25/25 | 1.000 | 1.000 | 1.000 | 24.4 ms | 70.0 ms |
| Morgan Reyes | 26 | 26/26 | 1.000 | 1.000 | 1.000 | 30.9 ms | 61.5 ms |

The first PostgreSQL scale baseline at 10,000 events was:

- Jordan: 27/37;
- Avery: 15/25;
- Morgan: 13/26.

The specificity-routed candidate union therefore restores every previously lost base/probe question at 10,000 events without increasing the 500-candidate bound.

## PostgreSQL — 50,000 events

| Persona | Questions | Success | Evidence recall | MRR | Unknown abstention | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Jordan Vale | 117 | 117/117 | 1.000 | 1.000 | 1.000 | 160.0 ms | 196.6 ms |
| Avery Chen | 105 | 105/105 | 1.000 | 1.000 | 1.000 | 163.3 ms | 206.1 ms |
| Morgan Reyes | 106 | 106/106 | 1.000 | 1.000 | 1.000 | 151.7 ms | 196.5 ms |

The first PostgreSQL scale baseline at 50,000 events was:

- Jordan: 46/117;
- Avery: 42/105;
- Morgan: 39/106.

The new router restores full accuracy and all distributed probe facts at the same bounded candidate-window size.

## Latency tradeoff

At 50,000 events, the first newest-first candidate router had p50 recall around **88–97 ms** but severe candidate recall loss. The specificity router increases p50 to roughly **152–163 ms** while restoring perfect benchmark correctness.

The full-history in-memory control at 50,000 events had p50 recall around **1.69–1.71 s**. The corrected PostgreSQL path therefore remains roughly an order of magnitude faster than the O(N) control while matching its observed accuracy on the frozen corpora.

This latency increase is accepted for v0.5 because it buys complete recovery of authoritative historical evidence under the current scale/noise benchmark while preserving a strict bounded candidate set. Query-plan/index optimization can be treated as a later performance experiment rather than weakening recall correctness.

## v0.5 causal result

The first scale run isolated three independent failure classes, each subsequently changed and measured separately:

1. **Association bookkeeping under interference** — fixed by separating direct propagation activation from association-earned activation.
2. **Evidence admission / abstention** — fixed by separating broad activation from support-aware final evidence admission while preserving entity, temporal, and association cues.
3. **PostgreSQL candidate routing** — fixed by specificity-aware multi-route candidate composition rather than newest-first truncation.

After those isolated changes, the frozen 10k and 50k PostgreSQL suites achieve:

- question success rate: **1.000**;
- evidence recall: **1.000**;
- mean reciprocal rank: **1.000**;
- unknown abstention rate: **1.000**;
- candidate limit: **500**.

## Decision

The candidate-router mechanism is **accepted** for the v0.5 milestone. The observed failures do not justify adding embeddings or another retrieval subsystem at this stage. The deterministic lexical/entity/association architecture is sufficient for the current robustness and 50,000-event scale benchmark.
