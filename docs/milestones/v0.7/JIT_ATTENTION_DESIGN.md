# JIT Attention — deterministic executive scheduling and resource allocation

## Status

This document began as the design for a deterministic single-focus scheduler. The first v0.7 implementation increment has already built and tested that kernel.

After the 2026-08-24 architectural pivot, the single-focus scheduler is now treated as the baseline for a more general **JIT Attention Fabric**. The fabric will preserve the existing scheduler invariants while supporting multiple concurrent execution lanes and removing the Primary Agent as the intended executive layer.

See:

- [`../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [`../../architecture/COGNITIVE_ARCHITECTURE.md`](../../architecture/COGNITIVE_ARCHITECTURE.md)
- [`README.md`](README.md)

## Purpose

JIT Attention is the executive-control subsystem for Prometheist. It decides which durable tasks are entitled to which bounded execution resources at a given scheduling point.

It is intentionally separate from semantic interpretation and from capabilities such as JIT Memory, web retrieval, code execution, database access, model inference, device I/O, or actuators.

The design goal is selective, resource-aware focus with deterministic scheduling semantics:

> **Workers may produce evidence, results, or task proposals; deterministic system policy controls attention, assignment, preemption, and resumption.**

No LLM decides queue order or owns system focus.

## Core invariant

The original single-focus invariant was:

> Prometheist may remember many things and hold many pending intentions, but only the highest-priority runnable task owns focus unless an already-running task is explicitly non-interruptible.

The generalized invariant is:

> **Prometheist may hold arbitrarily many durable intentions, but only a deterministic compatible subset may consume the execution capacity currently exposed by the Attention Fabric.**

## Task intake

Raw events are not the queue. An event may create zero, one, or several normalized tasks.

Once a task exists, it carries structured scheduling metadata including:

- `criticality`;
- `service_class`;
- `interruption_policy`;
- optional `deadline`;
- `required_capabilities` and/or resource requirements;
- `dependency_ids`;
- deterministic `created_seq`;
- stable `task_id`;
- resumable state.

Priority remains derived from `criticality`:

| Criticality | Priority |
| --- | --- |
| `EMERGENCY` | `P0` |
| `USER_BLOCKING` | `P1` |
| `USER_REQUESTED` | `P2` |
| `SUPPORTING` | `P3` |
| `MAINTENANCE` | `P4` |
| `OPPORTUNISTIC` | `P5` |

Lower numeric values are higher priority.

## Deterministic queue order

Runnable queued tasks are ordered by:

1. effective priority;
2. whether an explicit service guarantee is due;
3. deadline;
4. authoritative creation sequence;
5. task UUID as a final total-order tie-breaker.

Identical authoritative task state therefore produces identical task order.

Same-priority work does not preempt already-running same-priority work merely because a later tie-breaker differs. That prevents deterministic thrashing.

## Service guarantees

Service guarantees are expressed in scheduler cycles rather than wall-clock time for the deterministic baseline.

Current defaults:

| Service class | Due after | Guaranteed priority |
| --- | ---: | --- |
| `INTERACTIVE` | 1 cycle | `P1` |
| `USER_WORK` | 4 cycles | `P2` |
| `SUPPORT` | 8 cycles | `P2` |
| `MAINTENANCE` | 32 cycles | `P2` |
| `BACKGROUND` | 128 cycles | `P3` |

A guarantee may promote waiting work. It does **not** override interruption safety.

## Interruption policy

Every task declares one of three policies:

- `PREEMPTIBLE` — a strictly higher-priority compatible task may immediately suspend it and take the required execution resource;
- `CHECKPOINT_ONLY` — higher-priority compatible work may be recorded as pending, but the active task yields only at a declared safe checkpoint;
- `ATOMIC` — the normal scheduler never preempts the active operation.

When a task yields, its resumable state remains durable and it returns to the runnable set when appropriate.

`ATOMIC` is an execution-safety property, not permission for an operation to run forever. Separate timeout/failure/recovery policy may eventually be required, but ordinary priority promotion must not silently violate atomicity.

## Dependencies

A queued task is not runnable until every declared dependency has reached the required terminal state, initially `COMPLETED`.

Dependency gating occurs before ranking and assignment.

Priority inversion caused by high-priority work depending on lower-priority work is a known future hardening concern; it should be solved explicitly rather than hidden inside nondeterministic worker behavior.

## From focus to Attention Fabric

The first implementation has one `active_task_id`. The target generalization introduces explicit execution resources and assignments.

Conceptually:

```text
runnable tasks
      |
      v
rank deterministically
      |
      v
ATTENTION FABRIC <---- available resources / lanes
      |
      v
persisted assignment set
      |
      +--> lane 0 -> task A
      +--> lane 1 -> task B
      +--> lane 2 -> task C
```

A lane is not necessarily a CPU core or thread. It represents one unit of available capacity within a resource class.

Potential classes include:

- `CPU_GENERAL`;
- `LLM_INFERENCE`;
- `DATABASE`;
- `FILESYSTEM_IO`;
- `NETWORK_IO`;
- `GPU`;
- `DEVICE_IO`;
- `ACTUATOR`.

The host may expose different capacities for different classes. For example, eight logical CPU threads do not imply eight sensible simultaneous local-model generations.

## Deterministic scheduling epochs

Workers must not independently race to claim the next queue item.

Each scheduling epoch should be application-owned and deterministic:

1. read the authoritative runnable-task set;
2. read the available resource/lane set;
3. compute effective priorities and eligibility;
4. sort tasks deterministically;
5. sort lanes deterministically;
6. match tasks to compatible lanes with a deterministic algorithm;
7. persist the entire assignment set atomically;
8. release committed assignments to workers.

If two runs begin from identical durable state and identical resource availability, the resulting assignment set should be identical.

## Deterministic matching

The first matching algorithm should remain deliberately simple.

A reasonable baseline is:

1. iterate runnable tasks in deterministic priority order;
2. for each task, choose the first deterministically ordered compatible available lane;
3. reserve that lane for the epoch;
4. continue until no compatible tasks or lanes remain.

Do not introduce an optimization solver until a frozen benchmark demonstrates that greedy deterministic matching causes a material problem.

## Multi-lane preemption

With multiple active assignments, a high-priority task should affect only the compatible resources it actually needs.

Example:

```text
lane cpu-00      -> P3 preemptible task
lane db-00       -> P2 atomic transaction
lane network-00  -> P4 network task

new P1 CPU task arrives
```

The P1 task may preempt the P3 CPU task while the database and network lanes continue unaffected.

If several compatible active tasks could be preempted, victim selection must itself use a deterministic total order.

## Durable assignment state

The Attention Fabric will require durable state beyond the current single-focus scheduler snapshot.

Expected concepts include:

- execution-resource definitions;
- stable lane identifiers;
- scheduling epoch identifiers;
- task-to-lane assignments;
- assignment status/lease state;
- pending checkpoint preemptions;
- worker claim/heartbeat metadata if later justified;
- idempotency keys for externally visible capability effects.

Exact schema changes should be introduced incrementally and tested through migrations when the design is implemented.

## Stateless worker contract

The target worker is not a permanent agent.

A worker receives a committed bounded assignment, advances one durable unit of work, persists the result/checkpoint, and may disappear.

Conceptually:

```text
committed assignment
      |
      v
fresh worker process
      |
      +--> capability invocation
      +--> optional fresh LLM inference
      +--> optional JIT Memory request
      |
      v
structured result/checkpoint
      |
      v
persist
      |
      v
worker may be destroyed
```

A named role such as planner, researcher, analyst, or memory specialist may be a worker configuration, but it does not own durable identity or scheduling authority.

## Relationship to capabilities

JIT Attention schedules work. It is not itself memory, reasoning, or tool execution.

JIT Memory remains one capability among many that a task may request.

```text
durable task
     |
     v
attention assignment
     |
     v
worker
  /  |   \
memory model code web files devices ...
     |
     v
persisted result/checkpoint
```

Memory should remain demand-driven. The scheduler should not eagerly inject historical context merely because memory exists.

## Current implementation boundary

Already implemented in the v0.7 branch:

- `PriorityClass`, `TaskCriticality`, `ServiceClass`, `InterruptionPolicy`, and task lifecycle models;
- deterministic task UUIDs and transition UUIDs;
- deterministic priority derivation;
- total queue ordering;
- cycle-based service guarantees;
- dependency gating;
- single-focus preemption/checkpoint/atomic semantics;
- durable scheduler snapshots;
- PostgreSQL task/transition/scheduler state;
- restart reconstruction;
- transition idempotency;
- deterministic replay tests;
- forced-process-destruction acceptance proving unfinished work survives loss of Python process state.

Not yet implemented:

- explicit resource classes/capacities;
- multiple durable lanes;
- epoch assignment sets;
- multi-lane preemption;
- generic durable worker protocol;
- replacement of the live Primary-Agent orchestration path.

## Explicitly rejected next step

The previous design said the next v0.7 step was to route a real multi-step/multi-agent workflow through the single-focus scheduler.

That is superseded.

Do **not** merely wrap the current synchronous `PrimaryAgent.handle_interaction()` in the scheduler. That would preserve the old call stack as the real owner of execution while presenting a scheduler facade around it.

The correct direction is:

1. generalize scheduler state into the Attention Fabric;
2. define durable worker/capability steps;
3. decompose actual interactions into durable work;
4. retain the old Primary Agent temporarily only as compatibility/reference code until the replacement path is verified.

## v0.7 acceptance properties

The final milestone should prove all of the following:

- priority remains deterministically derived from structured metadata;
- task and transition identifiers are reproducible;
- task ordering and lane ordering are total and deterministic;
- service guarantees do not override interruption safety;
- dependencies gate runnability;
- resource requirements gate assignment compatibility;
- identical task/resource state produces identical complete assignment sets;
- no resource is oversubscribed beyond configured capacity;
- unrelated lanes continue while a compatible lane is preempted;
- `CHECKPOINT_ONLY` and `ATOMIC` semantics survive multi-lane generalization;
- assignment/checkpoint state survives full worker-process destruction;
- abandoned work can be recovered safely;
- idempotent/retry-safe boundaries prevent duplicate external side effects;
- an end-to-end workflow completes through disposable workers without a privileged Primary Agent;
- deterministic fake-worker tests and separate real-Ollama stateless-worker acceptance both pass.

## Milestone invariant

> **Prometheist owns attention and unfinished work; workers merely borrow bounded execution capacity to advance durable tasks.**
