# Experiment 3 — Historical person-evidence source policy

**Status:** frozen candidate and control fixture; awaiting native
`qwen3:4b-instruct-2507-q4_K_M` evidence. Production scopes and allowlists are
unchanged.

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

## Frozen controlled cases

The shared fixture
[`person_fidelity_mechanism_experiments_v1.json`](../../benchmarks/person_fidelity_mechanism_experiments_v1.json)
contains eleven current-prompt-only classifications. Four require
`PERSON_HISTORY`: belief change caused by observed experience,
self-report/behavior reconciliation, identity conflict involving an import, and a
novel prediction from both statements and behavior. The controls separately require
`USER_AUTHORED`, `MIXED_CONVERSATION`, `SYSTEM_RECORD`, `EXTERNAL_TOOL`,
`DERIVED_INTERNAL`, and `GENERAL_OR_CURRENT`.

This separation matters. A candidate that chooses `PERSON_HISTORY` for every personal
question or every `SYSTEM_EVENT` mention fails the controls.

## Decision rule

The exact production and candidate prompts, schemas, raw outputs, fixture hash,
model, revision, per-trial results, and report hash are captured by
[`run_person_fidelity_mechanism_experiments.py`](../../benchmarks/run_person_fidelity_mechanism_experiments.py).

Promotion requires every candidate case to pass on every trial, at least one baseline
failure to improve, and no baseline pass to regress. A pass authorizes adding the
scope, deterministic allowlist, and classifier wording together because the new enum
has no behavior without its exact allowlist. It does not authorize universal access
to system history or any relaxation of downstream authority handling.

## Run

Run this separately from Experiment 2 so each result changes one semantic mechanism:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -Experiment source-policy -Trials 3
```

Verify the resulting artifact:

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -VerifyResult benchmarks/results/PERSON-FIDELITY-EXP3-HISTORICAL-SOURCE-POLICY_<timestamp>.json
```

After an accepted candidate is promoted and regression-tested, rerun Mara unchanged;
then run Wren without tuning on Wren. Only full-pipeline evidence can establish that
the new source admission improves person-fidelity evidence delivery.
