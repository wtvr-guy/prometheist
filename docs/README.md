# Prometheist Documentation

This directory contains the current architecture, research milestones, historical design records, audits, experiments, and roadmap for Prometheist.

## Current architecture

These documents define the forward architecture beginning with v0.7:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — authoritative target architecture: persistent cognitive system, resource-aware Attention Fabric, perception/salience, retention, capabilities, disposable workers, session-independent interaction continuity, and system-owned continuity.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — authoritative lossless-memory and scaling constraints: durable source memories are never replaced by summaries/aggregations, derived structures remain routing aids, recall is progressive and source-backed, model context is bounded, and ordinary recall must avoid inference growth proportional to corpus size. Where older architecture/roadmap language conflicts on post-admission aggregation or expiry, this document controls.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — conversations/sessions/devices are provenance metadata rather than cognitive boundaries; defines natural topic resumption and binds the future design to the accepted v0.6 fresh-process continuity baseline.
- [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) — decision record explaining the move away from a privileged Primary Agent, permanent agent hierarchy, rigid conversation-scoped cognition, and unconditional persistence of raw external input.
- [`ROADMAP.md`](ROADMAP.md) — milestone path from the accepted v0.5/v0.6 baselines through the first complete attention-centric v1.0 architecture.

There is intentionally no current `PRIMARY_AGENT_SPEC_SHEET` under `docs/architecture/`. Permanent agents are no longer first-class architectural primitives. Historical Primary-Agent material has been moved under `docs/history/`.

## Architecture baselines

Long-lived mechanisms that remain applicable:

- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model. Its canonical-event rule remains directly aligned with the current lossless-memory architecture: associations are routing hints, never substitutes for source evidence.

These memory documents predate the attention-centric pivot. Where terminology conflicts, the current architecture documents listed above and the roadmap define the system-level architecture; `LOSSLESS_PROGRESSIVE_MEMORY.md` specifically controls the durable-memory fidelity and scaling rules frozen on 2026-08-26.

## Historical architecture and divergent v0.6 work

- [`history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](history/PRIMARY_AGENT_SPEC_SHEET_V06.md) — archived summary of the superseded v0.6 Primary-Agent design, retained so the experimental path is not erased. The complete original remains available in Git history.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted v0.6 experimental result. Its stateless-worker/JIT-Memory findings and useful conversational behavior remain regression baselines; its Primary/specialist hierarchy is historical.
- [`milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) — comparison of the divergent `v0.6-capability-registry` branch against the active v0.7 architecture. It records which continuity tests/mechanisms must survive, which capability-registry ideas should be adapted, and which Primary-Agent/semantic-vector work should remain historical or deferred.

Historical documents describe what was built or believed at a particular milestone. They do not override current architecture documents.

The `v0.6-capability-registry` branch is intentionally not merged wholesale into v0.7. It contains valuable behavioral evidence and reusable mechanisms, but also superseded Primary-Agent orchestration, conflicting historical documentation, and semantic-memory experiments that belong to later evidence-gated work.

## Active milestone

- [`milestones/v0.7/README.md`](milestones/v0.7/README.md) — v0.7 scope, implementation record, release-candidate evidence, task-neutral capability execution, forced-restart acceptance, and the remaining native-machine gate.
- [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md) — deterministic scheduler invariants, quantitative admission/reservations, atomic epoch assignments, contention preemption, and durable worker claims/checkpoint recovery.
- [`milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) — distinction between attention priority and safe concurrent hardware-resource admission.
- [`milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md`](milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md) — clarifies that safe concurrency is a baseline rather than the goal: attention may narrow and concentrate most safely useful resources on a focal task while preserving system viability, perception/orientation capacity, determinism, and resource safety.
- [`milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md) — implementation record for agent-neutral worker steps, guarded claim-time admission, leases, checkpoints, idempotent recovery, terminal results, and the exclusive process-launch boundary.
- [`milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md`](milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md) — implementation record for the durable attention-centric interaction path, reusable reference policy, restartable stateless stages, and deterministic effect persistence.
- [`milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) — migration policy for the divergent v0.6 continuity/capability work.

## Accepted milestones

- [`milestones/v0.4/MEMORY_KERNEL_V0.4.md`](milestones/v0.4/MEMORY_KERNEL_V0.4.md) — deterministic derived associations.
- [`milestones/v0.5/README.md`](milestones/v0.5/README.md) — final v0.5 status, accepted measurements, causal fixes, and closure state.
- [`milestones/v0.5/MEMORY_KERNEL_V0.5.md`](milestones/v0.5/MEMORY_KERNEL_V0.5.md) — original v0.5 design/experiment specification retained as research context.
- [`milestones/v0.5/SCALE_BENCHMARK.md`](milestones/v0.5/SCALE_BENCHMARK.md) — reproducible v0.5 scale-benchmark workflow.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted shared-JIT-memory and stateless-worker integration result.

The v0.5 and v0.6 documents are intentionally preserved as historical evidence. The architectural pivot changes their interpretation and forward role; it does not rewrite their measured results.

## Experiment records and audits

Dated experiment records under milestone directories preserve the sequence of hypotheses, failures, fixes, and measurements rather than collapsing them into retrospective claims.

Audit records under [`audits/`](audits/) similarly describe the repository at the time of each audit. They may therefore refer to superseded architecture and should be read as historical snapshots unless explicitly updated.

## Benchmark fixtures

Machine-readable benchmark fixtures remain in repository-level [`benchmarks/`](../benchmarks/) because they are runtime test inputs rather than narrative documentation.
