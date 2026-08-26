# Increment F — Durable Disposable-Worker Protocol

**Implementation date:** 2026-08-26

**Status:** implemented and verified in PostgreSQL 16 CI; post-implementation development-machine acceptance remains a separate evidence gate.

## Decision

A committed `READY` assignment is an entitlement, not permission to start a
process. Prometheist may execute one bounded step only after an atomic guarded
claim re-observes current host pressure and commits an expiring lease. The
Attention Fabric owns work selection and capacity; disposable workers borrow
that capacity without gaining scheduling authority or durable identity.

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
- `AT_MOST_ONCE` fails closed after abandonment until an explicit future
  reconciliation mechanism decides what happened.

Claims have deterministic attempt IDs, one owner, a bounded lease, and
ownership-checked heartbeats. Checkpoints are append-only deterministic
revisions. A step has at most one immutable terminal result, and a completed
step cannot be claimed again.

## Guarded claim boundary

Every claim:

1. samples live CPU/RAM pressure outside deterministic policy;
2. locks scheduler state, the step, and physical resource rows in a stable
   order;
3. marks expired leases abandoned;
4. reconstructs capacity held by all still-live claims;
5. loads the exact `ResourceSafetyPolicy` persisted with the current epoch;
6. rejects missing, stale, mismatched, unhealthy, oversubscribed, non-current,
   already-claimed, or already-completed work;
7. persists the exact resource snapshot and granted/denied reason;
8. commits a lease before any process may start.

`GuardedWorkerLauncher` is the only Prometheist-owned worker process-start
surface. It does not use a shell. It hands the child only durable IDs,
idempotency key, and checkpoint revision through environment variables. A
worker can reconstruct its ownership-checked live envelope and latest
checkpoint from PostgreSQL by claim ID. A denied claim never reaches the
process factory; a spawn failure releases the new claim because no worker began
execution.

The scheduler cannot replace a reservation set while a live worker holds any
reservation that would be removed. The worker must checkpoint, complete, or
explicitly release first; an expired lease is abandoned before replacement.

## PostgreSQL state

Increment F adds:

- `attention_worker_steps`;
- `attention_worker_claim_observations`;
- `attention_worker_claims`;
- `attention_worker_checkpoints`;
- `attention_worker_results`.

Partial unique indexes enforce at most one active claim per step and assignment.
Foreign keys bind every lifecycle record back to its durable step, assignment,
claim, and resource decision. Checkpoint and result rows are immutable at the
application boundary.

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

Static compilation, whitespace validation, and collection of all 175 repository
tests pass in the implementation workspace. GitHub Actions run #116 then
executed the complete suite against PostgreSQL 16: `171 passed, 4 skipped in
23.34s`. The earlier Windows local acceptance predates Increment F and does not
validate this worker boundary.

## Deliberate boundary

Increment F does not port the v0.6 Capability Registry, invoke real registered
capabilities/models, complete whole Attention Fabric tasks, replace the Primary
Agent interaction path, add accelerator/VRAM observation, or implement dynamic
focus concentration. Capability discovery should be adapted next in
task/worker-neutral terms; interaction decomposition remains Increment G. Focus
concentration remains evidence-gated until real worker resource profiles exist.
