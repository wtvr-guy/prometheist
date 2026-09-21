# Experiment 2 — Person-dependent memory sufficiency

**Status:** frozen candidate and control fixture; awaiting native
`qwen3:4b-instruct-2507-q4_K_M` evidence. Production behavior is unchanged.

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

## Frozen controlled cases

The shared fixture
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

## Candidate and decision rule

The exact production and candidate prompts, raw outputs, fixture hash, model,
revision, per-trial results, and report hash are captured by
[`run_person_fidelity_mechanism_experiments.py`](../../benchmarks/run_person_fidelity_mechanism_experiments.py).

Promotion requires all of the following:

1. every candidate case matches on every native trial;
2. at least one production-contract failure is repaired;
3. no production-contract pass regresses;
4. the result comes from a clean committed revision using the configured reference
   Ollama model; and
5. the exact raw result is preserved; and
6. a human review confirms that every `memory_deficit` identifies the missing
   remembered semantics rather than returning a vague request for "more context."

The runner can mark the mechanical gate as passed, but it deliberately leaves
production acceptance false until the frozen deficit oracles have been reviewed. An
accepted result authorizes promotion of the candidate Composer prompt only. It does
not prove that Adaptive Recall can recover every named deficit or that person fidelity
has improved end to end.

## Run

Commit this experimental harness first so the native result binds to immutable source,
then run on the configured Windows/Ollama host:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -Experiment composer -Trials 3
```

Verify the resulting artifact independently:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -VerifyResult benchmarks/results/PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_<timestamp>.json
```

Do not promote the candidate from fixture validation or mocked tests. Article 31
requires native model evidence for this semantic claim.
