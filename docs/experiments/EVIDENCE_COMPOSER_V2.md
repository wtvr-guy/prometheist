# Evidence Composer v2 Experiment

**Status:** experimental. Not wired into the production interaction path.

## Why v2 exists

`MEM-ADAPT-003` showed that raw retrieval-order top-k can lose useful evidence even when that evidence remains reachable far inside the candidate pool. A six-item packet frequently contained six repetitive high-ranked memories instead of the six most useful memories.

`MEM-ADAPT-004` then showed that the first coverage-aware composer overcorrected. Its lexicographic novelty/diversity utility could let lower-ranked novel junk displace stronger evidence, discard numerically distinct facts, suppress repeated corroboration, prefer verbose material, and allow stale retained evidence to consume a slot.

The two failures imply that relevance and coverage should not be collapsed into one scalar or one lexicographic utility.

## v2 rule

Composer v2 uses a two-stage deterministic policy:

```text
ordered retrieval candidates
        |
        v
current top-k relevance core
        |
        +-- preserve nonredundant evidence
        |
        +-- identify only demonstrably redundant slots
                    |
                    v
          coverage/support augmentation
                    |
                    v
              bounded packet
```

A core item is considered replaceable only when an earlier core item already has:

1. the same information signature; and
2. the same support identity.

This means coverage is allowed to spend redundancy; it is not allowed to evict arbitrary high-relevance evidence.

## Information signature

V2 keeps standalone numeric tokens because numbers may be the fact itself: dates, prices, thresholds, versions, measurements, times, counts, and similar data.

Numeric suffixes attached to words with a hyphen are stripped as mechanical labels. This prevents synthetic strings such as `duplicate-17` from creating fake information diversity while preserving a fact such as `threshold value 17`.

This syntactic rule is deliberately narrow. It does not claim to understand numeric semantics.

## Support identity

Repeated language is not automatically redundant evidence.

V2 first uses canonical `provenance_event_ids` when they are available. If provenance is absent, it conservatively falls back to `(source, conversation_id)`.

Therefore:

- equivalent evidence from the same observable origin can be treated as duplicate composition pressure;
- equivalent evidence with distinct canonical provenance can remain in the relevance core as independent support;
- if independence exists in the real world but is not represented in Prometheist's canonical metadata, the composer must not invent that independence.

`MEM-ADAPT-005` includes an explicit diagnostic case for this observability limit.

## Retained evidence

Retained evidence no longer receives an independent right to evict current nonredundant evidence.

Retained items participate in the augmentation stage only. They can survive an attention shift when the current core contains redundant slots, but stale retained evidence cannot consume a slot when all current core items contribute distinct information/support.

## No weighted relevance/diversity formula

V2 intentionally does not use a formula such as:

```text
0.65 * relevance + 0.35 * diversity
```

There are no learned weights, model-generated scores, similarity thresholds, or fixed relevance/diversity coefficients.

The ordering is structural:

1. preserve current nonredundant relevance-core evidence;
2. expose only redundant core capacity;
3. use retrieval score first when choosing informative augmentation candidates;
4. use information/support coverage as deterministic tie-breaking and qualification;
5. fall back to the original retrieval order if no informative augmentation remains.

## MEM-ADAPT-005

`benchmarks/compare_evidence_composers_v2.py` compares three policies under the same explicit candidate pools and six-item packet budget:

- raw top-k;
- frozen coverage-aware Composer v1;
- relevance-constrained Composer v2.

The corpus combines both previous adversarial regimes:

- old/unique evidence buried under duplicate pressure;
- claim + correction preservation;
- distributed weak clues;
- temporally distributed evidence;
- retained evidence across an attention shift;
- numeric payload attacks;
- random-token novelty attacks;
- metadata-diversity attacks;
- verbose-irrelevance attacks;
- stale-retention attacks;
- independent corroboration with explicit provenance;
- the original coverage positive control;
- a shared-success control.

A separate `unobservable_corroboration_diagnostic` intentionally gives repeated rows no distinct provenance/source/conversation signal. That case is reported but excluded from the observable-evidence acceptance summary because no deterministic composer can infer hidden independence from identical observable inputs.

The repository CI contract currently requires Composer v2 to pass every observable quick-mode case. Static checks, constraint governance/calibration, acceptance-gate collection, and the full PostgreSQL pytest suite are green with that contract in place. This is implementation validation, not evidence that stress-mode or real-world semantic composition is solved.

## Local run

```powershell
uv run pytest tests/test_evidence_composer_v2.py tests/test_evidence_composer_v2_benchmark.py -v
uv run pytest
uv run python benchmarks/compare_evidence_composers_v2.py
uv run python benchmarks/compare_evidence_composers_v2.py --stress
```

Artifacts are written as:

```text
benchmarks/results/MEM-ADAPT-005_*.json
```

## Acceptance discipline

Do not replace production composition because v2 passes the synthetic combined corpus.

The next acceptance layers are:

1. verify `MEM-ADAPT-005` quick/stress stability locally;
2. run v2 against real PostgreSQL candidate pools from the `MEM-ADAPT-003` integration scenarios;
3. add semantic/LLM acceptance tests where the final stateless worker must actually use the bounded packet correctly;
4. benchmark latency and memory overhead;
5. keep the frozen v1 and top-k policies runnable as regression baselines.

A failure should be classified by observable layer rather than patched by benchmark-specific weighting.
