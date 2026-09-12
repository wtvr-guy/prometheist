# Prometheist Roadmap to v1.0

**Integration update:** 2026-09-12

**Current milestone:** v0.8 — predictive situations and non-user cognition.

**v0.7 baseline:** closed at `39a3223c38f1b1f8fae7f9e667c6cd7460774ffe`
(`v0.7-closure`). The historical `v0.7` tag remains immutable.

Milestone labels describe architectural experiments, not package-release versions.
Every milestone starts from one frozen question and preserves previously accepted
invariants unless evidence explicitly justifies an amendment.

## Experimental rule

> Freeze a measurable baseline, change one mechanism, rerun the same experiment,
> and keep the mechanism only if the evidence justifies it.

Negative results and rejected implementations remain part of the historical record.
Branches do not become architecture merely because they exist.

## Accepted baselines

### v0.5 — deterministic memory robustness and scale

**Status:** accepted and frozen.

v0.5 established bounded deterministic associative recall, exact provenance,
support-aware evidence admission, specificity-aware candidate routing, abstention,
and the accepted 10k/50k synthetic scale baselines. It did not establish general
semantic-memory completeness.

### v0.6 — shared JIT Memory and stateless worker composition

**Status:** accepted historical result; closed 2026-08-21.

v0.6 proved that fresh model-backed components can participate in one continuous
system through shared durable memory without inherited transcripts. Its Primary
Agent/specialist organization is historical. Its cross-turn/session recall,
correction, temporal, ambiguity, and provenance behavior remains regression evidence.

## v0.7 — durable attention, minimal WorkingState, and v2 response path

**Status:** closed baseline; superseded as the active development milestone by v0.8.

Primary question: can Prometheist deterministically allocate durable work across
bounded resources, survive destruction of every worker, preserve bounded active
context, expose potentially relevant persistent memory before fresh model reasoning,
and produce a response without any privileged persistent agent or hidden transcript?

Implemented mechanisms include:

- resource-aware Attention with deterministic ordering, dependencies, reservations,
  scheduling epochs, service guarantees, headroom, and contention-only preemption;
- guarded disposable workers with durable claims, leases, checkpoints, terminal
  results, recovery, and effect idempotency;
- bounded canonical-reference WorkingState and a default memory attention aperture;
- the authoritative v2 user-prompt path: deterministic response requirement,
  a durable current-only evidence-policy specialist, pre-cognitive non-memory work
  triage, direct work-result handoff, memory-only Composer, deterministic Adaptive
  Recall, and a separate final responder;
- application-owned historical role filtering under the one committed policy,
  quarantined evidence transport, and validated exact-source output;
- independent immutable artifact chains and event reconstruction;
- incremental association-projection freshness;
- explicit model-evidence byte limits and adversarial evidence-authority tests.

The older recurrent general response router, separate named memory capabilities, and
parallel interaction runtime are rejected/superseded designs.

The first consolidated native run on 2026-09-03 executed all 14 model-backed tests
and failed 6. The exact-SHA remediation follow-up passed 11 of 14 and exposed that
the remaining response fixtures still used artificial exact-prose assertions. The
replacement gate is artifact-first: CI/native automation establishes delivery,
authority, isolation, and structural safety; a human explicitly judges the printed
natural responses on that same SHA.

The closure SHA is the preserved v0.7 baseline for all v0.8 regression work. Its
dated gate evidence remains in [`milestones/v0.7/CLOSURE_STATUS.md`](milestones/v0.7/CLOSURE_STATUS.md);
new v0.8 work must not rewrite that historical record.

## v0.8 — predictive situations on the consolidated v2 runtime

**Status:** active development milestone on the closed v0.7 baseline. Native
acceptance and experimental benefit remain separately gated.

The implementation includes typed perception/media adapters, expectations,
prediction errors, overlapping situations, contextual salience, non-user triage,
deterministic reflexes, situation attention, guarded workers, observed action
feedback, and scheduled derived consolidation. The seven-stage user pipeline
retains the closure functionality and mandatory user response policy.

See the [milestone](milestones/v0.8/README.md),
[independent hypotheses](milestones/v0.8/HYPOTHESIS.md),
[situation architecture](architecture/SITUATION_COGNITION.md), and
[per-change record](audits/V08_CLOSURE_INTEGRATION_2026-09-12.md).
Budgets and ordinal bins remain provisional; integration is not evidence of
improved cognition or native performance.

## v0.9 — candidate Epistemic WorkingState experiment

The earlier v0.8 proposal is preserved as
[`experiments/history/EPISTEMIC_WORKING_STATE_PROPOSAL_2026-09-03.md`](experiments/history/EPISTEMIC_WORKING_STATE_PROPOSAL_2026-09-03.md).
It remains unfrozen and is a candidate for the next separate experiment, not a
committed schedule for a future release.

The question is whether a bounded typed projection of goals, hypotheses,
evidence commitments, unresolved questions, dependencies, and termination criteria
improves interrupted reasoning without hidden transcripts or unqualified truth.
Run its frozen scenarios against the actual integrated baseline before adding the
projection. Do not bundle recurrent loops, learned retrieval, or consolidation into
that intervention.

## v0.10 — deterministic retention and memory admission

Primary question: can Prometheist avoid permanently storing useless external data
while preserving evidence required for cognition, continuity, explanation, and user
control?

The experiment will distinguish ephemeral raw observations, retained observational
memory, and canonical internal history; define versioned retention classes and
reference protection; and keep user-directed erasure distinct from automatic
retention or compaction.

## v0.11 — memory generalization and episode routing

Primary question: where does deterministic memory fail on zero-overlap paraphrases,
aliases, distributed facts, contradictions, corrections, temporal/causal chains,
dense associations, heterogeneous artifacts, and natural topic resumption?

Candidate mechanisms must repair a frozen failure. Hierarchical episode projection is
the first preferred experiment when failures are contextual/temporal. Learned
semantic retrieval may enter only if deterministic/episode-aware routes fail the same
frozen cases and the new route improves recall without unacceptable precision,
abstention, latency, or calibration loss.

## v0.12 — integrated persistent cognitive loop

Primary question: can perception, retention, memory, Epistemic WorkingState,
Attention, capabilities, disposable cognition, and interaction continuity operate as
one system even though no worker, model invocation, or chat session owns continuity?

Acceptance must exercise multi-day/multi-session overlapping situations, correction,
interruption, natural resumption, external work, provenance, ambiguity, and unknowns
without explicit conversation switching or inherited transcripts.

## v0.13 — operational hardening and portability

Primary question: is the integrated architecture trustworthy as persistent personal
infrastructure?

Candidate work includes migration, backup/restore, export/import, explicit erasure,
permissions, corruption recovery, model/backend replacement, assignment and effect
recovery, deadlock/starvation analysis, sensor failure, and reproducible installation
on modest local hardware.

## v1.0 — first complete Prometheist architecture

A defensible v1.0 demonstrates system-owned identity and continuity, stateless model
calls, no privileged persistent agent, deterministic control and retention authority,
bounded active state and recall, conservative source-backed evidence, safe concurrent
execution, process/model replacement, session-independent interaction continuity,
user-controlled portability, and reproducible deterministic plus native acceptance.

> Terminate every model and worker, restart or replace the implementation, cross
> interface/session boundaries, and Prometheist still retains its durable identity,
> history, active state, unfinished intentions, attention, and causal provenance—
> because none of them belonged to a transient agent context.

## Deferred unless evidence pulls them forward

Offline replay/consolidation, adaptive association plasticity, prediction-error
state, procedural skill compilation, learned salience, self-modifying scheduling,
multi-machine attention, speculative autonomous task formation, literal oscillatory
models, and biological simulation remain outside the committed path until a frozen
failure justifies a specific experiment.
