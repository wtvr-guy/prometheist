> **Historical experiment record (PR #22).** This file is preserved verbatim below as evidence. Branch implementation/status claims and earlier memory-profile names are historical; the live system uses the v2 memory-only Composer and Adaptive Recall. See `../../README.md` for current disposition.
>
# MEM-ADAPT-002: Semantic and Selection Adversarial Round

**Status:** active experiment on `experiment/adaptive-memory-attention`. The live interaction path remains on the frozen v0.7 memory-research architecture.

## Why a second round exists

`MEM-ADAPT-001` established two useful adaptive behaviors without demonstrating a new underlying graph-retrieval algorithm:

1. multi-anchor attention can use deeper traversal than the frozen `cross_reference` preset because anchor cardinality and association effort are independent; and
2. bounded anti-lock-in reorientation can recover evidence after repeated focus on a misleading anchor fails to improve support.

The first round also exposed a shared failure: an old memory can become practically unreachable when many newer memories are semantically indistinguishable under the current cue. The first benchmark sampled that failure only at large distractor counts, so it did not identify the stage at which the target was actually lost.

This round therefore separates two questions:

1. **Where does equal-term old-memory selection fail?**
2. **Does adaptive attention expose better evidence under semantic ambiguity, corrections, false associations, and attentional traps?**

## MEM-ADAPT-001-DIAGNOSTIC

`benchmarks/diagnose_memory_selection_ceiling.py` instruments the equal-term failure without changing production retrieval behavior.

For each tested distractor count, candidate window, and surfaced packet size it records:

- raw direct-candidate population size;
- the target's rank in the candidate router output;
- the target's rank after kernel admission and deterministic score sorting;
- whether the kernel selected the target within its own bounded output;
- whether the target survives the final surfaced packet bound.

The diagnostic explicitly distinguishes:

```text
candidate routing
    -> score admission/ranking
    -> bounded packet surfacing
```

This matters because candidate-window exhaustion and top-k degeneracy are different failure modes and require different remedies.

The current kernel tie-break order is:

```text
score descending
-> global_seq descending
-> event_id ascending
```

Therefore, when an old event and many newer events receive the same relevance score, recency deterministically wins the tie. Increasing a candidate window does not necessarily help if the old event remains below the surfaced packet rank.

## MEM-ADAPT-002 evaluation boundary

`benchmarks/compare_memory_attention_semantics.py` evaluates **evidence retrieval**, not final-answer LLM reasoning.

A retrieval architecture succeeds when it exposes the complete canonical evidence set required by a downstream stateless worker. The benchmark does not ask the retrieval layer itself to decide:

- which conflicting claim is true;
- whether a correction supersedes an earlier statement;
- whether temporal order proves causality;
- what final natural-language conclusion should be produced.

Those are separate cognitive/epistemic operations. Conflating them with retrieval would make a retrieval benchmark uninterpretable.

## Scenario families

### Correction-pair completeness

An older claim and a later correction must both remain available. Success means the downstream worker can see the history required to reason about supersession rather than receiving only the newest statement.

### Zero-overlap contextual bridge

The target has no useful lexical overlap with the current percept and must be recovered through a canonical focus anchor and persisted association route.

### Attractive false-short path versus deeper counterevidence

A plausible one-hop claim competes with evidence reachable only through a substantially deeper path. Success requires exposing both rather than allowing the short route to monopolize attention.

### Multi-anchor five-hop relationship

The required evidence depends on multiple focus anchors and deeper traversal than frozen `cross_reference` can request. This directly retests the hypothesis that anchor cardinality and association depth should be independent dimensions.

### Obsolete single-anchor lock-in

A plausible but obsolete anchor owns a large hostile association neighborhood. Repeated anchored passes make no support progress. Adaptive attention must eventually reorient and recover a correction from the original semantic cue.

### Mutually reinforcing multi-anchor lock-in

Two wrong anchors form a self-reinforcing cluster with a large hostile association frontier. This tests whether anti-lock-in works for a cluster rather than only for one bad focus event.

### Multiple weak clues under packet pressure

Several individually weaker memories are jointly necessary while exact-looking distractors compete for the bounded packet. This probes the shared top-k failure family from a synthesis perspective.

### Unsupported-query abstention

The ledger contains no historical support for the cue. Widening or reorienting attention must not manufacture evidence.

## What remains deliberately out of scope

This round still does not prove that a model will correctly interpret the evidence packet. Future acceptance work must separately test:

- correction/supersession reasoning;
- contradiction classification;
- causal versus merely temporal relationships;
- explicit uncertainty when evidence conflicts;
- provenance-sensitive answers;
- model selection of semantic uncertainty classes and canonical candidate indices;
- deterministic replay across full stateless interaction rounds.

## Running locally

Use only a dedicated database whose name contains `test` or `benchmark`.

```powershell
$env:TEST_DATABASE_URL = "postgresql://jit_agent_app@localhost:5432/jit_agent_test"
```

First update the experimental branch:

```powershell
git fetch origin
git switch experiment/adaptive-memory-attention
git pull --ff-only
```

Run the targeted contract and retrieval tests:

```powershell
uv run pytest tests/test_adaptive_memory_attention.py tests/test_adaptive_memory_retrieval.py tests/test_adaptive_memory_benchmark_contract.py tests/test_adaptive_memory_semantic_benchmark_contract.py -v
```

Then run the complete repository suite:

```powershell
uv run pytest
```

Instrument the shared equal-term failure first:

```powershell
uv run python benchmarks/diagnose_memory_selection_ceiling.py
uv run python benchmarks/diagnose_memory_selection_ceiling.py --stress
```

Then run the semantic comparison:

```powershell
uv run python benchmarks/compare_memory_attention_semantics.py
uv run python benchmarks/compare_memory_attention_semantics.py --stress
```

Each run writes a timestamped JSON result beneath `benchmarks/results/`.

## Interpretation rule

Do not merge the adaptive architecture merely because it wins more benchmark cases.

A useful decision requires understanding *why* each architecture succeeds or fails. In particular:

- a wider candidate window is not a solution to a final-packet ranking failure;
- deeper traversal is not a solution to missing or misleading association structure;
- successful reorientation must justify its additional retrieval work;
- semantic evidence completeness is not the same as correct epistemic reasoning;
- shared failures belong to the Memory Kernel or evidence-selection layer, not automatically to either attention-controller architecture.

The experiment remains falsifiable: if the adaptive controller cannot demonstrate a material capability or simplification advantage without new regressions, the frozen profiles remain the accepted baseline.

