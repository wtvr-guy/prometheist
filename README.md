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

### v0.7 — release-candidate architecture: durable JIT Attention + WorkingState + staged transient cognition

v0.7 establishes deterministic durable task scheduling, structured priority metadata, service guarantees, interruption policies, dependency gating, resumable PostgreSQL state, live CPU/RAM discovery, conservative observed-capacity snapshots, configured safe headroom, quantitative resource admission/reservations, a default single local-LLM slot, atomic durable scheduling epochs and assignment sets, contention-driven multi-assignment preemption, and a durable claim/lease/checkpoint/result protocol for disposable workers.

The target is a resource-aware **Attention Fabric** that determines which durable tasks deserve execution and which compatible subset can safely execute concurrently on available hardware. Higher-priority work does not automatically kill lower-priority work: it runs concurrently when safe capacity exists and preempts only when resource contention requires it and interruption policy permits it.

The goal is not to put a scheduler in front of the old Primary Agent. The goal is to remove permanent agents from executive architecture entirely.

Native release-candidate testing and subsequent red-team work exposed several important negative results.

First, natural continuity was becoming dependent on a growing application-owned vocabulary of entity/recency/reference phrases. That approach is deprecated. v0.7 now maintains a minimal durable `InteractionWorkingState` containing only bounded canonical active-event IDs.

Second, asking a fresh stateless model whether it needed unseen persistent memory proved circular: the evidence required to make that decision may itself be in memory. The live path therefore supplies a small, bounded, provenance-bearing JIT Memory packet for every percept **before** model cognition. This default activation intentionally casts a wide deterministic net while exposing only a small packet.

Third, once the model can select several optional capabilities, the returned list cannot safely become an execution schedule. The model selects a bounded set of application-owned capability indices. Prometheist expands declared dependencies and deterministically owns the execution plan, ordering, resource admission, and retry behavior.

Fourth, the first fresh-model capability implementation still used a recurrent general router. It preserved statelessness but could make repeated local-model inference the dominant latency/control mechanism. The production subprocess path now uses a **pre-cognitive transient-worker scheme** instead:

- every percept gets the automatic JIT aperture;
- one fresh `PRE_CAPABILITY` cognition worker classifies intent, evidence state, claim scopes, requirements, and—only if needed—bounded capability indices;
- Prometheist validates and persists that closed decision before downstream effects;
- selected work runs in a deterministic first capability tranche;
- if first-tranche work actually ran, one fresh `POST_CAPABILITY` worker receives the recomposed exact evidence and only newly exposed follow-up capabilities;
- at most one bounded follow-up tranche executes under scheme v1;
- one fresh response worker produces user-facing language from the final evidence packet and structured results.

The common path therefore targets two primary model invocations: pre-cognition and response. A capability path generally adds one post-capability cognition call, plus any narrowly scoped transient candidate selector that a specific memory capability needs. This is a mechanism under test, not a constitutional hard-coded model-call count.

Fifth, capabilities do not generate intermediate prose in the live path when structured evidence/state can represent the result. Canonical memory evidence is copied and deduplicated into bounded task-local packets; it is not replaced by summaries merely to fit a model context.

Persistent-memory investigation remains progressive:

- **automatic activation** is broad and shallow on every percept;
- **`deeper_research`** selects bounded current canonical memory candidates and broadens association traversal around them;
- **`cross_reference`** selects bounded candidates and jointly searches for shared, conflicting, causal, or bridging evidence;
- **`focused_recall`** becomes available only after broader research and selects one candidate for the deepest bounded association traversal.

Under the staged scheme, initial capabilities are not recursively reopened after every result. Completed first-tranche work exposes only newly legal follow-up capabilities. For the current registry, broader memory research can expose `focused_recall`.

As candidate focus narrows, associative depth increases. Evidence-admission thresholds remain conservative and unchanged: increased attention does not promote retrieved material to truth.

Transient host-pressure claim denials are treated as **delay/re-observe conditions**, not reasons to weaken safety policy. The guarded launcher retries a small bounded number of fresh resource observations while preserving the exact configured RAM/CPU thresholds and headroom. Structural denials remain terminal.

> **Working-state invariant:** current cognitive activation belongs to Prometheist itself. It is not reconstructed by an ever-growing regex vocabulary and is not stored in an LLM context window.

> **Memory-access invariant:** basic access to Prometheist's own persistent memory is cognitive substrate, not an optional model-selected capability.

> **Capability invariant:** models select bounded semantic requirements/capability indices; Prometheist owns capability identity, dependencies, execution order, resource policy, and capability availability.

> **Transient-cognition invariant:** semantic reassessment is fresh and bounded. Material model-control results are persisted before effects and reused after restart rather than re-rolled.

> **Model-output invariant:** model-generated natural language is the representation of last resort. Control/state schemas prefer enums, booleans, application-owned IDs, bounded indices, and mechanically verified selections. Free-form model language is reserved for boundaries where language is genuinely the product.

The production CLI continues to launch each durable interaction stage through the guarded disposable-worker boundary. The older recurrent in-process interaction helper remains temporarily for deterministic regression compatibility; it is not the normative production cognitive path on the transient-worker feature branch.

The current native acceptance model remains **Qwen3:4b**. A possible quantized 12–14B model is deliberately deferred as a separate experiment so the worker-mechanism change can be measured without changing model capacity at the same time.

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
    fresh PRE-CAPABILITY COGNITION
 intent + evidence + requirements
                  |
        sufficient | work required
             |            |
             |            v
             |    SYSTEM-OWNED EXECUTION
             |  dependencies + priority +
             |    resources + provenance
             |            |
             |       first capability tranche
             |            |
             |     exact bounded evidence
             |            |
             |      fresh POST-CAPABILITY
             |          cognition if needed
             |            |
             |    optional newly-exposed
             |       follow-up tranche
             |            |
             +------------+
                  |
                  v
          fresh final response/action
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

Basic memory activation is part of the cognitive substrate. Deeper memory operations are optional capabilities because they perform additional investigation over persistent internal evidence. Other installed tools/workflows can be selected alongside them as they are added. The model neither determines their execution order nor carries hidden context from one stage to another.

## Human-like interaction continuity

Prometheist should not require users to manage conversation IDs or explicitly switch between stored chats. Current context is maintained as bounded durable active state, and every percept receives bounded memory context before fresh semantic assessment.

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
4. **Transient compute, durable material control.** If a model decision can authorize downstream effects, validate and persist it before those effects; retries reuse the committed decision.
5. **Deterministic mechanics.** IDs, ordering, priority derivation, scheduling, retention rules, resource limits, and policy state belong to ordinary software whenever possible.
6. **Attention is distinct from resource admission.** Priority determines what deserves execution; resource policy determines what can safely run concurrently.
7. **Working state is distinct from long-term memory.** Active canonical evidence is bounded and durable.
8. **Default memory activation precedes model cognition.** A model is not asked to decide whether unseen memory exists or matters before it has received bounded internal evidence.
9. **Activation is distinct from evidence sufficiency.** High-recall activation must not silently weaken conservative evidence admission or abstention.
10. **Memory research narrows candidates while widening associations.** Progressively focused investigation means fewer selected subjects with greater bounded associative depth, not merely a smaller context window.
11. **Capabilities are requirements, not model-authored schedules.** Models select bounded capability indices; Prometheist expands dependencies and owns deterministic execution order.
12. **Capability reasoning is staged.** Fresh semantic reassessment occurs only at application-defined stage boundaries after material new evidence; the model does not own an open-ended recurrent control loop.
13. **Final response is a separate fresh worker.** Pre-cognitive control and user-facing language are different disposable roles.
14. **Bounded attention.** Prometheist may remember and intend much more than it actively processes at once.
15. **Natural language is last-resort state/control.** Prefer enums, booleans, IDs, bounded indices, and mechanically verified extractive selections; use generated language when language is the product.
16. **Model interpretation is advisory where policy must be deterministic.** Models may select among bounded semantic alternatives; deterministic policy owns scheduling, deletion, permissions, evidence boundaries, capability IDs, dependencies, execution ordering, and validation.
17. **Evidence and provenance survive interpretation changes.** Derived memory and activation are replaceable; retained source evidence remains traceable.
18. **Unknown facts may remain unknown.** Topical similarity is not evidence.
19. **Complexity must earn its place.** Freeze a baseline, add one mechanism, rerun the experiment, keep it only if evidence justifies it.
20. **No vocabulary patchwork.** Natural-language continuity must not depend on an ever-growing list of phrase-specific application rules.
21. **Transient capacity means wait, not weaken safety.** Resource-pressure denials may trigger bounded re-observation; configured headroom and admission thresholds are not reduced to force progress.

## Current implementation versus target architecture

Implemented/verified foundations include PostgreSQL authoritative history, deterministic ordering, the Memory Kernel, provenance-bearing `MemoryPacket`s, conservative evidence recall, high-recall default memory activation, deterministic attention/task state, resource admission, durable epoch-wide assignments, contention preemption, task-neutral capability discovery/execution, durable disposable-worker claims/checkpoints/results, guarded interaction workers, bounded active WorkingState, closed pre-cognitive assessments, index-only multi-capability selection, deterministic dependency-aware capability ordering, progressive candidate-index memory research, cross-reference and focused recall, exact bounded evidence composition, restart-stable cognitive control records, response-policy/evidence-authority gates, bounded transient resource re-observation, and restart/replay tests.

The legacy Primary Agent and memory-specialist ownership architecture has been removed. Historical event types remain supported so existing ledgers stay readable. Perception/salience, deterministic external-data retention, harder memory generalization, richer epistemic working state, broader typed external-capability result composition, and the fully integrated cognitive loop remain roadmap work.

## Roadmap

The currently published forward path remains:

- **v0.7** — durable resource-aware JIT Attention Fabric + minimal active WorkingState + automatic bounded memory activation + staged pre-cognitive transient workers;
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

- [`CONSTITUTION.md`](CONSTITUTION.md)
- [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)
- [`docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md)
- [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)
- [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)
- [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)
- [`docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/milestones/v0.7/PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md`](docs/milestones/v0.7/PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md)
- [`docs/milestones/v0.7/README.md`](docs/milestones/v0.7/README.md)

Concept/research inputs:

- [`docs/concepts/lessons_from_cognitive_neuroscience.md`](docs/concepts/lessons_from_cognitive_neuroscience.md)
- [`docs/concepts/lessons_from_similar_projects.md`](docs/concepts/lessons_from_similar_projects.md)
- [`docs/concepts/a_future_history_of_mankind.txt`](docs/concepts/a_future_history_of_mankind.txt)

Historical evidence:

- [`docs/history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](docs/history/PRIMARY_AGENT_SPEC_SHEET_V06.md)
- [`docs/milestones/v0.6/README.md`](docs/milestones/v0.6/README.md)
- [`docs/milestones/v0.5/README.md`](docs/milestones/v0.5/README.md)

Prometheist remains a cognitive-architecture research project. The current objective is not to reproduce biological neuroscience literally, but to test whether selective attention, bounded working state, automatic bounded memory activation, progressive associative focus, deterministic system mechanics, staged transient capability reasoning, and disposable model cognition can provide continuous machine identity without persistent model context.
