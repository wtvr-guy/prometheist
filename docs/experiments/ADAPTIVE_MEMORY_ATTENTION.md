# Adaptive Memory Attention Experiment

**Status:** experimental branch design. Not yet an accepted architectural replacement for the frozen v0.7 recall profiles.

## Question

Can Prometheist replace the named `deeper_research`, `cross_reference`, and `focused_recall` presets with one deterministic adaptive memory-attention controller while preserving or improving recall quality, provenance, determinism, latency, and resource safety?

The automatic attention aperture remains distinct and mandatory. The experiment concerns deliberate memory work after that initial packet proves semantically insufficient.

## Why this experiment exists

The current v0.7 profiles couple several independent retrieval variables:

| Profile | Direct candidates | Association edges | Hops | Decay |
| --- | ---: | ---: | ---: | ---: |
| automatic aperture | 750 | 0 | 0 | n/a |
| deeper research | 350 | 600 | 3 | 0.88 |
| cross-reference | 250 | 900 | 4 | 0.90 |
| focused recall | 150 | 1200 | 5 | 0.92 |

That progression encodes a hidden assumption: deliberate attention should become narrower as associative search becomes deeper. That may often be useful, but it is not generally true. Some tasks require broad+deep retrieval; others require narrow+shallow retrieval.

The three named research capabilities also invoke the same underlying associative memory mechanism. Their primary differences are anchor cardinality and fixed retrieval-budget presets. This suggests that they may be better represented as emergent configurations of one controller rather than separate first-class capabilities.

## Photography analogy: design aid, not runtime ontology

The discussion that motivated this experiment used camera concepts such as aperture, focal length, shutter speed, and ISO. The analogy was useful because it exposed independent control dimensions and tradeoffs.

Prometheist must **not** encode photography terms or assume that memory retrieval follows camera optics. Runtime concepts use literal retrieval terminology. The analogy has no evidentiary authority.

The useful architectural result is simply:

> Models point attention. Prometheist controls retrieval mechanics.

## Experimental control boundary

A model may express only bounded semantic direction:

1. a closed `MemoryUncertainty` enum describing what remains unresolved; and
2. bounded indices selecting zero or more candidates already visible in a canonical `MemoryPacket`.

The application resolves those indices to canonical event IDs. Models do not generate:

- search queries;
- event IDs;
- candidate limits;
- graph-hop counts;
- association budgets;
- decay values;
- score thresholds;
- execution order.

The deterministic controller receives semantic direction plus application-owned retrieval telemetry and derives the exact kernel mechanics.

## Initial semantic uncertainty vocabulary

The experimental closed enum is:

- `MISSING_CONTEXT`
- `AMBIGUOUS_CANDIDATES`
- `MISSING_RELATIONSHIP`
- `POSSIBLE_CONTRADICTION`
- `SPECIFIC_DETAIL_MISSING`

These values are experimental. They survive only if tests show that they provide useful signal beyond simpler candidate selection.

## Independent retrieval dimensions

### Scope

How broadly direct candidate generation frames persisted memory:

- `CONTEXTUAL`
- `BALANCED`
- `NARROW`

### Associative effort

How aggressively bounded association traversal is explored:

- `SHALLOW`
- `MODERATE`
- `DEEP`

Scope and associative effort are intentionally independent. The controller can therefore express both broad+deep and narrow+shallow retrieval.

### Focus

Canonical event anchors constrain topology without replacing the current percept as the semantic cue:

- zero anchors -> unanchored search;
- one anchor -> concentrated search;
- multiple anchors -> joint/relational search;
- reorientation -> deliberately ignore prior anchors for one bounded pass.

Multiple-anchor focus subsumes the useful retrieval behavior currently exposed as a separate `cross_reference` capability.

## Conservative sensitivity

The first experiment does **not** adapt the conservative evidence threshold. It remains `0.15`.

This is deliberate. Variable activation sensitivity may eventually be useful, but lowering the evidence floor when retrieval struggles risks confusing greater recall with greater evidentiary support. Scope, associative effort, and anchor focus should be evaluated first.

## Retrieval telemetry

The first controller uses only bounded, deterministic measurements:

- candidate score distribution;
- normalized score entropy;
- dominant score share;
- number of selected anchors;
- count of consecutive anchored passes;
- support gain since the previous deliberate pass.

Scores are attention telemetry, not truth probabilities.

## Anti-lock-in rule

Adaptive focusing creates a positive-feedback risk:

```text
initial candidate wins
    -> search around candidate
    -> candidate-related evidence increases
    -> same candidate wins again
```

The controller therefore includes an explicit exploration escape hatch. After repeated anchored passes without positive support gain, the next pass enters `REORIENT` mode:

- prior focus anchors are temporarily ignored;
- candidate scope widens;
- traversal remains shallow;
- the current percept remains the semantic cue.

This is intended to reduce attentional tunnel vision and dominant-distractor failure.

## Frozen baseline

The existing v0.7 profiles remain the comparison baseline until the adaptive controller earns replacement.

The branch must not claim architectural acceptance merely because the new abstraction is cleaner.

## Required evaluation

Before replacing the old profiles, compare both systems on at least:

1. ordinary current-context recall;
2. obscure old-memory recall;
3. dominant-distractor scenarios;
4. multiple weak-clue scenarios;
5. bridge-memory scenarios;
6. broad-and-deep questions;
7. narrow-and-shallow exact-detail questions;
8. false associative chains;
9. anchor traps requiring reorientation;
10. contradiction/correction scenarios;
11. exact provenance preservation;
12. deterministic replay;
13. latency and candidate/association work;
14. native local-model acceptance.

## Acceptance rule

The adaptive controller may replace the named profiles only if it reproduces all accepted continuity/provenance behavior and demonstrates a measurable advantage or meaningful simplification without material regression.

If it does not, retain the current profiles and preserve this branch/document as negative experimental evidence.
