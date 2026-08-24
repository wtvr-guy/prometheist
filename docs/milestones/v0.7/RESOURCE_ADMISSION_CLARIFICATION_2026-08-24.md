# v0.7 clarification — attention priority vs resource admission

**Date:** 2026-08-24

**Status:** accepted design clarification for the v0.7 Attention Fabric.

This note records a distinction that became explicit after Increment B introduced durable execution-resource definitions.

## Decision

Prometheist must not equate attention priority with a fixed number of permanent execution lanes.

The architecture separates two questions:

1. **Attention:** Which durable tasks are entitled to execution, and in what deterministic priority order?
2. **Resource admission:** Which subset of those entitled tasks can execute concurrently without exceeding safe hardware capacity or causing unacceptable system-wide degradation?

The resulting rule is:

> **JIT Attention ranks durable work deterministically; resource admission admits as much compatible work concurrently as the current safe execution-resource state can support.**

A higher-priority task does not automatically preempt lower-priority work. If both can run safely at the same time, both should ordinarily continue.

Preemption is considered only when a higher-priority task cannot be admitted because currently running work occupies resources that the higher-priority task requires. Even then, scheduler interruption policy still applies.

## Why this matters

A fixed-lane model is too crude for the intended system.

For example, a machine may be able to execute a database query, filesystem read, network request, lightweight CPU task, and local-model inference concurrently with no meaningful contention. Serializing all of that work would waste available hardware.

Conversely, a single large local inference or other resource-intensive operation may require enough RAM, CPU, GPU/VRAM, or exclusive backend capacity that starting it alongside existing work could cause swapping, severe latency, resource exhaustion, or process failure.

Prometheist therefore needs deterministic admission and reservation policy rather than a universal fixed-slot abstraction.

## Resource model

Execution resources are authoritative system state. Resource classes may expose different capacity semantics.

Initial v0.7 classes remain deliberately small:

- `CPU_GENERAL`
- `LLM_INFERENCE`
- `DATABASE`
- `FILESYSTEM_IO`
- `NETWORK_IO`

Later measured requirements may justify quantitative classes or dimensions such as:

- memory bytes;
- GPU/VRAM capacity;
- device I/O;
- actuator capacity;
- explicit exclusive/shared backend modes.

The resource model must not assume that host logical CPU count equals useful application concurrency. For example, a many-thread CPU may still expose local LLM inference capacity of one.

## Capacity, reservation, and headroom

Installed hardware is not identical to schedulable capacity.

Prometheist must preserve deterministic safety headroom for the operating system and other required processes such as PostgreSQL, Ollama, Prometheist itself, and user-authorized applications.

Conceptually:

```text
physical / configured capacity
        - reserved system headroom
        - active Prometheist reservations
        = currently admissible capacity
```

A task may eventually declare quantitative requirements or reservations such as:

```text
CPU_GENERAL: 2 units
MEMORY: 1 GiB
LLM_INFERENCE: 1 exclusive unit
DATABASE: 1 unit
```

Exact dimensions should be added only when tests demonstrate that they are required.

## Determinism boundary

Hardware availability can change over time. Determinism therefore applies to the scheduling policy given the same authoritative task state and the same captured resource state.

In other words:

> **Identical durable task state + identical resource snapshot + identical policy version must produce the same admission, reservation, and preemption decision.**

Runtime resource measurement may be an input to the deterministic policy; it must not become an untracked source of scheduling authority.

Any measured state that materially affects a scheduling decision must be represented in sufficient durable or reproducible form to explain that decision later.

## Admission algorithm baseline

The first implementation should remain deliberately simple.

At each scheduling epoch:

1. determine dependency-satisfied runnable tasks;
2. derive effective deterministic priorities;
3. capture or load the authoritative safe resource state;
4. preserve valid existing assignments where possible;
5. iterate candidate tasks in deterministic order;
6. admit a task if its required reservations fit within remaining safe capacity;
7. if a higher-priority task cannot fit, evaluate whether lower-priority compatible work may yield under its interruption policy;
8. preempt only the minimum deterministically selected work required to make the higher-priority task admissible;
9. persist the complete resulting reservations/assignments atomically before workers execute them.

Do not introduce an optimization solver unless a frozen benchmark demonstrates that a simpler deterministic algorithm is materially inadequate.

## Relationship to lanes

The term **lane** may still be useful for resources whose capacity is naturally represented as discrete concurrency slots, such as one local-model inference slot or a bounded pool of network workers.

However, lanes are not the universal hardware model and must not imply permanent partitioning of CPU, memory, or the whole machine.

If retained, a lane is best understood as one durable execution/assignment slot within a resource contract, not as the thing that defines total system capacity.

The core abstraction is therefore:

```text
attention priority
      +
resource requirements
      +
safe resource capacity
      +
interruption policy
      |
      v
deterministic admission / reservation
      |
      v
concurrent durable assignments
```

## Preemption rule

Priority alone is insufficient to justify preemption.

For a new higher-priority task:

```text
Can the task be admitted safely alongside current work?
        |
   YES  |  NO
        |   |
        v   v
     start   determine whether enough lower-priority
     task    compatible work may legally yield
     and     to satisfy the missing reservation
     keep
     current
     work
```

`ATOMIC` work remains non-preemptible under normal scheduler authority. `CHECKPOINT_ONLY` work may be selected as a future victim but does not release resources until its declared safe checkpoint. `PREEMPTIBLE` work may yield immediately when deterministic policy requires it.

## Verification policy

CI and real-machine verification serve different purposes.

### Deterministic CI baseline

GitHub Actions should verify:

- resource contracts and persistence;
- deterministic task/resource ordering;
- admission/rejection from synthetic resource snapshots;
- no oversubscription beyond configured capacity;
- deterministic victim selection;
- atomic assignment persistence;
- restart/replay equivalence;
- worker recovery invariants.

### Development-machine acceptance

Tests that depend on actual host behavior must also be run on the intended development machine before that functionality is treated as verified.

Those tests should eventually exercise the real local stack, including as applicable:

- the machine's actual CPU and memory constraints;
- PostgreSQL;
- Ollama/local model inference;
- filesystem and network behavior;
- any optional database extensions required by the specific test suite;
- process destruction and restart under real resource pressure.

A passing CI simulation is not evidence that a resource envelope is safe on a specific host.

Likewise, one successful local run is not a substitute for deterministic synthetic regression coverage. Both are required for resource-sensitive acceptance.

## pgvector boundary

pgvector is not required by the v0.7 attention/resource-admission architecture itself. Memory-vector experiments remain separately justified by measured memory failures and their own milestone/test requirements.

Installing pgvector on a development machine is still useful when the repository contains optional or experimental vector-backed tests that would otherwise be skipped, but its presence must not silently make vector retrieval a dependency of JIT Attention.

## Updated v0.7 direction

Increment B remains valid and is not reverted. It established explicit durable resource classes/capacities and resource-gated runnability.

The next implementation should build **resource reservations and deterministic admission semantics** before treating fixed durable lanes as the central capacity abstraction.

Any discrete lanes introduced later should be derived from resource contracts where discrete slots are actually appropriate.

## Invariant

> **Prometheist should exploit safe parallelism by default, constrain concurrency only when resource requirements demand it, and preempt work only when priority plus resource contention makes preemption necessary and interruption policy permits it.**
