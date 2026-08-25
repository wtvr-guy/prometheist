# JIT Attention — deterministic executive scheduling and resource allocation

## Status

This document began as the design for a deterministic single-focus scheduler. The first v0.7 implementation increment built and tested that kernel.

After the 2026-08-24 architectural pivot, the single-focus scheduler became the baseline for a more general **JIT Attention Fabric**. Increment B then made execution resources explicit and durable. A subsequent design clarification separated **attention priority** from **resource admission** so that Prometheist can exploit safe parallelism rather than treating fixed lanes as the universal capacity model. Increment C implemented quantitative admission/reservations, and Increment D now publishes complete durable assignment sets through atomic scheduling epochs.

See:

- [`../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](../../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md)
- [`../../architecture/COGNITIVE_ARCHITECTURE.md`](../../architecture/COGNITIVE_ARCHITECTURE.md)
- [`README.md`](README.md)
- [`RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md)

## Purpose

JIT Attention is the executive-control subsystem for Prometheist. It decides which durable tasks are entitled to execution and applies deterministic policy when those tasks compete for bounded hardware resources.

It is intentionally separate from semantic interpretation and from capabilities such as JIT Memory, web retrieval, code execution, database access, model inference, device I/O, or actuators.

The design goal is selective, resource-aware execution with deterministic scheduling semantics:

> **Workers may produce evidence, results, or task proposals; deterministic system policy controls attention, admission, assignment, preemption, and resumption.**

No LLM decides queue order, owns system focus, or arbitrates resource contention.

## Core invariant

The original single-focus invariant was:

> Prometheist may remember many things and hold many pending intentions, but only the highest-priority runnable task owns focus unless an already-running task is explicitly non-interruptible.

The generalized invariant is:

> **Prometheist may hold arbitrarily many durable intentions and should execute as many compatible tasks concurrently as the authoritative safe resource state permits.**

This means higher priority does not imply exclusive focus. Priority matters when work competes for insufficient resources.

## Attention vs resource admission

The Attention Fabric answers two distinct questions.

### Attention

Which runnable durable tasks deserve execution, and in what deterministic order?

Attention is derived from structured task state such as:

- criticality;
- service class;
- deadline;
- dependencies;
- creation sequence;
- interruption policy.

### Resource admission

Which subset of attention-eligible tasks can execute concurrently without exceeding the safe resource envelope of the machine?

Resource admission considers:

- required resource classes;
- configured or captured safe capacities;
- active reservations;
- reserved system headroom;
- exclusive/shared constraints;
- interruption policy when capacity is insufficient.

The core rule is:

> **A higher-priority task does not preempt lower-priority work if both can run safely at the same time.**

Preemption is considered only when the higher-priority task cannot be admitted because currently running work occupies resources it needs.

## Task intake

Raw events are not the queue. An event may create zero, one, or several normalized tasks.

Once a task exists, it carries structured scheduling metadata including:

- `criticality`;
- `service_class`;
- `interruption_policy`;
- optional `deadline`;
- `required_capabilities`;
- resource requirements/reservations;
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

A guarantee may promote waiting work. It does **not** override interruption safety or resource safety.

## Interruption policy

Every task declares one of three policies:

- `PREEMPTIBLE` — may immediately yield when deterministic contention policy selects it as necessary to admit higher-priority work;
- `CHECKPOINT_ONLY` — may be selected as a pending victim but retains its resources until a declared safe checkpoint;
- `ATOMIC` — the normal scheduler never preempts the active operation.

When a task yields, its resumable state remains durable and it returns to the runnable set when appropriate.

`ATOMIC` is an execution-safety property, not permission for an operation to run forever. Separate timeout/failure/recovery policy may eventually be required, but ordinary priority promotion must not silently violate atomicity.

## Dependencies

A queued task is not runnable until every declared dependency has reached the required terminal state, initially `COMPLETED`.

Dependency gating occurs before ranking and admission.

Priority inversion caused by high-priority work depending on lower-priority work is a known future hardening concern; it should be solved explicitly rather than hidden inside nondeterministic worker behavior.

## Explicit execution resources

Increment B introduced durable execution-resource definitions.

Current resource classes are:

- `CPU_GENERAL`;
- `MEMORY_RAM` (MiB);
- `LLM_INFERENCE`;
- `DATABASE`;
- `FILESYSTEM_IO`;
- `NETWORK_IO`.

A resource definition contains stable identity, class, capacity, enabled state, and metadata. `MEMORY_RAM` was added by the pre-Increment-F observation gate because actual RAM pressure cannot be represented safely as a CPU or generic concurrency slot.

Tasks may declare required resource classes. A task whose required class has no enabled capacity remains durably queued.

The host may expose different capacities for different classes. Eight logical CPU threads, for example, do not imply eight sensible simultaneous local-model generations.

## Safe capacity and headroom

Installed hardware is not identical to schedulable capacity.

Prometheist must reserve a safety envelope for the operating system and required processes such as PostgreSQL, Ollama, Prometheist itself, and user-authorized applications.

Conceptually:

```text
physical / configured capacity
        - reserved system headroom
        - active Prometheist reservations
        = currently admissible capacity
```

The initial implementation should favor configured deterministic capacity and reservation rules over opaque adaptive heuristics.

Runtime measurements may eventually inform admission, but any measurement that materially changes a scheduling decision must be represented as authoritative input so the decision remains explainable.

## Determinism boundary

Real hardware state can vary over time. Determinism applies to policy given the same authoritative inputs.

The required property is:

> **Identical durable task state + identical resource snapshot + identical policy version produces identical admission, reservation, assignment, and preemption decisions.**

The operating system may schedule threads nondeterministically at a lower level; Prometheist must not rely on those races to decide which durable task owns which resources.

## From focus to Attention Fabric

The retained Increment A compatibility kernel has one `active_task_id`. Increment D adds the forward generalization: a durable admitted assignment set owned by a committed scheduling epoch.

Conceptually:

```text
runnable tasks
      |
      v
rank attention deterministically
      |
      v
RESOURCE ADMISSION <---- safe capacity / reservations / headroom
      |
      v
persisted admitted assignment set
      |
      +--> task A -> worker/capability
      +--> task B -> worker/capability
      +--> task C -> worker/capability
```

The assignment set may contain several concurrent tasks whenever the resource envelope permits it.

## Relationship to lanes

A lane is no longer the universal model of hardware capacity.

Discrete lanes/slots may still be appropriate for resources whose capacity is naturally expressed as concurrency units, for example:

```text
llm-inference-00
network-worker-00
network-worker-01
```

But CPU and memory should not be permanently partitioned merely to make the scheduler easy to model.

If retained, a lane means one durable slot within a specific resource contract or assignment mechanism. It does not define total system capacity.

## Deterministic scheduling epochs

Workers must not independently race to claim the next queue item.

Each scheduling epoch is application-owned and deterministic:

1. read the authoritative runnable-task set;
2. read/capture the authoritative safe resource state;
3. compute effective priorities and eligibility;
4. preserve still-valid existing reservations/assignments where possible;
5. iterate tasks in deterministic order;
6. admit compatible tasks whose reservations fit;
7. in Increment E, if higher-priority work cannot fit, deterministically evaluate legal lower-priority victims;
8. persist the entire resulting reservation/assignment set atomically;
9. release only committed assignments to workers.

If two runs begin from identical durable task state and identical resource state, the resulting assignment set is identical. Increment D preserves all valid committed assignments before admitting new candidates; it does not yet release a lower-priority assignment to make room for a later higher-priority task.

A `PLANNED` epoch is provisional scheduler state. Workers can read assignments only from the scheduler's current `COMMITTED` epoch. PostgreSQL atomically commits immutable assignment rows, the immutable epoch and its complete reservation snapshot, the replaceable current reservation set, and the current-epoch pointer. The in-memory pointer changes only after that transaction succeeds.

## Deterministic admission baseline

The first admission algorithm should remain deliberately simple.

A reasonable baseline is:

1. iterate runnable tasks in deterministic priority order;
2. preserve existing valid assignments;
3. admit each candidate whose reservations fit inside remaining safe capacity;
4. leave candidates that do not fit queued in Increment D;
5. continue until no additional task can be admitted.

Increment E extends this baseline: only then may the scheduler identify lower-priority compatible work that may legally yield, select the minimum required victims using a deterministic total order, and release reservations to admit blocked higher-priority work.

Do not introduce an optimization solver until a frozen benchmark demonstrates that a simpler deterministic algorithm causes a material problem.

## Contention-driven preemption

With multiple active assignments, high-priority work should disturb only the work whose resources actually prevent admission.

Example:

```text
CPU task A      -> P3 PREEMPTIBLE
DB task B       -> P2 ATOMIC
network task C  -> P4 PREEMPTIBLE

new P1 CPU task D arrives
```

If sufficient CPU capacity exists, D starts and A continues.

If CPU capacity is insufficient, D may require A to yield. B and C continue because they do not block D's required capacity.

If several compatible active tasks could be preempted, victim selection must itself use a deterministic total order and release only enough capacity to admit the higher-priority work.

## Durable assignment and reservation state

The Attention Fabric requires durable state beyond the original single-focus scheduler snapshot.

Increment D persists:

- execution-resource definitions;
- resource snapshots or policy-versioned configured capacity;
- task resource requirements;
- active reservations;
- scheduling epoch identifiers;
- durable assignment identifiers;
- a `READY` assignment status that denotes entitlement, not a worker claim;
- an explicit assignment-policy version;
- append-only immutable epoch and assignment rows;
- the authoritative current-epoch pointer and current reservation set.

Still-future worker concepts include optional lane/slot identifiers for discrete resource contracts, assignment claims/leases, worker heartbeat metadata, and idempotency keys for externally visible capability effects. Increment E now persists checkpoint-gated preemption intents separately from that worker protocol.

Schema changes are introduced incrementally and must remain idempotent for existing local v0.7 databases.

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

JIT Attention schedules and admits work. It is not itself memory, reasoning, or tool execution.

JIT Memory remains one capability among many that a task may request.

```text
durable task
     |
     v
attention + resource admission
     |
     v
committed assignment
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
- forced-process-destruction acceptance proving unfinished work survives loss of Python process state;
- explicit execution-resource classes/capacities;
- deterministic durable resource ordering;
- task resource-class requirements;
- resource-gated runnability;
- PostgreSQL persistence/restart reconstruction of resource definitions and requirements;
- quantitative integer resource requirements with Increment B one-unit compatibility;
- explicit configured system headroom;
- deterministic greedy, all-or-nothing concurrent admission;
- deterministic allocation across fungible pools of the same class;
- stable task/resource reservation identities;
- explicit admission-policy versioning;
- durable admitted-task and reservation state;
- atomic PostgreSQL replacement/restart reconstruction of reservation sets;
- snapshot validation against incomplete or oversubscribed reservation state;
- deterministic `SchedulingEpoch` and `DurableAssignment` identities;
- policy-versioned, attention-ordered assignment sets over all admitted tasks;
- preservation of committed assignment/reservation identity across later arrivals;
- provisional epoch isolation from worker-visible state;
- atomic PostgreSQL publication of immutable assignments, immutable complete epoch snapshots, current reservations, and the current-epoch pointer;
- stale-scheduler generation rejection;
- idempotent epoch persistence and exact restart reconstruction;
- rollback verification that partial epoch persistence exposes no authoritative state;
- validation of complete epoch, assignment, revision, policy, and reservation consistency.
- policy-versioned contention preemption only after concurrent admission fails;
- exact minimum-cardinality victim selection over deficient resource classes;
- deterministic victim ordering and same-priority/`ATOMIC` stability;
- durable checkpoint-gated replacement intents with no partial release;
- target-capacity protection while selected checkpoint victims yield;
- append-only preemption lifecycle evidence and immutable epoch references;
- optimistic revision checks for concurrent checkpoint progress;
- restart, idempotency, and transaction-rollback coverage for preemption state.
- live host CPU/RAM discovery through a replaceable observer outside policy;
- explicit MiB RAM requirements and conservative persisted process estimates;
- versioned OS and uncertainty headroom plus a default single local-LLM slot;
- PostgreSQL-enforced global capacity across concurrent scheduler writers;
- immutable freshness-bounded resource observations referenced by exact epoch;
- fail-closed missing/stale/failed-observation behavior;
- atomic observation/epoch persistence and restart reconstruction.

Not yet implemented:

- generic durable worker protocol;
- claim-time resource revalidation immediately before process launch;
- accelerator/VRAM and inference-backend pressure observation;
- replacement of the live Primary-Agent orchestration path.

## Explicitly rejected next steps

Two shortcuts are explicitly rejected.

First, do **not** merely wrap the current synchronous `PrimaryAgent.handle_interaction()` in the scheduler. That would preserve the old call stack as the real owner of execution while presenting a scheduler facade around it.

Second, do **not** convert every unit of hardware capacity into a permanent attention lane merely because discrete lanes are easy to reason about. That would conflate priority with resource admission and could either serialize safe parallel work or oversubscribe resource-intensive workloads.

The correct direction is:

1. preserve the deterministic scheduler baseline;
2. make resource requirements, safe capacity, reservations, and headroom explicit;
3. deterministically admit as much concurrent work as safe capacity permits;
4. add durable assignment identities and optional discrete slots where appropriate;
5. add contention-driven preemption;
6. define durable worker/capability steps;
7. decompose actual interactions into durable work;
8. retain the old Primary Agent temporarily only as compatibility/reference code until the replacement path is verified.

## Verification policy

Deterministic CI and real-machine acceptance establish different facts.

GitHub Actions should prove deterministic policy and persistence against controlled synthetic resource snapshots.

Resource-sensitive claims about actual hardware must also be tested on the intended development machine using the real local stack where applicable: PostgreSQL, Ollama/local inference, actual CPU/RAM constraints, filesystem/network behavior, and process destruction/restart.

A passing CI simulation does not prove that a particular resource envelope is safe on a particular host. A successful local run does not replace deterministic synthetic regression coverage. Both forms of evidence are required.

pgvector is not a dependency of JIT Attention. Installing it may enable optional or experimental vector-backed memory tests, but vector retrieval must remain separately justified by measured memory failures.

## v0.7 acceptance properties

The final milestone should prove all of the following:

- priority remains deterministically derived from structured metadata;
- task and transition identifiers are reproducible;
- task ordering and resource ordering are total and deterministic;
- service guarantees do not override interruption or resource safety;
- dependencies gate runnability;
- resource requirements gate admission compatibility;
- safe concurrent capacity allows several tasks to execute without unnecessary preemption;
- identical task/resource state produces identical admission/reservation/assignment sets;
- no resource is oversubscribed beyond configured safe capacity;
- reserved system headroom is not consumed by ordinary work;
- higher-priority work preempts only when resource contention requires it and interruption policy permits it;
- unrelated work continues while contention is resolved elsewhere;
- `CHECKPOINT_ONLY` and `ATOMIC` semantics survive concurrent generalization;
- assignment/reservation/checkpoint state survives full worker-process destruction;
- abandoned work can be recovered safely;
- idempotent/retry-safe boundaries prevent duplicate external side effects;
- an end-to-end workflow completes through disposable workers without a privileged Primary Agent;
- deterministic fake-resource/fake-worker tests and separate real-development-machine/Ollama acceptance both pass for the functionality they are intended to verify.

## Milestone invariant

> **Prometheist owns attention and unfinished work, exploits safe parallelism by default, and constrains or preempts execution only when deterministic resource admission requires it.**
