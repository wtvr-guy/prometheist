# Prometheist v0.7 — Durable JIT Attention Fabric

**Status:** in development.

v0.7 is the first milestone after the 2026-08-24 architectural pivot from a privileged Primary Agent / fixed multi-agent hierarchy toward an attention-centric persistent cognitive system.

The accepted v0.6 result remains important: multiple fresh stateless LLM calls can participate in one continuous system through shared JIT Memory and durable system state. v0.7 generalizes that result by moving executive control out of any agent and into deterministic persistent attention state.

See:

- [`../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [`../../architecture/COGNITIVE_ARCHITECTURE.md`](../../architecture/COGNITIVE_ARCHITECTURE.md)
- [`JIT_ATTENTION_DESIGN.md`](JIT_ATTENTION_DESIGN.md)

## Primary question

> Can Prometheist deterministically allocate durable work across bounded concurrent execution resources, survive destruction of every worker process, and resume without any privileged Primary Agent or persistent LLM context?

## What is already implemented

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

The current implementation therefore proves that unfinished work can belong to persistent system state rather than the lifetime of a Python process or LLM context.

## What changed after the first increment

The original next step was to route the synchronous Primary Agent through the single-focus scheduler and demonstrate a restartable multi-agent workflow.

That is no longer the intended direction.

The new target is to generalize the scheduler into an **Attention Fabric** with multiple deterministic resource lanes, then replace Primary-Agent orchestration with a stateless worker/capability execution protocol.

The current scheduler code is retained as the baseline because its priority, interruption, service-guarantee, dependency, checkpoint, determinism, and restart properties remain necessary.

## Implementation sequence

### Increment A — freeze the single-focus kernel

Preserve the existing scheduler tests as regression invariants.

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

Introduce durable execution-resource definitions, for example:

```text
ExecutionResource
    resource_id
    resource_class
    capacity
    enabled
    metadata
```

Initial resource classes should be deliberately small and generic, such as:

```text
CPU_GENERAL
LLM_INFERENCE
DATABASE
FILESYSTEM_IO
NETWORK_IO
```

Do not assume capacity equals host logical CPU count. Local LLM inference may remain capacity 1 even on a many-thread CPU.

Tests:

- resource definitions round-trip durably;
- identical resource state produces identical ordering;
- disabled resources never receive assignments;
- tasks requiring unsupported resources remain queued.

### Increment C — durable attention lanes

Represent available capacity as deterministic lanes or equivalent durable slots.

Example:

```text
cpu-general-00
cpu-general-01
llm-inference-00
network-io-00
network-io-01
```

Lane identity must be stable and deterministic.

Tests:

- stable lane creation/order;
- no more assignments than declared capacity;
- a task occupies at most one exclusive lane unless its contract explicitly supports otherwise;
- lane state survives restart.

### Increment D — scheduling epochs

Replace single-task focus reconciliation with deterministic epoch assignment.

Each epoch should:

1. identify runnable tasks;
2. identify available lanes;
3. derive effective priorities;
4. deterministically rank tasks and lanes;
5. match compatible tasks to lanes;
6. persist the complete assignment atomically;
7. expose committed assignments to workers.

Workers must not race directly against the runnable queue.

Tests:

- identical state -> identical complete assignment set;
- task/lane matching respects resource requirements;
- total ordering remains deterministic;
- same-priority task arrivals do not cause unnecessary assignment churn;
- partial persistence cannot expose half an epoch as authoritative state.

### Increment E — multi-lane interruption semantics

Generalize preemption from one active task to N active assignments.

A new high-priority task should preempt only the lowest-ranked compatible active work necessary to satisfy its resource requirements, and only where interruption policy permits.

Tests:

- preemption affects only compatible resource lanes;
- `ATOMIC` remains non-preemptible under normal scheduler authority;
- `CHECKPOINT_ONLY` records pending replacement but retains its lane until checkpoint;
- unrelated lanes continue running;
- deterministic victim selection when several active tasks are preemptible.

### Increment F — durable worker protocol

Define a worker contract that is independent of named agents.

A worker should receive a durable assignment containing only what it needs to execute one bounded step, such as:

```text
assignment_id
lane_id
task_id
step_id / checkpoint revision
required capability
input refs
idempotency key
```

The worker may invoke a model or another capability, return a structured result, persist a checkpoint/result, and disappear.

The scheduler/fabric—not the worker—decides what work exists and what receives attention.

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
CLASSIFY / INTERPRET
REQUEST_CAPABILITY
WAIT_FOR_RESULT
RESPOND
PERSIST_RESULT
```

Exact stages should be introduced only as required by measured workflows.

The existing Primary Agent may remain temporarily as a compatibility CLI path while the new execution path is built and tested, but it should cease to be the architectural executive.

### Increment H — forced multi-lane restart acceptance

Acceptance scenario:

1. create several tasks with different resource requirements;
2. assign several simultaneously;
3. persist an intermediate checkpoint in at least one;
4. create higher-priority work that causes a permitted preemption;
5. kill all worker processes without graceful shutdown;
6. start fresh processes;
7. reconstruct authoritative assignments/checkpoints;
8. recover abandoned work without duplicate effects;
9. complete the workload;
10. compare causal history against expected deterministic state transitions.

A deterministic fake-model/capability path should establish orchestration invariants first. A real Ollama-backed acceptance path can then verify stateless model replacement separately.

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

- multiple durable tasks can execute concurrently across explicit bounded resource lanes;
- assignment is deterministic from authoritative state;
- workers cannot steal scheduling authority by racing for queue items;
- priority, service guarantees, dependencies, and interruption policy remain deterministic;
- task/lane state survives full process destruction;
- abandoned work is safely recoverable;
- checkpointed work resumes with fresh worker/model processes;
- at least one end-to-end workflow executes without requiring a privileged Primary Agent;
- the v0.5/v0.6 regression baselines remain green unless a separately documented reason justifies a change.

## Milestone invariant

> **Prometheist owns attention and unfinished work; workers merely borrow execution capacity to advance durable tasks.**
