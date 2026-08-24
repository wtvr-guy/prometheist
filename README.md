# Prometheist

**Persistent identity for stateless intelligence.**

Prometheist is an experimental, local-first persistent AI architecture built around a strict constraint: **every LLM invocation is stateless**.

Models and worker processes are never treated as durable memory, identity, attention, or authoritative system state.

> **Core thesis:** continuity belongs to the system, not to an LLM context window or worker process.

The project began as a stateless multi-agent prototype centered on a Primary Agent plus shared JIT Memory. v0.6 proved that fresh model invocations can participate in one continuous system without inherited transcripts. Beginning with v0.7, the project is deliberately pivoting away from a privileged Primary Agent toward an **attention-centric persistent cognitive architecture**.

## Current status

### v0.5 — accepted deterministic Memory Kernel baseline

Memory Kernel v0.5 established bounded deterministic associative recall with provenance, support-aware evidence admission, explicit abstention, and specificity-aware PostgreSQL candidate routing.

The frozen synthetic scale evaluation reached perfect observed correctness through 50,000 events per persona while keeping the PostgreSQL candidate window fixed at 500 events:

| Corpus | Questions | Evidence recall | MRR | Unknown abstention | PostgreSQL p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jordan Vale, 50k | 117/117 | 1.000 | 1.000 | 1.000 | 160.0 ms |
| Avery Chen, 50k | 105/105 | 1.000 | 1.000 | 1.000 | 163.3 ms |
| Morgan Reyes, 50k | 106/106 | 1.000 | 1.000 | 1.000 | 151.7 ms |

These are controlled benchmark results, not a claim of general semantic-memory completeness.

### v0.6 — accepted stateless-worker/JIT-Memory integration baseline

v0.6 proved that separate fresh LLM-backed components can obtain persistent internal context through the same `MemoryNeed` / `MemoryPacket` boundary without inheriting hidden transcripts.

The Primary Agent and specialist arrangement used in that experiment is retained as historical evidence, but it is no longer the intended permanent executive architecture.

### v0.7 — in development: durable JIT Attention Fabric

The first v0.7 increment has already introduced a deterministic durable single-focus scheduler with:

- structured priority metadata;
- deterministic P0-P5 priority derivation;
- service guarantees;
- `PREEMPTIBLE`, `CHECKPOINT_ONLY`, and `ATOMIC` interruption semantics;
- dependency gating;
- deterministic task/transition IDs;
- resumable PostgreSQL task state;
- forced-process-destruction restart recovery.

The current v0.7 direction generalizes that scheduler into a **multi-lane Attention Fabric** that deterministically allocates durable tasks to bounded execution resources. The goal is to remove the Primary Agent as an architectural requirement rather than wrapping it in a scheduler facade.

See:

- [Architectural pivot — 2026-08-24](docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [Current cognitive architecture](docs/architecture/COGNITIVE_ARCHITECTURE.md)
- [v0.7 implementation plan](docs/milestones/v0.7/README.md)
- [Roadmap to v1.0](docs/ROADMAP.md)

## Target architecture

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

The architecture distinguishes several kinds of attention:

- **perceptual attention** — what external changes warrant orientation;
- **executive attention** — what durable work deserves resources;
- **resource/lane attention** — which compatible task receives a specific execution slot;
- **cognitive attention** — what bounded task-specific information enters a disposable model call.

JIT Memory is one capability among many. It is demand-driven rather than universally injected.

## Persistence model

The project no longer assumes that every raw external datum should be stored forever.

Prometheist distinguishes:

1. **ephemeral raw experience** — high-volume source data that may exist only in bounded buffers;
2. **observational memory** — external observations retained according to explicit deterministic policy;
3. **internal history** — durable system state needed to explain what Prometheist knew, focused on, decided, attempted, or did.

The stronger invariant is:

> **Anything that materially influences Prometheist's attention, reasoning, decisions, commitments, or actions must leave enough durable provenance to explain that behavior later.**

## Design principles

1. **System-owned continuity.** Identity, memory, task state, attention, policy, and provenance live outside model/worker contexts.
2. **Disposable cognition.** LLM calls and worker processes may disappear after every bounded step.
3. **Deterministic mechanics.** IDs, ordering, scheduling, retention rules, resource limits, and policy state belong to ordinary software whenever possible.
4. **Demand-driven JIT Memory.** Historical context is retrieved only when a task requires it.
5. **Bounded attention.** Prometheist may remember and intend much more than it actively thinks about at once.
6. **Explicit resource capacity.** Concurrency is bounded by typed execution resources, not blindly by logical CPU thread count.
7. **Model interpretation is advisory where policy must be deterministic.** Models may classify or propose; deterministic policy owns scheduling, deletion, permissions, and reflex authority.
8. **Evidence and provenance survive interpretation changes.** Derived memory is replaceable; retained source evidence remains traceable.
9. **Unknown facts may remain unknown.** Topical similarity is not evidence.
10. **Complexity must earn its place.** Freeze a baseline, add one mechanism, rerun the experiment, keep it only if evidence justifies it.

## Current implementation

The repository currently includes:

- PostgreSQL authoritative event history and deterministic ordering;
- the frozen deterministic Memory Kernel baseline;
- lexical/entity/association routing and provenance-bearing `MemoryPacket`s;
- shared JIT Memory contracts;
- v0.6 Primary/specialist compatibility paths;
- deterministic v0.7 attention scheduler code and durable attention-task state;
- restart/replay tests, including forced Python-process destruction;
- local Ollama-backed stateless-model acceptance paths;
- PostgreSQL-backed GitHub Actions regression tests.

The target multi-lane Attention Fabric, perception/salience system, deterministic external-data retention layer, and integrated cognitive loop are roadmap work, not yet implemented.

## Versioning

Prometheist uses architectural milestone labels such as v0.5, v0.6, and v0.7. Those labels are not currently Python package-release versions.

The `version` field in `pyproject.toml` and `uv.lock` is package metadata for the `jit-agent` Python package. It should not be changed merely to mirror research milestone names.

## Quick start

Requirements:

- Python 3.12+
- `uv`
- PostgreSQL
- Ollama for LLM-backed acceptance paths

Clone and install:

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
uv sync
```

Create a PostgreSQL database and apply the schema:

```powershell
psql -d jit_agent -f schema.sql
```

Example `.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/jit_agent
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
```

Run the current compatibility CLI:

```powershell
uv run jit-agent
```

Single-shot mode remains useful for demonstrating process-level statelessness:

```powershell
uv run jit-agent --once "What did I tell you about Project Falcon?" --conversation-id <uuid>
```

The current CLI still exercises the v0.6 Primary-Agent path while the v0.7 attention-centric replacement is developed.

## Testing

Run the complete suite with:

```powershell
uv run pytest -v
```

Tests use a dedicated PostgreSQL database whose name must contain `test` or `benchmark`; the normal development history is not a valid destructive pytest target.

Some model-backed acceptance paths require Ollama. Deterministic Memory Kernel and Attention tests do not.

## Benchmarks

The repository includes fixed synthetic personas, adversarial robustness cases, deterministic scale-corpus generation, and PostgreSQL benchmark paths.

Useful commands include:

```powershell
uv run python -m jit_agent.synthetic_benchmark
uv run python -m jit_agent.associative_benchmark
uv run python -m jit_agent.derived_associative_benchmark
uv run python -m jit_agent.scale_benchmark --events 1000 10000 50000
uv run python -m jit_agent.postgres_scale_benchmark --events 1000 10000 50000
```

See [the v0.5 scale benchmark guide](docs/milestones/v0.5/SCALE_BENCHMARK.md).

## Repository layout

```text
prometheist/
├── README.md
├── pyproject.toml
├── uv.lock
├── schema.sql
├── .github/workflows/
├── benchmarks/
├── docs/
├── scripts/
├── src/jit_agent/
└── tests/
```

## Documentation

Start with the [documentation index](docs/README.md).

Key documents:

- [Current cognitive architecture](docs/architecture/COGNITIVE_ARCHITECTURE.md)
- [Architectural pivot — 2026-08-24](docs/architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [v0.7 Attention Fabric milestone](docs/milestones/v0.7/README.md)
- [JIT Attention design](docs/milestones/v0.7/JIT_ATTENTION_DESIGN.md)
- [Roadmap to v1.0](docs/ROADMAP.md)
- [Memory Kernel deterministic baseline](docs/architecture/MEMORY_KERNEL.md)
- [Associative-memory design](docs/architecture/ASSOCIATIVE_MEMORY.md)
- [v0.5 final status](docs/milestones/v0.5/README.md)
- [v0.6 final status](docs/milestones/v0.6/README.md)
- [Historical Primary Agent specification](docs/architecture/PRIMARY_AGENT_SPEC_SHEET.md)

## Research direction

The roadmap now proceeds through:

- v0.7 durable multi-lane JIT Attention;
- v0.8 deterministic perception and salience;
- v0.9 deterministic retention and memory admission;
- v0.10 harder memory-generalization failure discovery;
- v0.11 integrated persistent cognitive loop;
- v0.12 operational hardening and portability;
- v1.0 first complete attention-centric Prometheist architecture.

The long-term research question remains whether a local-first system can combine human-like selective recall/attention dynamics with machine-level historical fidelity while keeping durable identity independent of any one model.

Prometheist is a cognitive-architecture research platform. It is not a claim of consciousness transfer or a complete model of a person.
