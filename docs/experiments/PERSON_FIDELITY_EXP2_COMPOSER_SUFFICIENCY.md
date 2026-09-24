# Experiment 2 — Person-dependent memory sufficiency

**Status:** v1 and v2 rejected/revise from native evidence. The decomposed v3
candidate and a new prospective holdout are frozen for native
`qwen3:4b-instruct-2507-q4_K_M` execution. Production behavior is unchanged.

**Measured failure:** in the verified `PERSON-FIDELITY-001` native run, the
user-prompt Composer returned `sufficient=true` on its first call for probes 1–9,
including a novel person-dependent decision with no personal evidence and a
characteristic-expression task with no style evidence. Adaptive Recall therefore
performed no work.

**Changed mechanism:** v3 decomposes the experimental Composer decision into a
current-evidence specialist and a historical-memory-completeness specialist. The
application deterministically returns sufficient when history is unnecessary and
otherwise invokes the second specialist. Retrieval, packet bounds, source policy,
model, transport, final response, and Adaptive Recall remain fixed.

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

## v2 native result

The latest exact retained v2 result is
[`PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_2026-09-21_223254.json`](../../benchmarks/results/PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_2026-09-21_223254.json),
with its permanent 511-file raw journal rooted at
[`2026-09-21_223254`](../../benchmarks/generated/pfmx/2026-09-21_223254). It was
collected at revision `e373ac0b` with three trials per case.

| Measure | Production contract | v2 candidate |
|---|---:|---:|
| Cases passing every trial | 12/17 | 14/17 |
| Frozen failures repaired | — | 3 |
| Frozen passes regressed | — | 1 |

The candidate repaired the context-adjacent partial cases
`cs-004-partial-person-evidence`, `cs-005-empty-person-decision`, and
`cs2-014-context-partial`. It failed both one-sided reconciliation controls,
`cs-008-one-sided-contradiction` and `cs2-015-one-sided-pattern`, by returning
`sufficient=true` on all six trials. It also regressed
`cs2-012-current-personal-fact`: despite the prompt explicitly stating that walnuts
trigger the user's allergy, all three trials demanded historical allergy evidence.

Those results are deterministic semantic failures, not sampling noise. They show
that adding more ordered instructions to the same small-model decision does not
reliably preserve the current-evidence rule while also enforcing material-slot
completeness. v2 is rejected.

The raw v2 journal proved which prompt, evidence, output, and stage verdict were
used. It did not independently record the parse/schema verdict for each retry or the
backend's complete response metadata. That observability gap motivated the v3
artifact additions below; missing v2 metadata is not reconstructed after the fact.

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

The v3 fixture
[`person_fidelity_mechanism_experiments_v3.json`](../../benchmarks/person_fidelity_mechanism_experiments_v3.json)
permanently retains all seventeen earlier cases and adds eight cases frozen before
v3 native execution. The new holdout independently tests:

- a current personal health fact and an ordinary general-knowledge question;
- current constraints that supersede older preferences;
- self-report without observed behavior and observed behavior without self-report;
- the corresponding complete two-sided reconciliation; and
- context-adjacent versus context-diagnostic evidence for serious criticism.

The v3 candidate gives the first specialist no historical packet and asks only
whether history is required. When it is, a separate fresh specialist receives the
historical packet and asks only whether every material historical slot is filled.
Neither specialist may perform the other's semantic decision. This is an
experimental decomposition only; the production Composer remains unchanged pending
native acceptance.

## Candidate and decision rule

Every new run captures the exact production and candidate prompts, quarantined
evidence payloads and references, schemas, token limits, model identity and digest,
exact Ollama request and response envelopes, HTTP/timing/token metadata, every
parse/schema acceptance or rejection, raw outputs or transport errors, validated
stage results, benchmark evaluations, host/runtime evidence, fixture hash, revision,
and final disposition in a separate hash-linked interaction chain for each trial.
Hidden reasoning text is not persisted verbatim; its byte length and SHA-256 remain
in the redacted response envelope. A content-addressed `run_manifest.json`
inventories every raw artifact byte, and the compact result records the manifest
hash. Compact content-derived attempt directory names preserve Windows path budget;
the manifest and case-input artifact retain the complete experiment, variant, case,
and trial identity. Both are written by
[`run_person_fidelity_mechanism_experiments.py`](../../benchmarks/run_person_fidelity_mechanism_experiments.py).

The earlier 2026-09-21 v1 and first v2 compact results predate per-attempt journals.
The latest v2 run has complete invocation chains but predates explicit validation
and backend diagnostic artifacts. Neither omission can be reconstructed honestly
after execution; only a rerun can create the missing evidence.

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

Commit the v3 experimental harness first so the native result binds to immutable
source, then run on the configured Windows/Ollama host. The script defaults to v3:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -Experiment composer -CandidateVersion v3 -Trials 3
```

Verify the resulting artifact independently:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -VerifyResult benchmarks/results/PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_<timestamp>.json
```

Do not promote the candidate from fixture validation or mocked tests. Article 31
requires native model evidence for this semantic claim.
