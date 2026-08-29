# Adaptive Memory Attention Experiment

**Status:** active experimental branch implementation. Not yet an accepted architectural replacement for the frozen v0.7 recall profiles.

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

## Current branch implementation

The experiment is deliberately parallel to the production path.

- `src/jit_agent/adaptive_memory_attention.py` contains the deterministic controller.
- `src/jit_agent/adaptive_memory_retrieval.py` executes one adaptive pass against the same PostgreSQL Memory Kernel and canonical event ledger used by the frozen profiles.
- `tests/test_adaptive_memory_attention.py` verifies controller geometry, independence of scope/depth, multi-anchor focus, and anti-lock-in behavior.
- `tests/test_adaptive_memory_retrieval.py` verifies the actual PostgreSQL retrieval boundary, canonical focus use, reorientation, provenance-bearing packets, and the global-sequence leakage barrier.
- `benchmarks/compare_memory_attention_architectures.py` performs adversarial head-to-head retrieval comparisons.

The live capability registry and interaction runtime still use the frozen v0.7 profiles. This branch must earn any replacement through evidence first.

## Constraint governance

All adaptive runtime numbers are visible to the repository constraint auditor. Numeric policy maps were intentionally represented as named typed policy objects rather than hiding behavioral values inside dict/tuple literals.

The values are classified as follows:

- evidence floor -> existing `MEM-SCORE-001`;
- candidate scope windows -> existing `MEM-BREADTH-001`;
- graph budgets/hops/decay -> existing `MEM-GRAPH-001`;
- dominance/entropy/reorientation rules -> new `MEM-ADAPT-001`;
- zero/one/multiple anchor and non-negative-domain checks -> structural invariants.

Every new empirical value remains `PROVISIONAL`.

## Adversarial comparison design

`MEM-ADAPT-001` deliberately tries to break both architectures rather than demonstrate the new one.

### Common substrate

Every scenario uses the same:

- append-only canonical events;
- current percept;
- `before_global_seq` leakage boundary;
- conservative evidence floor;
- automatic broad/shallow attention aperture;
- canonical anchor IDs when focus is available.

The benchmark reports whether the automatic aperture already contained all required evidence. Such cases are excluded from downstream head-to-head wins because neither deliberate architecture deserves credit for work already completed by the common JIT substrate.

### Frozen side

The benchmark runs every applicable frozen explicit research profile rather than choosing a convenient loser:

- `DEEPER_RESEARCH` when at least one anchor exists;
- `CROSS_REFERENCE` when multiple anchors exist;
- `FOCUSED_RECALL` when exactly one anchor exists.

`STANDARD` is also recorded in direct-candidate sweeps as a kernel reference, but it is not counted as a currently selectable post-aperture research capability.

### Adaptive side

The adaptive side receives only:

- the same current percept;
- the same canonical focus anchors;
- a closed uncertainty enum;
- deterministic retrieval telemetry.

The controller derives all numeric mechanics.

### Hostile scenario families

The current harness includes:

1. **Aperture packet truncation** — required evidence is inside the broad candidate population but just outside the bounded surfaced packet.
2. **Direct candidate ceiling** — an old exact-phrase target competes against increasingly many newer equal-term distractors. This is expected to expose the important fact that the automatic aperture is already wider than every deliberate direct-candidate profile.
3. **Single-anchor depth sweep** — opaque target at association depths through and beyond the deepest supported traversal.
4. **Multi-anchor depth sweep** — joint relational search at depths that distinguish `DEEPER_RESEARCH`, `CROSS_REFERENCE`, and adaptive deep focus.
5. **Association fan-out ceiling** — the required edge sorts behind hundreds or thousands of distracting outgoing edges and disappears when an association budget is exhausted.
6. **Anchor lock-in** — a misleading anchor consumes the deep association budget while the correct evidence is reachable from the current semantic cue; adaptive attention must eventually drop the anchor and reorient.
7. **Shared ceilings** — candidate, depth, and association-budget cases intentionally extend far enough that both architectures should fail. Those failures are retained as architectural evidence rather than treated as benchmark defects.

The stress harness reports `largest_tested_success` and `smallest_tested_failure`. It does not claim an exact limit from sparse sample points.

## Running the experiment locally

The comparison script is destructive and refuses to run against a database whose name does not contain `test` or `benchmark`. By default it uses the same local test database as pytest:

```powershell
$env:TEST_DATABASE_URL = "postgresql://jit_agent_app@localhost:5432/jit_agent_test"
```

If that is already your normal test configuration, setting it again is unnecessary.

First run the targeted tests:

```powershell
uv run pytest tests/test_adaptive_memory_attention.py tests/test_adaptive_memory_retrieval.py -v
```

Then run the whole regression suite:

```powershell
uv run pytest
```

Run the comparison harness in its smaller boundary sample:

```powershell
uv run python benchmarks/compare_memory_attention_architectures.py
```

Run the hostile boundary-adjacent sweeps:

```powershell
uv run python benchmarks/compare_memory_attention_architectures.py --stress
```

Each benchmark run writes a timestamped JSON artifact under `benchmarks/results/` and prints a compact summary containing:

- aperture-sufficient case count;
- adaptive-only successes;
- frozen-only successes;
- cases both solve;
- cases neither solves;
- largest tested success / smallest tested failure for candidate breadth;
- single-anchor graph depth;
- multi-anchor graph depth;
- association fan-out;
- per-method elapsed time and configured/reached retrieval work in the full JSON.

The result artifact should be reviewed before changing any production profile or routing behavior.

## Frozen baseline

The existing v0.7 profiles remain the comparison baseline until the adaptive controller earns replacement.

The branch must not claim architectural acceptance merely because the new abstraction is cleaner.

## Required evaluation beyond the first harness

Before replacing the old profiles, the experiment must ultimately cover:

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
14. generated holdout histories not used to tune the controller;
15. native local-model acceptance after deterministic retrieval behavior is understood.

## Acceptance rule

The adaptive controller may replace the named profiles only if it reproduces all accepted continuity/provenance behavior and demonstrates a measurable advantage or meaningful simplification without material regression.

If it does not, retain the current profiles and preserve this branch/document as negative experimental evidence.
