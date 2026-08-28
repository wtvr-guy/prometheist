# Prometheist Cognitive Architecture

**Status:** current target architecture beginning with v0.7; revised 2026-08-28 after the transient-worker/workpiece refactor.  
**Constitutional status:** primary architecture authority for system-owned continuity, disposable cognition, bounded attention, typed execution, capability authority, epistemic separation, and terminalization. This document is subordinate to `CONSTITUTION.md`.

Prometheist is a local-first persistent cognitive system built around a strict rule:

> **Continuity belongs to Prometheist itself. Models and workers are disposable compute.**

The v0.6 Primary Agent/specialist hierarchy proved useful behavioral properties but is no longer the target architecture. Beginning with v0.7, permanent agents are not first-class executive primitives.

## 1. Durable cognitive primitives

Prometheist organizes itself around durable/application-owned primitives rather than long-lived agent identities:

- percepts and observations;
- situations/associations;
- tasks and intentions;
- attention priority;
- resource observations/admission;
- active WorkingState;
- persistent memory/internal history;
- capabilities;
- typed interaction workpieces;
- worker/component contracts;
- checkpoints and effect/idempotency state;
- terminal outcomes;
- policy and causal provenance.

Agent-like names may describe temporary worker configurations, but no worker owns identity, memory, continuity, attention, or the cumulative work product.

## 2. System-level loop

```text
external world / user / devices / software
                  |
                  v
          perception / intake
                  |
          situation / task formation
                  |
                  v
           ATTENTION FABRIC
       priority + safe admission
                  |
                  v
        INTERACTION / TASK WORKPIECE
      application-owned typed frame
                  |
                  v
          ACTIVE WORKING STATE
       bounded canonical event refs
                  |
                  v
       DEFAULT ATTENTION APERTURE
     bounded JIT memory activation
                  |
                  v
      DEMAND-DRIVEN STATION GRAPH
   deterministic / LLM / capability /
       tool / device / human gate
                  |
       each station contributes
          one typed component
                  |
                  v
             TERMINALIZER
        /       |        |       \
   response   action   waiting  deferred
      |          |        |        |
   optional      +--------+--------+
   language               |
                  v
       durable results + provenance
                  |
          retention / indexes
                  |
                  +------> next cycle
```

No LLM context window is the control loop. No final response worker is universally required.

## 3. Interaction Workpiece

The general execution primitive is defined in [`INTERACTION_WORKPIECE.md`](INTERACTION_WORKPIECE.md).

One unit of work is represented by an `InteractionWorkpiece`: a typed application-owned frame plus a sequence of validated components contributed by only the stations that the task actually needs.

Examples of current components include percept, WorkingState/reference availability, attention aperture, evidence-sufficiency decision, optional capability selection, application-composed pre-cognitive control, capability tranches, final evidence, current interactive response directive, optional user output, and terminal outcome.

The workpiece is **not** a giant context handed to an LLM. Worker profiles receive minimum projections of it.

The central execution rule is:

> **Each station performs one bounded responsibility, receives only the workpiece projection it needs, returns one validated component, and has no authority to attach that component or choose arbitrary next work.**

Application logic validates/attaches the component and determines next-station eligibility.

## 4. Demand-driven stations

Prometheist does not require a fixed universal pipeline. Different tasks may traverse radically different station graphs while using the same master workpiece contract.

A simple recall may need:

```text
percept -> aperture -> sufficiency -> response policy -> optional response -> terminal
```

A deeper memory task may need:

```text
percept -> aperture -> sufficiency
 -> capability selection
 -> research tranche
 -> sufficiency
 -> optional focused follow-up
 -> final evidence
 -> optional response
 -> terminal
```

An action task may eventually need:

```text
percept -> context/preferences -> policy/authorization
 -> external tool/action -> ACTION_COMPLETED
```

A user-facing response may be attached afterward if useful, but the action does not become conceptually incomplete merely because no prose was generated.

## 5. Four forms of attention

Prometheist distinguishes:

### Perceptual attention
Which external changes warrant orientation/evaluation.

### Executive attention
Which durable tasks deserve execution now; owned by the Attention Fabric.

### Resource attention
Which compatible tasks can safely run concurrently under CPU/RAM/LLM/I/O constraints.

### Cognitive attention
Which bounded information/components a disposable station receives.

The default attention aperture is a cognitive-attention mechanism, not proof of truth or sufficiency.

## 6. Attention Fabric and resource admission

Attention ranks durable work deterministically. Resource admission determines the safe concurrent subset.

The number of execution slots is not CPU-thread count. Different resource classes have different semantics; current local LLM inference remains conservatively one concurrent slot until evidence justifies another value.

Higher priority does not automatically imply preemption. If higher/lower work fit together safely, both should run. Preemption exists to resolve real contention under interruption policy.

Detailed rules live in [`ATTENTION_AND_EXECUTION_GOVERNANCE.md`](ATTENTION_AND_EXECUTION_GOVERNANCE.md).

## 7. Scheduling determinism

Workers do not race to determine durable authority. Scheduling epochs consume authoritative task/resource state and atomically publish deterministic assignment/reservation results.

Identical durable task state + authoritative resource observation + policy versions must reconstruct the same scheduling result.

See [`SYSTEM_DETERMINISM.md`](SYSTEM_DETERMINISM.md).

## 8. WorkingState

WorkingState is bounded system-owned current activation, primarily canonical event references. It is not:

- a hidden transcript;
- a profile blob;
- a free-form summary;
- a substitute long-term memory;
- the interaction workpiece itself.

The workpiece captures one task's cumulative assembly/provenance. WorkingState captures what canonical evidence/results remain cognitively active across interactions.

## 9. JIT Memory

JIT Memory has distinct roles.

### Default activation
Every percept gets a small bounded high-recall activation packet before semantic evidence judgment. A stateless model cannot reliably decide whether unseen memory matters before potentially relevant memory has been exposed.

### Conservative evidence retrieval
When a claim requires support, normal `MemoryNeed`/`MemoryPacket` evidence admission remains provenance-bearing and support-aware. Relevance is not truth.

### Deeper memory capabilities
`deeper_research`, `cross_reference`, and `focused_recall` perform additional bounded investigation when the current workpiece still lacks required evidence.

Basic persistent-memory access is substrate; deeper investigation is optional capability work.

## 10. Capabilities

Capabilities describe semantic work Prometheist can perform. They are not worker identities and are not model-authored schedules.

Models may select bounded legal capability indices through an appropriate station. Prometheist owns:

- capability identity;
- dependency closure;
- execution order;
- permissions;
- resource admission;
- durable identifiers;
- idempotency/effect policy;
- persistence/provenance.

Capabilities may be deterministic, hybrid, or include narrow stateless LLM subworkers.

## 11. Worker roles

A worker is a transient execution context for one bounded role. It may be ordinary software or contain one/more stateless model invocations.

Workers do not own:

- durable identity;
- continuity;
- memory;
- task authority;
- the cumulative workpiece;
- arbitrary next-step selection.

See [`WORKER_PROFILE_REGISTRY.md`](WORKER_PROFILE_REGISTRY.md).

## 12. Model-output minimization

Model-generated natural language is representation of last resort for machine state/control.

Preferred order:

```text
enum / boolean / application-owned ID / bounded integer
    before
mechanically verified extraction
    before
free-form generated language
```

Natural language remains appropriate when language is genuinely the product.

This rule is one reason workpiece components are typed Pydantic sub-schemas rather than prose notes from workers.

## 13. Current pre-cognitive acquisition mechanism

The current interactive v0.7 path uses two demand-driven semantic stations:

1. `evidence_sufficiency_verifier` -> `SUFFICIENT | INSUFFICIENT`;
2. `capability_selector` -> legal application-catalog indices, only after insufficiency.

Application code derives the aggregate `PreCognitiveAssessment`; no one LLM authors disposition, evidence state, routing, and metadata together.

The terminal workpiece records both atomic station contributions plus the application-composed control checkpoint.

See [`PRE_COGNITIVE_TRANSIENT_WORKERS.md`](PRE_COGNITIVE_TRANSIENT_WORKERS.md).

## 14. Terminalization

A terminal outcome is broader than a response.

Current general outcomes include:

- `RESPONSE_EMITTED`;
- `ABSTAINED`;
- `ACTION_COMPLETED`;
- `ACTION_FAILED`;
- `WAITING_EXTERNAL`;
- `DEFERRED`.

The current CLI is interactive and normally attaches a `USER_OUTPUT` component. Future grocery ordering, appointment scheduling, device control, background maintenance, or software automation may terminalize without invoking a language model for final prose.

The universal boundary is therefore **terminalization**, not “final response.”

## 15. Current interactive response boundary

For interactive response tasks, `FinalResponseDirective` remains a narrow application-owned terminal authority component.

It fixes response/abstain authorization, evidence/source policy, final packet/capability bindings, fallback behavior, and persona identity before language realization.

The final natural-language worker cannot reopen acquisition, change source policy, or decide to abstain.

This directive is not promoted into the universal terminal object for non-language actions.

## 16. Persona

Persona belongs only to optional user-facing natural-language realization.

Acquisition, evidence, routing, capability, scheduling, resource, action, and terminalization authority remain persona-free. Personality is expression, not factual evidence or policy authority.

## 17. Durability and terminal snapshot

Prometheist keeps two complementary representations:

1. append-only authoritative events/results/checkpoints/effect records at safety boundaries;
2. one materialized terminal `InteractionWorkpiece` JSON snapshot that captures the assembled components in causal order.

The snapshot improves audit/debug/replay/export ergonomics. It does not replace incremental durability or become a giant WorkingState/memory substitute.

## 18. Perception, salience, and situation assembly

Continuous external input should first be normalized through deterministic/conventional processing where feasible. Future perception/salience work should distinguish ignore, deliberate, orient, and reflex behavior without giving models unilateral deletion/actuation authority.

Situations are overlapping associations, not rigid chat/session containers.

This remains roadmap work after v0.7 rebaseline.

## 19. Retention architecture

Prometheist distinguishes:

- ephemeral raw experience;
- admitted observational memory;
- durable internal history;
- active WorkingState;
- bounded task/workpiece-local state.

Anything that materially influences attention, reasoning, decisions, commitments, or actions must leave enough durable provenance to explain the behavior later.

## 20. Epistemic boundary

Attention, activation, retrieval, sufficiency, interpretation, and truth are distinct.

Prometheist must preserve distinctions among canonical evidence, user statement/belief, system interpretation, derived hypothesis, confidence, counterevidence, correction/supersession, external-current evidence, and unknown.

Internal memory and external knowledge/tool results remain distinct evidence domains with explicit provenance/freshness.

## 21. Interaction continuity

Conversation/session/device identifiers are provenance and interface metadata, not default cognitive walls.

Current context is reconstructed from system-owned WorkingState, JIT memory, durable workpiece/task state, and explicit current inputs rather than inherited model transcripts.

Natural-language continuity must not depend on growing phrase/regex vocabularies.

See [`INTERACTION_CONTINUITY.md`](INTERACTION_CONTINUITY.md).

## 22. Historical compatibility

v0.5 remains the deterministic Memory Kernel baseline. v0.6 remains evidence that fresh stateless LLM components can share persistent continuity through system-owned memory/state.

The Primary Agent hierarchy used to prove v0.6 is historical. The v0.7 workpiece/station architecture must preserve or improve the useful continuity, correction, temporal, causal, opaque-token, provenance, and restart behavior.

## 23. Experimental discipline

Architecture is treated as falsifiable mechanism design:

> **freeze baseline -> change one mechanism -> rerun -> retain only if evidence justifies it**

Recent negative/positive results include:

- phrase-specific continuity control rejected;
- asking a model whether unseen memory matters rejected;
- recurrent general capability routing rejected for the production path;
- one overloaded pre-cognitive classifier rejected after native contradictions;
- demand-driven single-purpose sufficiency/capability stations retained for current testing;
- typed workpiece added to generalize execution beyond chat-response semantics.

Behavioral tunables remain governed by the constraint registry and native evidence where required.

## 24. v1.0 target invariant

A complete first architecture should satisfy:

> **You can terminate every LLM and worker process, replace the model, restart Prometheist, and cross chat/session/device boundaries while the system retains durable identity, internal history, unfinished intentions, attention/resource state, WorkingState, retained evidence, typed work-in-progress, interaction continuity, and causal provenance because none of those things belonged to an agent or model context.**

Additionally, Prometheist must be able to complete meaningful non-language work without inventing a mandatory chatbot response stage. Language is one optional product of a general persistent cognitive/execution system.
