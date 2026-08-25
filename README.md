# Prometheist

**Persistent identity and attention for stateless intelligence.**

Prometheist is an experimental, local-first persistent cognitive architecture built around a strict constraint: **every LLM invocation is stateless**.

Models and worker processes are disposable compute. They are never the durable owners of memory, identity, attention, interaction continuity, policy, or authoritative system state.

> **Core thesis:** continuity belongs to Prometheist itself, not to an LLM context window, chat session, agent, or worker process.

Prometheist began as a stateless multi-agent prototype. v0.6 used a Primary Agent plus specialists to prove that fresh model invocations could participate in one continuous system through shared JIT Memory without inherited transcripts. That hierarchy is now historical. Beginning with v0.7, **permanent agents are not first-class architectural primitives**. The system is being rebuilt around durable attention, tasks, capabilities, perception, retention, and disposable workers.

## Current status

### v0.5 — accepted deterministic Memory Kernel baseline

Memory Kernel v0.5 established bounded deterministic associative recall with provenance, support-aware evidence admission, explicit abstention, and specificity-aware PostgreSQL candidate routing. Controlled synthetic scale evaluation reached perfect observed correctness through 50,000 events per persona with a fixed 500-event PostgreSQL candidate window. Those results are a baseline, not a claim of general semantic-memory completeness.

### v0.6 — accepted historical stateless-worker/JIT-Memory baseline

v0.6 proved that separate fresh LLM-backed components can obtain persistent internal context through the same `MemoryNeed` / `MemoryPacket` boundary without inheriting hidden transcripts.

The Primary Agent/specialist structure used to prove that result is **superseded architecture**. Its implementation remains temporarily in the repository as compatibility and regression code while v0.7 replaces its executive role. Historical documentation is kept under `docs/history/` and the v0.6 milestone record rather than presented as current architecture.

### v0.7 — in development: durable JIT Attention Fabric

The first v0.7 increments establish deterministic durable task scheduling, structured priority metadata, service guarantees, interruption policies, dependency gating, resumable PostgreSQL state, resource requirements/admission, and forced-process restart recovery.

The target is a resource-aware **Attention Fabric** that determines which durable tasks deserve execution and which compatible subset can safely execute concurrently on available hardware. Higher-priority work does not automatically kill lower-priority work: it runs concurrently when safe capacity exists and preempts only when resource contention requires it and interruption policy permits it.

The goal is not to put a scheduler in front of the old Primary Agent. The goal is to remove permanent agents from executive architecture entirely.

## Target architecture

```text
external world / users / devices / software
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
      priority + safe resource admission
                  |
       +----------+----------+
       |          |          |
   assignment  assignment  assignment ...
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

JIT Memory is one capability among many. It supplies bounded historical context only when current work needs it.

## Human-like interaction continuity

Prometheist should not require users to manage conversation IDs or explicitly switch between stored chats. A user should be able to say, for example, "remember that thing we were talking about yesterday, about the attention layers?" and have the relevant context reconstructed from semantic, temporal, causal, entity, task, and situation cues.

Conversation/session/device identifiers remain useful provenance and ordering metadata, but they are not intended cognitive boundaries. Topics and situations are overlapping associations, not rigid replacement containers.

> **Interaction invariant:** conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Context is reconstructed just in time from current intent and available retrieval cues.

## Persistence model

Prometheist no longer assumes that every raw external datum should be stored forever.

It distinguishes:

1. **ephemeral raw experience** — high-volume source data that may exist only in bounded buffers;
2. **observational memory** — external observations retained according to explicit deterministic policy;
3. **internal history** — durable system state needed to explain what Prometheist knew, focused on, decided, attempted, committed to, or did.

> **Persistence invariant:** anything that materially influences Prometheist's attention, reasoning, decisions, commitments, or actions must leave enough durable provenance to explain that behavior later.

## Design principles

1. **System-owned continuity.** Identity, memory, tasks, attention, interaction continuity, policy, and provenance live outside model/worker contexts.
2. **No permanent agent hierarchy.** Agent-like names may describe temporary worker configurations, but workers do not own identity, continuity, memory, or executive authority.
3. **Disposable cognition.** LLM calls and workers may disappear after every bounded step.
4. **Deterministic mechanics.** IDs, ordering, priority derivation, scheduling, retention rules, resource limits, and policy state belong to ordinary software whenever possible.
5. **Attention is distinct from resource admission.** Priority determines what deserves execution; resource policy determines what can safely run concurrently.
6. **Demand-driven JIT Memory.** Historical context is retrieved only when current work requires it.
7. **Bounded attention.** Prometheist may remember and intend much more than it actively processes at once.
8. **Model interpretation is advisory where policy must be deterministic.** Models may classify or propose; deterministic policy owns scheduling, deletion, permissions, and bounded reflex authority.
9. **Evidence and provenance survive interpretation changes.** Derived memory is replaceable; retained source evidence remains traceable.
10. **Unknown facts may remain unknown.** Topical similarity is not evidence.
11. **Complexity must earn its place.** Freeze a baseline, add one mechanism, rerun the experiment, keep it only if evidence justifies it.

## Current implementation versus target architecture

The repository is in transition. It currently contains both accepted historical mechanisms and new v0.7 mechanisms.

Implemented/verified foundations include PostgreSQL authoritative history, deterministic ordering, the Memory Kernel, provenance-bearing `MemoryPacket`s, shared JIT Memory contracts, v0.6 compatibility paths, deterministic attention/task state, resource-admission work, and restart/replay tests.

`src/jit_agent/primary_agent.py`, Primary-Agent tests, and the current CLI are **legacy v0.6 compatibility surfaces**, not declarations of the target architecture. They remain until their useful behavioral baselines are reproduced by the attention-centric execution path. New architecture work should not extend the Primary Agent as a permanent coordinator.

The multi-lane/resource-aware Attention Fabric, perception/salience system, deterministic external-data retention layer, session-independent interaction mechanics, and fully integrated cognitive loop remain roadmap work unless a milestone document states otherwise.

## Roadmap

The forward research path is:

- **v0.7** — durable resource-aware JIT Attention Fabric;
- **v0.8** — deterministic perception and salience;
- **v0.9** — deterministic retention and memory admission;
- **v0.10** — memory generalization and natural topic-resumption failure discovery;
- **v0.11** — integrated persistent cognitive loop with session-independent interaction continuity;
- **v0.12** — operational hardening and portability;
- **v1.0** — first complete attention-centric Prometheist cognitive architecture.

## Quick start

Requirements: Python 3.12+, `uv`, PostgreSQL, and Ollama for model-backed acceptance paths.

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
uv sync
psql -d jit_agent -f schema.sql
uv run pytest -v
```

The current CLI still exercises the legacy v0.6 interaction path while its attention-centric replacement is developed:

```powershell
uv run jit-agent
```

Do not interpret that compatibility entry point as the target architecture.

## Documentation

Start with [`docs/README.md`](docs/README.md).

Current architecture:

- [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)
- [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)
- [`docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/milestones/v0.7/README.md`](docs/milestones/v0.7/README.md)
- [`docs/milestones/v0.7/JIT_ATTENTION_DESIGN.md`](docs/milestones/v0.7/JIT_ATTENTION_DESIGN.md)

Historical evidence:

- [`docs/history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](docs/history/PRIMARY_AGENT_SPEC_SHEET_V06.md)
- [`docs/milestones/v0.6/README.md`](docs/milestones/v0.6/README.md)
- [`docs/milestones/v0.5/README.md`](docs/milestones/v0.5/README.md)

Prometheist remains a cognitive-architecture research project. The current objective is not to reproduce biological neuroscience literally, but to test whether selective attention, demand-driven memory, deterministic system mechanics, and disposable model cognition can provide continuous machine identity without persistent model context.
