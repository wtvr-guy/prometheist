# Prometheist post-v0.6 codebase review — 2026-08-21

## Context

This review follows the accepted v0.6 shared-JIT-memory/stateless-MAS milestone. A repository-wide GitHub Copilot audit reported a green local suite (`81 passed`) and raised six risks: package/milestone versioning, database-level append-only enforcement, JIT projection-freshness scaling, lack of CI, unimplemented durable execution, and single-user/concurrency assumptions.

The purpose of this record is to classify those findings against Prometheist's actual architecture and roadmap rather than treating every deferred capability as a current defect.

## Dispositions

### P06-01 — Package version vs. architectural milestone

**Copilot finding:** `pyproject.toml` / `uv.lock` report package version `0.4.0` while Prometheist has accepted architectural milestone v0.6.

**Assessment:** valid ambiguity, but not a runtime bug. The earlier v0.5 closure audit already identified this as D-06 and deliberately avoided an unprincipled version bump.

**Disposition:** clarify the version domains now; do not mechanically couple them.

Prometheist architectural labels (`v0.5`, `v0.6`, etc.) identify accepted research/integration checkpoints. The Python package version is currently internal packaging metadata and is not a project-status indicator. The root README and `pyproject.toml` now state this explicitly. A formal package-release scheme must be chosen before external package distribution.

This avoids creating a new false invariant where every experiment branch or research milestone forces package metadata and lockfile churn.

### P06-02 — Append-only history is application-enforced

**Copilot finding:** `events` is treated as append-only by application code, but PostgreSQL does not prevent an appropriately privileged actor from `UPDATE`/`DELETE` operations.

**Assessment:** correct and already documented as v0.5 audit item D-02. It is a hardening/threat-model gap, not a v0.6 correctness regression.

**Disposition:** defer database-level enforcement to v0.9, where the threat model and operational roles are defined. The schema now explicitly warns that its append-only property is application-level and must not be mistaken for tamper protection.

A production-grade design should prefer explicit database authorization boundaries over a cosmetic trigger-only solution. Likely elements include:

- a normal Prometheist runtime role that can `INSERT`/`SELECT` canonical history but cannot `UPDATE`/`DELETE` it;
- a separate migration/maintenance authority with narrowly defined privileges;
- explicit backup/restore and migration behavior;
- a defined response to database-owner/superuser compromise;
- independent integrity anchoring only if the accepted threat model requires detection against a database-level adversary.

Adding one of these mechanisms now, before the threat model exists, would create the appearance of immutability without establishing what adversary it is intended to resist.

### P06-03 — Live JIT projection-freshness bridge scaling

**Copilot finding:** the v0.6 adapter synchronizes derived memory before recall and may not scale cleanly to large histories.

**Assessment:** valid performance hypothesis, and slightly more specific than the Copilot summary. `jit_memory._ensure_projection_fresh()` currently loads all visible canonical events and all projected lexical event IDs on every memory request. Even when no projection work is required, that freshness check is O(N) in visible history size. If any event is missing, deterministic association derivation is run over the visible history before idempotent insertion.

The accepted v0.5 50k PostgreSQL latency measures the frozen kernel/candidate path; it does **not** establish the end-to-end latency of the v0.6 live freshness bridge.

**Disposition:** measure before optimizing. Do not rewrite a green retrieval architecture from an unmeasured scaling concern.

A future benchmark should separately measure:

1. a memory request when projections are already current;
2. a request after one newly appended event;
3. a request after a burst of newly appended events;
4. histories at representative 1k/10k/50k+ sizes;
5. lexical-only versus association-producing new events.

If the measured cost is material, the likely optimization boundary is a persisted projection watermark/high-water mark plus tail-only incremental derivation, not a change to the frozen v0.5 recall policy. This performance work belongs in v0.9 unless it becomes an empirical blocker earlier.

### P06-04 — No repository CI

**Copilot finding:** regression trust depends on one local PostgreSQL/Ollama development environment.

**Assessment:** valid reliability gap. The v0.5 audit already recorded this as D-05.

**Disposition:** partially fix now because a deterministic PostgreSQL CI lane is low-risk infrastructure and directly improves regression trust without changing Prometheist runtime architecture.

A GitHub Actions workflow has been added that:

- provisions disposable PostgreSQL;
- installs Python 3.12 and `uv`;
- synchronizes from the checked-in lockfile with `uv sync --frozen`;
- runs the normal pytest suite.

Tests requiring a live Ollama daemon continue to skip in CI and remain part of local acceptance verification. This does **not** constitute complete release automation, model-backend CI, migration testing, or portability testing; those remain v0.9 work.

### P06-05 — Durable execution is not implemented

**Copilot finding:** Prometheist does not yet persist/resume unfinished multi-agent execution state across complete process destruction.

**Assessment:** correct observation, incorrect classification if called a defect. This is exactly the primary question of the next planned milestone, v0.7.

**Disposition:** no v0.6 patch. Freeze the accepted v0.6 architecture and begin v0.7 from a deliberately failing restartable-work acceptance scenario.

The v0.7 implementation should not be hidden inside memory events ad hoc. It needs explicit durable execution/task state, lifecycle transitions, execution identifiers, persisted handoffs/results, and retry/idempotency semantics sufficient to prove process-kill recovery with fresh LLM calls.

### P06-06 — Single-user/local concurrency assumptions

**Copilot finding:** the event store is single-user/local and uses a per-conversation row lock/simple sequence counter.

**Assessment:** partly misframed. Prometheist is intentionally local-first **personal** infrastructure; multi-tenancy is not a v1.0 requirement. Becoming a multi-user service would add complexity that is orthogonal to the project's goal.

The relevant engineering question is whether multiple local Prometheist agents/processes can append concurrently without corrupting ordering. `event_store.record_event()` uses `SELECT ... FOR UPDATE` on the conversation row, so writers to the same conversation should serialize sequence assignment while writes to different conversations can proceed independently; PostgreSQL `BIGSERIAL` supplies global sequence values.

**Disposition:** add a regression test for the relevant concurrency invariant rather than introducing distributed/multi-tenant machinery. The new test opens independent PostgreSQL connections, releases eight writers against one conversation concurrently, and verifies unique contiguous `conversation_seq` values plus unique `global_seq` / event IDs.

The result must be verified locally and in CI before this disposition is treated as closed.

## Additional minor observation

`src/jit_agent/postgres_memory_kernel.py` still contains an introductory docstring from the pre-v0.6 period saying that a later MAS milestone may place the kernel behind the shared JIT-memory boundary. That statement is now historical/stale because v0.6 completed exactly that integration. It is documentation debt only and does not affect runtime behavior; it should be cleaned up during the next source-comment hygiene pass.

## Priority after this review

1. Verify the new concurrent-writer regression and PostgreSQL CI workflow.
2. Keep database immutability and broader release/operational hardening scoped to v0.9 unless a concrete earlier failure changes priority.
3. Benchmark the v0.6 freshness bridge before attempting any performance optimization.
4. Start v0.7 with a frozen failing process-kill/resume acceptance case.
5. Continue to resist semantic/vector/distributed-system additions unless a measured requirement earns them.
