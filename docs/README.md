# Prometheist Documentation

This directory contains project documentation that is useful for understanding the architecture, research milestones, and benchmark history without cluttering the repository root.

## Architecture

Long-lived design documents and specifications:

- [`architecture/PRIMARY_AGENT_SPEC_SHEET.md`](architecture/PRIMARY_AGENT_SPEC_SHEET.md) — Primary Agent behavior and control contract.
- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model.

## Milestones

Versioned research checkpoints:

- [`milestones/v0.4/MEMORY_KERNEL_V0.4.md`](milestones/v0.4/MEMORY_KERNEL_V0.4.md) — deterministic derived associations.
- [`milestones/v0.5/MEMORY_KERNEL_V0.5.md`](milestones/v0.5/MEMORY_KERNEL_V0.5.md) — robustness, support-aware evidence admission, bounded PostgreSQL candidate routing, and scale characterization.
- [`milestones/v0.5/SCALE_BENCHMARK.md`](milestones/v0.5/SCALE_BENCHMARK.md) — reproducible v0.5 scale-benchmark workflow.

## v0.5 experiment record

The dated files under [`milestones/v0.5/experiments/`](milestones/v0.5/experiments/) preserve the experimental sequence used to diagnose and close v0.5 failures:

1. `V05_SCALE_BASELINE_2026-08-21.md` — frozen first full-scale baseline.
2. `V05_ASSOCIATION_FIX_RESULT_2026-08-21.md` — association-activation bookkeeping correction.
3. `V05_SUPPORT_GATE_REGRESSION_2026-08-21.md` — first support-gate regression and diagnosis.
4. `V05_SUPPORT_GATE_RESULT_2026-08-21.md` — accepted support-aware evidence-admission result.
5. `V05_CANDIDATE_ROUTER_RESULT_2026-08-21.md` — accepted specificity-aware PostgreSQL candidate-router result.

These records are intentionally retained as research evidence rather than collapsed into one retrospective summary. They document which mechanism changed, what failed, and what was measured at each step.

## Benchmark fixtures

Machine-readable benchmark fixtures remain in the repository-level [`benchmarks/`](../benchmarks/) directory because they are runtime test inputs rather than narrative documentation.
