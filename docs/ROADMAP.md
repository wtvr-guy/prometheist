# Prometheist Roadmap to v1.0

This roadmap describes the engineering path from the verified Memory Kernel research baseline to the first complete implementation of the Prometheist architecture.

Version numbers represent architectural milestones, not a promise to add one fashionable AI technique per release. Each milestone should begin from a specific measurable question and preserve previously verified invariants unless evidence justifies changing them.

## Experimental rule

> **Freeze a measurable baseline, add exactly one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**

This applies to memory, agent orchestration, infrastructure, dependencies, performance optimizations, and model integration.

---

## v0.5 — Deterministic memory robustness and scale

**Status:** accepted and frozen.

Question:

> Can deterministic JIT memory preserve bounded, provenance-bearing recall and abstention under competing states, lifecycle changes, lexical interference, and 50,000-event histories?

Result:

- deterministic association activation repaired under interference;
- support-aware evidence admission separated from broad activation;
- bounded PostgreSQL candidate routing made specificity-aware;
- 10k and 50k PostgreSQL scale suites reached perfect observed benchmark metrics at a fixed 500-event candidate limit;
- closure-audit regressions for temporal boundaries, source-type candidate filtering, and pytest isolation were repaired and verified;
- no measured failure justified embeddings or another retrieval subsystem.

See [`milestones/v0.5/README.md`](milestones/v0.5/README.md).

---

## v0.6 — Shared JIT Memory Interface and Stateless Multi-Agent Execution

**Status:** accepted and closed on 2026-08-21.

Primary question:

> Can multiple completely stateless agents behave as components of one continuous system by obtaining all persistent internal context through the same JIT Memory subsystem?

Accepted result:

- defined a stable `MemoryNeed` / `MemoryPacket` contract independent of retrieval implementation;
- placed the verified v0.5 Memory Kernel behind the shared JIT Memory boundary;
- migrated the live Primary Agent to that boundary;
- added the stateless LLM-backed `memory_specialist`;
- allowed the Primary Agent and specialist to request JIT memory independently;
- persisted agent delegations, agent results, memory requests, memory packets, failures, and correlation metadata;
- distinguished internal persisted-memory retrieval from future external web/API/tool acquisition;
- proved cross-agent and cross-process recall with fresh LLM invocations;
- preserved bounded evidence, exact source-event provenance, and unknown-fact abstention;
- added canonical-first user-query handling with bounded supplemental classifier cues after canonical abstention;
- post-closure revalidation proved four-turn conversational continuity across
  fresh processes while combining same-conversation context with older
  cross-conversation facts and exact source-event provenance;
- reran the v0.5 regression baseline unchanged and kept it green;
- passed the complete local pytest suite with PostgreSQL and Ollama available.

Acceptance demonstration:

1. An event is persisted in one interaction/process.
2. That process/context is discarded.
3. A later fresh Primary Agent invocation delegates a task to a specialist.
4. The specialist receives no hidden transcript.
5. The specialist independently requests the relevant persisted history through JIT Memory.
6. The specialist returns a useful result grounded in the retrieved packet.
7. The Primary Agent exposes the specialist result to the user through the same persisted interaction chain.
8. The entire causal chain is recoverable from persistent events.

No failure in the original 2026-08-21 closure justified embeddings or another
retrieval subsystem. Later work on the v0.6 capability-registry branch added a
strictly candidate-only Ollama/pgvector recovery route for lexically weak cues;
it runs only after deterministic abstention and cannot promote similarity to
supported evidence. This post-closure extension is recorded separately rather
than rewriting the original causal conclusion.

See [`milestones/v0.6/README.md`](milestones/v0.6/README.md) and the dated
[`conversation-continuity validation`](milestones/v0.6/experiments/V06_CONVERSATION_CONTINUITY_RESULT_2026-08-24.md).

---

## v0.7 — Durable execution and restartable orchestration

**Status:** next milestone.

Primary question:

> Can Prometheist preserve unfinished work, intentions, task state, and multi-agent handoffs without keeping an LLM context alive?

Primary deliverables:

- explicit durable task/execution state outside LLM context;
- structured task lifecycle events;
- resumable agent workflows;
- persisted step results and handoffs;
- deterministic correlation/execution identifiers;
- idempotent or explicitly retry-safe orchestration where required;
- deliberate process-kill/restart acceptance tests.

Acceptance demonstration:

A multi-step/multi-agent task is interrupted after an intermediate result, all LLM/process state is destroyed, Prometheist restarts, reconstructs task state from persistent system data, and resumes correctly with fresh LLM calls.

---

## v0.8 — Memory generalization and failure discovery

Primary question:

> Where does the deterministic memory architecture actually fail when recall becomes semantically, temporally, and relationally harder than the v0.5 synthetic scale benchmark?

Candidate benchmark domains:

- zero-keyword-overlap paraphrases;
- aliases and changing entity names;
- facts distributed across multiple events;
- contradictory reports from different sources;
- corrections and supersession;
- historical belief versus current belief;
- longer temporal/causal chains;
- dense ambiguous association graphs;
- artifact/file references across long periods;
- larger histories and more heterogeneous event types;
- episodic/event grouping.

The bounded, candidate-only pgvector route introduced during the later v0.6 work
is the baseline here, not a conclusion that semantic retrieval is justified. The
correct sequence is:

```text
freeze a deterministic-first failure
        |
        v
evaluate or change one bounded semantic mechanism
        |
        v
rerun identical benchmark
        |
        v
measure recall + precision + abstention + latency
        |
        v
keep or reject
```

The milestone is not defined as “add pgvector” or as automatically retaining the
existing route. It is defined as discovering and repairing measured
memory-generalization failures while preserving provenance and boundedness, then
keeping, retuning, or rejecting the semantic route according to the frozen
measurements.

---

## v0.9 — Operational hardening and portability

Primary question:

> Is the complete system robust enough to trust as persistent personal infrastructure rather than as a research prototype?

Primary deliverables should include the subset justified by the architecture at that point:

- explicit schema migration strategy;
- backup and restore;
- export/import and machine migration;
- crash recovery;
- database-enforced protection of authoritative history;
- integrity/threat-model hardening;
- retention and permission controls;
- sensitive-data handling;
- structured operational logging;
- deterministic startup/recovery behavior;
- model/backend replacement tests;
- reproducible installation;
- automated regression strategy appropriate to local PostgreSQL dependencies;
- performance profiling and bounded resource behavior.

Critical portability test:

Prometheist history is moved from Machine A to Machine B, a different compatible LLM backend is selected, and the system retains the same authoritative history, durable work state, and memory behavior without access to the previous model's context.

---

## v1.0 — First complete Prometheist architecture

v1.0 should not mean that the ultimate “digital doppelgänger” vision is finished.

It should mean:

> **Prometheist is a coherent, local-first, model-agnostic multi-agent system whose persistent identity, history, work state, and JIT memory remain outside all LLM context windows.**

A defensible v1.0 should demonstrate:

- every LLM invocation is stateless across separate calls;
- multiple agents can coordinate through structured persistent state;
- all agents use the same shared JIT Memory boundary for internal historical context;
- authoritative events remain user-controlled and provenance-bearing;
- derived memory can be rebuilt without rewriting source history;
- unknown facts can be explicitly unsupported rather than hallucinated from topical similarity;
- durable tasks survive process interruption;
- the system survives model/backend replacement;
- the system can be backed up, restored, and migrated;
- critical historical mutations are prevented or detectably outside the accepted threat model;
- the system remains usable on modest local hardware;
- the full regression/acceptance suite is reproducible.

The defining v1.0 invariant is:

> You can terminate every LLM process, replace the model, restart Prometheist, and the system still knows what happened, what it was doing, and where its evidence came from because none of those things belonged to an LLM context window.

---

## Beyond v1.0

Only after the core architecture is stable should Prometheist expand aggressively toward the longer-term personal-system vision, including:

- deeper user/personality/value modeling;
- richer device and environmental telemetry under user control;
- privacy/security representation on the user's behalf;
- contract/TOS/privacy-policy analysis and decision support;
- proactive opportunity discovery aligned with user goals;
- increasingly autonomous but permission-bounded personal representation;
- purpose-built mobile/device integration.

Those capabilities increase the consequences of memory, identity, and policy errors. They should sit on top of a stable v1.0 foundation rather than being used to define it.
