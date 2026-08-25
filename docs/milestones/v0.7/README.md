# Prometheist v0.7 — Durable JIT Attention Fabric

**Status:** in development.

v0.7 is the first milestone after the 2026-08-24 architectural pivot from a privileged Primary Agent / fixed multi-agent hierarchy toward an attention-centric persistent cognitive system.

The accepted v0.6 result remains important: multiple fresh stateless LLM calls can participate in one continuous system through shared JIT Memory and durable system state. v0.7 generalizes that result by moving executive control out of any agent and into deterministic persistent attention state.

The post-pivot branch comparison is recorded in [`V06_INTEGRATION_INVENTORY_2026-08-25.md`](V06_INTEGRATION_INVENTORY_2026-08-25.md). That inventory is authoritative for what should be preserved, adapted, or left historical from the divergent `v0.6-capability-registry` branch. In particular, do not merge that branch wholesale into v0.7: preserve its behavioral evidence, adapt reusable mechanisms such as deterministic capability discovery, and leave Primary-Agent orchestration and premature semantic/vector dependencies historical until their roadmap milestones justify them.

See:

- [`../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [`../../architecture/COGNITIVE_ARCHITECTURE.md`](../../architecture/COGNITIVE_ARCHITECTURE.md)
- [`../../architecture/INTERACTION_CONTINUITY.md`](../../architecture/INTERACTION_CONTINUITY.md)
- [`V06_INTEGRATION_INVENTORY_2026-08-25.md`](V06_INTEGRATION_INVENTORY_2026-08-25.md)
- [`JIT_ATTENTION_DESIGN.md`](JIT_ATTENTION_DESIGN.md)
- [`RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md)

## Primary question

> Can Prometheist deterministically allocate durable work across bounded concurrent execution resources, survive destruction of every worker process, and resume without any privileged Primary Agent or persistent LLM context?

## What is already implemented

### Increment A — deterministic single-focus kernel

The first v0.7 increment introduced a deterministic single-focus scheduler kernel and PostgreSQL durability layer.

Implemented/tested properties include:

- structured task scheduling metadata;
- deterministic P0-P5 priority derivation from criticality;
- total queue ordering;
- service guarantees expressed in scheduler cycles;
- `PREEMPTIBLE`, `CHECKPOINT_ONLY`, and `ATOMIC` interruption policies;
- dependency gating;
- deterministic task and transition IDs;
- durable task snapshots;
- durable scheduler focus/pending-preemption state;
- resumable task state;
- restart reconstruction from PostgreSQL;
- lifecycle persistence idempotency;
- deterministic replay equivalence;
- forced Python-process destruction followed by reconstruction/resumption in a fresh process.

This proves that unfinished work can belong to persistent system state rather than the lifetime of a Python process or LLM context.

### Increment B — explicit execution resources

The second v0.7 increment introduced explicit durable execution-resource state.

Implemented/tested properties include:

- explicit `ExecutionResourceClass` values for `CPU_GENERAL`, `LLM_INFERENCE`, `DATABASE`, `FILESYSTEM_IO`, and `NETWORK_IO`;
- durable `ExecutionResource` definitions with stable resource ids, explicit capacity, enabled/disabled state, and metadata;
- deterministic resource ordering independent of configuration order;
- resource-class requirements in task scheduling metadata;
- resource-gated runnability: tasks remain durably `QUEUED` until every required resource class has enabled capacity;
- disabled resources do not make tasks runnable;
- stable resource identity cannot silently change class;
- PostgreSQL persistence/restart reconstruction for resource definitions and task requirements;
- idempotent schema evolution for existing local v0.7 databases.

GitHub Actions run #78 verified the Increment B head with PostgreSQL 16: `99 passed, 4 skipped in 12.39s`.

That CI result verifies the deterministic test environment. Resource-sensitive behavior on the intended development machine still requires separate local acceptance before it is considered verified against real hardware.

### Increment C — deterministic resource admission and reservations

The third v0.7 increment introduces quantitative configured admission without yet pretending that an admission is a worker assignment.

Implemented/tested properties include:

- positive integer `ResourceRequirement` units per resource class;
- backward-compatible interpretation of Increment B class-only requirements as one unit;
- explicit per-resource `system_headroom` that ordinary work cannot reserve;
- deterministic all-or-nothing admission in attention order;
- deterministic splitting across ordered fungible pools of the same resource class;
- stable task/resource reservation identities;
- an explicit `v0.7-c-greedy-v1` admission-policy version;
- concurrent admission of higher- and lower-priority work whenever both fit safely;
- rejection without partial reservation when any part of a task's resource contract does not fit;
- preservation of the current single-focus task until contention-driven preemption is implemented;
- authoritative admitted-task and resource-reservation state in scheduler snapshots;
- PostgreSQL persistence/restart reconstruction of headroom, quantitative requirements, policy version, admitted task ids, and reservations;
- atomic replacement of each scheduler's complete reservation set;
- invalidation of stale admission state whenever task, cycle, or resource state changes;
- restart validation that rejects unknown, mismatched, incomplete, nondeterministic, or oversubscribed reservations.

The database-independent Increment C suite passes locally (`28 passed, 2 deselected`). GitHub Actions run #99 verified the complete Increment C head with PostgreSQL 16: `112 passed, 4 skipped in 10.39s`.

Increment C does **not** mark several tasks `RUNNING`, create worker-visible assignments, or implement contention-driven interruption. It proves the deterministic safe-capacity decision and makes that decision durable. Increment D will convert an admitted set into atomic scheduling-epoch assignments.

## Attention and resource admission are separate

After Increment B, the next design distinction became explicit:

> **Attention decides which durable tasks deserve execution. Resource admission decides which of those tasks can safely execute concurrently on the available hardware.**

A higher-priority task does not automatically preempt lower-priority work. If sufficient safe capacity exists, both should run concurrently.

Preemption is considered only when higher-priority work cannot be admitted because currently running work occupies resources it needs. Even then, `PREEMPTIBLE`, `CHECKPOINT_ONLY`, and `ATOMIC` interruption policy remains authoritative.

Fixed lanes are therefore not the universal hardware abstraction. Discrete lanes may still be useful for naturally slot-like resources such as a local-model inference backend or bounded worker pool, but quantitative reservation/admission is the core model for CPU, memory, and mixed resource demands.

See [`RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) for the complete decision.

## Implementation sequence

### Increment A — freeze the single-focus kernel

**Status:** implemented and retained as a regression baseline.

Do not weaken:

- deterministic priority derivation;
- same-priority non-preemption;
- service guarantees;
- interruption safety;
- dependency gating;
- deterministic transition IDs;
- snapshot/restart equivalence;
- forced-process recovery.

### Increment B — explicit execution resources

**Status:** implemented and verified in CI.

Resource definitions are durable and deterministically ordered. Tasks may declare resource-class requirements, and unsupported/disabled requirements keep those tasks queued.

This increment intentionally stops short of quantitative reservation, concurrency allocation, or worker assignment.

### Increment C — deterministic resource admission and reservations

**Status:** implemented and verified in CI.

Introduce the smallest resource-allocation mechanism that can answer:

> Given the runnable tasks, their priority/interruption metadata, and an authoritative safe resource snapshot, which compatible subset can execute concurrently without oversubscribing the machine?

The first version should support deterministic configured capacities/reservations rather than attempting a sophisticated dynamic optimizer.

The resource model must preserve explicit safety headroom rather than treating all installed hardware as schedulable capacity.

Conceptually:

```text
configured / measured resource capacity
        - reserved system headroom
        - active Prometheist reservations
        = safely admissible capacity
```

A task should be admitted if its reservation fits alongside current work. Higher priority alone is not a reason to stop work that can safely continue concurrently.

Tests:

- identical task state + identical resource snapshot + identical policy -> identical admission set;
- admitted work never exceeds configured safe capacity;
- a task whose reservation does not fit remains queued;
- sufficient concurrent capacity permits lower- and higher-priority tasks to run together;
- resource headroom is never allocatable to ordinary work;
- restart reconstructs the same authoritative reservations;
- synthetic resource snapshots remain deterministic and independent of worker race timing.

The implemented baseline uses deterministic greedy admission rather than an optimization solver. A multi-resource task is admitted only if its complete contract fits; a failed candidate consumes no partial capacity. Integer units are fungible within one resource class and allocate across stable resource ids in deterministic order. Any future exclusive, affinity, memory-byte, GPU/VRAM, or measured-runtime semantics require their own explicit resource contract and evidence.

### Increment D — durable assignments and scheduling epochs

Replace single-task focus reconciliation with deterministic epoch assignment over the admitted set.

Each epoch should:

1. identify dependency-satisfied runnable tasks;
2. derive effective priorities;
3. read/capture the authoritative safe resource state;
4. preserve valid existing reservations/assignments where possible;
5. deterministically admit compatible tasks;
6. create durable assignment identities or discrete slots where the resource contract requires them;
7. persist the complete assignment/reservation set atomically;
8. expose only committed assignments to workers.

Workers must not race directly against the runnable queue.

Tests:

- identical authoritative state -> identical complete assignment/reservation set;
- total ordering remains deterministic;
- same-priority arrivals do not cause unnecessary churn;
- no resource is oversubscribed;
- discrete resources never exceed their declared concurrency;
- partial persistence cannot expose half an epoch as authoritative state.

### Increment E — contention-driven interruption semantics

Generalize preemption from one active task to multiple concurrent assignments.

A higher-priority task should cause preemption only when it cannot otherwise be admitted. The scheduler should release only the minimum deterministically selected lower-priority compatible work needed to satisfy the missing reservation, and only where interruption policy permits.

Tests:

- no preemption occurs when safe concurrent capacity exists;
- preemption affects only resources relevant to the blocked higher-priority task;
- `ATOMIC` remains non-preemptible under normal scheduler authority;
- `CHECKPOINT_ONLY` records pending replacement but retains its reservation until checkpoint;
- unrelated work continues running;
- victim selection is deterministic when several active tasks are eligible to yield.

### Increment F — durable worker protocol

Define a worker contract that is independent of named agents.

A worker should receive a durable assignment containing only what it needs to execute one bounded step, such as:

```text
assignment_id
task_id
step_id / checkpoint revision
required capability
resource reservation refs
input refs
idempotency key
```

A discrete `lane_id` may appear when the relevant resource contract actually uses lanes/slots; it is not required as the universal capacity model.

The worker may invoke a model or another capability, return a structured result, persist a checkpoint/result, and disappear.

The scheduler/fabric—not the worker—decides what work exists and what receives attention.

Once this contract exists, adapt the deterministic v0.6 Capability Registry into task/worker-neutral terminology rather than recreating capability discovery from scratch. Preserve bounded deterministic matching, canonical-before-supplemental discovery, no-match abstention, progressive disclosure, and auditable selection. Do not preserve `CapabilityKind.AGENT` or `requesting_agent` as required architectural concepts.

Tests:

- worker can be destroyed after assignment but before completion;
- expired/abandoned assignment can be recovered deterministically;
- retry does not duplicate side effects when the capability declares idempotency;
- fresh worker can resume from committed checkpoint.

### Increment G — replace Primary-Agent orchestration path

Do not wrap `PrimaryAgent.handle_interaction()` inside the scheduler as a permanent design.

Instead, decompose a user interaction into durable steps/tasks that can be executed by disposable workers.

A minimal transition path may use stages such as:

```text
FORM_TASK
INTERPRET / RESOLVE_REFERENCES
REQUEST_CAPABILITY
WAIT_FOR_RESULT
RESPOND
PERSIST_RESULT
```

Exact stages should be introduced only as required by measured workflows.

The v0.6 `REFERENTIAL_CONTINUITY_REQUIRES_MEMORY_V1` behavior should be migrated here by moving deterministic unresolved-reference detection out of `primary_agent.py` and into reusable interaction/perception policy. The behavior survives; Primary-Agent ownership does not.

The existing Primary Agent may remain temporarily as a compatibility CLI path while the new execution path is built and tested, but it should cease to be the architectural executive.

### Increment H — forced concurrent restart acceptance

Acceptance scenario:

1. create several tasks with different resource requirements;
2. admit and assign several simultaneously where the machine/resource snapshot permits it;
3. persist an intermediate checkpoint in at least one;
4. create higher-priority work that cannot fit without a permitted preemption;
5. verify only the minimum necessary compatible work yields;
6. kill all worker processes without graceful shutdown;
7. start fresh processes;
8. reconstruct authoritative assignments/reservations/checkpoints;
9. recover abandoned work without duplicate effects;
10. complete the workload;
11. compare causal history against expected deterministic state transitions.

A deterministic fake-resource/fake-worker path should establish orchestration invariants first. A real development-machine acceptance path should then verify the actual PostgreSQL/Ollama/hardware stack separately.

### Post-worker continuity migration gate

Before Primary-Agent compatibility code is removed, rewrite the frozen v0.6 four-turn continuity scenario against the new task/worker path. Preserve these acceptance properties:

- one fresh external process/worker context per turn;
- recent and older cross-session evidence needed in the same response;
- distractor history;
- exact required source-event provenance;
- polarity-sensitive answer validation;
- causal-source fidelity;
- opaque identifier fidelity.

The new path must reproduce or improve the accepted v0.6 behavior without using a conversation ID as the user's semantic memory namespace.

## Verification policy

v0.7 uses two complementary forms of evidence.

### CI / deterministic simulation

CI establishes deterministic policy invariants from controlled task and resource state. It should remain reproducible independent of the user's particular machine.

### Development-machine acceptance

Any behavior that claims to manage real local hardware must also be exercised on the actual intended development environment before it is considered verified.

That acceptance should use the real local stack where applicable, including PostgreSQL, Ollama/local-model inference, actual CPU/RAM pressure, filesystem/network behavior, and process destruction/restart.

Optional database extensions required by specific experimental suites should be installed so those suites do not remain skipped. Their presence does not automatically make those mechanisms architectural dependencies.

In particular, pgvector is not a v0.7 JIT Attention dependency. Vector-backed memory experiments on the divergent v0.6 branch remain separately gated by measured memory failures and the v0.10 milestone; do not import them merely because the code already exists.

## Explicit non-goals for v0.7

v0.7 does **not** implement the later perception/salience or retention layers.

Do not yet add:

- continuous microphone/camera ingestion;
- general sensor adapters;
- salience classifiers;
- situation assembly;
- reflex actions;
- retention TTLs/ring buffers;
- semantic/vector memory simply because the architecture expanded.

Those mechanisms belong to later milestones and must be introduced against their own frozen baselines.

## Acceptance criteria

v0.7 closes only when all of the following are demonstrated:

- multiple durable tasks can execute concurrently when safe resource capacity permits;
- deterministic admission prevents oversubscription beyond the configured safe resource envelope;
- attention priority does not force unnecessary serialization or preemption;
- assignment/reservation decisions are deterministic from authoritative state;
- workers cannot steal scheduling authority by racing for queue items;
- priority, service guarantees, dependencies, resource requirements, and interruption policy remain deterministic;
- higher-priority work preempts only when resource contention requires it and policy permits it;
- assignment/reservation state survives full process destruction;
- abandoned work is safely recoverable;
- checkpointed work resumes with fresh worker/model processes;
- at least one end-to-end workflow executes without requiring a privileged Primary Agent;
- the v0.6 continuity behavioral baseline is reproduced or improved on the replacement path before compatibility orchestration is retired;
- deterministic CI and real development-machine resource-sensitive acceptance both pass for the functionality they are intended to verify;
- the v0.5/v0.6 regression baselines remain green unless a separately documented reason justifies a change.

## Milestone invariant

> **Prometheist owns attention and unfinished work; workers merely borrow safely admitted execution capacity to advance durable tasks.**
