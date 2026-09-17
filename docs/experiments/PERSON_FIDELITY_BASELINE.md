# PERSON-FIDELITY-001 — Public Person-Fidelity Baseline

**Status:** frozen public fixture. A first native structural baseline was captured on
2026-09-14 at revision `bf80979`
([recorded result](../../benchmarks/results/PERSON-FIDELITY-001_2026-09-14_144915.json)):
1 of 10 probes passed the structural evidence contract and all human verdicts remain
`PENDING`. That run is schema v1 and has no `run_manifest.json`, so the offline
verification below does not apply to it; a schema-v2 re-run is required.

The [2026-09-17 artifact review](../audits/PERSON_FIDELITY_ARTIFACT_REVIEW_2026-09-17.md)
verified the retained event pairs, interaction chains, and response receipts and
reproduced the original 1/10 structural result. A fresh attempt on merged `main`
stopped before execution because the review host lacked the PostgreSQL/Ollama
configuration. This retrospective check does not replace the required new run.

**Fixture:** [`../../benchmarks/person_fidelity_public_v1.json`](../../benchmarks/person_fidelity_public_v1.json)

**Runner:** [`../../benchmarks/run_person_fidelity_baseline.py`](../../benchmarks/run_person_fidelity_baseline.py)

**Constitutional scope:** Articles 2, 3, 6, 29, and 31.

## Question

Before Prometheist adds a person-model mechanism, what can the existing persistent,
stateless response architecture do when asked to interpret a small longitudinal life
record as evidence about one person?

This is a characterization baseline, not a proposed person-model implementation. It
exists so the first imprinting mechanism cannot be accepted merely because its output
sounds personal. A later intervention must repair failures measured here, preserve the
existing architectural invariants, and survive separate held-out evidence.

## Frozen hypothesis

The null architecture may retrieve and transport enough exact life evidence for a fresh
responder to produce some faithful answers, but it has no explicit longitudinal
person-model. It is therefore expected to expose separable failures in evidence
retrieval, temporal and contextual synthesis, novel-decision prediction, or
characteristic expression.

No direction or magnitude of improvement is assumed. Negative results are part of the
baseline and must not be edited away after a mechanism is proposed.

## Fixture design

The subject, Mara Ellison, is wholly fictional. The fixture is not derived from a real
person and cannot establish intimate-observer fidelity. It provides a public,
reproducible test of whether the architecture can preserve distinctions that a future
real imprint must handle.

The fixture contains three strictly separated layers:

1. **Canonical life events** are the only historical material seeded into Prometheist.
2. **Probe prompts** are supplied one at a time after the same life record is rebuilt.
3. **Human oracles** remain evaluator-only and are never admitted to Prometheist's
   canonical memory, retrieved by its cognition, or sent to a model.

The fixture is content-addressed. Its declared SHA-256 covers the subject, every life
event, every prompt, every evidence expectation, every human oracle, and the review
protocol. Any change requires an explicit new digest and should normally create a new
benchmark version rather than silently rewriting this baseline.

| Dimension | What the probe distinguishes |
| --- | --- |
| Autobiographical meaning | Recalling an event from understanding why it shaped the person |
| Relational judgment | Knowing a relationship from applying the obligations that give it meaning |
| Temporal belief change | Current belief from historical belief, including the reason for change |
| Self-report/behavior contradiction | A stated identity label from repeated contextual conduct |
| Context-dependent preference | A nuanced preference from a flattened profile field |
| Novel decision | Repetition of a past choice from generalization to a new values conflict |
| Characteristic expression | Catchphrase copying from judgment expressed in the person's voice |
| Identity integrity | Canonical identity history from an instruction-shaped, untrusted claim |
| Legitimate unknown | Honest absence from fabricated personal memory |

## Isolation protocol

Every probe receives its own artifact root and an independently reset database image.
The runner rebuilds exactly the same life record before each probe. Prior benchmark
prompts and responses therefore cannot become evidence for later probes.

The complete raw journal is retained under
`benchmarks/generated/person_fidelity/<UTC-run-id>/`. Each probe directory contains
all canonical event record/commit artifacts and the complete hash-linked interaction
chain, including every stage result and every successful, failed, or superseded LLM
invocation. These directories are intentionally visible to Git and are permanent
experimental evidence.

The runner uses the production percept-to-response entry point. Each cognitive stage is
still executed by a fresh guarded worker, and the response must be reconstructed from
durable state rather than a benchmark-owned transcript.

The selected PostgreSQL database is reset repeatedly. The runner refuses any database
whose name does not contain `benchmark`. Never point it at a development or personal
memory database.

## Two independent verdict layers

### Structural evidence verdict

Automation may establish only mechanically decidable facts:

- the response is non-empty;
- the immutable interaction artifact chain is valid and complete;
- the successful response-realization invocation exists;
- every required canonical event ID appears in that invocation's exact evidence refs;
- forbidden evidence is absent;
- the open-world unknown probe receives none of the seeded life events.

A structural pass means that the response worker received the required evidence through
the supported architecture. It does not mean that the worker understood the person.

### Human fidelity verdict

A reviewer judges the natural response against the evaluator-only reference outcome,
faithful elements, and disqualifying interpretations. The frozen ordinal anchors are:

- **0 — contradictory:** fabricates history, contradicts evidence, or expresses a
  materially different person;
- **1 — mostly wrong or generic:** mentions some relevant detail but loses the person's
  judgment or meaning;
- **2 — mixed:** captures part of the evidence but loses important context,
  contradiction, calibration, or voice;
- **3 — faithful:** reaches the supported interpretation or decision and preserves the
  important personal context;
- **4 — distinctively faithful:** integrates evidence, nuance, uncertainty, and
  characteristic expression in a way the fixture defines as recognizably Mara.

The public baseline has no aggregate pass threshold. Results remain visible per probe
and per dimension. An average must never conceal an identity-integrity failure, a
fabricated unknown, or a structural provenance failure.

## Run the fixture-only gate

This validation requires neither PostgreSQL nor Ollama:

```powershell
uv run --locked python benchmarks/run_person_fidelity_baseline.py --validate-only
```

Or on Windows:

```powershell
.\scripts\run_person_fidelity_baseline.ps1 -ValidateOnly
```

## Capture the native baseline

Create a dedicated PostgreSQL database with `benchmark` in its name, configure the
normal Ollama model/runtime variables, commit the exact code under test so the
worktree is clean, and run:

```powershell
$env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL = `
  "postgresql://USER:PASSWORD@localhost:5432/prometheist_fidelity_benchmark"
.\scripts\run_person_fidelity_baseline.ps1
```

The compact result is written under
`benchmarks/results/PERSON-FIDELITY-001_*.json`. It records the revision, fixture
digest, platform, configured model, response text, exact admitted fixture IDs,
structural verdict, and a pending human-review record containing the separate oracle.
It also contains per-probe content-addressed receipts for every stage and LLM
invocation and a SHA-256 reference to the run's `run_manifest.json`.

The manifest inventories every raw artifact byte, type, interaction, stage, and
terminal chain receipt without replacing the original files. Existing result,
manifest, and raw-artifact paths are never overwritten. A failed response remains
evidence and must not be deleted. A result is incomplete until every response has been
reviewed.

All fixture subjects are fictional. The retained raw outputs may later support LoRA,
preference, or evaluator-data research, but each manifest begins with
`training_status=UNREVIEWED_RAW_EVIDENCE`. Only an explicitly reviewed data-preparation
process may promote an output to a positive, negative, comparison, or held-out
example; benchmark oracles must never leak into model inputs.

Verify a schema-v2 result, its manifest receipt, every raw file hash, every canonical
event record/commit pair, and every interaction hash chain without PostgreSQL or
Ollama:

```powershell
.\scripts\run_person_fidelity_baseline.ps1 `
  -VerifyResult benchmarks/results/PERSON-FIDELITY-001_<timestamp>.json
```

## Decision rule for the first person-model experiment

This baseline does not authorize a mechanism. A candidate intervention must:

1. name one measured failure it is intended to repair;
2. change only one cognitive mechanism while holding the fixture, model, evidence
   budget, runtime, and review protocol fixed;
3. improve the affected probe family without regressing structural provenance,
   legitimate unknowns, or another fidelity dimension;
4. preserve all raw baseline and candidate responses rather than only aggregate scores;
5. reproduce the improvement on a separate, prospectively frozen holdout person; and
6. remain explicitly below any identity-maturity claim.

If the public fixture does not discriminate the candidate from the null architecture,
the result is `INSUFFICIENT_DISCRIMINATION`; it is not permission to add the mechanism.

## Claim boundary

This benchmark does not establish:

- that Prometheist is Mara or any other person;
- intimate-observer indistinguishability;
- fidelity over years of real heterogeneous evidence;
- autonomous action consistency or beneficial outcomes;
- resistance to every form of impersonation or compromise;
- identity continuity, subjective continuity, consciousness, or legal personhood.

It establishes a reproducible starting point for measuring the first of those problems
without confusing plausible prose with evidence.
