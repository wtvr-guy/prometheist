# Prometheist Roadmap to v1.0

This roadmap describes the engineering path from the verified Memory Kernel and stateless-worker baselines to the first complete attention-centric Prometheist architecture.

Version numbers represent architectural milestones, not package-release versions. Each milestone begins from a measurable question and should preserve previously verified invariants unless new evidence justifies changing them.

## Experimental rule

> **Freeze a measurable baseline, add exactly one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**

This applies to memory, attention, perception, retention, execution, infrastructure, model integration, and performance optimization.

## Architectural pivot — 2026-08-24

v0.5 and v0.6 remain accepted historical baselines. Beginning with v0.7, Prometheist no longer treats a privileged Primary Agent or a fixed multi-agent hierarchy as the target architecture.

The target is now a persistent cognitive system in which:

- identity, memory, tasks, attention, policy, and execution state belong to the system;
- LLM invocations and worker processes are disposable;
- JIT Memory is one capability among many;
- deterministic attention allocates durable work to bounded execution resources;
- continuous external input is filtered through perception, salience, and retention policy before becoming durable cognition;
- named agents may exist as temporary worker roles, but they are not first-class owners of continuity or executive authority.

See [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) and [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md).

---

## v0.5 — Deterministic memory robustness and scale

**Status:** accepted and frozen.

Question:

> Can deterministic JIT memory preserve bounded, provenance-bearing recall and abstention under competing states, lifecycle changes, lexical interference, and 50,000-event histories?

Accepted result:

- deterministic association activation repaired under interference;
- support-aware evidence admission separated from broad activation;
- bounded PostgreSQL candidate routing made specificity-aware;
- 10k and 50k PostgreSQL scale suites reached perfect observed benchmark metrics at a fixed 500-event candidate limit;
- closure-audit regressions for temporal boundaries, source-type candidate filtering, and pytest isolation were repaired and verified;
- no measured failure justified embeddings or another retrieval subsystem.

See [`milestones/v0.5/README.md`](milestones/v0.5/README.md).

---

## v0.6 — Shared JIT Memory and stateless worker composition

**Status:** accepted and closed on 2026-08-21.

Historical question:

> Can multiple completely stateless LLM-backed components behave as parts of one continuous system by obtaining persistent internal context through the same JIT Memory subsystem?

Accepted result:

- defined a stable `MemoryNeed` / `MemoryPacket` boundary independent of retrieval implementation;
- placed the verified v0.5 Memory Kernel behind that shared boundary;
- demonstrated fresh Primary and specialist model calls obtaining persistent internal context without inherited transcripts;
- persisted delegations, results, memory requests, memory packets, failures, and correlation metadata;
- preserved bounded evidence, exact source-event provenance, and unknown-fact abstention;
- reran the v0.5 regression baseline unchanged and kept it green.

Architectural interpretation after the 2026-08-24 pivot:

v0.6 remains valid evidence that disposable stateless workers can participate in one continuous persistent system. The Primary/specialist arrangement used to prove that result is no longer the intended permanent executive structure.

See [`milestones/v0.6/README.md`](milestones/v0.6/README.md).

---

## v0.7 — Durable JIT Attention Fabric

**Status:** in development.

Primary question:

> Can Prometheist deterministically allocate durable work across bounded concurrent execution resources, survive destruction of every worker process, and resume without any privileged Primary Agent or persistent LLM context?

The first v0.7 increment establishes a deterministic single-focus scheduler kernel with durable PostgreSQL task/checkpoint state, priority derivation, service guarantees, interruption policies, dependency gating, deterministic transition IDs, and forced-process restart recovery.

Increment B adds explicit durable execution-resource definitions and task resource requirements. The next step is to generalize that substrate into a resource-aware concurrent **Attention Fabric**.

The architecture now explicitly distinguishes attention from resource admission:

> **Attention determines which durable tasks deserve execution. Resource admission determines which compatible subset can safely execute concurrently on the available hardware.**

A higher-priority task does not automatically preempt lower-priority work. If sufficient safe capacity exists, both should execute concurrently. Preemption is considered only when resource contention prevents admission of higher-priority work and interruption policy permits lower-priority work to yield.

Primary deliverables:

- durable task/execution state outside all LLM and worker contexts;
- structured task lifecycle and checkpoint events;
- deterministic priority derived from structured metadata;
- explicit service guarantees;
- `PREEMPTIBLE`, `CHECKPOINT_ONLY`, and `ATOMIC` interruption policies;
- deterministic dependencies and eligibility;
- explicit execution-resource classes and capacities;
- explicit safe-capacity/headroom policy rather than assuming all installed hardware is schedulable;
- deterministic task resource requirements and reservations;
- deterministic concurrent resource admission;
- deterministic scheduling epochs;
- durable assignment identities, with discrete lanes/slots only where a resource contract naturally requires them;
- atomic assignment/reservation persistence before worker execution;
- contention-driven preemption that releases only the resources actually required by higher-priority work;
- resumable stateless worker protocol;
- idempotent or explicitly retry-safe capability boundaries where required;
- deliberate process-kill/restart acceptance tests;
- removal of the Primary Agent as an architectural requirement.

Resource capacity must be abstracted from raw CPU thread count. A system may expose separate capacities for CPU work, local LLM inference, database work, filesystem I/O, network I/O, GPU work, device I/O, actuators, or later quantitative dimensions such as RAM/VRAM when measured requirements justify them.

Installed capacity is not identical to schedulable capacity. The system must reserve explicit safety headroom for the operating system and required services.

Determinism applies given the same authoritative task state, resource snapshot, and policy version. Runtime hardware measurements may become deterministic policy inputs, but untracked worker/OS races must never become scheduling authority.

Acceptance demonstration:

1. Several durable tasks become runnable with different priorities, dependencies, resource requirements, and interruption policies.
2. The Attention Fabric deterministically admits as many compatible tasks concurrently as the safe resource envelope permits.
3. Higher-priority work starts without preemption when sufficient capacity exists.
4. When higher-priority work cannot be admitted, only the minimum necessary compatible lower-priority work yields, and only where interruption policy permits.
5. Intermediate checkpoints, resource reservations, and assignments are persisted atomically.
6. Every worker process is killed without graceful shutdown.
7. Fresh processes reconstruct authoritative task/resource/assignment state from PostgreSQL.
8. Work resumes from committed checkpoints without duplicate side effects.
9. The final result is correct without any inherited LLM or worker context.
10. Deterministic CI tests and real development-machine resource-sensitive acceptance both pass for the behavior each is intended to verify.

Critical invariant:

> **Scheduling decisions belong to persistent deterministic system policy; workers execute admitted assignments but do not own system attention or resource-allocation authority.**

See [`milestones/v0.7/README.md`](milestones/v0.7/README.md), [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md), and [`milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md).

---

## v0.8 — Deterministic perception and salience

Primary question:

> Can Prometheist continuously receive heterogeneous external observations, cheaply identify what might matter, and produce appropriate reflex, orienting, deliberate, or ignore dispositions without requiring an LLM to inspect every input?

Primary deliverables:

- normalized `Percept` contract;
- pluggable source/sensor adapters;
- bounded ephemeral source buffers;
- deterministic modality-specific anomaly detection where feasible;
- structured salience dimensions including threat, opportunity, goal relevance, novelty, uncertainty, and system-integrity relevance;
- deterministic salience classes and policy rules;
- temporal/cross-source situation assembly;
- explicit `REFLEX`, `ORIENT`, `DELIBERATE`, and `IGNORE` dispositions;
- deterministic task formation from situations;
- bounded pre-authorized reflex actions that do not wait for an LLM;
- optional stateless semantic-classification capability for ambiguous cases;
- strict separation between model interpretation and scheduling/action authority.

A highly salient observation must not automatically be treated as a known emergency. For example, a sudden loud impulse may trigger immediate orientation while its cause remains unknown. If the cause proves benign, the orientation task completes and previously suspended work resumes.

Acceptance demonstration:

Replay an identical deterministic stream containing large volumes of mundane observations, routine anomalies, benign high-salience events, genuine urgent conditions, and time-sensitive opportunities. Repeated runs must produce identical deterministic percept classifications, situation boundaries, task-formation decisions, attention demands, and reflex decisions.

Model-assisted semantic interpretation is tested separately from the deterministic policy baseline.

---

## v0.9 — Deterministic retention and memory admission

Primary question:

> Can Prometheist avoid permanently storing useless external data while preserving all information required for future cognition, evidence, provenance, and explanation of its own behavior?

The earlier blanket intuition to persist every incoming datum indefinitely does not scale to continuous sensors and high-volume external telemetry.

Prometheist now distinguishes:

- **ephemeral raw experience** — bounded rolling input that may never become durable;
- **observational memory** — external information retained according to explicit deterministic policy;
- **internal history** — system-internal causal state that is durable by default when needed to explain cognition, attention, decisions, commitments, or actions.

Primary deliverables:

- explicit retention contracts and policy versions;
- retention classes such as `R0 EPHEMERAL`, `R1 TEMPORARY`, `R2 DERIVED_ONLY`, `R3 EVENT`, `R4 EVIDENCE`, and `R5 PROTECTED`;
- deterministic TTL/correlation windows;
- bounded ring buffers for raw high-volume input;
- promotion of pre-event/post-event buffered context around salient situations;
- deterministic raw-to-derived aggregation or summarization paths;
- reference protection so evidence needed by durable tasks, policies, or provenance cannot expire;
- durable retention decisions even when underlying raw data expires;
- user-configurable retention overrides and permissions;
- optional model-generated retention proposals with no unilateral deletion authority;
- deterministic storage-pressure behavior.

Core invariant:

> **Anything that materially influences Prometheist's attention, reasoning, decisions, commitments, or actions must leave enough durable provenance to explain that behavior later.**

Acceptance demonstration:

Feed a large reproducible external-data stream through the system. Verify that repetitive low-value data expires, useful aggregates survive, context around significant events is promoted, referenced evidence cannot be discarded, every expiration is attributable to an explicit policy decision, and retained state remains sufficient to explain all observed Prometheist behavior.

---

## v0.10 — Memory generalization and failure discovery

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
- episodic/event grouping;
- interaction between durable internal history and selectively retained observational memory.

This remains the milestone where semantic/vector retrieval may earn an experiment.

```text
freeze deterministic failure
        |
        v
add one semantic mechanism
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

The milestone is not defined as "add pgvector." It is defined as discovering and repairing measured memory-generalization failures while preserving boundedness, provenance, and explicit abstention.

---

## v0.11 — Integrated persistent cognitive loop

Primary question:

> Can perception, retention, memory, attention, capabilities, and disposable cognition operate as one continuous system even though no worker or LLM invocation itself possesses continuity?

Primary deliverables:

- integrated control loop:

```text
perceive
  -> classify salience
  -> retain / buffer / discard according to policy
  -> assemble situation
  -> form durable task
  -> allocate attention + resource reservation
  -> invoke capabilities
  -> request JIT Memory only when required
  -> reason and/or act
  -> persist internal result
  -> perceive resulting state
```

- no privileged Primary Agent;
- no required persistent agent identities;
- stateless reasoning/semantic workers;
- stable capability invocation contracts;
- bounded task-local context construction;
- JIT Memory as demand-driven capability rather than eager universal context injection;
- causal/provenance linkage from observation through task formation, attention, capability use, action, and outcome;
- child/nested tasks and dependency chains;
- concurrent resource-admitted workflows;
- orienting tasks that can interrupt eligible work when contention requires it and return attention/resources after benign resolution;
- opportunity-triggered as well as threat-triggered attention;
- model/backend replacement during unfinished workflows.

Acceptance demonstrations should include at least:

1. a background task interrupted by a high-salience ambiguous observation when required by resource contention, followed by investigation, benign resolution, and exact resumption;
2. a time-limited high-value opportunity that deterministically outranks lower-value work, executes concurrently when possible, and otherwise receives the resources policy allows it to claim;
3. a model-backed workflow whose worker/model is destroyed and replaced between durable steps without loss of task identity or historical context.

---

## v0.12 — Operational hardening and portability

Primary question:

> Is the complete architecture robust enough to trust as persistent personal infrastructure rather than as a research prototype?

Primary deliverables should include the subset justified by the architecture at that point:

- explicit schema migration strategy;
- backup and restore;
- export/import and machine migration;
- crash recovery;
- database-enforced protection of authoritative internal history;
- integrity/threat-model hardening;
- permission and sensitive-data controls;
- structured operational logging;
- deterministic startup/recovery behavior;
- model/backend replacement tests;
- reproducible installation;
- performance profiling and bounded resource behavior;
- assignment/reservation lease and recovery semantics;
- starvation and deadlock tests;
- priority-inversion handling where required;
- resource oversubscription protection;
- capability timeout/retry semantics;
- sensor/source failure behavior;
- retention-policy corruption detection;
- protected-evidence guarantees;
- deterministic recovery from partial scheduling epochs.

Critical portability test:

Move Prometheist from Machine A to Machine B with different available execution resources and a different compatible LLM backend. The system must retain the same authoritative internal history, retained evidence, durable tasks, checkpoints, and causal provenance while adapting its Attention Fabric safe-capacity policy and concurrent admission to the new hardware.

---

## v1.0 — First complete Prometheist cognitive architecture

v1.0 does not mean the ultimate digital-representative vision is complete.

It means:

> **Prometheist is a coherent, local-first, model-agnostic persistent cognitive system in which perception, memory, attention, policy, and execution state remain system-owned while all model invocations and workers are disposable.**

A defensible v1.0 should demonstrate:

- every LLM invocation is stateless across separate calls;
- no Primary Agent is required for continuity or executive control;
- persistent identity belongs to the system;
- internal cognitive/execution history is durable by default;
- external observations pass through explicit deterministic retention policy;
- discarded external information is discarded deliberately rather than accidentally;
- JIT Memory supplies historical internal information on demand;
- retrieved evidence remains bounded and provenance-bearing;
- unknown facts can be explicitly unsupported rather than hallucinated from topical similarity;
- deterministic salience determines what observations warrant evaluation;
- deterministic task formation converts relevant situations into durable intentions;
- deterministic executive attention ranks those intentions while deterministic resource admission allocates bounded concurrent capacity;
- service guarantees and interruption policies coexist;
- urgent observations can orient the system and interrupt eligible work when resource contention actually requires it;
- safe noninterruptible work remains noninterruptible under normal scheduler authority;
- benign interruptions resolve and prior work resumes;
- opportunities can compete for attention as well as threats;
- multiple assignments execute concurrently without race-based scheduling semantics or unsafe resource oversubscription;
- every worker can be destroyed and replaced;
- model backends can be replaced;
- derived memory can be rebuilt without rewriting retained source evidence;
- the system can be backed up, restored, and migrated;
- critical historical mutations are prevented or detectably outside the accepted threat model;
- the system remains usable on modest local hardware;
- the full deterministic and model-backed acceptance suites are reproducible.

The defining v1.0 invariant is:

> **You can terminate every LLM and worker process, replace the model, restart Prometheist, and the system still retains its durable identity, internal history, unfinished intentions, attention state, retained evidence, and causal provenance because none of those things belonged to an agent or model context in the first place.**

---

## Beyond v1.0

Only after the core architecture is stable should Prometheist expand aggressively toward the longer-term personal-system vision, including:

- deeper user/personality/value modeling;
- richer user-controlled device and environmental telemetry;
- privacy/security representation on the user's behalf;
- contract/TOS/privacy-policy analysis and decision support;
- proactive opportunity discovery aligned with user goals;
- increasingly autonomous but permission-bounded personal representation;
- purpose-built mobile/device integration.

Those capabilities increase the consequences of perception, retention, memory, attention, identity, and policy errors. They should sit on top of a stable v1.0 foundation rather than defining it prematurely.
