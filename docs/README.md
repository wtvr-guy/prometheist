# Prometheist Documentation

This directory contains the current architecture, research milestones, historical design records, audits, experiments, and roadmap for Prometheist.

## Current architecture

These documents define the forward architecture beginning with v0.7:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — authoritative target architecture: persistent cognitive system, resource-aware Attention Fabric, perception/salience, retention, capabilities, disposable workers, session-independent interaction continuity, and system-owned continuity.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — conversations/sessions/devices are provenance metadata rather than cognitive boundaries; defines natural topic resumption and its future benchmark.
- [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) — decision record explaining the move away from a privileged Primary Agent, permanent agent hierarchy, rigid conversation-scoped cognition, and unconditional persistence of raw external input.
- [`ROADMAP.md`](ROADMAP.md) — milestone path from the accepted v0.5/v0.6 baselines through the first complete attention-centric v1.0 architecture.

There is intentionally no current `PRIMARY_AGENT_SPEC_SHEET` under `docs/architecture/`. Permanent agents are no longer first-class architectural primitives. Historical Primary-Agent material has been moved under `docs/history/`.

## Architecture baselines

Long-lived mechanisms that remain applicable:

- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model.

These memory documents predate the attention-centric pivot. Where terminology conflicts, `COGNITIVE_ARCHITECTURE.md` and the roadmap define the current system-level architecture.

## Historical architecture

- [`history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](history/PRIMARY_AGENT_SPEC_SHEET_V06.md) — archived summary of the superseded v0.6 Primary-Agent design, retained so the experimental path is not erased. The complete original remains available in Git history.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted v0.6 experimental result. Its stateless-worker/JIT-Memory findings and useful conversational behavior remain regression baselines; its Primary/specialist hierarchy is historical.

Historical documents describe what was built or believed at a particular milestone. They do not override current architecture documents.

## Active milestone

- [`milestones/v0.7/README.md`](milestones/v0.7/README.md) — v0.7 scope and implementation sequence for the durable resource-aware JIT Attention Fabric.
- [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md) — deterministic scheduler invariants, current implementation boundary, and planned resource/lane generalization.
- [`milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) — distinction between attention priority and safe concurrent hardware-resource admission.

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
