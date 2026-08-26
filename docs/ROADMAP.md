# Prometheist Roadmap to v1.0

This roadmap describes the engineering path from the verified Memory Kernel and stateless-worker baselines to the first complete attention-centric Prometheist architecture.

Version numbers represent architectural milestones, not package-release versions. Each milestone begins from a measurable question and should preserve previously verified invariants unless new evidence justifies changing them.

## Experimental rule

> **Freeze a measurable baseline, add exactly one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**

This applies to memory, attention, perception, retention, execution, infrastructure, model integration, interaction continuity, and performance optimization.

## Architectural pivot — 2026-08-24

v0.5 and v0.6 remain accepted historical baselines. Beginning with v0.7, Prometheist no longer treats a privileged Primary Agent, a fixed multi-agent hierarchy, or a conversation/session boundary as the target cognitive architecture.

The target is now a persistent cognitive system in which identity, memory, tasks, attention, interaction continuity, policy, and execution state belong to the system; LLM invocations and workers are disposable; JIT Memory is one capability among many; deterministic attention allocates durable work to bounded execution resources; external input passes through perception/salience/retention; and conversations, sessions, devices, and interfaces are provenance metadata rather than default semantic memory boundaries.

See [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md), [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md), and [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md).

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

## v0.7 — Durable JIT Attention Fabric

**Status:** release candidate. Deterministic PostgreSQL CI is complete; native
Windows/PostgreSQL/Ollama acceptance remains the final milestone gate.

Primary question: can Prometheist deterministically allocate durable work across bounded concurrent execution resources, survive destruction of every worker process, and resume without any privileged Primary Agent or persistent LLM context?

The milestone generalizes its deterministic single-focus scheduler seed into a resource-aware concurrent Attention Fabric with explicit resource classes/capacities, safe headroom, deterministic task requirements/reservations, scheduling epochs, atomic assignments, contention-driven preemption, authoritative resource-observation snapshots, service guarantees, `PREEMPTIBLE`/`CHECKPOINT_ONLY`/`ATOMIC` interruption semantics, dependencies, task-neutral capabilities, resumable stateless workers, and process-kill/restart acceptance.

> **Attention determines which durable tasks deserve execution. Resource admission determines which compatible subset can safely execute concurrently on the available hardware.**

Higher-priority work should execute concurrently with lower-priority work when safe capacity exists. Preemption occurs only when contention prevents admission and policy permits yielding.

Configured capacity is the initial deterministic baseline, not a claim of live
availability. Before durable workers execute real work, discovery and monitoring
must produce persisted, freshness-bounded snapshots that epochs reference as
authoritative inputs. Identical task state, resource snapshot, and policy must
still produce the same scheduling decision.

Critical invariant:

> **Scheduling decisions belong to persistent deterministic system policy; workers execute admitted assignments but do not own system attention or resource-allocation authority.**

---

## v0.8 — Deterministic perception and salience

Primary question: can Prometheist continuously receive heterogeneous external observations, cheaply identify what matters, and produce appropriate reflex, orienting, deliberate, or ignore dispositions without requiring an LLM to inspect every input?

Deliverables include normalized `Percept` contracts (including user interaction), pluggable sources/sensors, bounded input buffers, deterministic anomaly detection where feasible, structured threat/opportunity/goal/novelty/uncertainty/system-integrity salience, situation assembly, deterministic task formation, `REFLEX`/`ORIENT`/`DELIBERATE`/`IGNORE`, bounded pre-authorized reflexes, and optional model-assisted semantic classification without policy authority.

---

## v0.9 — Deterministic retention and memory admission

Primary question: can Prometheist avoid permanently storing useless external data while preserving all information required for future cognition, evidence, provenance, interaction continuity, and explanation of its behavior?

Distinguish ephemeral raw experience, observational memory, and durable internal history. Implement explicit policy versions, `R0`–`R5` retention classes, deterministic TTL/correlation windows, raw-input buffers, context promotion around salient situations, raw-to-derived aggregation, reference protection, durable retention decisions, user overrides, model proposals without deletion authority, and deterministic storage-pressure behavior.

> **Anything that materially influences Prometheist's attention, reasoning, decisions, commitments, actions, or meaningful interaction continuity must leave enough durable provenance to explain that behavior later.**

---

## v0.10 — Memory generalization and natural context resumption

Primary question: where does deterministic memory fail when recall becomes semantically, temporally, relationally, and interactionally harder than the v0.5 benchmark?

Benchmark domains include zero-keyword paraphrases; aliases; distributed facts; contradictions; corrections/supersession; historical versus current belief; temporal/causal chains; ambiguous association graphs; artifact references; episodic grouping; internal-history/observational-memory interaction; and **natural topic resumption across interaction boundaries**.

The natural topic-resumption benchmark must include implicit references such as "that thing we discussed yesterday," progressive disambiguation, overlapping situations/topics, and explicit source-scoped questions such as "what did I say in this chat?" No stored conversation ID should be supplied unless the user's request itself imposes that provenance constraint.

Measure referent accuracy, retrieval precision, temporal correctness, correction/supersession correctness, unnecessary clarification rate, correct clarification under genuine ambiguity, bounded context size, provenance correctness, and abstention.

Semantic/vector retrieval may earn an experiment here only by repairing a frozen measured failure.

See [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md).

---

## v0.11 — Integrated persistent cognitive loop

Primary question: can perception, retention, memory, attention, capabilities, disposable cognition, and natural interaction continuity operate as one continuous system even though no worker, LLM invocation, or chat session itself possesses continuity?

The integrated loop is: perceive -> classify salience -> apply retention -> assemble situation -> form/update durable task -> allocate attention/resources -> invoke capabilities -> request JIT Memory only when required -> reason/act -> persist result -> perceive resulting state.

It must have no privileged Primary Agent, no required persistent agent identities, bounded task-local context, demand-driven JIT Memory, causal provenance, nested tasks, concurrent workflows, orientation/resumption, opportunity-triggered attention, and model/backend replacement.

Conversation is an interface, not the execution engine:

```text
conversation != agent execution
conversation != task
conversation != attention lane
conversation != memory scope
```

A user must be able to move naturally among prior subjects without naming or switching conversations. Session/device identifiers remain provenance but do not normally bound semantic recall. Genuine ambiguity should produce natural semantic clarification rather than requests for internal identifiers.

Acceptance must include a multi-day/multi-session interaction that discusses overlapping subjects, resumes them implicitly, corrects prior information, changes subjects naturally, and later retrieves the correct historical context without an explicit conversation switch or inherited transcript.

---

## v0.12 — Operational hardening and portability

Primary question: is the complete architecture robust enough to trust as persistent personal infrastructure?

Deliverables include migrations, backup/restore, export/import, crash recovery, internal-history protection, permissions, structured logging, deterministic startup/recovery, model replacement, reproducible installation, resource profiling, assignment/reservation recovery, starvation/deadlock/priority-inversion handling, oversubscription protection, capability timeout/retry semantics, sensor failure behavior, retention-policy corruption detection, protected evidence, and partial-epoch recovery.

Portability must preserve authoritative history, retained evidence, durable tasks, checkpoints, causal provenance, and interaction continuity across machines with different resources and compatible model backends.

---

## v1.0 — First complete Prometheist cognitive architecture

> **Prometheist is a coherent, local-first, model-agnostic persistent cognitive system in which perception, memory, attention, interaction continuity, policy, and execution state remain system-owned while all model invocations and workers are disposable.**

A defensible v1.0 must demonstrate stateless LLM calls; no required Primary Agent; system-owned identity; deterministic retention/salience/task formation/attention/resource admission; bounded provenance-bearing JIT Memory; abstention; interruption safety and service guarantees; concurrent assignments without race-based authority or unsafe oversubscription; worker/model replacement; backup/restore/migration; modest-hardware usability; and reproducible acceptance suites.

It must also demonstrate that conversations, sessions, devices, and interfaces are provenance metadata rather than cognitive boundaries; natural topic resumption works across those boundaries without explicit switching; topic/situation associations may overlap; genuine ambiguity produces natural clarification; and unsupported historical references can abstain.

The defining invariant is:

> **You can terminate every LLM and worker process, replace the model, cross chat/session/device boundaries, restart Prometheist, and the system still retains its durable identity, internal history, unfinished intentions, attention state, retained evidence, natural interaction continuity, and causal provenance—because none of those things belonged to an agent, conversation, or model context in the first place.**

## Deferred beyond v1.0 unless evidence pulls them forward

Learned/adaptive salience, self-modifying scheduling policy, distributed multi-machine attention fabrics, speculative predictive task formation, sophisticated long-horizon planning, autonomous device ecosystems, human-memory-comparison studies, and purpose-built hardware/mobile integration remain compatible with the long-term vision but are not prerequisites for the first measurable cognitive architecture.
