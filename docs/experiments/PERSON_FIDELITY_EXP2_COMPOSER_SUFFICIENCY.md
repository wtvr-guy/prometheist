# Experiment 2 — Person-dependent memory sufficiency

**Status:** v1 rejected/revise from native evidence; v2 candidate and prospective
holdout frozen for a new native `qwen3:4b-instruct-2507-q4_K_M` run. Production
behavior is unchanged.

**Measured failure:** in the verified `PERSON-FIDELITY-001` native run, the
user-prompt Composer returned `sufficient=true` on its first call for probes 1–9,
including a novel person-dependent decision with no personal evidence and a
characteristic-expression task with no style evidence. Adaptive Recall therefore
performed no work.

**Changed mechanism:** the Composer's semantic sufficiency contract only. Retrieval,
packet bounds, source policy, model, transport, output schema, final response, and
Adaptive Recall remain fixed.

## Hypothesis

The production contract conflates two questions:

1. can a general model produce an answer; and
2. does the supplied evidence support an answer as this particular person?

Making that distinction explicit should cause the Composer to reject empty,
irrelevant, and materially partial personal packets while preserving success for
general knowledge, current-prompt evidence, complete personal evidence, and complete
contradictory evidence.

## v1 native result

The exact retained result is
[`PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_2026-09-21_130207.json`](../../benchmarks/results/PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_2026-09-21_130207.json).
It was collected at revision `b860a91e` with three trials per case.

| Measure | Production contract | v1 candidate |
|---|---:|---:|
| Cases passing every trial | 7/10 | 7/10 |
| Frozen failures repaired | — | 1 |
| Frozen passes regressed | — | 1 |

The candidate repaired `cs-005-empty-person-decision`: every trial correctly named
the missing values and decision history. It also produced semantically useful,
specific deficits for irrelevant evidence and the unknown teacher identity.

It nevertheless failed promotion for three independent reasons:

- it regressed `cs-002-current-evidence` by demanding historical confirmation for a
  preference explicitly stated in the current prompt;
- it still accepted topically related but non-diagnostic evidence in
  `cs-004-partial-person-evidence`; and
- it still accepted one-sided self-report in `cs-008-one-sided-contradiction`, even
  though the question explicitly required comparison with observed behavior.

The result is directional evidence that the generic-answerability distinction helps,
but the v1 wording overcorrects current evidence and does not reliably decompose a
question into all material evidence requirements. It is not a production candidate.

## Frozen controlled cases

The original shared fixture
[`person_fidelity_mechanism_experiments_v1.json`](../../benchmarks/person_fidelity_mechanism_experiments_v1.json)
was frozen before native candidate execution. It contains ten Composer cases:

| Evidence condition | Expected |
|---|---|
| General knowledge; no history required | sufficient |
| Fact introduced by the current prompt | sufficient |
| Complete person-dependent evidence | sufficient |
| Partial person-dependent evidence | insufficient |
| Empty novel-decision history | insufficient |
| Irrelevant personal memory | insufficient |
| Complete self-report/behavior contradiction | sufficient |
| Self-report without requested behavioral evidence | insufficient |
| Unknown personal fact before recall exhaustion | insufficient |
| Complete identity-conflict evidence | sufficient |

The fixture uses a third fictional subject and shares no Mara or Wren content. It is
a semantic-contract experiment, not the held-out person-fidelity evaluation.

The v2 fixture
[`person_fidelity_mechanism_experiments_v2.json`](../../benchmarks/person_fidelity_mechanism_experiments_v2.json)
permanently retains all ten v1 cases as development/retest cases and adds seven cases
frozen before v2 native execution. Those prospective cases independently test:

- direct current corrections despite conflicting older memory;
- a personal fact supplied entirely in the current prompt;
- complete versus merely adjacent evidence for a context-sensitive decision;
- one-sided versus complete self-report/behavior reconciliation; and
- an empty contextual prediction request.

The v2 contract uses an ordered current-evidence, evidence-need, and material-slot
decision procedure. Its key falsifiable addition is that evidence must discriminate
the requested context: a packet still compatible with materially different answers
is incomplete.

## Candidate and decision rule

Every new run captures the exact production and candidate prompts, quarantined
evidence payloads and references, schemas, token limits, model identity, raw outputs
or transport errors, validated stage results, benchmark evaluations, fixture hash,
revision, and final disposition in a separate hash-linked interaction chain for each
trial. A content-addressed `run_manifest.json` inventories every raw artifact byte,
and the compact result records the manifest hash. Compact content-derived attempt
directory names preserve Windows path budget; the manifest and case-input artifact
retain the complete experiment, variant, case, and trial identity. Both are written by
[`run_person_fidelity_mechanism_experiments.py`](../../benchmarks/run_person_fidelity_mechanism_experiments.py).

The retained 2026-09-21 v1 and v2 compact results predate this correction. They
contain prompts, raw outputs, parsed outputs, errors, and verdicts, but do not
contain independent per-invocation chains. That missing causal evidence cannot be
reconstructed honestly after the runs; only a rerun can create it.

Promotion requires all of the following:

1. every candidate case matches on every native trial;
2. at least one production-contract failure is repaired;
3. no production-contract pass regresses;
4. the result comes from a clean committed revision using the configured reference
   Ollama model; and
5. the exact raw result and its complete verified artifact manifest are preserved; and
6. a human review confirms that every `memory_deficit` identifies the missing
   remembered semantics rather than returning a vague request for "more context."

The runner can mark the mechanical gate as passed, but it deliberately leaves
production acceptance false until the frozen deficit oracles have been reviewed. An
accepted result authorizes promotion of the candidate Composer prompt only. It does
not prove that Adaptive Recall can recover every named deficit or that person fidelity
has improved end to end.

## Run

Commit the v2 experimental harness first so the native result binds to immutable
source, then run on the configured Windows/Ollama host. The script defaults to v2:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -Experiment composer -CandidateVersion v2 -Trials 3
```

Verify the resulting artifact independently:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -VerifyResult benchmarks/results/PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_<timestamp>.json
```

Do not promote the candidate from fixture validation or mocked tests. Article 31
requires native model evidence for this semantic claim.
