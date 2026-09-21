# Artifact Visibility and Retention Audit — 2026-09-14

## Decision

Prometheist's synthetic test and benchmark artifacts are permanent research
evidence. They remain visible to Git whether a run succeeds, fails, crashes, or
produces an incorrect response. A compact result file does not replace the raw
event mirrors, worker-stage results, model invocations, outputs, and final
disposition chain needed to reconstruct what happened.

This decision implements Constitution 2.0, especially Article 9 (lossless
canonical evidence), Article 24 (durable causal provenance), Article 31
(verification), and Article 36 (independent artifact durability). It does not
require another constitutional amendment.

## Finding

The runtime had already written immutable event and interaction artifacts, and
some historical examples were tracked. However, root `.gitignore` rules for
`.prometheist/` and `benchmarks/generated/` hid newly produced artifacts from
normal Git review. The initial `PERSON-FIDELITY-001` result therefore exposed a
discoverability and transport failure: its compact JSON summary was available,
while the exact raw journal remained only on the machine that ran it.

The benchmark also lacked a single manifest connecting the summary to every raw
file. Individual interaction chains were verifiable, but a reviewer could not
prove that a shared directory was the complete artifact set for the run.

## Remediation

- Removed all project artifact-directory rules from the root `.gitignore`.
- Kept `.prometheist/artifacts/` visible for synthetic and deliberately
  non-sensitive development interactions.
- Kept `benchmarks/generated/` visible for generated corpora, reports, and raw
  native benchmark journals.
- Made each future person-fidelity run write `run_manifest.json`, containing a
  SHA-256 and byte length for every raw JSON artifact plus per-probe interaction
  chain receipts.
- Extended the same requirement to the PostgreSQL-independent Composer and source-
  policy mechanism runners: every trial now records its case input, exact LLM
  invocation and retry envelopes, stage result or error, evaluation, and final
  disposition. Deterministic paths retain the same chain without inventing an LLM
  invocation.
- Linked each schema-v2 compact result to that manifest by SHA-256.
- Added offline verification of the result receipt, exact manifested file set,
  every file digest, canonical event record/commit pairs, complete interaction
  chains, artifact counts, and terminal hashes.
- Preserved a newly visible corrupt-media test object and classified it with a
  quarantine record instead of deleting it.

## Retention and future training

Preservation and training eligibility are separate decisions. Every raw
person-fidelity manifest begins as `UNREVIEWED_RAW_EVIDENCE`. Failed and
incorrect outputs are valuable for debugging and may later become negative or
preference examples; they must never be silently promoted into positive LoRA
training data. Any later dataset builder must retain the source artifact hashes,
tested revision, runtime/model identity, prompt/evidence roles, and explicit
human-review label.

No automatic cleanup process may delete or rewrite these benchmark histories.
A future storage migration may change representation only if it is reversible,
content-preserving, independently verifiable, and keeps the original identity
and provenance intact.

## Verification evidence

- Person-fidelity artifact tests: 15 passed, including preservation and
  verification of a probe that failed before interaction creation.
- Ruff repository check: passed.
- Constraint registry audit: 215 discovered, 215 registered, 0 uncovered, 0
  stale, 0 mismatched, 0 invalid.
- Git ignore checks confirm that both benchmark journals and development runtime
  journals are visible.

The complete PostgreSQL-backed suite still requires the repository's disposable
test database and should run in CI and on the native development host.
