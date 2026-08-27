# Prometheist

**Persistent identity and attention for stateless intelligence.**

Prometheist is an experimental, local-first persistent cognitive architecture built around a strict constraint: **every LLM invocation is stateless**.

Models and worker processes are disposable compute. They are never the durable owners of memory, identity, attention, working state, interaction continuity, policy, or authoritative system state.

> **Core thesis:** continuity belongs to Prometheist itself, not to an LLM context window, chat session, agent, or worker process.

Prometheist began as a stateless multi-agent prototype. v0.6 used a Primary Agent plus specialists to prove that fresh model invocations could participate in one continuous system through shared JIT Memory without inherited transcripts. That hierarchy is now historical. Beginning with v0.7, **permanent agents are not first-class architectural primitives**. The system is being rebuilt around durable attention, tasks, active working state, memory, capabilities, perception, retention, and disposable workers.

## Current status

### v0.5 — accepted deterministic Memory Kernel baseline

Memory Kernel v0.5 established bounded deterministic associative recall with provenance, support-aware evidence admission, explicit abstention, and specificity-aware PostgreSQL candidate routing. Controlled synthetic scale evaluation reached perfect observed correctness through 50,000 events per persona with a fixed 500-event PostgreSQL candidate window. Those results are a baseline, not a claim of general semantic-memory completeness.

### v0.6 — accepted historical stateless-worker/JIT-Memory baseline

v0.6 proved that separate fresh LLM-backed components can obtain persistent internal context through the same `MemoryNeed` / `MemoryPacket` boundary without inheriting hidden transcripts.

The Primary Agent/specialist structure used to prove that result is **superseded architecture**. v0.7 removes that execution path after reproducing its useful continuity baseline through durable task-neutral workers. Historical event names and documentation remain readable as evidence; they are not current executive architecture.

### v0.7 — release candidate: durable JIT Attention Fabric + WorkingState + recurrent bounded cognition

v0.7 establishes deterministic durable task scheduling, structured priority metadata, service guarantees, interruption policies, dependency gating, resumable PostgreSQL state, live CPU/RAM discovery, conservative observed-capacity snapshots, configured safe headroom, quantitative resource admission/reservations, a default single local-LLM slot, atomic durable scheduling epochs and assignment sets, contention-driven multi-assignment preemption, and a durable claim/lease/checkpoint/result protocol for disposable workers.

The target is a resource-aware **Attention Fabric** that determines which durable tasks deserve execution and which compatible subset can safely execute concurrently on available hardware. Higher-priority work does not automatically kill lower-priority work: it runs concurrently when safe capacity exists and preempts only when resource contention requires it and interruption policy permits it.

The goal is not to put a scheduler in front of the old Primary Agent. The goal is to remove permanent agents from executive architecture entirely.

Native release-candidate testing exposed several important negative results.

First, natural continuity was becoming dependent on a growing application-owned vocabulary of entity/recency/reference phrases. That approach is deprecated. v0.7 now maintains a minimal durable `InteractionWorkingState` containing only bounded canonical active-event IDs.

Second, asking a fresh stateless model whether it needed unseen persistent memory proved circular: the evidence required to make that decision may itself be in memory. The live path therefore supplies a small, bounded, provenance-bearing JIT Memory packet for every percept **before** model capability selection. This default activation intentionally casts a wide deterministic net while exposing only a small packet.

Third, once the model can select several optional capabilities, the returned list cannot safely become an execution schedule. The model selects a bounded set of application-owned capability indices. Prometheist expands declared dependencies and deterministically chooses the highest-priority currently runnable item, recomputing readiness after each completion. Canonical capability ID is the stable tie-breaker.

Fourth, one capability pass followed inevitably by a response proved too shallow. Routing is now a bounded recurrent loop of **fresh stateless model calls**. Each routing call explicitly chooses either `RESPOND` or `USE_CAPABILITIES`. If it selects capabilities, that model call ends; Prometheist runs the required work, persists structured results, rebuilds bounded context, and invokes a new stateless selector. The loop fails closed if it reaches its deterministic round bound without an explicit `RESPOND`.

Fifth, capabilities no longer generate intermediate prose in the live path. They return structured evidence/state whenever possible. Only after a fresh selector explicitly chooses `RESPOND` is a new final response worker summoned to produce user-facing language.

Persistent-memory investigation is progressive:

- **automatic activation** is broad and shallow on every percept;
- **`deeper_research`** selects 1–4 current canonical memory candidates and broadens association traversal around them;
- **`cross_reference`** selects 2–4 candidates and jointly searches for shared, conflicting, causal, or bridging evidence;
- **`focused_recall`** becomes available after broader research and selects exactly one candidate for the deepest bounded association traversal.

As candidate focus narrows, associative depth increases. Evidence-admission thresholds remain conservative and unchanged: increased attention does not promote retrieved material to truth.

A failed focused search does not force a response. The next fresh selector may respond with what it has, investigate a different candidate, broaden again, cross-reference another set, or use another installed capability.

Transient host-pressure claim denials are also treated as **delay/re-observe conditions**, not reasons to weaken safety policy. The guarded launcher retries a small bounded number of fresh resource observations while preserving the exact configured RAM/CPU thresholds and headroom. Structural denials remain terminal.

> **Working-state invariant:** current cognitive activation belongs to Prometheist itself. It is not reconstructed by an ever-growing regex vocabulary and is not stored in an LLM context window.

> **Memory-access invariant:** basic access to Prometheist's own persistent memory is cognitive substrate, not an optional model-selected capability.

> **Capability invariant:** models select required capabilities; Prometheist owns dependencies, execution order, resource policy, and capability availability.

> **Routing invariant:** every optional-capability round ends in a new stateless decision. Only an explicit `RESPOND` permits final language generation.

> **Model-output invariant:** model-generated natural language is the representation of last resort. Control/state schemas prefer enums, booleans, application-owned IDs, bounded indices, and mechanically verified selections. Free-form model language is reserved for boundaries where language is genuinely the product.

The release candidate also ports deterministic capability discovery into task/worker-neutral terminology, connects real JIT Memory execution, migrates the CLI to guarded child processes, removes the compatibility Primary Agent/specialist path, and adds forced-destruction/recovery tests covering concurrent assignments, checkpoint preemption, abandoned claims, readmission, and duplicate-effect prevention.

## Target architecture

```text
external world / users / devices / software
                  |
                  v
              perception
                  |
          situation / task formation
                  |
                  v
           ATTENTION FABRIC
        priority + safe admission
                  |
                  v
          ACTIVE WORKING STATE
       bounded canonical event refs
                  |
                  v
       DEFAULT MEMORY ACTIVATION
      wide/shallow bounded recall
                  |
                  v
      fresh stateless routing call
       RESPOND | USE_CAPABILITIES
                  |
        USE_CAPABILITIES selected
                  v
      SYSTEM-OWNED EXECUTION PLAN
 dependencies + priority + resources
                  |
                  v
      structured capability results
 deeper_research / cross_reference /
 focused_recall / code / web / ...
                  |
                  v
       recomposed bounded context
                  |
                  +------> fresh routing call
                              |
                       explicit RESPOND
                              v
                  fresh final response
                              |
                              v
                  results + observations
                              |
                              v
                       internal history
                              |
                       retention / indexes
                              |
                              +------> next cycle
```

Basic memory activation is part of the cognitive substrate. Deeper memory operations are optional capabilities because they perform additional investigation over persistent internal evidence. Other installed tools/workflows can be selected alongside them. The model neither determines their execution order nor keeps a hidden context between rounds.

## Human-like interaction continuity

Prometheist should not require users to manage conversation IDs or explicitly switch between stored chats. Current context is maintained as bounded durable active state, and every percept receives bounded memory context before fresh capability selection.

Conversation/session/device identifiers remain useful provenance and ordering metadata, but they are not intended cognitive boundaries. Topics and situations are overlapping associations, not rigid replacement containers.

> **Interaction invariant:** conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries.

The old phrase-specific `requires_persisted_context` mechanism is deprecated from the live path. Lexical/entity/temporal/associative retrieval remains valid *inside memory*; what is rejected is application policy that grows a special-case list every time natural language exposes a new surface form.

## Persistence model

Prometheist distinguishes:

1. **ephemeral raw experience** — high-volume source data that may exist only in bounded buffers;
2. **observational memory** — external observations retained according to explicit deterministic policy;
3. **internal history** — durable system state needed to explain what Prometheist knew, focused on, decided, attempted, committed to, or did;
4. **active working state** — bounded pointers to canonical events currently activated for cognition.

WorkingState and memory activation do not replace or summarize source evidence. An active/retrieved event means it is relevant enough to expose, not that every proposition inside it is true.

> **Persistence invariant:** anything that materially influences Prometheist's attention, reasoning, decisions, commitments, or actions must leave enough durable provenance to explain that behavior later.

## Design principles

1. **System-owned continuity.** Identity, memory, working state, tasks, attention, interaction continuity, policy, and provenance live outside model/worker contexts.
2. **No permanent agent hierarchy.** Agent-like names may describe temporary worker configurations, but workers do not own identity, continuity, memory, or executive authority.
3. **Disposable cognition.** LLM calls and workers may disappear after every bounded step.
4. **Deterministic mechanics.** IDs, ordering, priority derivation, scheduling, retention rules, resource limits, and policy state belong to ordinary software whenever possible.
5. **Attention is distinct from resource admission.** Priority determines what deserves execution; resource policy determines what can safely run concurrently.
6. **Working state is distinct from long-term memory.** Active canonical evidence is bounded and durable.
7. **Default memory activation precedes model routing.** A model is not asked to decide whether unseen memory exists or matters before it has received bounded internal evidence.
8. **Activation is distinct from evidence sufficiency.** High-recall activation must not silently weaken conservative evidence admission or abstention.
9. **Memory research narrows candidates while widening associations.** Progressively focused investigation means fewer selected subjects with greater bounded associative depth, not merely a smaller context window.
10. **Capabilities are requirements, not model-authored schedules.** Models select bounded capability indices; Prometheist expands dependencies and owns deterministic execution order.
11. **Capability use is recurrent.** After every capability round, a fresh stateless selector reassesses whether to respond or gather more evidence/work.
12. **Final response requires explicit readiness.** The final prose worker is summoned only after a fresh selector explicitly chooses `RESPOND`.
13. **Bounded attention.** Prometheist may remember and intend much more than it actively processes at once.
14. **Natural language is last-resort state/control.** Prefer enums, booleans, IDs, bounded indices, and mechanically verified extractive selections; use generated language when language is the product.
15. **Model interpretation is advisory where policy must be deterministic.** Models may select among bounded semantic alternatives; deterministic policy owns scheduling, deletion, permissions, evidence boundaries, capability IDs, dependencies, execution ordering, and validation.
16. **Evidence and provenance survive interpretation changes.** Derived memory and activation are replaceable; retained source evidence remains traceable.
17. **Unknown facts may remain unknown.** Topical similarity is not evidence.
18. **Complexity must earn its place.** Freeze a baseline, add one mechanism, rerun the experiment, keep it only if evidence justifies it.
19. **No vocabulary patchwork.** Natural-language continuity must not depend on an ever-growing list of phrase-specific application rules.
20. **Transient capacity means wait, not weaken safety.** Resource-pressure denials may trigger bounded re-observation; configured headroom and admission thresholds are not reduced to force progress.

## Current implementation versus target architecture

Implemented/verified foundations include PostgreSQL authoritative history, deterministic ordering, the Memory Kernel, provenance-bearing `MemoryPacket`s, conservative evidence recall, high-recall default memory activation, deterministic attention/task state, resource admission, durable epoch-wide assignments, contention preemption, task-neutral capability discovery/execution, durable disposable-worker claims/checkpoints/results, guarded interaction workers, bounded active WorkingState, explicit recurrent routing actions, index-only multi-capability selection, deterministic dependency-aware capability ordering, progressive candidate-index memory research, cross-reference and focused recall, a final-response readiness barrier, bounded transient resource re-observation, and restart/replay tests.

The legacy Primary Agent and memory-specialist ownership architecture has been removed. Historical event types remain supported so existing ledgers stay readable. Perception/salience, deterministic external-data retention, harder memory generalization, richer epistemic working state, broader typed external-capability result composition, and the fully integrated cognitive loop remain roadmap work.

## Roadmap

The currently published forward path remains:

- **v0.7** — durable resource-aware JIT Attention Fabric + minimal active WorkingState + automatic bounded memory activation + recurrent deterministic capability execution;
- **v0.8** — deterministic perception and salience, subject to a post-v0.7 rebaseline against the WorkingState/neuroscience evidence;
- **v0.9** — deterministic retention and memory admission;
- **v0.10** — memory generalization and natural topic-resumption failure discovery;
- **v0.11** — integrated persistent cognitive loop with session-independent interaction continuity;
- **v0.12** — operational hardening and portability;
- **v1.0** — first complete attention-centric Prometheist cognitive architecture.

The roadmap explicitly requires rebaselining after v0.7 before choosing whether richer epistemic WorkingState should precede perception/salience. Do not silently combine those mechanisms.

## Quick start

Requirements: Python 3.12+, `uv`, PostgreSQL, and Ollama for model-backed acceptance paths.

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
uv sync --frozen
psql -d jit_agent -f schema.sql
uv run pytest -v
```

The CLI forms a durable interaction task and launches every stage through the guarded disposable-worker boundary:

```powershell
uv run jit-agent
```

Ollama-backed acceptance requires the configured local model and a disposable PostgreSQL test database. The full native v0.7 gate is `scripts/run_v07_acceptance.ps1`.

## Documentation

Start with [`docs/README.md`](docs/README.md).

Current architecture and active milestone:

- [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)
- [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)
- [`docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md`](docs/milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md)
- [`docs/milestones/v0.7/README.md`](docs/milestones/v0.7/README.md)

Concept/research inputs:

- [`docs/concepts/lessons_from_cognitive_neuroscience.md`](docs/concepts/lessons_from_cognitive_neuroscience.md)
- [`docs/concepts/lessons_from_similar_projects.md`](docs/concepts/lessons_from_similar_projects.md)
- [`docs/concepts/a_future_history_of_mankind.txt`](docs/concepts/a_future_history_of_mankind.txt)

Historical evidence:

- [`docs/history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](docs/history/PRIMARY_AGENT_SPEC_SHEET_V06.md)
- [`docs/milestones/v0.6/README.md`](docs/milestones/v0.6/README.md)
- [`docs/milestones/v0.5/README.md`](docs/milestones/v0.5/README.md)

Prometheist remains a cognitive-architecture research project. The current objective is not to reproduce biological neuroscience literally, but to test whether selective attention, bounded working state, automatic bounded memory activation, progressive associative focus, deterministic system mechanics, recurrent capability use, and disposable model cognition can provide continuous machine identity without persistent model context.
