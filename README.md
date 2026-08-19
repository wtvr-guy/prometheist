# Prometheist

**Persistent identity for stateless intelligence.**

Prometheist is an experimental AI-agent architecture built around a deliberately unusual constraint: **every LLM invocation is stateless**.

The model is never treated as the durable memory, identity, or authoritative state of the agent. Instead, the system records experience externally, preserves original events with provenance, and reconstructs only the context needed for the current inference.

The current repository is a working proof-of-concept for that architecture. It demonstrates persistent memory across process restarts and conversation boundaries while keeping each new LLM interaction independent of any hidden accumulated chat transcript.

The longer-term research goal is broader: to investigate whether a sufficiently rich, provenance-preserving computational model of a person can eventually support a highly personalized AI that increasingly behaves as that person's **digital doppelgänger**. That goal is aspirational; this repository currently implements the foundational persistence-and-retrieval architecture, not a consciousness upload or a complete model of human identity.

> **Core thesis:** persistent state belongs to the system, not to an LLM context window.

---

## Why Prometheist Exists

Most conversational AI systems obtain continuity by repeatedly carrying forward a growing transcript, summary, or hidden conversation state. That works well for many applications, but it tightly couples an agent's apparent continuity to the active model context.

Prometheist explores a different architecture.

A model invocation should be disposable. The system should be able to stop the Python process, replace the LLM, begin a new conversation, or reconstruct the agent on another worker without losing the history that gives the agent continuity.

Conceptually:

```text
Persistent experience / identity-bearing state
                    |
                    v
          Just-in-time retrieval
                    |
                    v
       Temporary inference context
                    |
                    v
             Stateless LLM
                    |
                    v
         Response / decision / action
                    |
                    v
        Persist resulting experience
                    |
                    v
       Discard temporary LLM context
```

The LLM is therefore a **cognitive engine**, not the storage location of the agent's identity.

This separation is useful even without the long-term digital-doppelgänger objective. It makes model replacement, bounded context, exact historical recall, provenance, failure analysis, and retrieval experimentation much easier to reason about explicitly.

---

## What the Current Prototype Proves

The current implementation demonstrates:

- **Stateless Primary Agent interactions** — no accumulated transcript is silently carried between separate external interactions.
- **Complete event persistence** — meaningful user, agent, retrieval, and error events are recorded automatically.
- **Cross-process recall** — the application can terminate completely and recover prior information in a later process.
- **Cross-conversation recall** — conversation IDs organize history but are not memory walls.
- **Just-in-time context reconstruction** — historical information is retrieved only when the current task requires it.
- **Bounded retrieval context** — the amount returned to the model is limited independently of total stored history.
- **Exact provenance** — retrieved context retains source-event IDs and ordering metadata.
- **Deterministic temporal structure** — per-conversation and global sequence numbers give the model explicit ordering information instead of asking it to infer chronology from timestamps.
- **Structured LLM control outputs** — classification decisions are schema-constrained and validated with Pydantic.
- **Deterministic application control** — IDs, timestamps, sequence values, retrieval limits, scope, and other knowable system facts are generated in ordinary code rather than hallucinated by an LLM.
- **Persistent error events** — recoverable orchestration failures become part of the system record.
- **Local inference and storage** — the current prototype uses Ollama and native PostgreSQL on the development machine.
- **A disposable test database** — tests are isolated from the development history.

The prototype intentionally starts with PostgreSQL full-text search rather than embedding retrieval so the failure boundary of the simpler system can be measured before additional complexity is introduced.

---

## Architecture

The Primary Agent owns orchestration. The Retrieval Service owns the mechanics of locating historical information. PostgreSQL owns the authoritative persistent event history. The LLM is invoked fresh for each interaction.

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

The next external interaction starts fresh again.

Continuity exists because the **system can reconstruct relevant history**, not because the model itself remains continuously stateful.

---

## Design Principles

### 1. Persistent experience without persistent LLM context

Historical growth should primarily become a storage-and-retrieval problem, not an ever-growing inference-context problem.

A system with years of history should still be able to answer a simple current question with a small, task-specific context.

### 2. Persist first, interpret later

Prometheist preserves raw interactions and meaningful system events before attempting to decide what will matter in the future.

There is intentionally no LLM-controlled `remember_this`, `memory_assertion`, or similar gate controlling ordinary persistence.

If an event occurred, it belongs to the authoritative history.

Derived representations — summaries, embeddings, extracted facts, user models, graph relationships, consolidated memories — may be added later, but they should supplement rather than replace the source events from which they were derived.

### 3. Evidence is authoritative; interpretations are replaceable

A future system may infer that a user has a preference, belief, trait, relationship, habit, or value. Those interpretations can be useful, but they are not equivalent to the original evidence.

Prometheist is designed so derived models can be regenerated as algorithms improve while the underlying historical record remains available.

### 4. Deterministic code owns deterministic information

The LLM should not invent facts the application can know exactly.

Application code owns:

- event IDs
- conversation IDs
- correlation IDs
- timestamps
- sequence numbers
- source identifiers
- schema versions
- retrieval scope
- retrieval limits
- known model/runtime metadata

The model is used where language understanding or semantic judgment is actually required.

### 5. Retrieval is an implementation detail behind a stable boundary

The Primary Agent describes **what information it needs**.

The Retrieval Service decides **how to find it**.

Today that means metadata filtering and PostgreSQL full-text search. Later it can include embeddings, `pgvector`, hybrid candidate fusion, or reranking without forcing the Primary Agent to understand those techniques.

### 6. Preserve provenance

A memory system that can answer but cannot explain where its context came from is difficult to audit and difficult to improve.

Retrieval results therefore preserve source event IDs and temporal metadata so a generated answer can be traced back to the events that informed it.

### 7. Complexity must earn its place

The project deliberately avoids adding infrastructure merely because it is fashionable in agent systems.

A new framework, database, model layer, or distributed component should solve a demonstrated problem that the simpler architecture cannot reasonably solve.

---

## Event Model

The current append-only event history supports:

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

### Two explicit ordering systems

Prometheist tracks two sequence domains:

- `conversation_seq` — authoritative order within one conversation
- `global_seq` — authoritative order across all conversations

This distinction matters because local conversation sequence numbers are not comparable across different conversations.

It also means questions such as "what was current at that point?" do not have to rely solely on nearly identical wall-clock timestamps or LLM inference.

---

## Retrieval

The current Retrieval Service supports:

- current-conversation or all-conversation scope
- event/source-type filters
- chronological ordering
- relevance ordering
- bounded result limits
- PostgreSQL full-text search
- deterministic sequence cutoffs that prevent the current prompt from retrieving itself as history

Ordinary conversational retrieval currently searches persisted `USER_PROMPT` and `AGENT_RESPONSE` events across conversations by default.

When `query_text` exists, application policy uses relevance ordering. When it does not, policy uses reverse chronological ordering.

The important boundary is that this policy is ordinary application code. The LLM does not control database mechanics, SQL, limits, or persistence behavior.

---

## Why Full-Text Search Comes First

The current system intentionally uses lexical PostgreSQL FTS before semantic vector retrieval.

That decision is experimental rather than ideological: establish a simple baseline, characterize where it succeeds and fails, then introduce semantic retrieval against a measurable control.

The repository includes a failure corpus demonstrating the principal limitation of lexical retrieval. For example:

```text
Stored:
The codename for Falcon is Blue Cedar.

Query:
What was that tree-related name for the bird initiative?
```

The two statements may be semantically related while sharing essentially no useful vocabulary. Full-text search can therefore miss the source event.

That documented failure is the evidence-based reason for the next likely retrieval phase.

Expected future direction:

```text
metadata filtering
        +
PostgreSQL full-text search
        +
pgvector semantic similarity
        |
        v
candidate fusion / ranking
        |
        v
bounded, provenance-preserving context
```

A reranker should only be introduced if measurements show that the hybrid candidate set still requires one.

---

## Statelessness: What It Does and Does Not Mean

"Stateless" in this project refers specifically to the LLM across separate external interactions.

During one interaction, temporary working context can exist. A single interaction may:

1. receive the current prompt;
2. classify whether historical context is necessary;
3. issue a retrieval request;
4. receive historical events;
5. reason over that context;
6. produce a response.

What is prohibited is treating that temporary context as the authoritative memory automatically supplied to the next interaction.

The persistence layer, retrieval layer, and database are intentionally stateful. The **LLM worker is disposable**.

---

## Proof-of-Concept Recall Scenario

A minimal end-to-end demonstration looks like this.

### Process A

```text
User:
The codename for Project Falcon is Blue Cedar.
```

The interaction is persisted. The process exits completely.

### Process B

A brand-new Python process — with no shared in-memory conversational state — receives:

```text
What codename did I give Project Falcon?
```

The Primary Agent recognizes that history is required, the Retrieval Service locates the prior event, the relevant persisted event is supplied to the fresh response inference, and the model answers from retrieved evidence.

The test suite contains both cross-process and cross-conversation acceptance coverage for this property.

---

## Current LLM Backend

The prototype currently uses Ollama through a deliberately small `LLMClient` interface.

The underlying model is environment-configured rather than architecturally hardcoded.

Current behavior includes:

- Ollama JSON-schema-constrained classification output
- Pydantic validation
- thinking disabled for the tested Qwen configuration
- bounded classification generation
- bounded response generation
- timing/token telemetry logging for diagnostics

The architecture is intended to remain model-agnostic. Replacing the current model should not require redesigning persistence or retrieval.

---

## Development Environment

The prototype has been developed and exercised on a modest Windows laptop:

- quad-core Intel Core i5 with Hyper-Threading
- 16 GB RAM
- NVMe SSD
- Intel integrated graphics
- no dedicated GPU

The point is not that this is the target production hardware. It demonstrates that the architecture itself does not require a large GPU workstation to validate.

Current requirements:

- Python 3.12+
- `uv`
- PostgreSQL
- Ollama
- a compatible local instruct model

No Docker, remote database, or hosted LLM is required by the current implementation.

---

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
```

### 2. Install Python dependencies

```powershell
uv sync
```

### 3. Configure PostgreSQL

Create a local development database and apply the schema:

```powershell
psql -d jit_agent -f schema.sql
```

Configure the connection through `DATABASE_URL`.

### 4. Configure Ollama

Start Ollama and pull the instruct model you want to use.

### 5. Create `.env`

Example:

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

The CLI prints a `conversation_id` that can be used again later:

```powershell
uv run jit-agent --conversation-id <uuid>
```

Single-shot mode:

```powershell
uv run jit-agent --once "What did I tell you about Project Falcon?" --conversation-id <uuid>
```

`--once` is particularly useful for demonstrating process-level statelessness because every invocation starts a new Python process.

---

## Testing

Run the suite with:

```powershell
uv run pytest
```

The tests are designed to use a dedicated PostgreSQL test database rather than destructively resetting the normal development history.

Coverage includes:

- persistence of every current event type
- append-only event-store behavior at the application layer
- conversation sequence ordering
- global sequence ordering
- exact event retrieval
- full-text retrieval
- bounded result limits
- source-event provenance
- all-conversation retrieval
- global cutoff semantics
- stateless Primary Agent behavior
- persistent error events
- cross-process recall
- cross-conversation recall
- documented lexical-retrieval failure cases

Some acceptance tests require Ollama and are skipped when it is unavailable.

---

## Diagnostic and Benchmark Scripts

### Ollama diagnostics

```powershell
uv run python scripts/diagnose_ollama.py
```

Used to isolate model-loading, prompt-evaluation, generation, structured-output, token-count, and request-latency behavior.

### Scale/noise probe

```powershell
uv run python scripts/scale_test.py --count 500
```

A measured prototype run inserted increasing amounts of unrelated history and performed a real end-to-end retrieval:

| Noise events | Items returned | Target found | Retrieved content | Latency |
|---:|---:|:---:|---:|---:|
| 500 | 1 | Yes | 45 chars | ~8.7 s |
| 2,000 | 1 | Yes | 45 chars | ~7.8 s |
| 5,000 | 1 | Yes | 45 chars | ~7.9 s |

At this tested scale, stored history increased 10× while retrieved context remained constant.

This is evidence for the intended bounded-context property. It is **not** a claim of production-scale performance.

### Adversarial retrieval benchmark

```powershell
uv run python scripts/adversarial_benchmark.py
```

The benchmark probes:

- high lexical overlap
- closely related entity names
- conflicting facts over time
- current vs. original vs. immediately previous values

One early temporal failure was fixed not by adding a larger model or another AI subsystem, but by exposing the already-known deterministic `conversation_seq` metadata to the response model.

That result reflects a central project principle: **preserve and expose deterministic structure before adding model complexity.**

---

## Repository Layout

```text
prometheist/
├── PRIMARY_AGENT_SPEC_SHEET.md
├── README.md
├── pyproject.toml
├── schema.sql
├── scripts/
│   ├── adversarial_benchmark.py
│   ├── diagnose_ollama.py
│   └── scale_test.py
├── src/
│   └── jit_agent/
│       ├── __init__.py
│       ├── cli.py
│       ├── db.py
│       ├── event_store.py
│       ├── llm.py
│       ├── models.py
│       ├── primary_agent.py
│       └── retrieval.py
└── tests/
    ├── conftest.py
    ├── test_acceptance_restart.py
    ├── test_cross_conversation_memory.py
    ├── test_event_store.py
    ├── test_fts_failure_corpus.py
    ├── test_primary_agent.py
    └── test_retrieval.py
```

`PRIMARY_AGENT_SPEC_SHEET.md` contains the original prototype architecture specification and design constraints.

---

## Current Status

```text
Complete event persistence       PASS
Stateless Primary Agent          PASS
Cross-process recall             PASS
Cross-conversation recall        PASS
Bounded JIT context              PASS at tested scale
Temporal ordering                PASS
Structured LLM decisions         PASS
Deterministic retrieval policy   PASS
Error persistence                PASS
Lexical semantic-equivalent      LIMITED / documented
True semantic recall             NOT YET IMPLEMENTED
Production scalability           NOT CLAIMED
Digital-doppelgänger model       LONG-TERM RESEARCH DIRECTION
Consciousness transfer           NOT CLAIMED
```

---

## Long-Term Direction: From Memory to Personal Identity Modeling

The current prototype answers a narrow engineering question:

> Can an AI agent preserve continuous experience while every LLM interaction remains stateless?

The longer-term Prometheist project asks a harder one:

> How much of a person's functional identity can be represented as persistent, inspectable, model-independent state and reconstructed just in time for cognition?

A mature system would need much more than conversational recall. Potential future identity-bearing representations include:

- episodic/autobiographical memory
- stable personal facts
- preferences and their context
- values and decision criteria
- habits and procedural tendencies
- relationships and social context
- communication style
- evolving beliefs
- contradictions and belief changes over time
- self-reported traits
- behaviorally inferred traits
- personal narratives and long-term goals
- provenance linking every inference back to supporting evidence

The intended architecture keeps those representations outside any particular foundation model so that models can be upgraded or replaced without making the model itself the sole repository of the person's accumulated history.

This is the project's connection to transhumanist ideas about substrate independence and digital continuity. It is a research direction, not a claim that current LLM technology can reproduce consciousness or establish continuity of subjective identity.

---

## Why the Name "Prometheist"?

The name is intentionally Promethean.

Prometheus is a symbol of humanity acquiring capabilities that exceed inherited natural limits. Prometheist applies that idea to intelligent systems and, eventually, to the question of whether important informational components of human identity can be externalized into a computational substrate.

The name is therefore not just branding for a memory implementation. It reflects the project's broader motivation: using technology to investigate forms of cognitive and personal continuity that are not limited to one transient model context — and, in the long term, perhaps not limited to one biological substrate.

---

## Intentionally Deferred

The current prototype does **not** use:

- LangChain
- LangGraph
- CrewAI
- AutoGen
- Neo4j
- Temporal
- Redis
- Kafka
- a dedicated vector database
- a separate reranker
- a workflow framework
- Docker
- Kubernetes
- distributed workers

These are not categorically rejected. They are deferred until a concrete requirement demonstrates that their complexity is justified.

---

## Next Engineering Milestone

The most evidence-supported next capability is **hybrid semantic retrieval using PostgreSQL + pgvector** while retaining the existing metadata and FTS paths.

The existing lexical failure corpus should remain as a control. Semantic retrieval should be considered an improvement only if it:

1. recovers the documented zero-vocabulary paraphrase failures;
2. preserves exact and temporal retrieval behavior;
3. keeps returned context bounded;
4. avoids materially increasing false positives;
5. preserves exact provenance back to authoritative source events.

That sequence captures the development philosophy of Prometheist: establish a simple working system, characterize its failure boundary, then add complexity only where measurements justify it.
