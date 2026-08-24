# Prometheist Documentation

This directory contains the architecture, research milestones, audit history, experiment records, and roadmap for Prometheist.

## Current architecture

Start here for the post-v0.6 direction:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — current target architecture: persistent cognitive system, multi-lane Attention Fabric, perception/salience, retention, capabilities, disposable workers, and system-owned continuity.
- [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) — decision record explaining why Prometheist moved away from a privileged Primary Agent / fixed MAS hierarchy.
- [`ROADMAP.md`](ROADMAP.md) — revised milestone path from the accepted v0.5/v0.6 baselines through the first complete attention-centric v1.0 architecture.

## Architecture baselines

Long-lived design/reference documents:

- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model.
- [`architecture/PRIMARY_AGENT_SPEC_SHEET.md`](architecture/PRIMARY_AGENT_SPEC_SHEET.md) — **historical/superseded target architecture** used to guide the v0.6 Primary-Agent/stateless-specialist prototype. It remains useful as a record of the design that established shared JIT Memory and stateless LLM execution, but it is no longer the intended executive architecture from v0.7 onward.

## Active milestone

- [`milestones/v0.7/README.md`](milestones/v0.7/README.md) — v0.7 scope and implementation sequence for the durable multi-lane JIT Attention Fabric.
- [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md) — deterministic scheduler invariants, current single-focus implementation boundary, and planned resource/lane generalization.

## Accepted milestones

Versioned research checkpoints:

- [`milestones/v0.4/MEMORY_KERNEL_V0.4.md`](milestones/v0.4/MEMORY_KERNEL_V0.4.md) — deterministic derived associations.
- [`milestones/v0.5/README.md`](milestones/v0.5/README.md) — final v0.5 status, accepted measurements, causal fixes, and closure state.
- [`milestones/v0.5/MEMORY_KERNEL_V0.5.md`](milestones/v0.5/MEMORY_KERNEL_V0.5.md) — original v0.5 design/experiment specification retained as research context.
- [`milestones/v0.5/SCALE_BENCHMARK.md`](milestones/v0.5/SCALE_BENCHMARK.md) — reproducible v0.5 scale-benchmark workflow.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted shared-JIT-memory and stateless multi-component integration result.

The v0.5 and v0.6 documents are intentionally preserved as historical evidence. The 2026-08-24 pivot changes the interpretation and forward architecture; it does not rewrite or invalidate those experiments.

## v0.5 experiment record

The dated files under [`milestones/v0.5/experiments/`](milestones/v0.5/experiments/) preserve the experimental sequence used to diagnose and close the measured v0.5 failures:

1. `V05_SCALE_BASELINE_2026-08-21.md` — frozen first full-scale baseline.
2. `V05_ASSOCIATION_FIX_RESULT_2026-08-21.md` — association-activation bookkeeping correction.
3. `V05_SUPPORT_GATE_REGRESSION_2026-08-21.md` — first support-gate regression and diagnosis.
4. `V05_SUPPORT_GATE_RESULT_2026-08-21.md` — accepted support-aware evidence-admission result.
5. `V05_CANDIDATE_ROUTER_RESULT_2026-08-21.md` — accepted specificity-aware PostgreSQL candidate-router result.

These records are intentionally retained rather than collapsed into a retrospective. They document which mechanism changed, what failed, and what was measured at each step.

## Audits

- [`audits/V05_CLOSURE_AUDIT_2026-08-21.md`](audits/V05_CLOSURE_AUDIT_2026-08-21.md) — static codebase audit performed before freezing v0.5 and beginning v0.6 integration work.
- [`audits/POST_V06_CODEBASE_REVIEW_2026-08-21.md`](audits/POST_V06_CODEBASE_REVIEW_2026-08-21.md) — post-v0.6 review of versioning, append-only enforcement, JIT freshness scaling, CI, durable execution, and concurrency assumptions.

Audit records distinguish immediate correctness defects from deliberately deferred architecture/hardening work so later milestones do not silently inherit unresolved assumptions.

## Benchmark fixtures

Machine-readable benchmark fixtures remain in repository-level [`benchmarks/`](../benchmarks/) because they are runtime test inputs rather than narrative documentation.
