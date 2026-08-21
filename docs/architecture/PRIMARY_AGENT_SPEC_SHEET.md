# PRIMARY AGENT SPEC SHEET

## 1. Purpose

Prometheist is a local-first multi-agent system (MAS) built around a strict architectural invariant:

> **Every LLM invocation is stateless. Persistent continuity belongs to the system, not to any model context window.**

The Primary Agent is the top-level coordinator of that system. It should behave as a continuous, increasingly personalized intelligence from the user's perspective while remaining technically independent of any persistent LLM session, hidden transcript, or provider-specific conversation state.

Prometheist therefore separates three things that conventional assistants often blur together:

1. **LLM computation** — disposable inference workers;
2. **persistent system state** — authoritative history and derived memory maintained outside the LLM;
3. **just-in-time working context** — a bounded evidence packet reconstructed only when an agent needs it.

The central design equation is:

```text
Stateless LLM workers
        +
Authoritative persistent system history
        +
Just-in-time memory retrieval
        =
Continuous agent experience without persistent model context
```

The long-term objective is not merely a chatbot with recall. Prometheist is intended to become a persistent personal AI system whose continuity, identity, user model, preferences, relationships, obligations, projects, and accumulated experience can survive process restarts, conversation boundaries, model replacement, hardware migration, and long periods of time.

---

## 2. System-Wide Statelessness

Statelessness is not only a Primary Agent property.

**No LLM-backed agent in Prometheist may rely on retained context from a previous invocation.**

This applies to the Primary Agent and to future specialized agents such as planning, research, file, security, workflow, maintenance, or memory agents.

Each LLM call must be treated as disposable:

```text
new task / event / trigger
        |
        v
construct bounded working context
        |
        v
fresh LLM invocation
        |
        v
response / decision / action
        |
        v
persist resulting events
        |
        v
discard temporary LLM context
```

A single user interaction may require more than one fresh LLM call. That is acceptable. What is prohibited is treating any previous LLM context window as durable memory for the next call.

If an agent needs information that already exists inside Prometheist, it must obtain that information through the system's memory interfaces rather than by assuming that a previous model invocation still remembers it.

---

## 3. Primary Agent Role

The Primary Agent is the top-level cognitive coordinator and user-facing decision layer.

Its responsibilities should eventually include:

- interpreting the user's present request or current system event;
- determining whether additional internal memory is needed;
- determining whether external information or tools are needed;
- delegating bounded tasks to specialized agents or services;
- integrating returned evidence and tool results;
- deciding what action or response should follow;
- preserving alignment with the user's stated goals, preferences, values, permissions, and interests;
- maintaining continuity through retrieved system memory rather than persistent model state.

The Primary Agent should not become a monolith that directly implements every subsystem. It should orchestrate capabilities behind explicit interfaces.

The Primary Agent is also **not the exclusive consumer of memory**. Any specialized agent may need JIT memory to complete its own task. The memory subsystem is shared infrastructure for the MAS.

---

## 4. JIT Memory as Shared MAS Infrastructure

Prometheist's memory subsystem exists to reconstruct relevant internal context for any agent that needs it.

Conceptually:

```text
                 +------------------+
                 | authoritative     |
                 | event history     |
                 +---------+--------+
                           |
                           v
                 +------------------+
                 | derived memory    |
                 | projections       |
                 +---------+--------+
                           |
                           v
agent need ---> JIT Memory subsystem ---> bounded MemoryPacket
   ^                                      |
   |                                      v
   +------------------------------ fresh agent call
```

The calling agent should express **what it needs to know**. The memory subsystem should decide **how to retrieve the best supporting evidence**.

For example, an agent may ask for:

- the user's current preference on a subject;
- what happened immediately before a later state change;
- the original wording of a prior statement;
- whether an obligation was later resolved;
- relevant events involving a specific person, place, project, artifact, or concept;
- the most relevant evidence about a previously discussed issue;
- exact events from a specified time range or conversation.

The caller should not need to know whether the answer came from exact metadata, lexical indexes, entity routes, temporal structure, associations, future semantic retrieval, or another internal mechanism.

Retrieval strategy is an implementation detail behind a stable memory boundary.

---

## 5. Internal Memory vs. External Knowledge

Prometheist must distinguish between **system memory** and **outside information**.

System memory means information already stored inside Prometheist's persistent state, including prior user interactions, system events, tool results, artifacts, device observations, and other retained experience.

External knowledge means information that must be obtained from outside the system, for example:

- the current weather;
- a newly published article;
- a live market price;
- a website not previously ingested;
- current laws, schedules, availability, or news;
- information from an external account or service that has not yet been persisted.

The JIT memory subsystem retrieves **internal persisted data**. Web/API/tool connectors retrieve **external or currently authoritative outside data**.

Once meaningful external results become part of an interaction, those results should themselves be persisted as system events so they can later become internal memory with provenance.

---

## 6. Complete Persistence Is Mandatory

**Every meaningful event that occurs inside Prometheist must be persisted automatically.**

Persistence is application behavior, not an LLM decision.

At minimum, the event history should be capable of recording:

- user prompts and user-generated events;
- Primary Agent responses and decisions;
- specialized-agent requests and results;
- JIT memory requests and returned packets;
- tool calls and tool results;
- external/system/device-triggered events;
- files, artifacts, and references involved in an interaction;
- errors, retries, failures, cancellations, and important control events;
- deterministic execution metadata;
- future system telemetry that the user has authorized Prometheist to retain.

There should be no `remember_this`, `memory_assertion`, importance gate, or similar LLM-controlled mechanism deciding whether ordinary history survives.

If something meaningful happened, it belongs in the system history.

---

## 7. Authoritative History Must Be Append-Only

The authoritative autobiographical/event history is the source of truth.

Original events must be treated as append-only, non-destructive records. Later interpretation must not silently rewrite what originally happened.

Corrections should themselves be new events. If the user says a previous fact was wrong, the system should preserve both:

1. the original event showing what was previously stated; and
2. the later event correcting or superseding it.

This distinction is essential because Prometheist must support both:

- **historical truth** — what was actually said, observed, or recorded at a particular time; and
- **current state** — what the system should presently believe or use after later evidence or corrections.

Historical depth should not imply destructive summarization. The system should remain capable, in principle, of accurate recall from very old retained history with exact provenance.

---

## 8. Authoritative Evidence vs. Derived Memory

Prometheist already distinguishes authoritative events from rebuildable derived memory.

Authoritative state includes canonical source events.

Derived state may include:

- lexical projection entries;
- entity indexes;
- deterministic associations;
- integrity metadata;
- future summaries;
- extracted facts;
- inferred relationships;
- embeddings;
- user-model features;
- episodic groupings;
- importance or salience signals;
- consolidated memory structures.

Derived memory is an **optimization and interpretation layer**, not a replacement for source evidence.

Every derived item should, where applicable:

- retain provenance to source events;
- be versioned by derivation policy;
- be reproducible or rebuildable when deterministic;
- be disposable without destroying authoritative history;
- avoid being treated as more authoritative than the evidence from which it was derived.

The current Memory Kernel work demonstrates this principle with deterministic lexical projections, provenance-bearing associations, and integrity metadata.

---

## 9. Human-Like Recall, Machine-Level Fidelity

Prometheist's memory goal is not to imitate human forgetting or human inaccuracy.

The intended direction is:

> **human-like just-in-time recall dynamics combined with machine-level historical fidelity.**

A human generally does not carry every lifetime memory in conscious working context. Relevant memories are activated when needed. Prometheist should similarly avoid loading its entire history into every inference.

However, unlike biological memory, Prometheist's underlying event record should remain sufficiently precise that retrieved evidence can be checked against immutable source history.

The architecture should therefore optimize for:

- selective activation;
- bounded working context;
- precise source recovery;
- provenance;
- temporal depth;
- resistance to interference from irrelevant history;
- explicit abstention when the stored evidence does not support an answer.

---

## 10. Bounded MemoryPackets

JIT retrieval should return a bounded, structured evidence packet rather than an uncontrolled dump of historical text.

A MemoryPacket should provide enough information for the consuming agent to reason correctly while preserving source identity and retrieval traceability.

Depending on the task, it may include:

- canonical event content;
- event IDs;
- timestamps;
- sequence/order metadata;
- conversation or execution identifiers;
- provenance-bearing relationship information;
- retrieval scores or trace information;
- explicit indications that no supporting evidence was found.

The size of persistent history must not determine the size of an LLM context window.

Years of retained history should still permit a small, task-specific inference context.

---

## 11. Retrieval Policy

Retrieval should use the simplest mechanism that reliably satisfies the information need.

Preferred order of reasoning:

1. exact IDs or deterministic metadata when available;
2. structured temporal/conversation/source filters;
3. entity and lexical specificity routes;
4. deterministic association traversal where relationships have been derived;
5. other retrieval mechanisms only when measured failures justify them.

Do not add embeddings, vector search, graph databases, rerankers, or LLM-based retrieval layers merely because they are common in RAG systems.

The current v0.5 benchmark demonstrates perfect observed correctness through 50,000 events per persona with a fixed 500-event PostgreSQL candidate bound using deterministic lexical/entity/association routing. That result means additional retrieval machinery has not yet earned its complexity.

If future benchmarks expose failures that deterministic mechanisms cannot reasonably solve, add exactly one new mechanism, measure it against a frozen baseline, and keep it only if the evidence justifies the change.

---

## 12. Unknown-Fact Abstention

Topical similarity is not sufficient evidence.

The memory subsystem must distinguish between:

- evidence that supports the requested fact or relationship; and
- context that merely mentions the same general topic.

If the system has events about a vehicle but no evidence identifying the vehicle's insurer, a query asking who insures the vehicle should not return unrelated vehicle events as though they answered the question.

Broad matches may be useful internally for routing or association activation. They should not automatically be surfaced as final evidence.

When stored history does not support the requested fact, the correct retrieval result may be an empty or explicitly unsupported MemoryPacket.

---

## 13. Deterministic Application Ownership

Information that can be known exactly by ordinary software must be generated and controlled by ordinary software rather than by an LLM.

Examples include:

- event IDs;
- conversation IDs;
- correlation/execution IDs;
- timestamps;
- global and conversation sequence numbers;
- source/agent identifiers;
- schema versions;
- model/provider identifiers;
- retrieval limits and scopes;
- database operations;
- policy versions;
- deterministic association IDs;
- provenance links;
- integrity digests.

LLMs should be used for semantic interpretation, language generation, planning, or other tasks that genuinely require model reasoning.

Do not ask an LLM to manufacture system facts the application already knows exactly.

---

## 14. Structured Agent Communication

Inter-agent and agent-to-service communication should use explicit schemas wherever practical.

Use Pydantic models or equivalent strongly validated structures for:

- agent decisions;
- memory requests;
- memory packets;
- tool requests/results;
- task delegation;
- status/error events;
- future policy/permission decisions.

LLM control outputs should be narrow and constrained.

The original prototype used decisions such as:

```text
RESPOND_DIRECTLY
RETRIEVE_CONTEXT
```

Future MAS protocols may become richer, but the principle remains:

> give an LLM only the control authority it actually needs.

Natural-language user responses may remain free-form. System mechanics should not.

---

## 15. Provenance and Auditability

Prometheist must be able to explain where remembered information came from.

For a retrieved fact or event, the system should be able to identify relevant source-event IDs and ordering metadata. For derived relationships, it should preserve the source events and derivation policy that produced them.

This is important for:

- debugging;
- benchmark evaluation;
- historical verification;
- correcting stale interpretations;
- user trust;
- future security and policy checks;
- comparing different retrieval algorithms against the same evidence.

An answer that cannot be traced back to evidence should not be treated as equivalent to one that can.

---

## 16. Integrity and Historical Preservation

Prometheist should make silent historical mutation detectable.

The current Memory Kernel maintains hash-chain integrity metadata over authoritative events. Future storage changes should preserve the same principle even if the exact mechanism evolves.

Integrity verification should remain independent of semantic interpretation.

A later model, projection algorithm, or memory policy may reinterpret an event. It should not be able to rewrite the event undetectably.

---

## 17. Local-First and User-Controlled Architecture

Prometheist is intended to run primarily on hardware controlled by its user.

The architecture should favor:

- local PostgreSQL storage;
- local files/artifacts where practical;
- local inference through swappable model backends such as Ollama when feasible;
- minimal external dependencies;
- inspectable data formats;
- user-controlled retention and permissions;
- portability to inexpensive commodity hardware.

The system must not depend architecturally on a particular cloud LLM, hosted vector database, SaaS orchestration framework, or vendor-specific memory product.

External services may be used where explicitly useful or authorized, but the persistent identity and autobiographical history of Prometheist should remain under the user's control.

The long-term personal-system direction is that data generated by the user's own devices and activities should primarily benefit the user and their Prometheist system, not become an invisible third-party asset by default.

---

## 18. LLM Agnosticism

Foundation models are replaceable cognitive engines.

Prometheist should be able to switch between model families, sizes, providers, or local inference backends without redesigning its persistent-memory architecture.

No model should own the canonical identity of the system.

Model-specific adapters may exist, but the following must remain outside the model:

- persistent history;
- memory projections;
- identity continuity;
- deterministic metadata;
- permissions and policy state;
- provenance;
- durable task/workflow state.

A stronger future model should be able to inherit Prometheist's history through the same memory interfaces without requiring the old model's context window.

---

## 19. Commodity-Hardware Constraint

Prometheist should remain usable on modest hardware and should not assume datacenter-scale resources.

The current development environment includes a Windows laptop with approximately:

- Intel Core i5 quad-core CPU with Hyper-Threading;
- 16 GB RAM;
- 1 TB NVMe SSD;
- integrated Intel graphics;
- no dedicated GPU.

The architecture should therefore favor bounded retrieval, indexed storage, incremental/rebuildable projections, and lightweight deterministic mechanisms before computationally expensive alternatives.

Hardware constraints are not temporary inconveniences. They are useful design pressure toward an efficient local-first system.

---

## 20. Simplicity and Evidence-Driven Complexity

Prometheist should remain understandable to a single human developer.

Do not prematurely introduce:

- Neo4j;
- Temporal;
- LangChain;
- LangGraph;
- CrewAI;
- AutoGen;
- dedicated vector databases;
- multiple overlapping databases;
- Docker as an architectural dependency;
- Kubernetes;
- Redis;
- Kafka;
- distributed microservices;
- elaborate orchestration frameworks;
- unnecessary API servers;
- unnecessary abstraction layers.

These tools are not prohibited forever. They must solve a demonstrated problem before being added.

The experimental rule is:

> **Freeze a measurable baseline, add exactly one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**

This rule should apply to memory mechanisms, agent architecture, dependencies, infrastructure, and performance optimizations.

---

## 21. Current Verified Memory Baseline

As of Memory Kernel v0.5, Prometheist has demonstrated:

- append-only canonical event persistence;
- deterministic event ordering;
- cross-conversation and cross-process recall;
- deterministic lexical/entity/temporal/conversation scoring;
- bounded MemoryPackets;
- rebuildable lexical projections;
- provenance-bearing deterministic associations;
- association-derived prior-state, resolution, concept-instance, and disposition routing;
- support-aware evidence admission and unknown-fact abstention;
- bounded PostgreSQL candidate routing by specificity;
- integrity metadata and rebuild verification;
- perfect observed benchmark correctness through 50,000 events per synthetic persona at a fixed 500-event PostgreSQL candidate bound.

This is a research baseline, not proof of general intelligence or universal memory correctness.

The purpose of preserving this baseline is to prevent future architecture changes from being justified only by intuition.

---

## 22. Future Multi-Agent Direction

Prometheist may eventually contain specialized agents or services for:

- JIT memory retrieval;
- planning;
- file/artifact management;
- ingestion;
- external research;
- software/tool execution;
- workflows;
- security and permission enforcement;
- contract/policy analysis;
- device telemetry interpretation;
- memory maintenance and consolidation;
- long-running or scheduled tasks;
- resource management;
- self-diagnostics and maintenance.

Every LLM-backed specialist remains stateless between calls.

A specialist that requires historical system data should request JIT memory rather than asking the Primary Agent to carry a large transcript on its behalf.

This avoids recreating a giant shared context window at the MAS level.

The desired architecture is therefore not:

```text
one huge Primary Agent context
        |
        +--> many tools
```

It is closer to:

```text
                    persistent system state
                             |
                             v
                    JIT memory subsystem
                      /      |      \
                     v       v       v
              Primary     Agent A   Agent B
              Agent          |        |
                 \           |       /
                  \----------+------/
                             |
                         tools/actions
```

Each cognitive worker receives only the internal memory and external evidence needed for its current bounded task.

---

## 23. Long-Term Personal Identity Direction

Prometheist is intended to become more than a task assistant.

Its long-term direction is a persistent digital representative whose behavior becomes increasingly aligned with the user's accumulated preferences, values, relationships, goals, history, and decision patterns.

That continuity should emerge from retained evidence and explicit system state, not from pretending that one particular LLM instance has an uninterrupted consciousness.

The architecture should make it possible for the system to become a durable personal digital counterpart while remaining:

- evidence-grounded;
- inspectable;
- correctable;
- portable;
- model-independent;
- user-controlled.

This direction is aspirational. Current milestones should implement only the mechanisms needed to test the next concrete architectural hypothesis.

---

## 24. Safety, Permissions, and User Agency

As Prometheist gains tools and autonomy, user-controlled permissions must remain first-class system state.

Agents should not infer durable authority merely from past model behavior or conversational momentum.

Future capabilities that can modify external systems, share personal data, spend resources, accept terms, communicate with third parties, or perform consequential actions should operate through explicit policy and permission boundaries.

These permissions should be persistent, auditable, and independent of any single LLM context.

The user's data should not be disclosed or used for third-party benefit merely because an agent can technically access it.

---

## 25. Implementation Guidance for GitHub Copilot

Use this document as the high-level architecture contract for Prometheist.

When implementing changes:

- treat **all LLM calls** as stateless across invocations;
- never rely on hidden or accumulated chat context for durable continuity;
- persist every meaningful event automatically;
- preserve authoritative events append-only;
- represent corrections and superseding information as new events;
- keep derived memory disposable, versioned, provenance-bearing, and rebuildable;
- make JIT memory available to every agent that needs internal system data;
- keep internal memory retrieval distinct from external web/API/tool retrieval;
- return bounded, structured evidence packets rather than uncontrolled history dumps;
- prefer deterministic exact/structured retrieval when it can answer reliably;
- preserve unknown-fact abstention rather than surfacing merely topical context as evidence;
- generate deterministic metadata in ordinary application code;
- constrain structured LLM outputs with Pydantic or equivalent schemas;
- keep model/provider interfaces replaceable;
- favor local-first operation and modest hardware requirements;
- preserve provenance and integrity verification;
- avoid introducing a new framework, database, service, model layer, or retrieval mechanism without a demonstrated failure that justifies it;
- add regression tests before or alongside fixes for discovered failure modes;
- compare architectural changes against frozen benchmarks whenever practical;
- keep the complete control flow understandable to one developer.

When a design choice is ambiguous, prefer:

> **simplicity, inspectability, deterministic behavior, user control, complete historical preservation, explicit provenance, bounded working context, and evidence-driven complexity.**
