# Prometheist Roadmap to v1.0

This roadmap describes the engineering path from the verified Memory Kernel and stateless-worker baselines to the first complete attention-centric Prometheist architecture.

Version numbers represent architectural milestones, not package-release versions. Each milestone begins from a measurable question and should preserve previously verified invariants unless new evidence justifies changing them.

## Experimental rule

> **Freeze a measurable baseline, add exactly one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**

This applies to memory, attention, perception, retention, execution, infrastructure, model integration, interaction continuity, and performance optimization.

## Architectural pivot — 2026-08-24

v0.5 and v0.6 remain accepted historical baselines. Beginning with v0.7, Prometheist no longer treats a privileged Primary Agent, a fixed multi-agent hierarchy, or a conversation/session boundary as the target cognitive architecture.

The target is now a persistent cognitive system in which identity, memory, tasks, attention, working state, interaction continuity, policy, and execution state belong to the system; LLM invocations and workers are disposable; deterministic attention allocates durable work to bounded execution resources; external input passes through perception/salience/retention; and conversations, sessions, devices, and interfaces are provenance metadata rather than default semantic memory boundaries.

Basic access to internal memory is now treated as cognitive substrate rather than an optional live model-selected capability. Optional capabilities include deeper internal-memory investigation, code, web/external retrieval, tools, devices, and other operations.

See [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md), [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md), and [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md).

## Empirical continuity corrections — 2026-08-26/27

Native v0.7 acceptance falsified two implementation assumptions.

First, natural stateless continuity should not be reconstructed primarily by growing an application-owned vocabulary of text/entity/recency cues. The release candidate therefore adds a bounded `InteractionWorkingState` containing only canonical active-event IDs.

Second, a stateless model should not be asked whether unseen persistent memory needs to be consulted before any memory has been exposed. That decision is circular because the evidence required to decide may itself be stored in memory.

The replacement mechanism is a small system-owned **attention aperture** opened for every percept before model cognition:

```text
percept + WorkingState
    -> bounded high-recall JIT activation
    -> default MemoryPacket
    -> fresh stateless semantic assessment
       -> sufficient: respond from bounded context
       -> insufficient: request bounded deeper/cross-reference capability work
```

Aperture activation and conservative evidence admission are deliberately different roles. Activation means “potentially relevant enough to keep available now”; it does not weaken support-aware evidence requirements or convert relevance into truth.

Model-generated natural language is also now a representation of last resort system-wide. Control/state schemas prefer enums, booleans, application-owned IDs, bounded integers, and mechanically verified selections. Tests must not replace this with a hand-maintained natural-language keyword oracle.

These are scoped corrections, not the full future epistemic-state architecture. See [`milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md`](milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md).

## Pre-cognitive transient-worker correction — 2026-08-28

The next red-team result exposed a different problem: the fresh-model recurrent capability router satisfied statelessness but could make local-model inference itself the dominant latency and control mechanism. A system designed for modest local hardware should not need an open-ended sequence of general routing calls merely to decide whether enough evidence has been gathered.

The current experiment replaces that recurrent mechanism with staged disposable cognition while keeping Qwen3:4b fixed:

```text
percept
  -> JIT attention aperture
  -> fresh PRE_CAPABILITY cognition
     -> sufficient: fresh responder
     -> work required:
          deterministic first capability tranche
          -> exact bounded evidence composition
          -> fresh POST_CAPABILITY cognition
             -> respond/abstain
             -> or one newly-exposed follow-up tranche
          -> fresh responder
  -> persist result / WorkingState
```

The cognition workers do not write plans, queries, capability IDs, event IDs, dependencies, execution order, scheduling policy, or resource policy. They emit a closed validated assessment plus integer indices into an application-owned catalog. Material pre/post decisions are persisted before effects and reused after restart so a crash cannot re-roll model nondeterminism.

Under scheme v1, ordinary interactions should require two primary LLM invocations (pre-cognition + response); interactions that actually execute a first capability tranche may require a third primary invocation (post-capability cognition), plus narrowly scoped transient selectors used by a capability itself. The exact bound is an implementation mechanism under test, not a universal constitutional number.

This correction explicitly amended Constitution Article 27 from “capability reasoning is recurrent” to “capability reasoning is staged; every semantic reassessment is fresh.” See [`architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md) and [`milestones/v0.7/PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md`](milestones/v0.7/PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md).

After v0.7 closes, the roadmap must still be rebaselined against the cognitive-neuroscience and prior-project synthesis in `docs/concepts/`. The remaining open ordering question is whether a richer epistemic WorkingState should precede deterministic perception/salience. The transient-worker mechanism itself is now part of the v0.7 baseline under test rather than a deferred recurrent-inference milestone.

---

## v0.5 — Deterministic memory robustness and scale

**Status:** accepted and frozen.

Question: can deterministic JIT memory preserve bounded, provenance-bearing recall and abstention under competing states, lifecycle changes, lexical interference, and 50,000-event histories?

Accepted result: deterministic association activation, support-aware evidence admission, specificity-aware PostgreSQL candidate routing, successful 10k/50k scale suites, repaired temporal/source/isolation regressions, and no measured failure justifying embeddings.

---

## v0.6 — Shared JIT Memory and stateless worker composition

**Status:** accepted and closed on 2026-08-21.

v0.6 proved that fresh stateless LLM-backed components can participate in one continuous system through shared JIT Memory and durable events. Its useful conversational behavior remains a regression baseline. The Primary/specialist arrangement and conversation-scoped retrieval mechanics used to prove that result are no longer intended as permanent executive or cognitive boundaries.

Preserve or generalize tests for cross-turn/cross-session recall, corrections, temporal reference, ambiguity handling, topic resumption, and prior-information use without inherited transcripts. Tests whose essential assertion is that the Primary Agent owns the turn remain historical.

---

## v0.7 — Durable JIT Attention Fabric + minimal WorkingState + default attention aperture + staged transient cognition

**Status:** release-candidate architecture under final deterministic/native validation. The 2026-08-28 transient-worker amendment must pass deterministic PostgreSQL CI and native Windows/PostgreSQL/Ollama Qwen3:4b acceptance before v0.7 can close.

Primary question: can Prometheist deterministically allocate durable work across bounded concurrent execution resources, survive destruction of every worker process, preserve bounded current cognitive context, automatically expose potentially relevant persisted memory before fresh inference, acquire additional evidence in bounded stages, and resume without any privileged Primary Agent or persistent LLM context?

The milestone generalizes its deterministic single-focus scheduler seed into a resource-aware concurrent Attention Fabric with explicit resource classes/capacities, safe headroom, deterministic task requirements/reservations, scheduling epochs, atomic assignments, contention-driven preemption, authoritative resource-observation snapshots, service guarantees, `PREEMPTIBLE`/`CHECKPOINT_ONLY`/`ATOMIC` interruption semantics, dependencies, task-neutral capabilities, resumable stateless workers, and process-kill/restart acceptance.

The late release-candidate continuity/cognition corrections add three bounded primitives justified by native/red-team experiments:

```text
InteractionWorkingState
  state_id
  revision
  conversation_ids
  active_event_ids   # bounded canonical provenance pointers

Default attention aperture
  current percept
  + active_event_ids
  -> bounded deterministic activation MemoryPacket

Pre-cognitive transient workers
  aperture packet
  -> fresh closed semantic assessment
  -> deterministic staged acquisition if required
  -> fresh response synthesis
```

WorkingState is not long-term memory, a copied transcript, or a free-form summary. The aperture is not exhaustive history and is not proof that surfaced content is sufficient evidence. It is the small cognitive activation set given to a fresh model before semantic assessment.

If the aperture is insufficient, the pre-cognitive worker may select only application-owned capability indices from the current bounded catalog. The current internal-memory capability path may perform deeper research or cross-reference work and expose focused recall only as a newly legal follow-up. The original catalog is not recursively reopened under scheme v1.

> **Attention determines which durable tasks deserve execution. Resource admission determines which compatible subset can safely execute concurrently. WorkingState preserves active canonical evidence. The default aperture determines which bounded persisted evidence is cognitively available before fresh model reasoning. Transient cognition classifies unresolved semantic requirements; deterministic software owns execution.**

Higher-priority work should execute concurrently with lower-priority work when safe capacity exists. Preemption occurs only when contention prevents admission and policy permits yielding.

Configured capacity is the initial deterministic baseline, not a claim of live availability. Before durable workers execute real work, discovery and monitoring must produce persisted, freshness-bounded snapshots that epochs reference as authoritative inputs. Identical task state, resource snapshot, and policy must still produce the same scheduling decision.

Critical invariant:

> **Scheduling, current cognitive activation, basic access to persistent memory, and durable control state belong to Prometheist; workers execute admitted bounded roles but do not own attention, memory, continuity, or resource-allocation authority.**

v0.7 acceptance must keep the established continuity/restart benchmarks fixed and add transient-worker evidence: ordinary interactions should avoid recurrent general routing, pre/post assessments must be restart-stable, exact source evidence must survive staged composition, and native Qwen3:4b must preserve recall correctness without hidden transcripts, model-generated control/search text, or weakened evidence admission.

---

## v0.8 — Deterministic perception and salience (subject to post-v0.7 rebaseline)

Primary question: can Prometheist continuously receive heterogeneous external observations, cheaply identify what matters, and produce appropriate reflex, orienting, deliberate, or ignore dispositions without requiring an LLM to inspect every input?

Deliverables include normalized `Percept` contracts (including user interaction), pluggable sources/sensors, bounded input buffers, deterministic anomaly detection where feasible, structured threat/opportunity/goal/novelty/uncertainty/system-integrity salience, situation assembly, deterministic task formation, `REFLEX`/`ORIENT`/`DELIBERATE`/`IGNORE`, bounded pre-authorized reflexes, and optional model-assisted semantic classification without policy authority.

The post-v0.7 rebaseline must explicitly compare this milestone against a possible richer epistemic WorkingState milestone motivated by `docs/concepts/lessons_from_cognitive_neuroscience.md` and measured continuity failures. Do not silently combine both mechanisms; whichever comes next must be a frozen one-mechanism experiment.

---

## v0.9 — Deterministic retention and memory admission

Primary question: can Prometheist avoid permanently storing useless external data while preserving all information required for future cognition, evidence, provenance, interaction continuity, and explanation of its behavior?

Distinguish ephemeral raw experience, observational memory, and durable internal history. Implement explicit policy versions, `R0`–`R5` retention classes, deterministic TTL/correlation windows, raw-input buffers, context promotion around salient situations, raw-to-derived aggregation, reference protection, durable retention decisions, user overrides, model proposals without deletion authority, and deterministic storage-pressure behavior.

> **Anything that materially influences Prometheist's attention, reasoning, decisions, commitments, actions, or meaningful interaction continuity must leave enough durable provenance to explain that behavior later.**

---

## v0.10 — Memory generalization and natural context resumption

Primary question: where does deterministic memory fail when recall becomes semantically, temporally, relationally, and interactionally harder than the v0.5/v0.7 benchmarks?

Benchmark domains include zero-keyword paraphrases; aliases; distributed facts; contradictions; corrections/supersession; historical versus current belief; temporal/causal chains; ambiguous association graphs; artifact references; episodic grouping; internal-history/observational-memory interaction; and natural topic resumption across interaction boundaries.

The natural topic-resumption benchmark must include implicit references, progressive disambiguation, overlapping situations/topics, and explicit source-scoped questions. No stored conversation ID should be supplied unless the user's request itself imposes that provenance constraint.

Measure referent accuracy, retrieval precision, temporal correctness, correction/supersession correctness, unnecessary clarification rate, correct clarification under genuine ambiguity, bounded aperture/context size, provenance correctness, and abstention.

Semantic/vector retrieval may earn an experiment here only by repairing a frozen measured failure.

---

## v0.11 — Integrated persistent cognitive loop

Primary question: can perception, retention, memory activation/analysis, working state, attention, capabilities, disposable cognition, and natural interaction continuity operate as one continuous system even though no worker, LLM invocation, or chat session itself possesses continuity?

The integrated loop is:

```text
perceive
 -> classify salience
 -> apply retention
 -> assemble situation/working state
 -> form/update durable task
 -> allocate attention/resources
 -> open bounded default memory aperture
 -> summon fresh pre-cognitive worker
 -> execute deterministic staged memory/tool/capability work if required
 -> optionally summon fresh post-capability worker for newly enabled work
 -> summon fresh response/action cognition
 -> persist result
 -> update active state
 -> perceive resulting state
```

It must have no privileged Primary Agent, no required persistent agent identities, bounded task-local context, bounded WorkingState, bounded default memory activation, conservative deeper evidence retrieval, causal provenance, nested tasks, concurrent workflows, orientation/resumption, opportunity-triggered attention, and model/backend replacement.

Conversation is an interface, not the execution engine:

```text
conversation != agent execution
conversation != task
conversation != attention lane
conversation != memory scope
conversation != working state
```

A user must be able to move naturally among prior subjects without naming or switching conversations. Genuine ambiguity should produce natural semantic clarification rather than requests for internal identifiers.

Acceptance must include a multi-day/multi-session interaction that discusses overlapping subjects, resumes them implicitly, corrects prior information, changes subjects naturally, and later retrieves the correct historical context without an explicit conversation switch or inherited transcript.

---

## v0.12 — Operational hardening and portability

Primary question: is the complete architecture robust enough to trust as persistent personal infrastructure?

Deliverables include migrations, backup/restore, export/import, crash recovery, internal-history protection, permissions, structured logging, deterministic startup/recovery, model replacement, reproducible installation, resource profiling, assignment/reservation recovery, starvation/deadlock/priority-inversion handling, oversubscription protection, capability timeout/retry semantics, sensor failure behavior, retention-policy corruption detection, protected evidence, and partial-epoch recovery.

Portability must preserve authoritative history, retained evidence, durable tasks, WorkingState, checkpoints, causal provenance, and interaction continuity across machines with different resources and compatible model backends.

---

## v1.0 — First complete Prometheist cognitive architecture

> **Prometheist is a coherent, local-first, model-agnostic persistent cognitive system in which perception, memory, working state, attention, interaction continuity, policy, and execution state remain system-owned while all model invocations and workers are disposable.**

A defensible v1.0 must demonstrate stateless LLM calls; no required Primary Agent; system-owned identity; deterministic retention/salience/task formation/attention/resource admission; bounded current WorkingState; bounded automatic memory activation before reasoning; staged transient cognition; conservative provenance-bearing evidence retrieval; abstention; interruption safety and service guarantees; concurrent assignments without race-based authority or unsafe oversubscription; worker/model replacement; backup/restore/migration; modest-hardware usability; and reproducible acceptance suites.

It must also demonstrate that conversations, sessions, devices, and interfaces are provenance metadata rather than cognitive boundaries; natural topic resumption works across those boundaries without explicit switching; topic/situation associations may overlap; genuine ambiguity produces natural clarification; and unsupported historical references can abstain.

The defining invariant is:

> **You can terminate every LLM and worker process, replace the model, cross chat/session/device boundaries, restart Prometheist, and the system still retains its durable identity, internal history, active WorkingState, unfinished intentions, attention state, retained evidence, natural interaction continuity, and causal provenance—because none of those things belonged to an agent, conversation, or model context in the first place.**

## Deferred beyond v1.0 unless evidence pulls them forward

Learned/adaptive salience, self-modifying scheduling policy, distributed multi-machine attention fabrics, speculative predictive task formation, sophisticated long-horizon planning, autonomous device ecosystems, human-memory-comparison studies, and purpose-built hardware/mobile integration remain compatible with the long-term vision but are not prerequisites for the first measurable cognitive architecture.
