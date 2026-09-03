# Prometheist Roadmap to v1.0

**Rebaselined:** 2026-09-03

**Current transition:** finish v0.7 repository closure before creating a v0.8 branch

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

**Status:** closure candidate; not closed until every gate below passes on one frozen
SHA.

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
  pre-cognitive non-memory work selection, direct work-result handoff, memory-only
  Composer, deterministic Adaptive Recall, and a separate final responder;
- independent immutable artifact chains and event reconstruction;
- incremental association-projection freshness;
- explicit model-evidence byte limits and adversarial evidence-authority tests.

The older recurrent general response router, separate named memory capabilities, and
parallel interaction runtime are rejected/superseded designs.

### Closure gates

v0.7 closes only when all of the following apply to the same candidate SHA:

1. deterministic CI passes `ruff`, the fail-fast constraint audit, calibration, and
   complete non-Ollama pytest with PostgreSQL;
2. the complete native Windows/PostgreSQL/Ollama acceptance script passes with
   environment-dependent tests actually executed rather than skipped;
3. ported red-team cases pass, including memory authority/prompt injection,
   assistant-only claims, oversized evidence, saturated WorkingState, deep temporal
   history, and projection freshness;
4. superseded runtime/control code and tracked runtime artifacts are absent;
5. selective PR/branch evidence disposition is recorded and obsolete open PRs are
   closed without merging their superseded implementations;
6. current README, architecture, milestone, testing, constraint, and roadmap text
   agree with the implemented v2 path;
7. a final constitutional/codebase audit is recorded against the frozen SHA;
8. that SHA is merged, then marked with a new closure tag. The existing `v0.7` tag
   remains immutable.

Only after those gates pass may the v0.8 hypothesis be marked frozen and its branch
be created from the closure SHA.

## v0.8 — Epistemic WorkingState

**Status:** selected next experiment, provisional until v0.7 closure.

This rebaseline chooses richer Epistemic WorkingState before broad
perception/salience. The choice follows the measured continuity limits and the
highest-priority recommendation in the neuroscience synthesis: Prometheist has a
durable scheduler and minimal activation set, but does not yet have a typed cognitive
workspace for multi-step evidence integration.

Primary hypothesis:

> Adding one bounded, typed, durable Epistemic WorkingState projection will improve
> interrupted multi-step reasoning, unresolved-question continuity, and evidence
> integration without creating hidden transcript growth, unqualified truth state, or
> model-owned authority.

The proposed state contains application-owned fields for current goal, subgoals,
active hypotheses, evidence commitments with source IDs, unresolved questions,
uncertainty/status, dependencies, prior step-result references, and explicit
termination criteria. It remains a rebuildable projection over canonical events.

The experiment compares the frozen v0.7 baseline with this mechanism alone. Broad
general perception/salience, automatic episode segmentation, replay, embeddings, and
procedural learning are excluded. A general recurrent inference loop is not silently
bundled into the milestone; it may be proposed only if the typed-state experiment
exposes a frozen failure that requires it.

Required scenario families and decision rules are specified in
[`milestones/v0.8/HYPOTHESIS.md`](milestones/v0.8/HYPOTHESIS.md).

## v0.9 — deterministic perception and salience

Primary question: can Prometheist receive heterogeneous observations, cheaply
identify what matters, and form appropriate reflex/orient/deliberate/ignore
dispositions without requiring an LLM to inspect every input?

Candidate deliverables include normalized percept contracts, bounded source buffers,
deterministic anomaly and system-integrity signals, structured novelty/threat/
opportunity/goal/uncertainty salience, situation assembly, task formation, and
bounded pre-authorized reflexes. Model-assisted semantics may propose within policy
but never own authority.

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
