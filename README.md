# Prometheist

**Persistent identity for stateless intelligence.**

Prometheist is an experimental AI-agent architecture built around a deliberately unusual constraint: **every LLM invocation is stateless**.

The model is never treated as durable memory, identity, or authoritative system state. Prometheist records experience externally, preserves original events with provenance, derives replaceable memory structures from those events, and reconstructs only the context needed for the current inference.

> **Core thesis:** persistent state belongs to the system, not to an LLM context window.

The current repository contains a working stateless-agent MVP plus a sequence of deterministic memory-kernel experiments. Memory Kernel v0.4 is the current research milestone: it automatically derives a small set of provenance-bearing associative relationships from authoritative events and uses those relationships for bounded just-in-time recall.

The longer-term research goal is to investigate whether this architecture can support human-inspired just-in-time recall with machine-level factual fidelity, and eventually a highly personalized AI whose persistent identity is independent of any one foundation model. That direction is aspirational; the present repository is a memory architecture and research platform, not a complete model of a person or a claim of consciousness transfer.

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

### Stateless-agent MVP

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

### Memory Kernel v0.2 — deterministic control

Memory Kernel v0.2 introduced the core memory invariant:

> **What happened is authoritative; how Prometheist currently remembers it is disposable.**

It added deterministic cue scoring over canonical events, bounded `MemoryPacket` outputs, rebuildable lexical projections, and tamper-evident event-integrity metadata. It remains the control retrieval algorithm for later experiments.

For a fixed evidence set, cue state, and policy version:

```text
same evidence + same cues + same policy = same MemoryPacket
```

See [`MEMORY_KERNEL.md`](MEMORY_KERNEL.md).

### Memory Kernel v0.3 — curated associative recall

v0.3 tested whether a small deterministic association graph could repair known lexical-retrieval failures without weakening boundedness, provenance, determinism, or unknown-fact abstention.

```text
present cues
    |
    v
bounded spreading activation
    |
    v
association routing hints
    |
    v
canonical source-event evidence
```

The mechanism succeeded on the Jordan Vale benchmark, improving the v0.2 control from 15/18 to 18/18. The v0.3 associations were deliberately curated, so the experiment proved the usefulness of associative activation but did **not** prove automatic association discovery.

See [`ASSOCIATIVE_MEMORY.md`](ASSOCIATIVE_MEMORY.md).

### Memory Kernel v0.4 — derived associative memory

v0.4 keeps the v0.3 retrieval mechanism but changes how associations are produced.

```text
authoritative PostgreSQL events
            |
            v
deterministic association derivation
            |
            v
versioned association projection
            |
            v
bounded associative activation
            |
            v
canonical source-event evidence
```

Associations are derived state, not facts. They can be deleted and rebuilt from the authoritative event ledger.

The current derivation projection implements three deliberately narrow rule families:

- `PREVIOUS_STATE` — links a change event to the nearest earlier event in the same coarse concept class, gated by a past-state cue;
- `RESOLVED_BY` — links an unresolved event to a later resolution event when explicit entity overlap supports the relationship;
- `CONCEPT_INSTANCE` — maps the general concept `vehicle` to qualifying acquisition/ownership evidence for a recognized vehicle instance.

Every derived association carries a deterministic ID, typed endpoints, relationship type, deterministic strength, source-event provenance, and optional cue gates. A deterministic projection digest makes repeated rebuilds directly comparable.

See [`MEMORY_KERNEL_V0.4.md`](MEMORY_KERNEL_V0.4.md).

---

## What the Current Repository Demonstrates

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
- **Rebuildable derived memory** — lexical and associative projections plus integrity metadata can be regenerated from authoritative events.
- **Tamper-evident derivation** — a SHA-256 hash chain verifies the event sequence used to build memory state.
- **Bounded associative recall** — explicit associations can activate canonical evidence that lexical overlap misses.
- **Automatic deterministic association derivation** — v0.4 derives limited association types from events rather than requiring answer-specific hand-authored edges.
- **Held-out synthetic evaluation** — the same derivation code is evaluated unchanged against a second fictional persona.

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

## Authoritative vs. Derived State

PostgreSQL `events` is the authoritative structured memory ledger.

The Memory Kernel currently maintains disposable derived state in:

- `event_integrity`
- `memory_projection_entries`
- `memory_association_entries`
- `memory_projection_runs`

`postgres_memory_kernel.rebuild()` regenerates integrity metadata, lexical projection entries, and association projection entries from `events`. Association rebuilds record the projection name/version, source-event count, association count, and deterministic projection digest.

A rebuild must never rewrite authoritative event rows.

Run a rebuild/verification with:

```powershell
uv run python scripts/rebuild_memory_kernel.py
```

---

## Verified Memory Benchmarks

The repository uses synthetic personas with known evaluator ground truth so retrieval changes can be compared against a fixed event history.

### Jordan Vale — v0.2 lexical/control baseline

```text
questions: 15/18
question_success_rate: 0.833
evidence_recall: 0.833
mean_reciprocal_rank: 0.941
unknown_abstention_rate: 1.000
```

The three preserved failures are:

1. historical-state recall — recovering an earlier latte preference when asked about the state before a later coffee-habit change;
2. associative/paraphrastic recall — connecting recovery of money from an old apartment to the returned security-deposit event;
3. concept-to-instance recall — connecting the general concept `vehicle` to the Toyota Corolla ownership event.

### Jordan Vale — v0.3 curated associations

```text
v0.2 baseline:    15/18
v0.3 associative: 18/18
v0.3 evidence recall: 1.000
v0.3 mean reciprocal rank: 1.000
v0.3 unknown abstention: 1.000
```

### v0.4 deterministic derived associations

Verified locally on August 20, 2026:

```text
Jordan Vale
  baseline: 15/18
  derived:  18/18
  derived evidence recall: 1.000
  derived unknown abstention: 1.000

Avery Chen (held out)
  baseline: 3/6
  derived:  6/6
  derived evidence recall: 1.000
  derived unknown abstention: 1.000
```

The Avery corpus has no hand-authored association fixture. The same derivation code used for Jordan is applied unchanged to Avery.

These results are evidence that the current limited deterministic rules generalize beyond the corpus on which associative activation was first developed. They are **not** evidence of broad semantic-memory generalization: the benchmark remains intentionally small and synthetic.

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

The deterministic Memory Kernel and synthetic/associative benchmarks do not require an LLM.

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

The full v0.4 regression suite was verified passing locally on August 20, 2026. Coverage includes the original MVP, Memory Kernel v0.2, v0.3 associative recall, and v0.4 association derivation, including:

- append-only event persistence
- per-conversation and global sequencing
- exact and full-text retrieval
- bounded retrieval and provenance
- cross-conversation and cross-process recall
- persistent error events
- documented lexical failure cases
- deterministic Memory Kernel scoring
- unknown-fact abstention
- projection rebuild determinism
- integrity-chain verification and tamper detection
- PostgreSQL Memory Kernel rebuild/idempotence
- bounded associative activation
- deterministic association derivation
- false-association rejection tests
- exact association provenance
- association projection digest reproducibility
- held-out Avery benchmark generalization

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

v0.2 control benchmark:

```powershell
uv run python -m jit_agent.synthetic_benchmark
```

v0.3 curated-association comparison:

```powershell
uv run python -m jit_agent.associative_benchmark
```

v0.4 derived-association evaluation:

```powershell
uv run python -m jit_agent.derived_associative_benchmark
```

---

## Repository Layout

```text
prometheist/
├── ASSOCIATIVE_MEMORY.md
├── MEMORY_KERNEL.md
├── MEMORY_KERNEL_V0.4.md
├── PRIMARY_AGENT_SPEC_SHEET.md
├── README.md
├── benchmarks/
│   ├── avery_chen_v1.json
│   ├── jordan_vale_associations_v1.json
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
│       ├── association_projection.py
│       ├── associative_benchmark.py
│       ├── associative_memory.py
│       ├── cli.py
│       ├── db.py
│       ├── derived_associative_benchmark.py
│       ├── event_store.py
│       ├── llm.py
│       ├── memory_integrity.py
│       ├── memory_kernel.py
│       ├── memory_projection.py
│       ├── models.py
│       ├── postgres_association_projection.py
│       ├── postgres_memory_kernel.py
│       ├── primary_agent.py
│       ├── retrieval.py
│       └── synthetic_benchmark.py
└── tests/
    ├── conftest.py
    ├── test_association_projection.py
    ├── test_associative_benchmark.py
    ├── test_associative_memory.py
    ├── test_derived_associative_benchmark.py
    ├── test_memory_integrity.py
    ├── test_memory_kernel.py
    ├── test_memory_projection.py
    ├── test_postgres_association_projection.py
    ├── test_postgres_memory_kernel.py
    └── ...
```

`PRIMARY_AGENT_SPEC_SHEET.md` records the original prototype constraints. `MEMORY_KERNEL.md` records the deterministic kernel/control contract. `ASSOCIATIVE_MEMORY.md` records the v0.3 associative-retrieval experiment. `MEMORY_KERNEL_V0.4.md` records automatic deterministic association derivation and held-out evaluation.

---

## Current Status

```text
Complete event persistence           PASS
Stateless Primary Agent              PASS
Cross-process recall                 PASS
Cross-conversation recall            PASS
Bounded JIT context                  PASS at tested scale
Deterministic temporal ordering      PASS
Structured LLM decisions             PASS
MVP deterministic retrieval policy   PASS
Memory Kernel v0.2 control           PASS
Memory Kernel v0.3 associative       PASS — Jordan 18/18
Memory Kernel v0.4 derivation        PASS — Jordan 18/18, Avery 6/6
Unknown-fact abstention              1.000 in verified synthetic benchmarks
Rebuildable lexical projections      PASS
Rebuildable association projection   PASS
Projection digest reproducibility    PASS
Integrity verification               PASS
Full v0.4 regression suite           PASS locally 2026-08-20
Vector semantic retrieval            DEFERRED pending evidence
Production scalability               NOT CLAIMED
Digital-doppelgänger model           LONG-TERM RESEARCH DIRECTION
Consciousness transfer               NOT CLAIMED
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

## Next Research Milestone

v0.4 establishes that a small deterministic derivation layer can reproduce the v0.3 associative-recall result without loading Jordan's curated association fixture and can transfer unchanged to a small held-out Avery corpus.

The next experiment should test **robustness and scale**, not simply add more examples of the same three relationships. Candidate stressors include:

- multiple competing historical states;
- repeated preference changes over time;
- several semantically similar entities;
- unresolved and resolved obligations interleaved with distractors;
- ownership vs. consideration vs. disposal of objects;
- deliberately misleading lexical overlap;
- longer histories with unrelated noise;
- false-association pressure and bounded-recall tradeoffs.

The development rule remains:

> **Freeze a measurable baseline, add one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**
