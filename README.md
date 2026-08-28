# Prometheist

**Persistent identity, attention, and work for stateless intelligence.**

Prometheist is an experimental local-first persistent cognitive/execution architecture built around one strict constraint:

> **Every LLM invocation is stateless. Continuity belongs to Prometheist itself, not to a model context window, chat session, named agent, or worker process.**

Models and worker processes are disposable compute. Durable identity, memory, WorkingState, tasks, attention, resource state, execution state, work-in-progress, policy, and causal provenance live outside them.

Prometheist began as a stateless multi-agent prototype. v0.6 proved that multiple fresh model invocations could participate in one continuous system through shared JIT Memory. Beginning with v0.7, the Primary Agent/fixed-agent hierarchy is historical: permanent agents are no longer first-class executive primitives.

## Current status

- **v0.5:** accepted deterministic Memory Kernel baseline.
- **v0.6:** accepted stateless-worker/shared-JIT-memory baseline; its Primary/specialist hierarchy is historical.
- **v0.7:** release-candidate architecture under final deterministic/native validation.

The v0.7 release candidate now combines:

- durable resource-aware JIT Attention;
- bounded active WorkingState;
- automatic JIT memory activation before semantic model judgment;
- deterministic capability discovery/execution;
- guarded disposable-worker claims/checkpoints/results;
- demand-driven single-purpose semantic workers;
- a typed cumulative `InteractionWorkpiece`;
- application-owned terminalization in which a natural-language response is optional.

The current native acceptance model remains **Qwen3:4b through Ollama**. Model capacity is being held constant so architectural changes are not hidden by a model swap. The final v0.7 release gate remains native Windows/PostgreSQL/Ollama acceptance after deterministic CI.

## The current architectural model

Prometheist is better understood as a persistent cognitive workflow system than as a chatbot or a collection of autonomous agents.

```text
external world / user / devices / software
                  |
                  v
          perception / task intake
                  |
                  v
           ATTENTION FABRIC
       priority + safe admission
                  |
                  v
       TYPED INTERACTION WORKPIECE
        application-owned frame
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
          one validated component
                  |
                  v
             TERMINALIZER
        /       |       |       \
   response   action  waiting  deferred
      |         |        |        |
   optional     +--------+--------+
   language              |
                  v
       durable results + provenance
```

No LLM context is the control loop. No final response worker is universally required.

## Interaction Workpiece

The current organizing abstraction is a typed **Interaction Workpiece**.

A workpiece begins with a small application-owned frame and accumulates only the components required by the current task. Pydantic discriminated unions define the legal component schemas.

Current component families include:

```text
PERCEPT
[REFERENCE_RESOLUTION]
[ATTENTION_APERTURE]
[EVIDENCE_SUFFICIENCY]
[CAPABILITY_SELECTION]
[PRE_COGNITIVE_CONTROL]
[CAPABILITY_WORK]
[FINAL_EVIDENCE]
[FINAL_RESPONSE_DIRECTIVE]
[USER_OUTPUT]
TERMINAL_OUTCOME
```

Square brackets mean conditional.

A simple recall and a complex action can therefore use the same master workpiece contract while traversing radically different station graphs.

### Workers receive projections, not the whole workpiece

The master workpiece is not a giant LLM prompt.

Each station has a narrow private worker profile and minimum packet contract. Deterministic application code projects only the fields needed for that role. The worker emits one small validated component; Prometheist attaches it and determines what station, if any, is eligible next.

```text
workpiece/application state
        |
        v
minimum station projection
        |
        v
bounded worker
        |
        v
one typed component
        |
        v
Pydantic validation
        |
        v
deterministic attachment / routing
```

Workers never own the workpiece.

### One job per station — and no unnecessary station

Specialization is demand-driven, not maximal.

A station belongs on the production path only when its output changes what Prometheist can legally or usefully do next. Warm model residency reduces load overhead, but every inference still has cost and failure surface.

The current pre-acquisition semantic path therefore uses only:

1. `evidence_sufficiency_verifier` — returns `SUFFICIENT | INSUFFICIENT`;
2. `capability_selector` — runs only after insufficiency and returns legal application-catalog indices.

Application code alone derives the aggregate `PreCognitiveAssessment` and the `RESPOND | ACQUIRE_CAPABILITIES | ABSTAIN` control state. No single small-model call owns all of those responsibilities.

## Terminalization is broader than response

Prometheist is not architecturally shaped around chat.

Current general terminal vocabulary includes:

- `RESPONSE_EMITTED`
- `ABSTAINED`
- `ACTION_COMPLETED`
- `ACTION_FAILED`
- `WAITING_EXTERNAL`
- `DEFERRED`

A future task that places an authorized grocery order, schedules an appointment, controls software, performs maintenance, or waits on an external condition may terminalize without any final language-model response call.

The current CLI is interactive, so its terminal path normally attaches a `USER_OUTPUT` component. That is an interface behavior, not a universal system requirement.

## One terminal JSON, without sacrificing append-only durability

When the current interaction path terminalizes, Prometheist persists one materialized `INTERACTION_WORKPIECE_SNAPSHOT` containing the complete typed assembly in causal order.

That snapshot is useful for audit, debugging, replay inspection, evaluation, and future export.

It does **not** replace the underlying append-only history. Durable events, worker claims/checkpoints/results, capability evidence, control records, and side-effect/idempotency records remain the authoritative incremental history and recovery substrate.

```text
append-only causal history
        +
materialized terminal workpiece JSON
        =
crash safety + comprehensible complete product
```

The giant workpiece snapshot is also not shoved into WorkingState. Current activation remains bounded canonical evidence/result references.

## Attention and resource governance

Attention and resource admission are separate.

- **Attention:** which durable tasks deserve execution and in what deterministic order.
- **Resource admission:** which compatible subset can safely execute concurrently under current CPU/RAM/LLM/I/O conditions.

Higher-priority work does not automatically preempt lower-priority work. If both fit safely, both may run. Preemption occurs only to resolve real contention and only when interruption policy permits it.

Worker launch is separately guarded by fresh resource observation. Current local inference defaults to one concurrent LLM slot and maintains explicit CPU/RAM headroom.

## WorkingState and JIT Memory

### WorkingState

WorkingState is bounded current activation owned by Prometheist. It primarily contains canonical event references; it is not a transcript, free-form summary, profile blob, truth store, or workpiece dump.

### Default attention aperture

Every percept receives a bounded high-recall JIT Memory packet **before** semantic model judgment. A stateless model is not asked whether unseen memory matters before potentially relevant memory has been exposed.

### Deeper internal-memory capabilities

When the aperture is insufficient, the current internal-memory capability surface can progressively investigate with:

- `deeper_research`
- `cross_reference`
- `focused_recall`

Canonical source evidence is copied/deduplicated into bounded task-local packets rather than replaced by generated summaries.

Activation, evidence sufficiency, and truth remain distinct.

## Capability / worker / LLM separation

A capability is what work may be requested. A worker profile is how one bounded role is implemented. An LLM invocation is merely one implementation mechanism for some workers.

```text
semantic capability
   -> application-owned capability registration
   -> deterministic root worker
   -> optional narrow LLM subworker
```

Models may select bounded legal capability indices. Prometheist owns capability identity, dependencies, execution order, resource admission, permissions, durable identifiers, retries, effect policy, persistence, and provenance.

All current LLM profiles share the logical `ollama-primary` model pool. Ollama may keep model weights warm between calls, but each invocation receives fresh prompt/context; model residency is not conversational continuity.

## Response and persona boundary

For the current interactive path, `FinalResponseDirective` remains the application-owned authority that fixes response/abstention, evidence/source policy, final evidence identity, completed capability identities, fallback behavior, and personality binding before optional response synthesis.

Only the final natural-language realization worker receives the response persona. Persona is expression only; it cannot create evidence, reopen acquisition, change source admissibility, or authorize actions.

`FinalResponseDirective` is a component of the current interactive path, **not** Prometheist's universal terminal object.

## Persistence and epistemic rules

Prometheist maintains several distinct information domains:

1. ephemeral raw external experience;
2. admitted observational memory;
3. append-only internal history/canonical evidence;
4. bounded active WorkingState;
5. bounded workpiece/task-local assembly state;
6. rebuildable derived indexes/associations.

Canonical evidence is not rewritten by summaries or derived memory. Anything that materially affects attention, reasoning, commitments, actions, or terminal outcomes must leave enough durable provenance to explain the behavior later.

Internal memory retrieval is distinct from external web/API/tool knowledge and action. Their provenance and authority remain explicit.

## Design principles

1. **System-owned continuity.** Durable identity/state belongs outside workers/models.
2. **Stateless LLMs and disposable workers.** Every model call is fresh.
3. **Typed workpiece assembly.** Heterogeneous tasks share a cumulative application-owned frame.
4. **Minimum information apertures.** Workers receive only what their bounded role needs.
5. **One job per station; no unnecessary station.** Specialization must earn its cost.
6. **Deterministic attachment/control.** Workers contribute components; application code owns authority and topology.
7. **Terminalization, not mandatory response.** Language is one possible product.
8. **Transient compute, durable material authority.** Decisions that authorize effects are committed before effects.
9. **Bounded cognition.** Corpus growth does not become context-window growth.
10. **Default memory activation before semantic routing.** Unseen memory is not delegated to model guesswork.
11. **WorkingState is not long-term memory.** Current activation remains bounded and canonical.
12. **Attention is distinct from resource admission.** Safe concurrency is exploited.
13. **Natural language is last-resort machine state/control.** Prefer closed typed representations.
14. **Models interpret bounded semantics; Prometheist executes policy.** No model-owned control plane.
15. **Evidence survives interpretation changes.** Derived structures remain replaceable.
16. **Unknown may remain unknown.** Relevance is not proof.
17. **No vocabulary patchwork.** Continuity is not a regex collection.
18. **Complexity must earn its place.** Freeze, change one mechanism, rerun, keep only if evidence supports it.
19. **Behavioral numbers are governed.** No magic-number patches.
20. **Resource pressure means wait/re-observe, not weaken safety.**

## Recent architectural sequence

The last several days intentionally changed several organizing assumptions while preserving prior empirical baselines:

- **2026-08-24:** pivot away from privileged Primary Agent/fixed agent hierarchy toward durable Attention Fabric and disposable workers.
- **2026-08-26/27:** native continuity testing rejected phrase-specific continuity policy and “ask the model whether it needs unseen memory”; bounded WorkingState + automatic attention aperture replaced them.
- **2026-08-28:** recurrent general capability routing was replaced by staged transient cognition.
- **2026-08-28:** native Qwen behavior exposed the danger of one overloaded pre-cognitive classifier; evidence sufficiency and capability selection were separated into demand-driven single-purpose stations.
- **2026-08-28:** the interaction path was generalized into a typed `InteractionWorkpiece` with general terminal outcomes, so response generation is no longer the organizing abstraction for the system.

Historical experiment results remain evidence. Superseded orchestration structures are not current architecture.

## Roadmap

- **v0.7** — durable resource-aware Attention Fabric, WorkingState, default attention aperture, guarded disposable workers, demand-driven transient cognition, typed workpiece/terminalization.
- **v0.8** — deterministic perception and salience, subject to post-v0.7 rebaseline.
- **v0.9** — deterministic retention and memory admission.
- **v0.10** — memory generalization and natural context-resumption failure discovery.
- **v0.11** — integrated persistent cognitive/execution loop using workpieces across interactive and non-interactive tasks.
- **v0.12** — operational hardening, portability, backup/restore/migration.
- **v1.0** — first complete attention-centric persistent cognitive architecture.

## Quick start

Requirements: Python 3.12+, `uv`, PostgreSQL, and Ollama for model-backed paths.

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
uv sync --frozen
psql -d jit_agent -f schema.sql
uv run pytest -v
```

Run the CLI:

```powershell
uv run jit-agent
```

The final native v0.7 gate on the development machine is:

```powershell
.\scripts\run_v07_acceptance.ps1
```

The script requires the configured disposable PostgreSQL test database, installed Qwen3:4b model, and explicit native-acceptance opt-in documented by the script/milestone docs.

## Documentation

Start with [`docs/README.md`](docs/README.md).

Primary current authorities:

- [`CONSTITUTION.md`](CONSTITUTION.md)
- [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)
- [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)
- [`docs/architecture/WORKER_PROFILE_REGISTRY.md`](docs/architecture/WORKER_PROFILE_REGISTRY.md)
- [`docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md)
- [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)
- [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)
- [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)
- [`docs/architecture/SYSTEM_DETERMINISM.md`](docs/architecture/SYSTEM_DETERMINISM.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/milestones/v0.7/README.md`](docs/milestones/v0.7/README.md)

The project Constitution is the top-level review/audit authority. Current architecture documents explain it; milestone and historical records preserve how the current design was reached.
