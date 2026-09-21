# Experiment 3 — Historical person-evidence source policy

**Status:** v1 rejected/revise from native evidence; v2 candidate and prospective
holdout frozen for a new native `qwen3:4b-instruct-2507-q4_K_M` run. Production
scopes and allowlists are unchanged.

**Measured failure:** the verified public baseline selected `USER_AUTHORED` for the
remote-work change and identity-integrity probes. Application code correctly enforced
that decision and excluded the `SYSTEM_EVENT` observations required by their frozen
evidence contracts.

**Changed mechanism:** the evidence-policy semantic ontology and classifier contract
only. The candidate adds one application-owned scope, `PERSON_HISTORY`, whose proposed
closed allowlist is:

- `USER_PROMPT` — direct self-report and first-person history;
- `SYSTEM_EVENT` — preserved observations and imported claims; and
- `PERCEPT_OBSERVATION` — direct admitted observations.

Retrieval scoring, truth evaluation, authority ranking, packet bounds, Composer,
Adaptive Recall, and response realization remain fixed. Admission under
`PERSON_HISTORY` does not promote a `SYSTEM_EVENT` to truth; it only prevents the
source classifier from deleting one side of a person-model question before cognition
can compare provenance.

## Hypothesis

The current ontology has scopes for user claims and system records but no scope for a
question that explicitly requires both. A dedicated person-history domain should
admit self-report plus behavioral/observational evidence for longitudinal synthesis
without broadening unrelated historical questions.

## v1 native result

The exact retained result is
[`PERSON-FIDELITY-EXP3-HISTORICAL-SOURCE-POLICY_2026-09-21_130846.json`](../../benchmarks/results/PERSON-FIDELITY-EXP3-HISTORICAL-SOURCE-POLICY_2026-09-21_130846.json).
It was collected at revision `b860a91e` with three trials per case.

| Measure | Production contract | v1 candidate |
|---|---:|---:|
| Cases passing every trial | 5/11 | 9/11 |
| Frozen failures repaired | — | 4 |
| Frozen passes regressed | — | 0 |

The candidate selected `PERSON_HISTORY` on all three trials for belief change,
self-report/behavior reconciliation, identity conflict, and novel prediction. This is
strong evidence that the missing semantic domain is useful and that the proposed
person-history boundary is understandable to the reference model.

Promotion was still rejected under the frozen rule. Both the production and
candidate contracts failed the external-tool and derived-internal controls. The v1
candidate consistently collapsed each into `SYSTEM_RECORD`, showing that adding
`PERSON_HISTORY` improved the target cases but left the source-origin boundaries too
ambiguous. Passing only the new scope's target cases is insufficient for a closed
source policy.

## Frozen controlled cases

The original shared fixture
[`person_fidelity_mechanism_experiments_v1.json`](../../benchmarks/person_fidelity_mechanism_experiments_v1.json)
contains eleven current-prompt-only classifications. Four require
`PERSON_HISTORY`: belief change caused by observed experience,
self-report/behavior reconciliation, identity conflict involving an import, and a
novel prediction from both statements and behavior. The controls separately require
`USER_AUTHORED`, `MIXED_CONVERSATION`, `SYSTEM_RECORD`, `EXTERNAL_TOOL`,
`DERIVED_INTERNAL`, and `GENERAL_OR_CURRENT`.

This separation matters. A candidate that chooses `PERSON_HISTORY` for every personal
question or every `SYSTEM_EVENT` mention fails the controls.

The v2 fixture
[`person_fidelity_mechanism_experiments_v2.json`](../../benchmarks/person_fidelity_mechanism_experiments_v2.json)
retains all eleven v1 cases and adds eight prospective cases frozen before v2 native
execution. They separately probe two external-tool paraphrases, two internally
derived outputs, raw scheduler state, a new person-history synthesis, prior model
output, and a current-prompt fact.

The v2 classifier contract now makes producing source explicit: storage inside
Prometheist does not turn a tool payload or derived cognitive result into a raw
runtime record. `SYSTEM_RECORD` is reserved for operational control-plane facts.
These are semantic boundary clarifications; the proposed `PERSON_HISTORY` allowlist
is unchanged.

## Decision rule

Every new run captures the exact production and candidate prompts, schemas, token
limits, model identity, raw outputs or transport errors, validated stage results,
benchmark evaluations, fixture hash, revision, and final disposition in a separate
hash-linked interaction chain for each trial. Deterministic prior-assistant routing
also receives a complete chain, with zero model-invocation artifacts. A
content-addressed `run_manifest.json` inventories every raw artifact byte, and the
compact result records the manifest hash. These records are written by
[`run_person_fidelity_mechanism_experiments.py`](../../benchmarks/run_person_fidelity_mechanism_experiments.py).

The retained 2026-09-21 v1 and v2 compact results predate this correction. Their
compact JSON retains the raw and parsed model outputs, errors, and verdicts, but no
independent per-invocation chains. The omitted causal trace must not be fabricated
after the fact; native reruns are required to produce it.

Promotion requires every candidate case to pass on every trial, at least one baseline
failure to improve, and no baseline pass to regress. A pass authorizes adding the
scope, deterministic allowlist, and classifier wording together because the new enum
has no behavior without its exact allowlist. It does not authorize universal access
to system history or any relaxation of downstream authority handling.

## Run

Run this separately from Experiment 2 so each result changes one semantic mechanism:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -Experiment source-policy -CandidateVersion v2 -Trials 3
```

Verify the resulting artifact:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -VerifyResult benchmarks/results/PERSON-FIDELITY-EXP3-HISTORICAL-SOURCE-POLICY_<timestamp>.json
```

After an accepted candidate is promoted and regression-tested, rerun Mara unchanged;
then run Wren without tuning on Wren. Only full-pipeline evidence can establish that
the new source admission improves person-fidelity evidence delivery.
