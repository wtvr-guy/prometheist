# Composer v3 observability and decomposition — 2026-09-22

## Decision

The Composer v2 candidate is rejected. Production behavior remains unchanged. The
next native experiment tests one narrower mechanism: split current-answerability
from historical-memory completeness so the reference model no longer has to preserve
both rules inside one overloaded classification.

The v3 fixture and contracts were frozen before any v3 native call. No mocked result
or static test is treated as semantic acceptance evidence.

## Evidence motivating v3

The artifact-backed v2 run at revision `e373ac0b` produced 12/17 baseline passes and
14/17 candidate passes. The candidate improved three cases but failed both one-sided
self-report/behavior controls on every trial and regressed a current-prompt allergy
fact on every trial. The repeated outcomes point to a semantic role-conflict, not
sampling variance:

- the same classifier must first honor facts stated now;
- decide whether personal history is needed;
- enumerate every historical evidence slot; and
- judge a supplied historical packet.

The v3 experimental path assigns the first two questions to a fresh
Current-Evidence Specialist with no history packet. Application-owned control returns
`sufficient=true` when it says history is unnecessary. Otherwise, a separate fresh
Historical-Memory Completeness Specialist receives quarantined history and decides
only whether all required historical slots are present.

## Frozen prospective controls

`person_fidelity_mechanism_experiments_v3.json` retains all seventeen prior Composer
cases and adds eight untouched prospective cases. They cover current personal facts,
general knowledge with a current constraint, current correction over old preference,
both directions of one-sided reconciliation, a complete reconciliation, and
context-adjacent versus diagnostic evidence.

The source-policy v3 mapping intentionally remains identical to v2. This change does
not mix a second semantic source-policy mechanism into the Composer experiment.

## Artifact remediation

Every model attempt now produces two separately hash-linked records:

1. `LLM_INVOCATION` contains the exact application prompt/schema plus the backend
   request body, redacted response envelope, response byte count/SHA-256, HTTP
   status, elapsed time, token counts, completion reason, and transport error fields.
2. `LLM_VALIDATION` links to that invocation by artifact ID and hash and records the
   accepted parsed object or the exact parse/schema/transport rejection.

Retries preserve every rejected attempt. A worker cannot issue its next model call
until the previous successful transport has a persisted validation outcome. Hidden
reasoning is represented only by byte length and SHA-256, never plaintext.

The run report and content-addressed manifest now also bind host CPU/RAM/platform
facts, discoverable NVIDIA GPU identity/driver/VRAM, Ollama version, configured model
record and digest, and loaded-model data. Artifact-backed execution fails closed when
the Ollama version or configured model digest is unavailable. Verification requires a
one-to-one invocation/validation mapping and checks each link, status, diagnostic
envelope, v3 specialist result count, file digest, and interaction chain.

## Validation before native execution

- v3 fixture validation: 25 Composer cases, 19 source-policy cases, LF-canonical
  SHA-256 `bbc135520b0f612b778963445432c3ee10520fbd84154d8661289aa7d60d0c4e`;
- focused artifact, transport, Composer, and Ollama-adapter tests: 48 passed without
  PostgreSQL;
- Ruff repository check: passed;
- Python compilation: passed.

The full pytest suite was attempted in the implementation workspace but its required
PostgreSQL server was unavailable at `localhost:5432`; all collected tests stopped in
the session database fixture before test bodies ran. That infrastructure absence is
not reported as a code pass or failure. The native Windows host must run the normal
database-backed suite and the v3 experiment from the clean committed revision.

## Native command

```powershell
.\scripts\run_person_fidelity_mechanism_experiments.ps1 `
  -Experiment composer -CandidateVersion v3 -Trials 3
```

The result remains non-promotable unless every frozen case passes every trial with no
regression, every deficit passes human semantic review, and the complete manifest
verifies independently.
