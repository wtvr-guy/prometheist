# Experiment 1 — Lexical relevance against common-word matches and long-prompt dilution

**Status:** candidate mechanisms tested and **rejected**. Verdict
`INSUFFICIENT_DISCRIMINATION` under the
[baseline decision rule](PERSON_FIDELITY_BASELINE.md). No production retrieval
code was changed.

**Question named by the review:** can lexical relevance be changed so that it
resists common-word matches and long-prompt dilution, repairing the evidence
selection failures measured on `PERSON-FIDELITY-001`?

**Answer:** not by any scoring function tested here. Every candidate that
improved evidence delivery produced outcomes *identical* to simply lowering the
admission cutoff, which the review explicitly forbids. The one candidate family
that was not cutoff-equivalent repaired the unknown probe only by breaking three
probes it had previously passed.

## Method

The attention aperture's retrieval is deterministic: a pure function of the
event ledger, the cue, and the scoring policy. It therefore does not need a
native run to characterize, and a native run would measure it less precisely
because generation variance is layered on top.

[`benchmarks/replay_person_fidelity_retrieval.py`](../../benchmarks/replay_person_fidelity_retrieval.py)
rebuilds the seeded ledger exactly as the native runner orders it, applies the
aperture cue (current percept text only, six-item recall budget, `minimum_score`
0.15), and reports the delivered packet plus the complete score table.

**Replay fidelity was verified before it was used to judge anything.** Against
[`PERSON-FIDELITY-001_2026-09-16_215839.json`](../../benchmarks/results/PERSON-FIDELITY-001_2026-09-16_215839.json)
at revision `9f1cc3c`, the replay reproduces all ten recorded native retrieval
packets exactly.

Holding fixture, budget, cutoff, and packet limit fixed, only the lexical scoring
function was varied.

## The negative baseline, on both frozen people

| Fixture | Retrieval contract met |
| --- | --- |
| `PERSON-FIDELITY-001` (Mara Ellison) | 2/10 |
| `PERSON-FIDELITY-002-HOLDOUT` (Wren Adisa) | 2/10 |

The holdout was frozen before any mechanism work and independently reproduces
the same failure families: origin evidence half-delivered, relational context
lost, the long multi-constraint decision prompt and the characteristic-expression
prompt delivering nothing, and the open-world unknown probe admitting unrelated
records. The failures are properties of the mechanism, not of Mara's fixture.

## Candidates tested

All at the unchanged 0.15 cutoff, six-item budget, and 0.78 lexical weight.

| # | Candidate | Baseline probes met | Unknown probe clean |
| --- | --- | --- | --- |
| 0 | current uniform query-token coverage | 2/10 | no |
| 1 | ledger-IDF weighted coverage | 2/10 | no |
| 2 | IDF cosine (query- and event-normalized) | 3/10 | **yes** |
| 3 | absolute matched-saliency mass, saturating | 6/10 | no |
| 4 | BM25, Robertson IDF with pivoted length | 6/10 | no |
| 5 | general-language saliency tier (α = 0…0.5) | 6/10 | no |
| 6 | damped query-mass normalization (p = 0.5) | 5/10 | no |

## Why each was rejected

### Corpus-derived saliency cannot identify common words at this ledger size

Nineteen life events give document frequency almost no resolution. Measured IDF
over the baseline ledger spans only 1.569 to 2.996, and the words that cause the
false matches are indistinguishable from the words that carry the topic:

| Token | Document frequency | IDF |
| --- | --- | --- |
| `would` | 4 | 1.569 |
| `name` | 2 | 1.992 |
| `espresso` | 2 | 1.992 |
| `hybrid` | 1 | 2.351 |
| `surprise` | 1 | 2.351 |

`name` and `espresso` receive exactly the same weight. Candidate 1 therefore
reproduced candidate 0's probe outcomes exactly.

### A general-language saliency tier changed nothing measurable

Candidate 5 replaced ledger statistics with a frozen tier of English
closed-class and light-verb vocabulary, authored from grammatical categories
rather than from the observed failures. Sweeping its weight α across
0.0, 0.1, 0.2, 0.3, and 0.5 produced **identical** probe outcomes at every
value. The damping exponent, not the saliency tier, accounted for the entire
effect. Two independent saliency sources therefore both failed to discriminate.

### The decisive control: recall gains were exactly cutoff-equivalent

Candidate 6 was compared against the current formula run at progressively lower
cutoffs, matched on admission volume:

| Configuration | Probes met | Lexically reachable met | Noise admitted | Total admitted |
| --- | --- | --- | --- | --- |
| current, cutoff 0.15 | 2 | 4 | 3 | 13 |
| damped p = 0.7, cutoff 0.15 | 4 | 6 | 15 | 28 |
| current, cutoff 0.07 | 4 | 6 | 15 | 28 |
| damped p = 0.5, cutoff 0.15 | 5 | 7 | 35 | 50 |
| current, cutoff 0.03 | 5 | 7 | 35 | 50 |

The two families trace the same curve. Per query, dividing by a power of the cue
mass and moving the threshold are the same monotone reparametrization, and
empirically the across-query differences were nil on this fixture. Candidates 3
and 4 behave the same way: they gain probes by admitting four to five unrelated
records per probe, saturating the six-item budget.

This is the change the review prohibited: "Do not lower a cutoff or edit
expected evidence merely to make these ten probes pass."

### The one non-cutoff-equivalent family trades failures rather than removing them

Event-length normalization is genuinely different. The unknown probe fails at
**every** cutoff of the current formula from 0.15 down to 0.02, so no threshold
change can clean it, but candidate 2 does clean it. That difference is real.

It is also not an improvement. At the normalization strength that keeps the
unknown probe clean, `pf-q001`, `pf-q002`, and `pf-q005` all stop delivering
their required evidence, capping the family at 4/10. It exchanges one failure
family for another.

## Two findings that constrain any future retrieval work

### A lexical ceiling of 8/10, not 10/10

`pf-e006` (the observed isolation record) and `pf-e009` (the observed camera
deliberation) score **exactly 0.0** against their probes' cues. They are
third-person observational records that share no vocabulary with the
first-person questions they answer. No admission threshold and no weighting of
shared tokens can deliver evidence that shares no tokens. These two probes are
unreachable for the entire lexical family and belong to the association and
source-policy mechanisms instead.

### The unknown probe's failure is a part-of-speech collision

`pf-q010` asks for a teacher's **name**. It matches `pf-e014`, "I *name* what is
known," where the token is a verb, and `pf-e017`, "My legal *name* is Mara
Ellison." A bag-of-words kernel cannot separate these senses, which is why
candidates 0, 1, 3, 4, 5, and 6 all admit them and only whole-document
normalization suppresses them.

## Verdict and consequence

`INSUFFICIENT_DISCRIMINATION`. The public fixture does not separate any tested
lexical candidate from the null architecture plus a threshold change. Under
decision rule item 3 this is not permission to add the mechanism, so the
deterministic kernel is unchanged and the 2/10 retrieval baseline stands as
recorded evidence.

The holdout was **not** spent selecting among these candidates. It was used only
to confirm that the null architecture's failure families reproduce on an unseen
person. It remains available for a future candidate.

## What this redirects

The review proposed three experiments. This result changes what the other two
must explain:

1. Two of the nine structural failures are lexically unreachable in principle,
   so the Composer's sufficiency judgement and source-policy selection carry
   more of the remaining burden than the review's ordering implied.
2. Because raising retrieval volume is available at any time by moving a
   threshold, and does not repair the contract, the question is no longer "how
   much evidence reaches the responder" but "which evidence the architecture is
   willing to treat as sufficient" — Experiment 2 — and "which source roles it
   is willing to consider at all" — Experiment 3.

## Reproduce

```powershell
uv run --locked python benchmarks/replay_person_fidelity_retrieval.py --summary
uv run --locked python benchmarks/replay_person_fidelity_retrieval.py --holdout --summary
uv run --locked python benchmarks/replay_person_fidelity_retrieval.py `
  --compare-result benchmarks/results/PERSON-FIDELITY-001_2026-09-16_215839.json
```

The rejected candidate implementations were exploratory and are deliberately not
retained in the repository; the table above records what each one was, and the
replay harness reproduces the null baseline they were measured against.
