# PRIMARY AGENT SPEC SHEET

## 1. Purpose

Build a small prototype of a persistent-memory agentic system centered
on a **Primary Agent**.

The Primary Agent should behave like a continuous assistant from the
user's perspective while the LLM that powers it remains **stateless
between separate interactions**. The system must not depend on an
ever-growing chat context window to remember what has happened.

Instead, the system must persist a complete record of everything that
happens and retrieve only the information needed for the current
interaction.

The central design goal is:

> **Persistent experience without persistent LLM context.**

The prototype should prove that an agent can accumulate an effectively
unbounded external history while each new LLM invocation begins fresh
and receives only the context relevant to the current task.

------------------------------------------------------------------------

## 2. Core Concept

Every new prompt, event, or trigger starts a fresh Primary Agent
interaction.

The Primary Agent does **not** automatically receive the entire previous
conversation. It receives the current input and may ask the Retrieval
Service for relevant historical information when needed.

Conceptually:

``` text
Current prompt/event
        ↓
Fresh Primary Agent invocation
        ↓
Does this task require historical information?
        ↓
   No ───────→ Respond/act
        ↓ Yes
Query Retrieval Service
        ↓
Retrieve relevant persisted history
        ↓
Return only useful context
        ↓
Primary Agent responds/acts
        ↓
Persist everything that happened
        ↓
Discard temporary LLM context
```

The next interaction starts fresh again.

------------------------------------------------------------------------

## 3. Complete Persistence Is Mandatory

**Everything that happens in the system must be persisted.**

Persistence is not optional and is not something the LLM decides.

The system should automatically record, at minimum:

-   every user prompt
-   every Primary Agent response
-   every external/system-triggered event
-   every Primary Agent decision
-   every request sent to the Retrieval Service
-   every result returned by the Retrieval Service
-   every future tool or agent call
-   every future tool or agent result
-   errors, retries, and other meaningful system events
-   references to files or artifacts involved in an interaction
-   the deterministic metadata needed to reconstruct what happened and
    in what order

There should be **no `memory_assertion`, `remember_this`, or similar
LLM-controlled gate that determines whether ordinary history is
retained**.

If something happened, it is part of the system's history and must be
stored.

------------------------------------------------------------------------

## 4. Exact Historical Recall

The persisted history must preserve original information accurately
enough for exact historical questions.

For example, if the user asks:

> What was the first thing I said to you in the conversation that
> started Monday at roughly 5:30 PM?

The system should be able to locate the relevant conversation and return
the user's original wording verbatim.

The system should therefore preserve original prompts and responses
rather than replacing them with summaries.

Summaries, semantic interpretations, embeddings, indexes, or other
derived representations may be created later to improve retrieval, but
they must **supplement rather than replace** the authoritative original
record.

------------------------------------------------------------------------

## 5. Stateless Primary Agent

The Primary Agent's LLM must be stateless across separate external
interactions.

A conversation should feel continuous to the user because the system can
retrieve its history, not because the LLM is silently carrying an
accumulated transcript.

Temporary context is allowed during one interaction. For example, the
Primary Agent may:

1.  receive the current prompt;
2.  decide that historical context is needed;
3.  query the Retrieval Service;
4.  receive the retrieval result;
5.  reason over that result;
6.  produce the final response.

That temporary working context may exist for the duration of the
interaction. Once the interaction is complete, it should not serve as
persistent memory for the next interaction.

------------------------------------------------------------------------

## 6. Retrieval Service

The prototype should include a minimal Retrieval Service responsible for
finding historical information for the Primary Agent.

The Primary Agent decides **what information it needs**. The Retrieval
Service decides **how to find that information in persisted history**.

The Retrieval Service should support both exact and semantic retrieval.

Examples of exact/structured retrieval:

-   the first prompt in a particular conversation
-   what happened at a particular time
-   the immediately preceding response
-   all events belonging to a particular conversation
-   a specific event identified by ID

Examples of semantic retrieval:

-   what the user previously said about a particular project
-   the number the user recently asked the agent to remember
-   the earlier discussion most relevant to the current question

Whenever exact metadata can answer a question reliably, use exact
retrieval over asking an LLM to infer the answer.

------------------------------------------------------------------------

## 7. Just-in-Time Context

The Retrieval Service should return **only the historical information
reasonably relevant to the current task**, rather than dumping the
entire stored history into the Primary Agent's context.

The objective is not to eliminate context windows. The objective is to
keep inference context bounded and task-specific.

A system with years of stored history should still be capable of
answering a simple new prompt without loading years of history into the
LLM.

Historical data growth should primarily become a retrieval/storage
problem rather than an ever-growing inference-context problem.

------------------------------------------------------------------------

## 8. Deterministic Metadata

The application, not the LLM, must generate information that can be
known deterministically.

Examples include:

-   unique IDs
-   conversation IDs
-   event IDs
-   timestamps
-   ordering/sequence information
-   relationships between events
-   source identifiers
-   agent identifiers
-   execution/correlation identifiers
-   schema versions
-   known model identifiers

The LLM should not be used to invent this information.

The LLM should generate only content or decisions that genuinely require
language understanding or semantic reasoning.

------------------------------------------------------------------------

## 9. Structured and Constrained LLM Communication

LLM outputs should be structured and constrained whenever practical.

Use **Pydantic** schemas to validate structured communication between
the Primary Agent, Retrieval Service, and future components.

Prefer narrowly defined choices and fields over arbitrary free-form
control output.

For example, the Primary Agent may initially need only to decide between
concepts such as:

``` text
RESPOND_DIRECTLY
RETRIEVE_HISTORY
```

Do not give the LLM unnecessary authority over system state, metadata,
persistence, database structure, or workflow mechanics.

Natural-language response text may of course remain natural language.

------------------------------------------------------------------------

## 10. Authoritative History vs. Derived Memory

For this prototype, treat the complete persisted event history as the
system's authoritative memory.

Do not require a separate LLM-generated "memory assertion" mechanism.

Later versions may derive additional memory representations from
historical events, such as:

-   semantic summaries
-   user facts
-   observations
-   inferred relationships
-   knowledge-graph relationships
-   importance scores
-   consolidated memories

Those are future optimization layers. They must remain traceable to the
underlying source events and must never replace the original history.

The first prototype should prove that complete event persistence plus
retrieval works before adding sophisticated memory interpretation or
consolidation.

------------------------------------------------------------------------

## 11. Storage Direction

Use **PostgreSQL running locally on the Windows development machine as a
native service**.

Do not use Docker or a remote/cloud database.

The development laptop has approximately:

-   Intel Core i5 quad-core CPU with Hyper-Threading
-   16 GB system RAM
-   1 TB M.2 NVMe PCIe SSD
-   Intel Iris Xe integrated graphics
-   no dedicated GPU

The prototype should be designed comfortably within these constraints.

PostgreSQL should ultimately support structured metadata retrieval and
semantic/vector retrieval. **pgvector may be used when semantic vector
retrieval is implemented.**

Do not introduce another database unless a demonstrated requirement
later justifies it.

------------------------------------------------------------------------

## 12. LLM Direction

The architecture should remain LLM-agnostic.

The development laptop does not need to run a large local model for the
prototype to be valid. A hosted LLM API may be used while developing and
testing the architecture.

Local Ollama-compatible models may also be supported where practical,
but local large-model inference is not a requirement for the first
prototype.

Keep the model interface simple enough that the underlying
model/provider can be changed later without redesigning the persistence
and retrieval architecture.

------------------------------------------------------------------------

## 13. Prototype Scope

The first prototype should be deliberately small.

It needs only enough functionality to demonstrate:

1.  a fresh Primary Agent invocation for each user interaction;
2.  automatic persistence of every event;
3.  retrieval of relevant prior events;
4.  use of retrieved history to answer a current prompt;
5.  structured/constrained communication;
6.  deterministic metadata generation;
7.  traceability from an answer back to the events and retrieval
    operations that produced it.

A simple CLI interface is sufficient.

Do not build a production platform yet.

------------------------------------------------------------------------

## 14. Initial Acceptance Scenario

The prototype should be able to demonstrate the following sequence.

### Interaction 1

User:

``` text
hello
```

The Primary Agent responds normally. The prompt, response, and
associated system events are persisted.

The LLM's temporary context is then discarded.

### Interaction 2

User:

``` text
I want you to remember <some random sequence of characters>.
```

This interaction begins with a fresh Primary Agent invocation.

The prompt and response are persisted automatically because **all events
are persisted**, not because the LLM elects to create a special memory.

The temporary context is discarded afterward.

### Interaction 3

User:

``` text
Hey — what was that number I just asked you to remember?
```

This again begins with a fresh Primary Agent invocation.

The Primary Agent recognizes that historical information is required and
requests it from the Retrieval Service.

The Retrieval Service locates the relevant prior event and returns it.

The Primary Agent answers:

``` text
You asked me to remember <insert exact sequence of characters from last step here>.
```

The new prompt, retrieval request, retrieval result, Primary Agent
response, and associated metadata are all persisted.

------------------------------------------------------------------------

## 15. Historical Recall Acceptance Scenario

The system should also eventually support a query such as:

``` text
What was the first thing I said to you in our conversation that started <insert date> at roughly <insert time>?
```

The system should use stored timestamps, conversation relationships,
event ordering, and original event content to locate the relevant prompt
and reproduce it accurately.

This scenario is important because it demonstrates that the system has a
complete historical record rather than merely a collection of selected
semantic memories.

------------------------------------------------------------------------

## 16. Simplicity Is a Design Requirement

The prototype must remain easy for one developer to understand.

Do not prematurely introduce:

-   Neo4j
-   Temporal
-   LangChain
-   LangGraph
-   CrewAI
-   AutoGen
-   dedicated vector databases
-   multiple database systems
-   distributed services
-   Docker
-   Kubernetes
-   Redis
-   Kafka
-   elaborate agent frameworks
-   elaborate workflow frameworks
-   unnecessary API servers
-   unnecessary abstraction layers

These technologies may become useful later. Their possible future
usefulness is not sufficient reason to include them now.

Before adding any major dependency or architectural component, identify
the concrete problem that the existing prototype cannot reasonably solve
without it.

------------------------------------------------------------------------

## 17. Future System Direction

The long-term system may eventually include additional specialized
agents or services for:

-   ingestion
-   memory maintenance/consolidation
-   files and artifacts
-   web retrieval
-   external tools
-   workflow execution
-   security/policy checks
-   knowledge graphs
-   sophisticated reranking
-   background tasks
-   resource management

The Primary Agent is intended to become the orchestration layer that
decides when those capabilities are needed.

However, **do not implement them merely because they are part of the
eventual vision**.

The prototype should first establish the core architecture:

``` text
Stateless Primary Agent
        +
Complete persistent event history
        +
Just-in-time Retrieval Service
        =
Continuous agent experience without accumulated LLM context
```

------------------------------------------------------------------------

## 18. Instructions to GitHub Copilot

Use this document as the high-level product and architecture
specification for the prototype.

When implementing it:

-   favor the smallest working design;
-   keep the complete control flow understandable;
-   persist every meaningful event automatically;
-   never make persistence dependent on an LLM decision;
-   do not silently maintain accumulated chat context;
-   generate deterministic metadata in application code;
-   constrain structured LLM outputs with Pydantic;
-   preserve original event content and provenance;
-   retrieve historical information just in time;
-   prefer deterministic retrieval when metadata can answer the question
    exactly;
-   use semantic retrieval when the request is genuinely semantic;
-   avoid adding infrastructure for hypothetical future requirements;
-   add tests that prove the architecture behaves as specified;
-   ask before introducing a major new dependency, framework, database,
    service, or architectural layer.

When a design choice is ambiguous, prefer **simplicity, inspectability,
deterministic behavior, complete historical preservation, and bounded
LLM context**.
