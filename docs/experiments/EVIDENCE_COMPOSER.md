# Evidence Composer Experiment

**Status:** experimental. Not wired into the production interaction path.

## Question

Can Prometheist improve bounded working evidence without enlarging the final `MemoryPacket` by replacing raw top-k surfacing with deterministic coverage-aware composition?

`MEM-ADAPT-001-DIAGNOSTIC` showed that old relevant evidence can remain in the raw candidate population hundreds of ranks beyond the point where a six- or ten-item packet stops surfacing it. The early practical failure is therefore often composition/ranking pressure rather than candidate-generation exhaustion.

`MEM-ADAPT-002` also showed a shared failure when several individually weaker memories jointly matter but stronger repetitive distractors consume the bounded packet.

## Separation of concerns

The experiment treats retrieval and composition as different mechanisms:

```text
current percept
    -> adaptive retrieval controller
    -> Memory Kernel candidate pool
    -> Evidence Composer
    -> bounded evidence packet
    -> fresh stateless cognition
```

The adaptive attention controller is frozen for this experiment. Both composer variants receive the same ordered candidate pool and the same final packet budget.

Every composition-specific scenario must first verify that all required evidence is present in the shared candidate pool. If required evidence never reaches that pool, the case is an upstream retrieval/admission failure and cannot be counted as evidence for or against either composer.

## Baseline

The baseline is the current effective behavior: take the first `N` evidence items in retrieval order.

That ordering is deterministic and relevance-sensitive, but equal-score ties are recency-biased. Near-duplicate or semantically indistinguishable newer events can therefore crowd older evidence out of the cognition boundary even while the old evidence remains retrievable.

## Experimental composer

`src/jit_agent/evidence_composer.py` implements a deterministic, parameter-light greedy composer.

The strongest current retrieval candidate is preserved first. Remaining slots maximize marginal evidence coverage using application-observable properties:

- new canonical provenance;
- new retrieval reasons/routes;
- lexical content not already represented in the packet;
- source diversity;
- event-type diversity;
- conversation diversity;
- previously surfaced evidence as a tie preference;
- existing retrieval score and rank as final tie-breakers.

There are no model-generated weights, no learned scoring coefficients, and no ground-truth labels available to the composer.

Numeric-only lexical suffixes are ignored in the lexical signature so mechanically numbered near-duplicates do not masquerade as unique evidence merely because their sequence token differs.

## Retention semantics

Previously surfaced evidence may be supplied as retained evidence on a later pass. Retention is deliberately sticky rather than absolute: retained evidence wins a tie, but genuinely more informative new evidence can evict it.

This tests the proposed invariant:

> Retrieval may redirect attention; it must not silently erase uniquely useful evidence already admitted to bounded cognition.

The experiment does not yet define a durable production evidence reservoir. It only tests whether this composition rule is useful enough to justify designing one.

## MEM-ADAPT-003 scenarios

The benchmark currently includes:

1. **Equal-term old memory** — an old tied memory competes with many newer near-duplicates.
2. **Correction pair under duplicate pressure** — both an older claim and its later correction must survive.
3. **Distributed weak clues** — several older complementary memories and newer repetitive distractors all satisfy the same retrieval cue; top-k may prefer recency while the composer is tested only after every required clue is confirmed present in the shared pool.
4. **Near-duplicate flood** — one information-dense older event competes against many repetitive updates.
5. **Temporally distributed evidence** — early, middle, and late project-history facts must coexist in one bounded packet.
6. **Retained evidence across an attention shift** — a later retrieval pass changes focus, but uniquely useful prior evidence should remain available.
7. **Unsupported-query abstention** — composition must not manufacture evidence when retrieval provides no historical support.

Quick mode uses a 32-item candidate pool; stress mode uses 64. Both use the same six-item final packet for the two composer variants. These are benchmark mechanics only, not proposed production settings.

## Running locally

Use only a disposable test or benchmark database:

```powershell
$env:TEST_DATABASE_URL = "postgresql://jit_agent_app@localhost:5432/jit_agent_test"
```

Run the focused tests:

```powershell
uv run pytest tests/test_evidence_composer.py tests/test_evidence_composer_benchmark_integration.py -v
```

Then the full suite:

```powershell
uv run pytest
```

Run the benchmark:

```powershell
uv run python benchmarks/compare_evidence_composers.py
uv run python benchmarks/compare_evidence_composers.py --stress
```

Artifacts are written as `benchmarks/results/MEM-ADAPT-003_*.json`.

## Evaluation rule

Do not adopt the composer because it improves one synthetic old-memory case. The experiment must show:

- every required event is present in the common candidate pool before a composition win/loss is counted;
- no top-k-only regressions on the hostile corpus;
- improved worst-case required-evidence completeness;
- preserved abstention;
- deterministic replay;
- bounded final packet size;
- no dependence on answer labels or model-generated control state.

If coverage-aware composition merely trades one kind of crowd-out for another, retain top-k and preserve the experiment as negative evidence.
