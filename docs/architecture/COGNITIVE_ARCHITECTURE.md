# Prometheist Cognitive Architecture

**Status:** target architecture beginning with v0.7. Revised 2026-08-27 after native continuity experiments established the default attention-aperture boundary.

**Constitutional status:** primary architecture authority for Articles 1, 2, 15, 16, 17, 18, and 19 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md). This document explains those constitutional rules in depth and is subordinate to the Constitution where wording conflicts.

Prometheist is evolving from a stateless multi-agent prototype into a persistent cognitive system whose identity, memory, attention, execution state, interaction continuity, and policy remain outside all LLM contexts and worker processes.

The central architectural rule is:

> **The system owns continuity. Models and workers are disposable compute.**

This document supersedes the Primary Agent as the target top-level architecture. The removed Primary-Agent implementation remains part of the verified v0.6 historical record, not the executive structure for v0.7 and later.

## 1. Architectural pivot

The v0.6 prototype proved that multiple fresh, stateless LLM invocations can participate in one persistent system through shared JIT Memory and durable event state. That result remains valid.

The next question is no longer how to make a Primary Agent orchestrate more specialists. The more general design removes privileged agents from the center of the system and organizes Prometheist around durable cognitive primitives:

- percepts;
- interaction events and streams;
- situations and associations;
- retention decisions;
- tasks and intentions;
- attention allocation;
- execution resources;
- active working state;
- capabilities;
- checkpoints;
- actions and results;
- internal events;
- memory;
- policy.

Named agents may still describe temporary worker roles, but they are optional compositions of capabilities rather than owners of continuity or executive authority.

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
       priority + resource admission
                  |
       +----------+----------+
       |          |          |
  assignment  assignment  assignment ...
       |          |          |
       +----------+----------+
                  |
                  v
          ACTIVE WORKING STATE
       bounded canonical event refs
                  |
                  v
       DEFAULT ATTENTION APERTURE
   bounded JIT activation for each percept
                  |
                  v
        fresh stateless cognition
                  |
          +-------+-------+
          |               |
       respond      deeper capability
                       |
                MEMORY_ANALYSIS /
                 code / web / etc.
          |               |
          +-------+-------+
                  |
                  v
          results + observations
                  |
                  v
            internal history
                  |
          +-------+-------+
          |               |
     memory indexes    retention
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

### 3.2 Executive attention

Determines which durable tasks deserve system execution resources now. This is the responsibility of the JIT Attention Fabric.

### 3.3 Resource attention

Determines which compatible tasks may execute concurrently under current CPU, RAM, local-model, I/O, and other resource constraints.

### 3.4 Cognitive attention

Determines what bounded information is made available to a particular disposable inference.

Beginning with the v0.7 attention-aperture correction, every percept receives a small system-owned JIT Memory activation packet before model routing. This packet combines current WorkingState with bounded potentially relevant canonical history. If the default aperture is insufficient, the model may request `MEMORY_ANALYSIS` for deeper/focused memory work.

The aperture is therefore an attention mechanism, not a claim of truth or evidentiary sufficiency.

## 4. JIT Attention Fabric

The Attention Fabric maintains one globally authoritative runnable-task model while allowing bounded concurrent execution. It ranks durable work deterministically and admits as much compatible work as current safe resource capacity permits.

The number of execution slots must not be hard-coded to CPU thread count. Different resource classes have different capacity semantics. A commodity system may expose many CPU threads but only one sensible local-LLM inference slot.

> **Concurrency is bounded by declared resource capacity, while task selection and assignment remain globally deterministic.**

Detailed constitutional execution rules now live in [`ATTENTION_AND_EXECUTION_GOVERNANCE.md`](ATTENTION_AND_EXECUTION_GOVERNANCE.md).

## 5. Scheduling epochs and determinism

Workers must not race independently to claim arbitrary tasks. Scheduling occurs in deterministic epochs:

1. read authoritative runnable tasks;
2. capture authoritative safe resource state;
3. derive deterministic priorities;
4. preserve valid assignments where possible;
5. admit compatible work deterministically;
6. persist the complete assignment/reservation result atomically;
7. allow workers to execute only persisted assignments.

Determinism means identical durable task state + identical captured resource state + identical policy version produces the same scheduling result.

The repository-wide determinism contract is defined in [`SYSTEM_DETERMINISM.md`](SYSTEM_DETERMINISM.md).

## 6. Priority, service guarantees, interruption, and resource safety

Task priority is derived from structured metadata, not model preference. The current criticality mapping remains a useful baseline: `EMERGENCY/P0`, `USER_BLOCKING/P1`, `USER_REQUESTED/P2`, `SUPPORTING/P3`, `MAINTENANCE/P4`, and `OPPORTUNISTIC/P5`.

Service guarantees prevent starvation. Interruption policies remain `PREEMPTIBLE`, `CHECKPOINT_ONLY`, and `ATOMIC`.

Priority alone does not justify preemption. If higher- and lower-priority work can execute safely together, both continue. Preemption is considered only when resource contention blocks higher-priority work and the victim's interruption policy permits yielding.

## 7. Perception and salience

Continuous external input should not flow directly into an LLM or durable task queue. Sources first produce normalized percepts through cheap deterministic or conventional signal-processing logic where possible.

A percept may carry structured dimensions such as source/modality, magnitude, novelty, rate of change, anomaly class, confidence, threat relevance, opportunity relevance, goal relevance, uncertainty, and system-integrity relevance.

Prometheist should distinguish at least `IGNORE`, `DELIBERATE`, `ORIENT`, and `REFLEX` dispositions. Model interpretation may assist ambiguous cases, but deterministic policy retains authority over deletion, priority, permissions, and actuator use.

## 8. Situation assembly

Individual percepts often become meaningful only when correlated. Prometheist should assemble temporally, semantically, causally, and relationally connected percepts into overlapping situation representations where evidence justifies the mechanism.

Situations are associations, not rigid containers. One event may contribute to several situations; one situation may span sessions, devices, days, and tasks.

## 9. Reflex, orient, deliberate

Prometheist should support three distinct response paths:

- **Reflex:** known condition -> bounded deterministic action -> durable follow-up event/task.
- **Orient:** potentially consequential but uncertain condition -> high-priority investigation.
- **Deliberate:** meaningful but non-immediate condition -> normal durable task formation/scheduling.

## 10. Retention architecture

Prometheist distinguishes:

- **ephemeral raw experience** — bounded rolling data not necessarily retained;
- **observational memory** — external observations retained by explicit policy;
- **internal history** — durable state needed to explain what Prometheist knew, focused on, decided, attempted, committed to, or did;
- **active working state** — bounded canonical event pointers currently activated for cognition.

An LLM may propose that input is routine or low-value, but an LLM must not possess unilateral deletion authority.

## 11. Retention invariant

> **Anything that materially influences Prometheist's attention, reasoning, decisions, commitments, or actions must leave enough durable provenance to explain that behavior later.**

Raw data may expire under policy, but causal records explaining attention shifts and actions must remain sufficient for audit/reconstruction.

## 12. JIT Memory: substrate, activation, and analysis

The phrase “JIT Memory” now refers to a subsystem with two different cognitive roles that must not be conflated.

### 12.1 Default attention activation

Every percept automatically opens a small bounded memory aperture. This does not depend on a model deciding whether memory is needed.

The reason is structural: a stateless model cannot reliably decide whether unseen memory matters when the fact that would change its decision may itself be in unseen memory.

The default aperture uses the deterministic candidate/scoring layer in a high-recall activation role. A surfaced item means:

> **potentially relevant enough to keep available now**

not:

> **sufficient evidence that a proposition is true**

### 12.2 Conservative evidence retrieval

When a task needs evidence, the normal `MemoryNeed` / `MemoryPacket` path retains support-aware admission, provenance, and abstention. This boundary may reject sparse topical overlap that the aperture is still allowed to activate.

### 12.3 `MEMORY_ANALYSIS`

`MEMORY_ANALYSIS` remains an optional capability because it is an operation performed on memory. After the model has seen the current percept and default aperture, it may request deeper/focused analysis if the bounded activation packet is insufficient.

The live interaction model therefore does **not** select a basic `INTERNAL_MEMORY` capability. Basic access already occurred.

This yields a useful hierarchy:

```text
always:
  percept + WorkingState -> bounded activation aperture

when needed:
  MEMORY_ANALYSIS -> deeper/focused evidence retrieval and reasoning
```

## 13. Model-output minimization

Prometheist adopts a system-wide representation preference:

> **Model-generated natural language is the representation of last resort.**

Preferred order:

```text
enum / boolean / application-owned id / bounded integer
    before
mechanically verified extractive selection
    before
free-form generated natural language
```

This applies to schemas, routing, state transitions, scheduling metadata, retrieval control, capability selection, and test oracles. JSON alone is not sufficient if it contains unconstrained model-authored control strings.

Natural language remains appropriate when language is actually the product: user-facing responses, requested prose artifacts, or genuinely irreducible semantic content.

For the live v0.7 path, the post-aperture routing model can emit only `NONE` or `MEMORY_ANALYSIS`. Deeper memory planning emits only a scope enum and bounded indices into an application-generated anchor catalog. Invalid or unexpected fields fail validation.

## 14. Human-like interaction continuity

Prometheist's persistent experience must be continuous across chat/session boundaries. Conversation IDs remain provenance, ordering, debugging, UI, and explicit source-scoping metadata—not default semantic walls.

The interaction path is now:

```text
current percept
    +
WorkingState
    |
    v
default bounded attention aperture
    |
    v
fresh stateless model
    |
    +--> respond
    |
    +--> MEMORY_ANALYSIS when deeper focus is required
```

The old phrase-specific `requires_persisted_context()` mechanism is deprecated and disabled. Prometheist must not grow an application-owned vocabulary of phrases such as “just discussed,” “those approaches,” or other surface forms to decide whether continuity exists.

Lexical, entity, temporal, associative, and future experimentally justified semantic retrieval remain legitimate *inside memory*. The rejected mechanism is natural-language phrase policy in the control plane.

## 15. Disposable cognition and worker roles

A reasoning worker receives only bounded durable/task-local state:

```text
durable task/checkpoint
        +
current percept/input
        +
default attention-aperture packet
        +
optional explicit capability results
        |
        v
fresh stateless model invocation
        |
        v
closed structured control result or user-facing language
        |
        v
persist
        |
        v
discard worker/model context
```

Worker roles such as planner, researcher, code reviewer, analyst, or responder describe temporary compute behavior, not persistent cognitive entities.

## 16. Capability boundary

Capabilities remain modular and independently invokable: model inference, memory analysis, code execution, database operations, filesystem access, web/API retrieval, artifact processing, device sensing, actuator control, and others.

Capabilities expose explicit schemas, permissions, resource requirements, idempotency behavior, and provenance.

Basic memory activation is intentionally outside this optional capability boundary because it is part of the cognitive substrate. Deeper memory analysis is inside it.

### 16.1 Internal memory versus external knowledge

Prometheist's persistent internal memory and knowledge fetched from outside the system are distinct evidence domains.

Internal memory answers questions about the system's retained experience, user/system history, prior evidence, commitments, observations, and internal state. External capabilities such as web/API/tool retrieval obtain information from the outside world now. External evidence must retain source and freshness provenance and must not silently masquerade as something Prometheist previously remembered. Conversely, an old internal memory is not automatically evidence of the current external state of the world.

A result may combine both domains, but their provenance and authority remain explicit.

## 17. Epistemic boundary

Attention, activation, retrieval, interpretation, and truth are distinct.

A WorkingState event or aperture item says only that canonical evidence is currently active/relevant enough to expose. It does not assert that every proposition in that event is correct or current.

Prometheist must preserve distinctions among:

- canonical observation/evidence;
- user belief or statement;
- system interpretation;
- derived claim/hypothesis;
- confidence;
- counterevidence;
- supersession/correction;
- unknown.

Richer epistemic working state remains future work; v0.7 must not smuggle it into free-form summaries.

## 18. Historical compatibility

v0.5 established the deterministic Memory Kernel baseline. v0.6 established that fresh stateless LLM invocations can share persistent context through JIT Memory without hidden transcripts. Those results remain accepted evidence even though the Primary/specialist hierarchy is superseded.

The replacement architecture must reproduce or improve useful cross-turn, cross-process, cross-session, correction, temporal, causal, opaque-token, and provenance behavior.

## 19. Scientific-method rule

Architectural mechanisms are experimental claims:

> **Freeze baseline -> add one mechanism -> rerun the same experiment -> keep it only if the evidence justifies it.**

Negative results are retained. Phrase-cue continuity and “ask the model whether it needs unseen memory” are now explicit negative results from v0.7 acceptance.

The engineering rules for constraints, benchmarks, and evidence are defined in [`../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md) and [`../engineering/TESTING_AND_ACCEPTANCE.md`](../engineering/TESTING_AND_ACCEPTANCE.md).

## 20. v1.0 target invariant

A complete first architecture should satisfy:

> **You can terminate every LLM and worker process, replace the model, restart Prometheist, and the system still retains its durable identity, internal history, unfinished intentions, attention state, active working state, retained evidence, interaction continuity, and causal provenance because none of those things belonged to an agent, chat session, or model context in the first place.**

The roadmap defines the experiments required to earn that claim.
