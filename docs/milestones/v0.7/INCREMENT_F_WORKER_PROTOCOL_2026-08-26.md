# Increment F — Durable Disposable-Worker Protocol

**Implementation date:** 2026-08-26

**Status:** implemented and verified v0.7 milestone record. Its durable-worker invariants are now constitutionalized by Article 14 of [`../../../CONSTITUTION.md`](../../../CONSTITUTION.md) and governed in depth by [`../../architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](../../architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md). This document remains implementation and test evidence for that authority. PostgreSQL 16 CI verified this increment; post-implementation development-machine acceptance remains a separate evidence gate.

## Decision

A committed `READY` assignment is an entitlement, not permission to start a process. Prometheist may execute one bounded step only after an atomic guarded claim re-observes current host pressure and commits an expiring lease. The Attention Fabric owns work selection and capacity; disposable workers borrow that capacity without gaining scheduling authority or durable identity.

## Durable contract

`WorkerStep` is immutable and agent-neutral. It binds:

- the committed assignment, task revision, and epoch sequence;
- one bounded `step_key` and required capability;
- the complete reservation references and bounded input references;
- one deterministic step ID and stable idempotency key;
- an explicit external-effect policy.

The effect policies make crash recovery explicit:

- `NO_EXTERNAL_EFFECT` may be retried after abandonment;
- `IDEMPOTENT_WITH_KEY` may be retried only with the same step-level key;
- `AT_MOST_ONCE` fails closed after abandonment until an explicit future reconciliation mechanism decides what happened.

Claims have deterministic attempt IDs, one owner, a bounded lease, and ownership-checked heartbeats. Checkpoints are append-only deterministic revisions. A step has at most one immutable terminal result, and a completed step cannot be claimed again.

## Guarded claim boundary

Every claim:

1. samples live CPU/RAM pressure outside deterministic policy;
2. locks scheduler state, the step, and physical resource rows in a stable order;
3. marks expired leases abandoned;
4. reconstructs capacity held by all still-live claims;
5. loads the exact `ResourceSafetyPolicy` persisted with the current epoch;
6. rejects missing, stale, mismatched, unhealthy, oversubscribed, non-current, already-claimed, or already-completed work;
7. persists the exact resource snapshot and granted/denied reason;
8. commits a lease before any process may start.

`GuardedWorkerLauncher` is the only Prometheist-owned worker process-start surface. It does not use a shell. It hands the child only durable IDs, idempotency key, and checkpoint revision through environment variables. A worker can reconstruct its ownership-checked live envelope and latest checkpoint from PostgreSQL by claim ID. A denied claim never reaches the process factory; a spawn failure releases the new claim because no worker began execution.

The scheduler cannot replace a reservation set while a live worker holds any reservation that would be removed. The worker must checkpoint, complete, or explicitly release first; an expired lease is abandoned before replacement.

## PostgreSQL state

Increment F adds:

- `attention_worker_steps`;
- `attention_worker_claim_observations`;
- `attention_worker_claims`;
- `attention_worker_checkpoints`;
- `attention_worker_results`.

Partial unique indexes enforce at most one active claim per step and assignment. Foreign keys bind every lifecycle record back to its durable step, assignment, claim, and resource decision. Checkpoint and result rows are immutable at the application boundary.

These table names are v0.7 implementation details, not constitutional interfaces. The constitutional requirement is the durable guarded ownership/recovery behavior they realize.

## Regression coverage

The focused suite covers:

- deterministic, agent-neutral step identity and registration idempotence;
- fresh high-pressure denial after an earlier low-pressure assignment;
- exact committed-policy enforcement and persisted stale denials;
- live-claim exclusion, heartbeat extension, and lease-expiry recovery;
- stable idempotency keys across abandoned attempts;
- fresh-worker checkpoint resumption;
- terminal-result idempotence and completed-work retry prevention;
- fail-closed `AT_MOST_ONCE` abandonment;
- scheduler reservation protection while a worker is live;
- forced child-process disappearance and PostgreSQL-only recovery;
- denial-before-spawn and spawn-failure claim release.

Static compilation, whitespace validation, and collection of all 175 repository tests pass in the implementation workspace. GitHub Actions run #116 then executed the complete suite against PostgreSQL 16: `171 passed, 4 skipped in 23.34s`. The earlier Windows local acceptance predates Increment F and does not validate this worker boundary.

## Deliberate boundary

Increment F does not by itself define the complete cognitive architecture. Capability discovery/execution, interaction decomposition, attention focus concentration, and later portability remain governed by their current architecture/milestone documents and the Constitution.
