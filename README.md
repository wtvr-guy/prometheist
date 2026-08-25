# Prometheist

**Persistent identity for stateless intelligence.**

Prometheist is an experimental, local-first AI-agent architecture built around a strict constraint: **every LLM invocation is stateless**.

The model is never treated as durable memory, identity, or authoritative system state. Prometheist records experience externally, preserves original events with provenance, derives replaceable memory structures from those events, and reconstructs only the context required for the current inference.

> **Core thesis:** persistent state belongs to the system, not to an LLM context window.

The repository currently contains a working stateless multi-agent prototype and a deterministic Memory Kernel research track through **v0.6**.

## Current status

Memory Kernel v0.5 is the accepted robustness-and-scale baseline. It extends deterministic associative recall with lifecycle-aware routing, support-aware evidence admission, and a bounded specificity-aware PostgreSQL candidate router.

The frozen scale evaluation reached perfect observed correctness through 50,000 events per synthetic persona while keeping the PostgreSQL candidate window fixed at 500 events:

| Corpus | Questions | Evidence recall | MRR | Unknown abstention | PostgreSQL p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jordan Vale, 50k | 117/117 | 1.000 | 1.000 | 1.000 | 160.0 ms |
| Avery Chen, 50k | 105/105 | 1.000 | 1.000 | 1.000 | 163.3 ms |
| Morgan Reyes, 50k | 106/106 | 1.000 | 1.000 | 1.000 | 151.7 ms |

These are controlled synthetic benchmark results, not a claim of general semantic-memory completeness. They show that the measured v0.5 failures did not justify embeddings or another retrieval subsystem.

v0.6 is the accepted shared-JIT-memory and stateless multi-agent integration milestone. The live Primary Agent and a stateless `memory_specialist` now obtain persistent internal context through the same `MemoryNeed` / `MemoryPacket` boundary backed by the frozen v0.5 kernel. Agent delegations, results, memory requests, memory packets, failures, source-event provenance, and correlation metadata are persisted outside all LLM contexts.

The later capability-registry work keeps deterministic retrieval first and adds a bounded pgvector recovery route for lexically weak cues. That route exposes canonical source events only as `SEMANTIC_CANDIDATE` items; vector similarity alone never admits a fact or changes a packet to `supported=true`.

The v0.6 acceptance path was verified locally with PostgreSQL and Ollama: a fact persisted in one process was later recovered by a fresh Primary Agent and independently by a fresh specialist without an inherited transcript, while the complete pytest suite and frozen v0.5 regression baseline remained green.

See the [v0.5 final status](docs/milestones/v0.5/README.md), [v0.6 final status](docs/milestones/v0.6/README.md), [v0.5 experiment records](docs/milestones/v0.5/experiments/), and [closure audit](docs/audits/V05_CLOSURE_AUDIT_2026-08-21.md).

## Versioning

Prometheist uses architectural milestone labels such as **v0.5** and **v0.6** to identify accepted research/integration checkpoints. Those labels are not currently Python package release versions.

The `version` field in `pyproject.toml` and the corresponding value in `uv.lock` are internal packaging metadata for the `jit-agent` Python package. They should not be used to infer which Prometheist architectural milestone is accepted. Until a formal distribution/release process is introduced, the milestone documents and this README are authoritative for project status.

Before the first externally distributed package release, Prometheist should adopt an explicit package-release policy (for example SemVer) and either reconcile or deliberately continue separating package versions from architectural milestone labels. Development work must not casually bump package metadata merely to mirror a branch name or research experiment.

## Architecture

```text
Authoritative event history
          |
          v
Derived memory structures
          |
          v
Shared JIT Memory boundary
          |
          v
Bounded MemoryPacket
          |
          v
Fresh stateless Primary / specialist LLM call
          |
          v
Response / decision / delegation / result
          |
          v
Persist resulting events
          |
          v
Discard temporary LLM context
```

The LLM is a **cognitive engine**, not the storage location of the agent's identity.

Prometheist currently combines:

- an append-only PostgreSQL event ledger at the application layer;
- explicit global and per-conversation ordering;
- deterministic cue scoring;
- rebuildable lexical and associative projections;
- bounded spreading activation with provenance;
- support-aware evidence admission and open-world abstention;
- bounded PostgreSQL candidate routing;
- a shared `MemoryNeed` / `MemoryPacket` JIT Memory interface;
- canonical-first user-query recall with bounded supplemental semantic cues after canonical abstention;
- deterministic-first, bounded pgvector recovery whose `SEMANTIC_CANDIDATE` events never self-admit as evidence;
- persisted memory requests, memory packets, agent delegations, specialist results, and correlation metadata;
- a stateless Primary Agent plus a stateless LLM-backed memory specialist;
- structured, schema-validated LLM control outputs;
- local inference through Ollama for LLM-backed acceptance paths.

The older Retrieval Service remains in the repository for regression compatibility, but the live Primary Agent uses the shared JIT Memory boundary.

## Design principles

1. **Persistent experience without persistent LLM context.** Historical growth should primarily become a storage-and-retrieval problem.
2. **Persist first, interpret later.** Ordinary persistence is not gated by an LLM deciding what deserves to be remembered.
3. **Evidence is authoritative; interpretations are replaceable.** Summaries, projections, associations, embeddings, and user models are derived state.
4. **Deterministic code owns deterministic information.** IDs, timestamps, sequence numbers, limits, and schema versions are application state.
5. **Retrieval mechanisms sit behind stable boundaries.** Consumers describe the information need; the memory subsystem decides how to satisfy it.
6. **Preserve provenance.** Retrieved evidence should remain traceable to canonical source events.
7. **Complexity must earn its place.** New retrieval technologies are added only when measured failures justify them.

## Quick start

Requirements:

- Python 3.12+
- `uv`
- PostgreSQL with pgvector
- Ollama for the live CLI and LLM-backed acceptance paths

Clone and install:

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
uv sync
```

Create a PostgreSQL database and apply the schema:

```powershell
psql -d jit_agent -f schema.sql
psql -d jit_agent -f schema_pgvector.sql
```

Example `.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/jit_agent
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:4b-q4_K_M
```

Pull both configured models before running live semantic/acceptance paths:

```powershell
ollama pull qwen3:4b
ollama pull qwen3-embedding:4b-q4_K_M
```

`.env` is ignored by Git and should not be committed.

Run the interactive agent:

```powershell
uv run jit-agent
```

Single-shot mode is useful for demonstrating process-level statelessness:

```powershell
uv run jit-agent --once "What did I tell you about Project Falcon?" --conversation-id <uuid>
```

## Testing

Run the complete suite with:

```powershell
uv run pytest -v
```

Tests use a dedicated PostgreSQL database whose name must contain `test` or `benchmark`; the normal long-lived development history is not a valid destructive pytest target. Some LLM-backed acceptance paths require Ollama; deterministic Memory Kernel benchmarks do not.

Database-backed pytest runs must be serialized when they share a
`TEST_DATABASE_URL`: the isolation fixture truncates the disposable database at
the start of each test, so concurrent runs require separate test databases.

Run the v0.6 multi-turn continuity acceptance gate, including its Ollama/model
preflight and visible transcript, with:

```powershell
.\scripts\run_v06_continuity.ps1
```

This runner fails when the configured chat or embedding model is unavailable;
it never reports an unavailable local-model test as a pass-by-skip. The test
launches a fresh CLI process for every turn and verifies the source-event IDs in
persisted memory packets as well as the answers. Pytest intentionally replaces
the normal `DATABASE_URL` with `TEST_DATABASE_URL` (defaulting to the disposable
`jit_agent_test` database); set that variable explicitly when your test database
uses a different safe name or credential.

GitHub Actions runs the deterministic suite explicitly with `-m "not ollama"`
against a disposable pgvector/PostgreSQL service and separately verifies that
all `ollama` acceptance tests remain collectable. A Windows lane exercises the
CLI UTF-8 subprocess contract without database fixtures. Real-Ollama acceptance
remains a required local gate because hosted CI does not provide the project's
models; ordinary pytest runs may skip it when Ollama is unavailable, while the
script above turns missing prerequisites into a failure.

## Benchmarks

The repository includes fixed synthetic personas, adversarial robustness cases, deterministic scale-corpus generation, and both full-history and indexed PostgreSQL benchmark paths.

The v0.5 scale workflow is documented in:

- [Scale benchmark guide](docs/milestones/v0.5/SCALE_BENCHMARK.md)
- [v0.5 experiment records](docs/milestones/v0.5/experiments/)
- [`benchmarks/`](benchmarks/) for checked-in benchmark fixtures

Useful commands include:

```powershell
uv run python -m jit_agent.synthetic_benchmark
uv run python -m jit_agent.associative_benchmark
uv run python -m jit_agent.derived_associative_benchmark
uv run python -m jit_agent.scale_benchmark --events 1000 10000 50000
uv run python -m jit_agent.postgres_scale_benchmark --events 1000 10000 50000
```

The PostgreSQL scale runner is destructive to its selected database and refuses to run unless the database name contains `test` or `benchmark`.

## Repository layout

```text
prometheist/
├── README.md
├── pyproject.toml
├── uv.lock
├── schema.sql
├── .github/workflows/    # automated PostgreSQL-backed regression lane
├── benchmarks/          # checked-in evaluation fixtures
├── docs/                # architecture, roadmap, milestones, audits, experiment records
├── scripts/             # diagnostics, rebuilds, benchmark entry points
├── src/jit_agent/       # application and Memory Kernel implementation
└── tests/               # regression and acceptance suite
```

The project root is intentionally kept limited to entry-point documentation, package metadata, database schema, and primary source/test directories. Historical research records belong under `docs/` rather than accumulating beside runtime files.

## Documentation

Start with the [documentation index](docs/README.md).

Key documents:

- [Primary Agent specification](docs/architecture/PRIMARY_AGENT_SPEC_SHEET.md)
- [Memory Kernel deterministic baseline](docs/architecture/MEMORY_KERNEL.md)
- [Associative-memory design](docs/architecture/ASSOCIATIVE_MEMORY.md)
- [Memory Kernel v0.4](docs/milestones/v0.4/MEMORY_KERNEL_V0.4.md)
- [Memory Kernel v0.5 final status](docs/milestones/v0.5/README.md)
- [Prometheist v0.6 final status](docs/milestones/v0.6/README.md)
- [Roadmap to v1.0](docs/ROADMAP.md)

## Research direction

The next milestone is **v0.7: Durable Execution and Restartable Orchestration**. Its purpose is to test whether unfinished work, intentions, task state, and multi-agent handoffs can survive complete process destruction and resume correctly using fresh LLM calls and durable system state.

The longer-term goal is to investigate whether stateless LLM workers plus persistent, auditable JIT memory can support human-inspired recall dynamics with machine-level factual fidelity and eventually a highly personalized agent whose durable identity is independent of any one foundation model.

See the [roadmap](docs/ROADMAP.md) for the proposed path through durable execution, harder memory generalization, operational hardening, and the first defensible v1.0 architecture.

The present repository is a memory architecture and research platform. It is not a claim of consciousness transfer or a complete model of a person.
