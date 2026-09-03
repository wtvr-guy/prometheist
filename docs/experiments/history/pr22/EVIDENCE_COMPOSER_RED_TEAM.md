> **Historical experiment record (PR #22).** This file is preserved verbatim below as evidence. Branch implementation/status claims and earlier memory-profile names are historical; the live system uses the v2 memory-only Composer and Adaptive Recall. See `../../README.md` for current disposition.
>
# Evidence Composer Red Team

**Status:** active adversarial experiment. The coverage-aware composer is frozen for this round and remains disconnected from the production interaction path.

## Question

Can the current parameter-light coverage-aware composer be made to lose against ordinary retrieval-order top-k when novelty, diversity, or retention are misleading signals?

`MEM-ADAPT-003` showed large gains for coverage-aware composition in the failure families it was designed to address. That evidence is not sufficient for adoption because the benchmark and algorithm share an inductive bias: repetitive high-ranked evidence can crowd out lower-ranked informationally distinctive evidence.

`MEM-ADAPT-004` reverses the pressure. It deliberately constructs cases where high retrieval rank should matter more than marginal diversity.

## Isolation boundary

This round does not use PostgreSQL retrieval. Each case constructs an explicit `MemoryEvidence` candidate pool in retrieval order, with fixed scores and canonical IDs.

Both policies receive exactly the same candidates and the same six-item final packet budget:

```text
explicit ordered MemoryEvidence pool
        |-- retrieval-order top-k
        `-- frozen coverage-aware composer
                    |
              six-item packet
```

This isolates the composer itself. A failure cannot be blamed on candidate generation, admission thresholds, association traversal, adaptive attention control, or model behavior.

## Red-team rule

A `top_k_only` result is evidence against the current composer. It must not be relabeled as a bad fixture merely because the case was intentionally designed to exploit the composer's bias.

Do not tune the composer until the unmodified implementation has been measured against the complete corpus.

## Attack families

### Numeric fact blindness

The current lexical signature ignores numeric-only tokens so mechanically numbered near-duplicates do not masquerade as unique evidence. The attack makes the numbers themselves the payload: six high-ranked calibration facts differ only by their numeric values, while lower-ranked verbose memories contain abundant lexical novelty.

This tests whether duplicate suppression accidentally erases semantically critical numeric distinctions.

### Corroboration is repetition

Several highly ranked near-identical observations are all required because repetition itself represents corroboration. Lower-ranked anecdotes are lexically distinctive.

This attacks the assumption that redundancy is usually waste.

### Random-token novelty attack

Lower-ranked irrelevant memories contain deterministic token salad. If lexical novelty dominates retrieval relevance too strongly, the composer can be gamed by meaningless uniqueness.

### Diversity-metadata attack

Six strong required facts come from one trusted source and one conversation. Lower-ranked irrelevant memories vary source, conversation, and event type.

This tests whether diversity is being treated as intrinsic utility rather than a conditional signal.

### Stale-retention poisoning

A low-score item retained from an earlier attention round is obsolete, while the six current top-ranked facts are all required. The current implementation prepends retained evidence to the composition pool, so this case tests whether retention has accidentally become an unconditional slot reservation rather than a tie preference.

### Verbose irrelevance over concise truth

Six concise high-ranked facts compete against lower-ranked verbose narratives containing many unique tokens.

This tests whether content length/lexical richness can masquerade as informational utility.

## Controls

The corpus also includes:

- a positive control from the `MEM-ADAPT-003` failure family, where a uniquely informative lower-ranked memory should beat repetitive top-k crowd-out; and
- a shared-success control where both policies should retain a small set of distinct high-ranked facts.

The red-team benchmark is therefore not constructed so top-k must always win.

## Running locally

No database is required for this benchmark.

Run the focused tests:

```powershell
uv run pytest tests/test_evidence_composer_redteam.py -v
```

Then run the full regression suite:

```powershell
uv run pytest
```

Run the red team:

```powershell
uv run python benchmarks/redteam_evidence_composer.py
uv run python benchmarks/redteam_evidence_composer.py --stress
```

Artifacts are written as `benchmarks/results/MEM-ADAPT-004_*.json`.

## Interpretation

The important output is:

```text
head_to_head:
    coverage_aware_only
    top_k_only
    both
    neither
```

A nonzero `top_k_only` count is expected and useful: it identifies where the current composer's inductive bias is unsafe.

The next design step must be based on the failure mechanisms, not aggregate score. For example:

- numeric blindness may require typed fact/value features rather than changing a global novelty weight;
- stale retention may require retention to enter only after current relevance constraints, not as a prepended candidate;
- corroboration may require duplicate-cluster support counts instead of preserving every duplicate;
- novelty attacks may require relevance floors or conditional diversity rather than abandoning diversity entirely.

Do not add those mechanisms before the frozen composer has been measured.

