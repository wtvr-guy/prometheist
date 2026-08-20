# Prometheist

**Persistent identity for stateless intelligence.**

Prometheist is an experimental AI-agent architecture built around a deliberately unusual constraint: **every LLM invocation is stateless**.

The model is never treated as durable memory, identity, or authoritative system state. Prometheist records experience externally, preserves original events with provenance, derives replaceable memory structures from those events, and reconstructs only the context needed for the current inference.

> **Core thesis:** persistent state belongs to the system, not to an LLM context window.

The repository currently contains two related layers:

1. the original working **stateless-agent MVP**, which proves persistence and just-in-time recall across process and conversation boundaries; and
2. **Memory Kernel v0.2**, an additive deterministic memory-research layer that treats source events as authoritative evidence and all derived memory representations as disposable, versioned projections.

The longer-term research goal is to investigate whether this architecture can support human-inspired just-in-time recall with machine-level factual fidelity, and eventually a highly personalized AI whose persistent identity is independent of any one foundation model. That direction is aspirational; the present repository is a memory architecture and research platform, not a consciousness upload or complete model of a person.

---

## Why Prometheist Exists

Most conversational AI systems obtain continuity by repeatedly carrying forward a growing transcript, summary, hidden conversation state, or some combination of them. Prometheist explores a different architecture.

A model invocation should be disposable. The system should be able to stop the Python process, replace the LLM, begin a new conversation, or reconstruct the agent elsewhere without losing the history that gives it continuity.

```text
Authoritative event history
          |
          v
Derived memory structures
          |
          v
Just-in-time retrieval
          |
          v
Bounded working memory
          |
          v
Fresh stateless LLM call
          |
          v
Response / decision / action
          |
          v
Persist resulting events
          |
          v
Discard temporary LLM context
```

The LLM is therefore a **cognitive engine**, not the storage location of the agent's identity.

---

## Current Architecture

### Original MVP path

The original proof-of-concept remains intact:

```text
Current user input
        |
        v
Persist USER_PROMPT
        |
        v
Fresh Primary Agent classification
        |
        +------------------------------+
        |                              |
        | RESPOND_DIRECTLY             | RETRIEVE_CONTEXT
        |                              |
        |                              v
        |                    Persist RETRIEVAL_REQUEST
        |                              |
        |                              v
        |                    Retrieval Service
        |                              |
        |                              v
        |                    Persist RETRIEVAL_RESULT
        |                              |
        +---------------+--------------+
                        |
                        v
                 Fresh LLM response
                        |
                        v
              Persist AGENT_RESPONSE
                        |
                        v
            Discard temporary context
```

The MVP Retrieval Service uses PostgreSQL metadata filtering and full-text search. Conversation IDs organize history but are not memory walls, and global sequence numbers provide authoritative ordering across conversations.

### Memory Kernel v0.2

Memory Kernel v0.2 sits **beside** the MVP Retrieval Service rather than replacing it.

Its central invariant is:

> **What happened is authoritative; how Prometheist currently remembers it is disposable.**

```text
Immutable events
      |
      +-------------------+
      |                   |
      v                   v
Integrity chain     Versioned projections
      |                   |
      +---------+---------+
                |
                v
       Deterministic cue scoring
                |
                v
       Bounded MemoryPacket
                |
                +--> source event evidence
                +--> score components
                +--> retrieval reasons
                +--> policy version
```

The kernel currently combines lexical, explicit-entity, temporal, and conversation cues. It does not require an LLM.

For a fixed evidence set, cue state, and policy version:

```text
same evidence + same cues + same policy = same MemoryPacket
```

See [`MEMORY_KERNEL.md`](MEMORY_KERNEL.md) for the v0.2 contract and benchmark details.

---

## What the Current Repository Proves

The implementation currently demonstrates:

- **Stateless Primary Agent interactions** — no accumulated transcript is silently carried between separate external interactions.
- **Complete event persistence** — meaningful user, agent, retrieval, and error events are recorded automatically.
- **Cross-process recall** — a later process can recover information persisted by an earlier process.
- **Cross-conversation recall** — conversation boundaries do not become memory boundaries.
- **Bounded JIT context** — retrieved context remains bounded independently of total stored history.
- **Exact provenance** — retrieved context retains source-event identifiers and ordering metadata.
- **Deterministic temporal structure** — `conversation_seq` and `global_seq` provide explicit ordering domains.
- **Structured LLM control outputs** — classification decisions are schema-constrained and Pydantic-validated.
- **Deterministic application control** — IDs, timestamps, sequence values, scope, limits, and other knowable system facts are generated by ordinary code.
- **Persistent error events** — orchestration failures can become part of the event history.
- **Local inference and storage** — the prototype uses Ollama and native PostgreSQL on modest hardware.
- **Disposable test database** — tests use `jit_agent_test`, not the long-lived development history.
- **Deterministic Memory Kernel** — cue scoring and evidence selection can be tested without an LLM.
- **Rebuildable derived memory** — projections and integrity metadata can be deleted and regenerated from authoritative events.
- **Tamper-evident derivation** — a SHA-256 hash chain can verify the event sequence used to build memory state.
- **Synthetic-life evaluation** — a fictional lifetime provides known ground truth for repeatable memory experiments.

---

## Design Principles

### 1. Persistent experience without persistent LLM context

Historical growth should primarily become a storage-and-retrieval problem, not an ever-growing inference-context problem.

### 2. Persist first, interpret later

If an event occurred, it belongs to authoritative history. There is intentionally no LLM-controlled `remember_this` gate controlling ordinary persistence.

### 3. Evidence is authoritative; interpretations are replaceable

Summaries, embeddings, extracted facts, user models, associations, and other memory representations may be useful, but they are derived state. They should remain traceable to source events and rebuildable as algorithms improve.

### 4. Deterministic code owns deterministic information

The LLM should not invent facts the application can know exactly: IDs, timestamps, sequence numbers, schema versions, retrieval limits, scope, and similar system facts remain ordinary application state.

### 5. Retrieval mechanisms sit behind stable boundaries

A consumer should describe the information need. The memory subsystem decides how to satisfy it. Lexical, semantic, associative, episodic, temporal, or future routes should not require redesigning the agent protocol.

### 6. Preserve provenance

A memory system that can answer but cannot show where its evidence came from is difficult to audit and difficult to improve.

### 7. Complexity must earn its place

A framework, database, model layer, or distributed component should solve a demonstrated problem that the simpler architecture cannot reasonably solve.

---

## Event Model

The append-only event history currently supports:

- `USER_PROMPT`
- `AGENT_DECISION`
- `RETRIEVAL_REQUEST`
- `RETRIEVAL_RESULT`
- `AGENT_RESPONSE`
- `SYSTEM_EVENT`
- `ERROR`

Each event carries deterministic metadata including:

- `event_id`
- `conversation_id`
- `correlation_id`
- `global_seq`
- `conversation_seq`
- `event_type`
- `source`
- `created_at`
- structured JSON payload
- schema version

`conversation_seq` is authoritative only inside one conversation. `global_seq` is authoritative across conversations.

---

## Retrieval: MVP Baseline vs. Memory Research

The MVP Retrieval Service currently supports:

- current-conversation or all-conversation scope
- event/source-type filters
- chronological and relevance ordering
- bounded result limits
- PostgreSQL full-text search
- deterministic sequence cutoffs that prevent current-turn leakage

That lexical system remains valuable because it provides a simple control whose failure boundary is known.

Memory Kernel v0.2 adds a second, LLM-independent experimental surface. It scores canonical events using explicit cue components and returns a bounded `MemoryPacket` plus an audit trace. The kernel is intentionally simple enough that later associative or semantic mechanisms can be measured against it rather than introduced by intuition.

The repository therefore does **not** assume that vector retrieval is automatically the next answer. The next mechanism must first demonstrate measurable improvement over the deterministic baseline.

---

## Memory Kernel v0.2 Synthetic-Life Benchmark

`benchmarks/jordan_vale_v1.json` defines a fictional person and an artificial event history containing changing preferences, ambiguous names, contradictions, temporal facts, exact identifiers, weak lexical overlap, and an intentionally unknown fact.

The kernel receives the event stream, not the persona's evaluator-only oracle truth.

Run the benchmark with:

```powershell
uv run python -m jit_agent.synthetic_benchmark
```

Verified v0.2 baseline:

```text
questions: 15/18
question_success_rate: 0.833
evidence_recall: 0.833
mean_reciprocal_rank: 0.941
unknown_abstention_rate: 1.000
```

The three known failures are intentionally preserved as research targets:

1. historical-state recall — recovering the earlier latte preference from a question about the state before the coffee habit changed;
2. associative/paraphrastic recall — connecting “recover the money from the old apartment” to the event that the landlord returned the security deposit;
3. concept-to-instance recall — connecting the concept `vehicle` to the stored Toyota Corolla purchase event despite no shared vocabulary.

These failures define the first v0.3 research objective.

---

## Rebuildable Memory State

Memory Kernel v0.2 adds three derived PostgreSQL tables:

- `event_integrity`
- `memory_projection_entries`
- `memory_projection_runs`

They are disposable. `rebuild()` regenerates them from `events` and never updates or deletes authoritative events.

Run a rebuild/verification with:

```powershell
uv run python scripts/rebuild_memory_kernel.py
```

---

## Statelessness: What It Does and Does Not Mean

“Stateless” refers to the LLM across separate external interactions.

During one interaction, temporary working context can exist. A single interaction may classify the task, retrieve evidence, reason over that evidence, and produce a response. What is prohibited is treating that temporary context as authoritative memory automatically supplied to the next invocation.

The persistence, retrieval, and memory layers are intentionally stateful. The **LLM worker is disposable**.

---

## Development Environment

The prototype has been developed and exercised on a modest Windows laptop with a quad-core Intel Core i5, 16 GB RAM, NVMe storage, and integrated graphics.

Current requirements:

- Python 3.12+
- `uv`
- PostgreSQL
- Ollama for LLM-backed MVP acceptance paths
- a compatible local instruct model

The deterministic Memory Kernel and synthetic benchmark do not require an LLM.

No Docker, remote database, or hosted LLM is required by the current implementation.

---

## Installation

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
uv sync
```

Create a local development PostgreSQL database and apply the schema:

```powershell
psql -d jit_agent -f schema.sql
```

Example `.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/jit_agent
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
```

`.env` is ignored by Git and should not be committed.

---

## Running the Agent

Interactive REPL:

```powershell
uv run jit-agent
```

Reuse a conversation ID:

```powershell
uv run jit-agent --conversation-id <uuid>
```

Single-shot mode:

```powershell
uv run jit-agent --once "What did I tell you about Project Falcon?" --conversation-id <uuid>
```

`--once` is useful for demonstrating process-level statelessness because each invocation starts a new Python process.

---

## Testing

Run the complete suite with:

```powershell
uv run pytest -v
```

The suite is configured to use the dedicated `jit_agent_test` PostgreSQL database. The normal `.env` development database is not the default pytest target.

The currently verified suite contains **34 passing tests** covering the original MVP and Memory Kernel v0.2, including:

- append-only event persistence
- per-conversation and global sequencing
- exact and full-text retrieval
- bounded retrieval and provenance
- cross-conversation and cross-process recall
- persistent error events
- documented lexical failure cases
- deterministic Memory Kernel scoring
- unknown-fact abstention
- blank-entity and normalization regressions
- projection rebuild determinism
- integrity-chain verification and tamper detection
- PostgreSQL Memory Kernel rebuild/idempotence
- constrained candidate selection
- synthetic-life benchmark regression floors

Some LLM-backed acceptance paths require Ollama.

---

## Diagnostic and Benchmark Commands

Ollama diagnostics:

```powershell
uv run python scripts/diagnose_ollama.py
```

Scale/noise probe:

```powershell
uv run python scripts/scale_test.py --count 500
```

Original adversarial retrieval benchmark:

```powershell
uv run python scripts/adversarial_benchmark.py
```

Memory Kernel rebuild and integrity verification:

```powershell
uv run python scripts/rebuild_memory_kernel.py
```

Synthetic-life benchmark:

```powershell
uv run python -m jit_agent.synthetic_benchmark
```

---

## Repository Layout

```text
prometheist/
├── MEMORY_KERNEL.md
├── PRIMARY_AGENT_SPEC_SHEET.md
├── README.md
├── benchmarks/
│   └── jordan_vale_v1.json
├── pyproject.toml
├── schema.sql
├── scripts/
│   ├── adversarial_benchmark.py
│   ├── diagnose_ollama.py
│   ├── rebuild_memory_kernel.py
│   └── scale_test.py
├── src/
│   └── jit_agent/
│       ├── cli.py
│       ├── db.py
│       ├── event_store.py
│       ├── llm.py
│       ├── memory_integrity.py
│       ├── memory_kernel.py
│       ├── memory_projection.py
│       ├── models.py
│       ├── postgres_memory_kernel.py
│       ├── primary_agent.py
│       ├── retrieval.py
│       └── synthetic_benchmark.py
└── tests/
    ├── conftest.py
    ├── test_acceptance_restart.py
    ├── test_cross_conversation_memory.py
    ├── test_event_store.py
    ├── test_fts_failure_corpus.py
    ├── test_memory_integrity.py
    ├── test_memory_kernel.py
    ├── test_memory_projection.py
    ├── test_postgres_memory_kernel.py
    ├── test_primary_agent.py
    ├── test_retrieval.py
    └── test_synthetic_benchmark.py
```

`PRIMARY_AGENT_SPEC_SHEET.md` records the original prototype constraints. `MEMORY_KERNEL.md` records the current v0.2 kernel contract and benchmark baseline.

---

## Current Status

```text
Complete event persistence          PASS
Stateless Primary Agent             PASS
Cross-process recall                PASS
Cross-conversation recall           PASS
Bounded JIT context                 PASS at tested scale
Deterministic temporal ordering     PASS
Structured LLM decisions            PASS
MVP deterministic retrieval policy  PASS
Memory Kernel v0.2                  PASS
Rebuildable projections             PASS
Integrity verification              PASS
Synthetic benchmark harness         PASS
Full regression suite               34/34 PASS
Jordan Vale v0.2 baseline           15/18
Unknown-fact abstention              1.000
Associative recall                  NEXT RESEARCH MILESTONE
Vector semantic retrieval           DEFERRED pending evidence
Production scalability              NOT CLAIMED
Digital-doppelgänger model          LONG-TERM RESEARCH DIRECTION
Consciousness transfer              NOT CLAIMED
```

---

## Long-Term Direction

The current system asks:

> Can an AI agent preserve continuous experience while every LLM interaction remains stateless?

The longer-term project asks:

> How much of a person's functional identity can be represented as persistent, inspectable, model-independent state and reconstructed just in time for cognition?

Potential future identity-bearing representations include autobiographical memory, preferences, values, relationships, evolving beliefs, habits, goals, communication tendencies, uncertainty, and provenance linking every inference back to evidence.

Those representations should remain outside any particular foundation model so models can be replaced without making the model itself the sole repository of accumulated identity.

---

## Intentionally Deferred

The current system does **not** require:

- LangChain
- LangGraph
- CrewAI
- AutoGen
- Neo4j
- Redis
- Kafka
- a dedicated vector database
- a reranker
- a workflow framework
- Docker
- Kubernetes
- distributed workers

These are not categorically rejected. They are deferred until a measured requirement justifies their cost.

---

## Next Engineering Milestone: Memory Kernel v0.3

The next research branch focuses on **deterministic associative recall**.

The immediate goal is not to add a vector database or a larger model. It is to determine whether a small, inspectable association mechanism can improve the three known Jordan Vale failures while preserving the v0.2 strengths.

A proposed primitive is an explicit, provenance-bearing association:

```text
Association
├── source concept/event
├── target concept/event
├── relationship
├── strength
└── provenance
```

Recall can then perform bounded spreading activation over those associations rather than requiring exact vocabulary overlap.

Any v0.3 change is considered an improvement only if it:

1. beats the exact 15/18 Jordan Vale v0.2 baseline;
2. preserves 1.000 unknown-fact abstention;
3. does not regress the existing 34-test suite;
4. keeps evidence packets bounded;
5. remains deterministic and inspectable; and
6. preserves provenance back to authoritative source events.

That is the development philosophy of Prometheist: **freeze a measurable baseline, add one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**
