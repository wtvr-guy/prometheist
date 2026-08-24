# JIT Attention — deterministic executive scheduling

## Purpose

JIT Attention is the executive-control layer for Prometheist. It decides which durable task is entitled to system focus at a given moment. It is intentionally separate from semantic interpretation and from individual capabilities such as JIT Memory, web retrieval, code execution, or specialist agents.

The design goal is human-like selective focus without human-like scheduling inconsistency: agents may propose work, but deterministic application policy decides execution priority, preemption, and resumption.

## Core invariant

> Prometheist may remember many things and hold many pending intentions, but only the highest-priority runnable task owns focus unless an already-running task is explicitly non-interruptible.

No LLM decides queue order.

## Task intake

Raw events are not the queue. An event may create zero, one, or several normalized tasks. Once a task exists, it carries structured scheduling metadata:

- `criticality`
- `service_class`
- `interruption_policy`
- optional `deadline`
- `required_capabilities`
- `dependency_ids`
- deterministic `created_seq`
- stable `task_id`
- resumable state

Priority is derived from `criticality`:

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

Identical state therefore produces identical queue order.

Same-priority work does not preempt an already-running task. That rule prevents deterministic thrashing. Tie-breakers govern which task starts when focus becomes free.

## Service guarantees

Service guarantees are expressed in scheduler cycles rather than wall-clock time. This removes machine-speed and clock differences from the scheduling decision.

Default guarantees currently promote waiting work as follows:

| Service class | Due after | Guaranteed priority |
| --- | ---: | --- |
| `INTERACTIVE` | 1 cycle | `P1` |
| `USER_WORK` | 4 cycles | `P2` |
| `SUPPORT` | 8 cycles | `P2` |
| `MAINTENANCE` | 32 cycles | `P2` |
| `BACKGROUND` | 128 cycles | `P3` |

A guarantee changes queue eligibility/priority; it does **not** override interruption safety. In particular, an `ATOMIC` task cannot be killed merely because another task's service guarantee has matured.

## Interruption policy

Every task declares one of three policies:

- `PREEMPTIBLE`: a strictly higher-priority runnable task may immediately suspend it and return it to the queue.
- `CHECKPOINT_ONLY`: higher-priority work is recorded as pending, but the active task yields only at an explicit safe checkpoint.
- `ATOMIC`: the task is never preempted. Even `P0` work waits until it completes or fails.

When a task is preempted, its resumable state remains durable and the task returns to the queue with a new wait interval.

## Dependencies

A queued task is not runnable until every declared dependency has reached `COMPLETED`. Dependency gating is deterministic and occurs before queue ranking.

## Lifecycle

The scheduler uses the following states:

```text
NEW -> QUEUED -> RUNNING -> COMPLETED
                 |   |
                 |   +-> FAILED
                 |
                 +-> SUSPENDED -> QUEUED
```

Each transition receives a deterministic transition UUID derived from the task UUID, revision number, and state change.

## Durability

PostgreSQL stores three kinds of scheduler data:

- `attention_tasks`: current durable task snapshots;
- `attention_task_transitions`: append-only application-level lifecycle journal;
- `attention_scheduler_state`: current focus, pending checkpoint preemption, and monotonic scheduler cycle.

A fresh process can reconstruct the scheduler directly from this state. No LLM transcript or context window is required to know which task was active, which tasks were queued, or what resumable state the active task had reached.

## Relationship to capabilities

JIT Attention is not itself the memory subsystem. It schedules work. JIT Memory becomes one capability among many that an active task may require.

Conceptually:

```text
incoming events
     |
     v
 task formation
     |
     v
JIT Attention
     |
     v
active durable task
     |
     v
capability routing
  /   |    \
memory web   code ...
     |
     v
stateless cognition/action
```

This keeps execution continuity in deterministic persistent state while LLM invocations remain disposable.

## Current implementation boundary

The first v0.7 increment implements and tests the deterministic scheduler kernel plus PostgreSQL restart state. It also includes a deterministic forced-process-destruction acceptance test: one Python process persists an unfinished active task and is killed without graceful shutdown; a second process reconstructs the exact focus/checkpoint from PostgreSQL, completes that task, and advances to the queued task.

The live Primary Agent orchestration path is not yet routed through JIT Attention. The remaining v0.7 integration step is to place a real multi-step/multi-agent workflow behind this scheduler and repeat the kill/restart demonstration with fresh LLM calls. That model-backed acceptance path is necessarily distinct from the deterministic scheduler regression suite.

## Acceptance properties for this increment

The deterministic test suite establishes that:

- priority is derived from structured metadata;
- stable task identifiers are reproducible;
- queue order has a total deterministic ordering;
- same-priority arrivals do not preempt and cause focus thrash;
- identical scheduling replay produces identical structured focus and transition identifiers;
- higher-priority work preempts `PREEMPTIBLE` work;
- `CHECKPOINT_ONLY` work yields only at a checkpoint;
- `ATOMIC` work cannot be preempted even by `P0`;
- service guarantees promote long-waiting work without overriding interruption safety;
- dependencies gate runnability;
- snapshot reconstruction preserves focus and resumable state;
- PostgreSQL reconstruction works across fresh connections;
- lifecycle persistence is idempotent;
- unfinished work survives forced Python process destruction and resumes in a fresh process from committed durable state.
