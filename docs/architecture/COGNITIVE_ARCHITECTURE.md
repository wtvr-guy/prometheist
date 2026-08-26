# Prometheist Cognitive Architecture

**Status:** target architecture beginning with v0.7.

Prometheist is evolving from a stateless multi-agent prototype into a persistent cognitive system whose identity, memory, attention, execution state, interaction continuity, and policy remain outside all LLM contexts and worker processes.

The central architectural rule is:

> **The system owns continuity. Models and workers are disposable compute.**

This document supersedes the Primary Agent as the target top-level architecture. The removed Primary-Agent implementation remains part of the verified v0.6 historical record, not the executive structure for v0.7 and later.

## 1. Architectural pivot

The v0.6 prototype proved that multiple fresh, stateless LLM invocations can participate in one persistent system by using shared JIT Memory and durable event state. That result remains valid.

The next question is no longer how to make a Primary Agent orchestrate more specialists. The more general design is to remove privileged agents from the center of the system.

Prometheist should instead be organized around durable cognitive primitives:

- percepts;
- interaction events and streams;
- situations and associations;
- retention decisions;
- tasks and intentions;
- attention allocation;
- execution resources;
- capabilities;
- checkpoints;
- actions and results;
- internal events;
- memory;
- policy.

Named agents may still exist as convenient worker roles, but they are optional compositions of capabilities rather than owners of continuity or executive authority.

## 2. System-level loop

The target control loop is:

```text
external world / user / devices / software
                  |
                  v
        ephemeral input buffers
                  |
                  v
              perception
                  |
          +-------+-------+
          |               |
       reflex          salience
          |               |
          |        situation assembly
          |               |
          |          task formation
          |               |
          +-------+-------+
                  |
                  v
           ATTENTION FABRIC
                  |
       deterministic allocation
                  |
       +----------+----------+
       |          |          |
     lane       lane       lane ...
       |          |          |
       +----------+----------+
                  |
              capabilities
       memory / models / code /
       web / files / devices /
             actuators / ...
                  |
                  v
          results + observations
                  |
                  v
            internal history
                  |
          +-------+-------+
          |               |
       JIT Memory      retention
          |               |
          +-------+-------+
                  |
                  +----------> next cycle
```

No LLM context window is the control loop. No worker process is the durable system.

## 3. Four forms of attention

Prometheist uses the word attention at several distinct levels.

### 3.1 Perceptual attention

Determines which external changes warrant orientation or further evaluation.

Examples include a sudden loud impulse, an unexpected filesystem mutation, an unusual transaction, an approaching object, a temperature excursion, a user utterance, or a short-lived opportunity.

### 3.2 Executive attention

Determines which durable tasks deserve system execution resources now.

This is the responsibility of the JIT Attention Fabric.

### 3.3 Resource/lane attention

Determines which compatible task is assigned to a particular execution resource or lane during a scheduling epoch.

### 3.4 Cognitive attention

Determines what bounded information is admitted into a particular disposable model invocation. JIT Memory participates here when historical internal context is required.

These layers must not be conflated. A percept may be highly salient but produce no durable task after investigation. A low-salience observation may later produce a high-priority task because of semantic meaning or a deadline.

## 4. JIT Attention Fabric

The single-focus JIT Attention scheduler introduced in the first v0.7 increment is the seed of a more general Attention Fabric.

The fabric maintains one globally authoritative runnable-task model while allowing bounded concurrent execution.

Conceptually:

```text
                  runnable durable tasks
                           |
                           v
                 deterministic ranking
                           |
                           v
                  ATTENTION FABRIC
                           |
                  deterministic match
                           |
          +----------------+----------------+
          |                |                |
       lane-00          lane-01          lane-02 ...
          |                |                |
        task A           task B           task C
```

The number of lanes must not be hard-coded to CPU thread count. A lane represents available execution capacity for a resource class.

Possible resource classes include `CPU_GENERAL`, `LLM_INFERENCE`, `DATABASE`, `FILESYSTEM_IO`, `NETWORK_IO`, `GPU`, `DEVICE_IO`, and `ACTUATOR`.

A commodity system may expose several CPU threads but only one sensible local-LLM inference lane. Conversely, many network-I/O tasks may be safe to overlap while one CPU-intensive model call is active.

The invariant is:

> **Concurrency is bounded by declared resource capacity, while task selection and assignment remain globally deterministic.**

## 5. Scheduling epochs and determinism

Workers must not race independently to claim arbitrary tasks. Timing-dependent claims would make identical state produce different assignments.

Instead, scheduling occurs in deterministic epochs:

1. read the authoritative runnable-task set;
2. read currently available execution resources;
3. rank tasks deterministically;
4. rank lanes/resources deterministically;
5. match tasks to compatible lanes deterministically;
6. persist the complete assignment atomically;
7. allow workers to execute only persisted assignments.

The first v0.7 scheduler already establishes core ordering, service-guarantee, interruption, dependency, checkpoint, and restart semantics. Multi-lane work extends those invariants rather than replacing them.

## 6. Priority, service guarantees, and interruption

Task priority should be derived from structured metadata, not model preference.

The current criticality mapping remains a useful baseline: `EMERGENCY/P0`, `USER_BLOCKING/P1`, `USER_REQUESTED/P2`, `SUPPORTING/P3`, `MAINTENANCE/P4`, and `OPPORTUNISTIC/P5`.

Service guarantees prevent starvation through explicit deterministic promotion policy.

Every runnable task must also carry an interruption policy:

- `PREEMPTIBLE` — may yield immediately to strictly higher-priority compatible work;
- `CHECKPOINT_ONLY` — yields only at a declared safe checkpoint;
- `ATOMIC` — cannot be preempted by the normal scheduler.

Service guarantees must never silently override interruption safety.

## 7. Perception and salience

Continuous external input should not flow directly into an LLM or durable task queue.

Each source should first produce normalized percepts through cheap deterministic or conventional signal-processing logic where possible. A user utterance is also an external percept, although its semantic value and retention policy normally differ sharply from high-volume raw sensor data.

A percept may contain structured dimensions such as source and modality, magnitude, novelty, rate of change, anomaly class, confidence, threat relevance, opportunity relevance, goal relevance, uncertainty, and system-integrity relevance.

Prometheist should distinguish at least four dispositions:

- `IGNORE` — no further action beyond any required retention bookkeeping;
- `DELIBERATE` — meaningful work, but ordinary scheduling is sufficient;
- `ORIENT` — significance is uncertain enough to justify immediate investigation;
- `REFLEX` — a previously authorized deterministic condition permits an immediate bounded action.

A sudden loud noise illustrates the distinction. It may be extremely salient because its cause is unknown. That warrants orientation. It does not yet prove an emergency.

## 8. Situation assembly

Individual percepts often become meaningful only when correlated. Prometheist should therefore assemble temporally, semantically, and causally related percepts into durable or temporary `Situation` objects before task formation where appropriate.

Situations are associations, not rigid containers. One event may contribute to several situations or topics, and one situation may span multiple UI sessions, devices, days, or interaction streams.

LLMs may assist with ambiguous semantic classification, but their output must be treated as structured evidence or a proposal. Deterministic policy retains authority over salience class, task priority, deletion, permissions, and actuator use.

## 9. Reflex, orient, deliberate

Prometheist should support three distinct response paths.

### Reflex

Known condition -> bounded deterministic action -> durable follow-up event/task.

### Orient

Potentially consequential but uncertain condition -> high-priority investigation task. If benign, prior eligible work resumes.

### Deliberate

Meaningful but non-immediate condition -> normal durable task formation and scheduling.

## 10. Retention architecture

The earlier rule to persist every incoming datum indefinitely does not scale to continuous sensory input.

Prometheist instead distinguishes:

- **Ephemeral raw experience** — raw external input may exist only in bounded rolling buffers unless policy promotes it.
- **Observational memory** — external observations are retained according to deterministic retention policy.
- **Internal history** — system-internal information that materially explains what Prometheist knew, focused on, decided, attempted, or did is durable by default.

A useful initial retention classification is `R0 EPHEMERAL`, `R1 TEMPORARY`, `R2 DERIVED_ONLY`, `R3 EVENT`, `R4 EVIDENCE`, and `R5 PROTECTED`.

Uncertain potentially important input should normally be retained temporarily rather than destroyed immediately.

## 11. Retention invariant

The strongest persistence rule applies to internal causality:

> **Anything that materially influences Prometheist's attention, reasoning, decisions, commitments, or actions must leave enough durable provenance to explain that behavior later.**

Raw data may later expire, but the system should retain the retention decision and the causal record that explains why an attention shift or action occurred.

An LLM may propose that data is routine or low-value, but an LLM must not possess unilateral deletion authority.

## 12. JIT Memory as a capability

JIT Memory is one capability among many.

An active task requests memory only when it needs historical internal information. Memory is not injected universally and does not control scheduling.

The consumer expresses what information it requires through a stable contract such as `MemoryNeed`; the memory subsystem determines how to retrieve a bounded provenance-bearing `MemoryPacket`.

The verified Memory Kernel remains valuable because it provides deterministic, bounded, provenance-aware historical retrieval behind that capability boundary.

## 13. Human-like interaction continuity

Prometheist's persistent experience must be continuous across chat/session boundaries. A conversation identifier is useful provenance metadata, but it is not a cognitive boundary and must not normally be exposed as something the user has to manage.

The target user experience is ordinary human conversational resumption. A user should be able to say:

> "Remember that thing we were talking about yesterday, about the attention layers?"

and allow Prometheist to resolve the referent from semantic, temporal, causal, entity, task, and situation cues. The user should not have to select or name a stored conversation.

The architecture therefore distinguishes:

- **interaction stream** — where and when communication physically occurred, including UI session/device/source provenance;
- **topic/situation associations** — what events appear to concern, represented as overlapping associations rather than exclusive containers;
- **task/intention** — what durable work Prometheist is pursuing.

These relationships are many-to-many. A single utterance may relate to several situations and tasks. A single situation may span many interaction streams. A task may continue after the conversation that created it has ended.

`conversation_id`, `conversation_seq`, session IDs, device IDs, and similar coordinates may remain valuable for provenance, ordering, debugging, UI grouping, explicit source-scoped questions, and retrieval optimization. They must not become default semantic walls around recall.

Accordingly, concepts such as `CURRENT_CONVERSATION` versus `ALL_CONVERSATIONS` are historical retrieval mechanics rather than the target cognitive model. Ordinary recall should be ranked and constrained by evidence such as:

- semantic/referential cues;
- temporal cues;
- causal relationships;
- entities;
- active and recent tasks;
- situation/topic associations;
- provenance/source constraints when the user explicitly asks for them;
- confidence and authority.

Context is reconstructed just in time for the current task. It is not carried forward because a model happened to inherit a transcript.

If the evidence uniquely supports an earlier topic, Prometheist should resume it without fanfare. If genuine semantic ambiguity remains, Prometheist should ask a natural clarification about meaning (for example, which of two attention discussions the user means), not ask the user to operate an internal memory namespace.

The interaction invariant is:

> **Conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Context is reconstructed just in time from current intent and available retrieval cues.**

## 14. Disposable cognition and worker roles

A reasoning worker should receive only the task-local state it needs:

```text
durable task/checkpoint
        +
current inputs
        +
explicit capability results
        +
JIT-retrieved memory when required
        |
        v
fresh stateless model invocation
        |
        v
structured result
        |
        v
persist
        |
        v
worker/model context discarded
```

A worker may be configured as a planner, researcher, code reviewer, analyst, summarizer, conversational responder, or another specialist role. Those identities describe temporary compute behavior, not persistent cognitive entities.

## 15. Capability boundary

Capabilities should remain modular and independently invokable. Examples include JIT Memory, model inference, code execution, database operations, filesystem access, web/API retrieval, artifact processing, device sensing, and actuator control.

Capabilities expose explicit schemas, permissions, resource requirements, idempotency behavior, and provenance where applicable.

## 16. Historical compatibility and conversation baseline

The v0.5 and v0.6 results remain accepted evidence.

v0.5 established a deterministic Memory Kernel baseline.

v0.6 established that fresh stateless LLM invocations can use a shared JIT Memory boundary and persistent events to participate in one continuous system. Its conversation behavior remains an important regression baseline even though its Primary/specialist orchestration is superseded.

Tests of cross-turn recall, corrections, temporal reference, cross-session recall, topic resumption, ambiguous references, and specialist use of prior information without inherited transcripts should be preserved or generalized. Tests whose essential assertion is that the Primary Agent owns the turn or orchestration should remain historical rather than constrain the new architecture.

The replacement architecture must reproduce or improve the useful conversational behavior demonstrated by v0.6 while removing session boundaries from the user's cognitive model.

## 17. v1.0 target invariant

A complete first architecture should satisfy:

> **You can terminate every LLM and worker process, replace the model, restart Prometheist, and the system still retains its durable identity, internal history, unfinished intentions, attention state, retained evidence, interaction continuity, and causal provenance because none of those things belonged to an agent, chat session, or model context in the first place.**

The roadmap defines the experimental milestones required to earn that claim.
