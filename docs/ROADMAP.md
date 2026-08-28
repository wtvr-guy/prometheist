# Prometheist Roadmap to v1.0

This roadmap describes the engineering path from the accepted deterministic-memory/stateless-worker baselines to a complete attention-centric persistent cognitive/execution architecture.

Version numbers are architectural milestones, not promises that every long-term idea is implemented in that release.

## Experimental rule

> **Freeze a measurable baseline, change one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**

This applies to memory, attention, WorkingState, workpieces, perception, retention, execution, models, tools, interaction continuity, and performance optimizations.

## Current architectural baseline — 2026-08-28

The last several days produced four linked corrections:

1. **2026-08-24 — permanent-agent pivot.** The Primary Agent/fixed MAS hierarchy became historical. Identity, tasks, attention, memory, WorkingState, execution state, and continuity belong to Prometheist itself; workers/models are disposable.
2. **2026-08-26/27 — continuity correction.** Native acceptance rejected growing phrase/entity heuristics and rejected asking a fresh model whether unseen memory matters. Bounded `InteractionWorkingState` plus an automatic JIT attention aperture now precede semantic model judgment.
3. **2026-08-28 — transient cognition correction.** Recurrent general capability routing was replaced by staged fresh cognition. Native Qwen3:4b behavior then showed that one aggregate pre-cognitive classifier still owned too many semantic responsibilities.
4. **2026-08-28 — workpiece/station correction.** The pre-acquisition path was split into a demand-driven binary evidence-sufficiency station plus conditional capability-selection station. The larger execution model was generalized into a typed `InteractionWorkpiece`: different tasks traverse different station graphs and terminalize into explicit outcomes; natural-language response is optional.

Current primary authorities:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md)
- [`architecture/INTERACTION_WORKPIECE.md`](architecture/INTERACTION_WORKPIECE.md)
- [`architecture/WORKER_PROFILE_REGISTRY.md`](architecture/WORKER_PROFILE_REGISTRY.md)
- [`architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md)
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md)

## v0.5 — Deterministic memory robustness and scale

**Status:** accepted and frozen.

Question: can deterministic JIT memory preserve bounded provenance-bearing recall and abstention under competing state, lifecycle changes, lexical interference, and large histories?

Accepted result: deterministic association activation, support-aware evidence admission, specificity-aware PostgreSQL candidate routing, successful 10k/50k scale suites, repaired temporal/source/isolation regressions, and no measured failure that justified embeddings as a v0.5 dependency.

## v0.6 — Shared JIT Memory and stateless worker composition

**Status:** accepted and closed.

Question: can fresh stateless model-backed components participate in one continuous system through shared external memory without inherited transcripts?

Accepted result: yes. Cross-turn/cross-session recall, corrections, temporal reasoning, ambiguity handling, and shared JIT-memory continuity became regression baselines.

The Primary Agent/specialist hierarchy used to prove that result is historical. Its behavioral evidence remains important; its executive structure does not constrain current design.

## v0.7 — Durable Attention + WorkingState + JIT aperture + typed transient execution

**Status:** release candidate under final deterministic/native validation.

Primary question:

> Can Prometheist allocate durable work deterministically across bounded resources, survive destruction of every worker/model process, preserve current cognitive activation and persistent memory continuity, acquire additional evidence through bounded fresh stations, and produce a complete provenance-bearing terminal workpiece without any privileged agent or persistent LLM context?

### v0.7 implemented mechanisms

#### Attention and resource execution

- durable task scheduling metadata and total deterministic ordering;
- service guarantees and explicit interruption policy;
- quantitative CPU/RAM/LLM/resource admission with configured headroom;
- authoritative resource observations and conservative estimates;
- atomic scheduling epochs, assignments, and reservations;
- contention-driven preemption rather than priority-only preemption;
- default one-concurrent-local-LLM slot;
- guarded claim-time re-observation;
- disposable-worker leases, checkpoints, results, idempotency/effect policy, and restart recovery.

#### Continuity and memory activation

- bounded `InteractionWorkingState` using canonical active-event references;
- conversations/sessions/devices treated as provenance rather than cognitive walls;
- automatic bounded high-recall JIT attention aperture before semantic cognition;
- no phrase-specific application vocabulary as continuity authority;
- deeper internal-memory investigation through `deeper_research`, `cross_reference`, and `focused_recall` capabilities;
- exact canonical evidence composition rather than summary replacement.

#### Demand-driven semantic stations

Current pre-acquisition model-backed stations are intentionally narrow:

```text
evidence_sufficiency_verifier
    -> SUFFICIENT | INSUFFICIENT

if INSUFFICIENT and legal catalog exists:
capability_selector
    -> bounded application-catalog indices
```

Deterministic application code derives the aggregate control disposition and owns capability identities, dependencies, order, resources, persistence, and effects.

Other LLM-backed stations such as final readiness, response policy, exact-source selection, candidate selection, and final response are invoked only on paths that need them.

#### Typed Interaction Workpiece

The production interaction path now carries a typed `InteractionWorkpiece` through the existing five durable stage keys for migration/restart compatibility.

A workpiece accumulates only the components contributed by stations that actually ran. Worker profiles receive minimum projections rather than the full workpiece.

At terminalization Prometheist persists a materialized `INTERACTION_WORKPIECE_SNAPSHOT` JSON in addition to the append-only causal history.

Current terminal vocabulary includes:

- `RESPONSE_EMITTED`
- `ABSTAINED`
- `ACTION_COMPLETED`
- `ACTION_FAILED`
- `WAITING_EXTERNAL`
- `DEFERRED`

The current CLI is interactive and therefore emits user output. The core architecture does not require a final response worker for future action/background tasks.

### v0.7 closure gates

v0.7 does not close merely because the architecture is documented or deterministic CI passes.

Required:

1. final-head static checks and constraint audit;
2. full deterministic PostgreSQL test suite;
3. native Windows/PostgreSQL/Ollama Qwen3:4b acceptance, including the established five release scenarios;
4. PR/review cleanup and branch/release bookkeeping after the native gate succeeds.

Qwen3:4b remains fixed for this acceptance experiment. A larger model is not an allowed substitute for repairing an architectural failure.

## Post-v0.7 rebaseline

Before starting the next major mechanism, re-evaluate the roadmap against:

- v0.7 native acceptance behavior;
- `docs/concepts/lessons_from_cognitive_neuroscience.md`;
- `docs/concepts/lessons_from_similar_projects.md`;
- measured WorkingState/workpiece/continuity failure modes;
- actual modest-hardware latency/resource data.

The current ordering below is the default, not a license to combine several mechanisms into one experiment.

## v0.8 — Deterministic perception and salience

**Primary question:** can Prometheist continuously receive heterogeneous external observations, cheaply identify what matters, and form/update durable work without requiring an LLM to inspect every raw input?

Candidate deliverables:

- normalized typed `Percept` contracts for user, software, device, sensor, and external-service inputs;
- bounded input buffers;
- deterministic anomaly/priority signals where feasible;
- structured threat/opportunity/goal/novelty/uncertainty/system-integrity salience;
- situation assembly and durable task formation;
- `REFLEX` / `ORIENT` / `DELIBERATE` / `IGNORE` dispositions;
- bounded pre-authorized reflexes;
- optional semantic model assistance without policy authority;
- integration into the workpiece/station graph rather than a separate agent hierarchy.

If post-v0.7 evidence instead justifies richer epistemic WorkingState first, rebaseline explicitly; do not silently merge both experiments.

## v0.9 — Deterministic retention and memory admission

**Primary question:** can Prometheist avoid permanently storing useless external data while preserving everything required for future cognition, provenance, interaction continuity, and explanation of actions?

Candidate deliverables:

- explicit ephemeral/raw versus admitted observation versus internal-history classes;
- deterministic retention-policy versions and TTL/correlation windows;
- context promotion around salient situations;
- raw-to-derived aggregation while retaining protected canonical evidence;
- reference protection for evidence/workpiece dependencies;
- durable retention decisions and user overrides;
- model proposals without deletion authority;
- deterministic storage-pressure behavior.

Anything that materially influences attention, reasoning, commitments, actions, or terminal outcomes must leave enough durable provenance to explain that behavior later.

## v0.10 — Memory generalization and natural context resumption

**Primary question:** where does deterministic memory fail when recall becomes semantically, temporally, relationally, and interactionally harder than the accepted baselines?

Benchmark domains:

- zero-keyword paraphrase;
- aliases/identity resolution;
- distributed facts;
- contradiction and correction/supersession;
- historical versus current belief;
- temporal/causal chains;
- ambiguous association graphs;
- artifact/workpiece references;
- episodic grouping;
- internal versus external evidence;
- implicit topic/situation resumption across sessions/interfaces.

Measure correctness, precision, provenance, unnecessary clarification, correct ambiguity handling, bounded workpiece/packet aperture, latency, and abstention.

Embeddings/vector retrieval or other semantic machinery earn a production role only by repairing frozen measured failures.

## v0.11 — Integrated persistent cognitive/execution loop

**Primary question:** can perception, retention, memory, WorkingState, attention, capabilities, typed workpieces, disposable cognition, tools/actions, and natural continuity operate as one continuous system even though no worker/model/chat session possesses continuity?

Target loop:

```text
perceive
 -> classify salience / form or update durable task
 -> allocate attention and safe resources
 -> initialize/resume typed workpiece
 -> open bounded JIT memory aperture
 -> invoke only required semantic/deterministic/tool stations
 -> attach validated components
 -> acquire further evidence/action results only as needed
 -> terminalize: response | action | wait | defer | failure/abstention
 -> persist append-only causal records + terminal workpiece snapshot
 -> update WorkingState / retention
 -> perceive resulting world/system state
```

Conversation is an interface, not the execution engine:

```text
conversation != agent
conversation != task
conversation != memory scope
conversation != WorkingState
conversation != workpiece
conversation != mandatory terminal response
```

Acceptance should include multi-day/multi-session interaction plus non-language tasks whose correct completion does not require a response worker.

## v0.12 — Operational hardening and portability

**Primary question:** is the complete architecture robust enough to trust as persistent personal infrastructure?

Candidate deliverables:

- migrations;
- backup/restore/export/import;
- crash and partial-workpiece recovery;
- internal-history/workpiece integrity verification;
- permissions and authorization state;
- structured observability;
- deterministic startup/recovery;
- model/runtime replacement;
- reproducible installation;
- resource profiling/history-based estimates;
- starvation/deadlock/priority-inversion handling;
- capability/tool timeout/retry/reconciliation semantics;
- protected evidence and user-directed erasure mechanisms.

Portability must preserve durable identity/history, tasks, WorkingState, workpieces/checkpoints, causal provenance, and continuity across compatible machines/backends.

## v1.0 — First complete Prometheist cognitive architecture

A defensible v1.0 must demonstrate a coherent local-first persistent cognitive/execution system in which:

- every model invocation can be destroyed after its bounded call;
- no permanent Primary Agent is required;
- identity, memory, attention, WorkingState, tasks, workpieces, policy, and provenance are system-owned;
- perception/retention/task formation/attention/resource admission are governed outside model context;
- internal memory activation/retrieval remains bounded and provenance-bearing;
- typed workpieces support heterogeneous demand-driven station graphs;
- workers receive minimum projections and return bounded validated components;
- tool/action workflows can complete safely without mandatory chatbot response;
- external effects have explicit authorization/idempotency/reconciliation semantics;
- unsupported evidence/authority fails closed;
- natural context resumes across session/device/interface boundaries;
- worker/model/backend replacement and backup/restore preserve continuity;
- the architecture remains practical on modest local hardware.

The defining invariant is:

> **Terminate every LLM and worker process, replace the model, cross chat/session/device boundaries, restart Prometheist, and the system still retains its durable identity, internal history, WorkingState, unfinished intentions, work-in-progress, attention state, retained evidence, and causal provenance—because none of them belonged to an agent or model context in the first place.**

## Deferred beyond v1.0 unless evidence pulls them forward

Learned/adaptive salience, self-modifying policy, distributed multi-machine attention fabrics, speculative predictive task formation, sophisticated long-horizon autonomous planning, broad device ecosystems, human-memory-comparison studies, and purpose-built/mobile hardware remain compatible with the vision but are not prerequisites for the first measurable complete architecture.
