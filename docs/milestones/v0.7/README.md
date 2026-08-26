# Prometheist v0.7 — Durable JIT Attention Fabric

**Status:** release candidate. Deterministic PostgreSQL CI is complete; final
native Windows/PostgreSQL/Ollama acceptance is still required before the
milestone is marked accepted and closed.

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
- [`INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md)

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
- invalidation of stale reservation-only admission state whenever task, cycle, or resource state changes;
- restart validation that rejects unknown, mismatched, incomplete, nondeterministic, or oversubscribed reservations.

The database-independent Increment C suite passes locally (`28 passed, 2 deselected`). GitHub Actions run #99 verified the complete Increment C head with PostgreSQL 16: `112 passed, 4 skipped in 10.39s`.

Increment C does **not** mark several tasks `RUNNING`, create worker-visible assignments, or implement contention-driven interruption. It proves the deterministic safe-capacity decision and makes that decision durable. Increment D converts an admitted set into atomic scheduling-epoch assignments.

### Increment D — durable assignments and scheduling epochs

The fourth v0.7 increment replaces single-task focus reconciliation as the forward scheduling path with deterministic assignment over a complete epoch.

Implemented/tested properties include:

- explicit policy-versioned `SchedulingEpoch` and `DurableAssignment` models;
- deterministic epoch and assignment identities derived from authoritative state;
- one total, attention-ordered assignment set per epoch;
- preservation of existing valid assignment and reservation identities before new admission;
- no priority-only displacement of committed work while contention preemption remains deferred to Increment E;
- a provisional `PLANNED` epoch that cannot be observed through the worker-facing assignment API;
- one PostgreSQL transaction for immutable assignment rows, the immutable complete epoch snapshot, the current reservation set, and the scheduler's `COMMITTED` epoch pointer;
- in-memory publication only after that database transaction commits;
- append-only epoch/assignment history plus an authoritative current-epoch pointer;
- optimistic generation checks that reject stale schedulers instead of allowing them to overwrite a newer epoch;
- exact PostgreSQL restart reconstruction and idempotent persistence;
- rollback tests proving that an injected late transaction failure exposes neither assignments nor a partial epoch;
- discrete-resource and configured-headroom enforcement without oversubscription;
- snapshot validation that rejects mismatched revisions, assignment identities, epoch identities, reservations, policy versions, and incomplete current sets.

An Increment D assignment is a durable `READY` entitlement, not a worker claim. Increment D does not mark several tasks `RUNNING`, introduce leases/heartbeats, execute capabilities, or release reservations on completion. Those lifecycle semantics remain explicitly assigned to Increment F after contention behavior is generalized in Increment E.

The database-independent Increment D tests pass locally (`7 passed, 3 deselected`). GitHub Actions run #101 verified the complete Increment D head with PostgreSQL 16: `122 passed, 4 skipped in 12.69s`.

### Increment E — contention-driven interruption semantics

The fifth v0.7 increment generalizes interruption from one active focus to a
complete committed assignment set.

Implemented/tested properties include:

- an explicit `v0.7-e-contention-v1` preemption-policy version;
- preemption only after direct safe admission fails;
- exact minimum victim count across all deficient resource classes, followed by
  one total deterministic victim order: least important, immediately
  preemptible, newest assignment, then UUID;
- eligibility only for assignments that hold capacity in a resource class the
  blocked higher-priority task actually lacks;
- same-priority stability and normal-scheduler immunity for `ATOMIC` work;
- immediate atomic replacement for wholly `PREEMPTIBLE` victim sets;
- durable `CHECKPOINT_ONLY` replacement intents that retain every selected
  assignment and reservation until all required safe checkpoints are recorded;
- protection of the target's already-free capacity while it waits, so later
  lower-ranked work cannot invalidate half of its replacement contract;
- cancellation without victim churn when the target later fits concurrently;
- append-only `REQUESTED`, `CHECKPOINT_ACKNOWLEDGED`, `EXECUTED`, and
  `CANCELLED` causal events;
- optimistic preemption-state revisions that prevent concurrent checkpoint
  writers from erasing one another's progress;
- immutable epoch snapshots that bind policy, pending intents, causal event ids,
  and executed/cancelled preemption ids to deterministic epoch identity;
- restart reconstruction, idempotent event persistence, and rollback isolation;
- backward-compatible validation of pre-Increment-E epoch identities.

Increment E still exposes `READY` entitlements rather than worker claims. A
released victim remains a durable `QUEUED` task for reconsideration in a later
epoch; this increment does not invent leases, heartbeats, completion release,
or effect execution before Increment F's worker contract exists.

The database-independent Increment E suite passes locally (`10 passed, 3
deselected`). GitHub Actions run #103 verified the complete Increment E head
with PostgreSQL 16: `136 passed, 4 skipped in 13.73s`.

### Pre-Increment-F resource safety gate — observed host capacity

The worker boundary now has an authoritative resource-observation prerequisite
rather than treating durable configuration as current availability.

Implemented/tested properties include:

- a replaceable standard-library host probe for current CPU pressure and
  available RAM, with Linux and Windows native counters and conservative macOS
  support;
- a real `MEMORY_RAM` resource dimension whose units are MiB;
- an explicit `v0.7-resource-observation-v1` policy with a five-second maximum
  observation age;
- discovered `host-cpu`, `host-ram-mib`, and `local-llm` pools, with local LLM
  capacity defaulting to exactly one concurrent inference;
- transaction-level global reservation checks, ordered resource-row locks, and
  rollback on contention so separate processes/scheduler keys cannot race past
  the same physical pool or the one-LLM ceiling;
- a default CPU pressure ceiling of 85%, multi-core OS headroom, RAM headroom
  equal to the greater of 10% or 1 GiB, and a further 20% uncertainty reserve;
- one immutable observation per planning cycle containing raw normalized host
  metrics, configured and committed capacity, each headroom component, the
  resulting admission envelope, health, and probe failures;
- deterministic observation identity and an epoch reference to the exact
  observation and policy version consumed;
- fail-closed behavior for missing, stale, incomplete, mismatched, or failed
  observations—there is no fallback to configured CPU/RAM capacity;
- persisted process estimates with provenance values for declared, profiled,
  historical-peak, and conservative-default estimates;
- a current conservative fallback of one CPU slot and 512 MiB RAM for ordinary
  work, or one CPU slot, 4 GiB RAM, and one exclusive LLM slot for LLM work;
- preservation of explicit/profiled estimates so real peak data can replace
  fallback guesses without changing the admission contract;
- atomic PostgreSQL publication of the observation, estimate-bearing task
  state, assignments, reservations, epoch, and scheduler pointers;
- restart reconstruction, deterministic replay, and rollback isolation for the
  observation path.

The probe never runs inside deterministic policy evaluation. The local
controller first assesses unestimated work, captures one bounded host sample,
attaches it as explicit state, and only then asks the scheduler for an epoch.
Identical task state, observation, and policy therefore still produce an
identical assignment set.

At this checkpoint the gate controlled only `READY` assignment green-lighting.
Increment F now re-observes immediately before a claim becomes executable and
makes the guarded launcher the only Prometheist-owned worker process-start
boundary. The v0.6 Primary Agent was retained only until the replacement path
reproduced its useful behavioral evidence, then removed before this release
candidate.

The database-independent resource-observation suite passes locally (`11
passed, 3 deselected`). GitHub Actions run #105 verified the complete safety
gate head with PostgreSQL 16: `150 passed, 4 skipped in 24.13s`.

### Increment F — durable disposable-worker protocol

The sixth v0.7 increment turns a committed `READY` entitlement into executable
work only through an expiring, freshly guarded claim.

Implemented/tested properties include:

- immutable, agent-neutral `WorkerStep` contracts derived only from current
  committed assignments;
- deterministic step, claim, checkpoint, result, and claim-observation IDs;
- one stable idempotency key across every attempt for a step;
- explicit `NO_EXTERNAL_EFFECT`, `IDEMPOTENT_WITH_KEY`, and `AT_MOST_ONCE`
  effect policies;
- exact claim-time CPU/RAM/LLM reobservation using the full policy persisted
  with the committed epoch, not caller-selected thresholds;
- immutable granted and denied claim observations with freshness bounds,
  resource snapshots, active-claim sets, and reasons;
- PostgreSQL-enforced exclusion of simultaneous claims for the same step or
  assignment;
- expiring leases, ownership-checked heartbeats, deterministic abandonment,
  and recovery by a fresh worker;
- append-only checkpoint revisions handed to the next worker claim;
- exactly one terminal result per step and idempotent completion retries;
- fail-closed abandoned recovery for `AT_MOST_ONCE` effects that require
  explicit reconciliation;
- reservation protection that prevents a new scheduler epoch from releasing
  capacity beneath a live worker;
- a `GuardedWorkerLauncher` that commits the claim before invoking a shell-free
  process factory, injects only bounded durable identifiers, never spawns after
  denial, and releases the claim if process creation fails;
- forced child-process disappearance followed by lease-expiry recovery from
  PostgreSQL alone.

The worker protocol still does not choose queue work, interpret capability
registrations, mark an entire durable task complete, or replace the Primary
Agent interaction path. Those decisions remain with the Attention Fabric and
the next integration increments. See
[`INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md)
for the implementation boundary and verification status.

GitHub Actions run #116 verified the Increment F head with PostgreSQL 16:
`171 passed, 4 skipped in 23.34s`. Real Windows worker launch/recovery and real
LLM-backed capability execution remain separate development-machine gates.

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

**Status:** implemented and verified in CI.

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

The implemented boundary preserves all valid committed assignments before considering new candidates. A later higher-priority arrival therefore cannot displace committed lower-priority work in Increment D; it remains queued when capacity is unavailable. Contention-driven victim selection and reservation release begin only in Increment E.

`PLANNED` epochs exist only in scheduler memory and remain worker-invisible. PostgreSQL stores only immutable `COMMITTED` epochs. Assignment rows, the epoch's complete assignment/reservation snapshot, the authoritative current reservations, and the scheduler's current-epoch pointer commit together before the in-memory worker view changes.

Tests:

- identical authoritative state -> identical complete assignment/reservation set;
- total ordering remains deterministic;
- same-priority arrivals do not cause unnecessary churn;
- no resource is oversubscribed;
- discrete resources never exceed their declared concurrency;
- partial persistence cannot expose half an epoch as authoritative state.

### Increment E — contention-driven interruption semantics

**Status:** implemented and verified in CI.

Generalize preemption from one active task to multiple concurrent assignments.

A higher-priority task should cause preemption only when it cannot otherwise be admitted. The scheduler should release only the minimum deterministically selected lower-priority compatible work needed to satisfy the missing reservation, and only where interruption policy permits.

Tests:

- no preemption occurs when safe concurrent capacity exists;
- preemption affects only resources relevant to the blocked higher-priority task;
- `ATOMIC` remains non-preemptible under normal scheduler authority;
- `CHECKPOINT_ONLY` records pending replacement but retains its reservation until checkpoint;
- unrelated work continues running;
- victim selection is deterministic when several active tasks are eligible to yield.

The implemented selector minimizes victim cardinality exactly over the blocked
task's resource deficits. Equal-cardinality sets use the policy order documented
above. If any selected victim is `CHECKPOINT_ONLY`, none of the selected work is
partially released; the complete replacement becomes visible only in a later
committed epoch after every required checkpoint acknowledgement.

### Resource observation gate — implemented prerequisite for Increment F

**Status:** implemented and verified in CI.

The bounded observation mechanism now:

- discovers installed/available resource identities separately from policy
  capacity;
- samples current CPU and RAM pressure through a replaceable observer outside
  the scheduler;
- persists an immutable, timestamped/freshness-bounded resource snapshot;
- makes each scheduling epoch reference the exact snapshot it consumed;
- applies fail-closed behavior to stale, missing, mismatched, or failed
  observations;
- keeps scheduling deterministic for identical task state, snapshot, and
  policy.

The scheduler performs no unrecorded live reads in the middle of policy
evaluation. Accelerator/VRAM pressure and inference-backend state remain
unobserved dimensions; the current conservative protection is the single LLM
slot plus the LLM task's larger RAM estimate. Those dimensions require explicit
contracts if hardware acceptance shows they matter independently.

### Increment F — durable worker protocol

**Status:** core protocol implemented and verified in PostgreSQL 16 CI;
development-machine worker acceptance is tracked separately.

The implemented worker contract is independent of named agents.

A worker receives a durable envelope containing only what it needs to execute
one bounded step:

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

The worker may invoke a model or another capability, return a structured
result, persist a checkpoint/result, and disappear. A worker that disappears
without cleanup leaves an expiring claim; a safe effect policy allows a fresh
worker to recover the same step and idempotency key.

The scheduler/fabric—not the worker—decides what work exists and what receives attention.

The release-candidate capability slice adapts the deterministic v0.6 registry
into task/worker-neutral terminology. It preserves bounded deterministic
matching, canonical-before-supplemental discovery, no-match abstention,
progressive disclosure, and auditable selection without preserving
`CapabilityKind.AGENT` or `requesting_agent` as architectural concepts. The
selected `internal_memory` and `memory_analysis` registrations execute through
application-owned bindings behind durable worker steps.

Tests:

- worker can be destroyed after assignment but before completion;
- expired/abandoned assignment can be recovered deterministically;
- retry retains one stable external-effect key when idempotency is declared;
- completed work cannot be claimed again;
- fresh worker can resume from a committed checkpoint;
- claim denial cannot reach the process factory;
- live worker capacity cannot be released by epoch replacement.

### Increment G — replace Primary-Agent orchestration path

**Status:** implemented and verified in PostgreSQL 16 CI; development-machine
acceptance is tracked separately.

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

The compatibility Primary Agent and specialist path was removed only after the
replacement runtime and continuity regressions were in place. Historical event
types remain readable for existing ledgers.

The new `interaction_runtime` path forms one durable Attention task and
executes reference analysis, capability discovery/execution, response
synthesis, and idempotent result persistence as separately claimed worker
steps. The CLI launches each stage as a separately guarded child process. Fresh
workers resume by inspecting immutable step results in PostgreSQL; the path has
no Primary-Agent dependency. See
[`INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md`](INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md).

GitHub Actions run #123 verified the complete Increment G head with PostgreSQL
16: `177 passed, 4 skipped in 26.78s`.

### Increment H — forced concurrent restart acceptance

**Status:** implemented in the deterministic PostgreSQL suite; native-machine
execution remains part of the final acceptance script.

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

The deterministic scenario admits three assignments, checkpoints a
`CHECKPOINT_ONLY` victim, introduces resource-contending P0 work, destroys all
three worker processes, reconstructs state in a fresh process, recovers two
idempotent effects without duplication, readmits the checkpointed task under a
new immutable assignment generation, and completes the workload. The real
development-machine path remains a separate PostgreSQL/Ollama/hardware gate.

### Post-worker continuity migration gate

**Status:** ported to the guarded task/worker CLI path and collected in CI;
execution with the real local Ollama model remains part of the native gate.

The frozen v0.6 four-turn continuity scenario is rewritten against the new
task/worker path and preserves these acceptance properties:

- one fresh external process/worker context per turn;
- recent and older cross-session evidence needed in the same response;
- distractor history;
- exact required source-event provenance;
- polarity-sensitive answer validation;
- causal-source fidelity;
- opaque identifier fidelity.

The new path must reproduce or improve the accepted v0.6 behavior without using a conversation ID as the user's semantic memory namespace.

### Release-candidate state

The code-complete candidate now demonstrates every deterministic milestone
criterion in PostgreSQL CI, including task-neutral capability execution,
concurrent forced-restart recovery, and removal of compatibility orchestration.
GitHub Actions run #129 verified the exact release-candidate code head with
PostgreSQL 16: Ruff passed and pytest reported `205 passed, 5 skipped in
31.81s`; the five skips are the explicitly collected local-Ollama acceptance
cases rather than missing deterministic coverage.
The exact local command is `scripts/run_v07_acceptance.ps1`. Until that script
passes on the intended Windows/PostgreSQL/Ollama development machine, v0.7 is a
release candidate rather than an accepted baseline and PR #18 must remain
unmerged.

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
