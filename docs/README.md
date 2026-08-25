# Prometheist Documentation

This directory contains project documentation useful for understanding the architecture, research milestones, audit history, and roadmap without cluttering the repository root.

## Architecture

Long-lived design documents and specifications:

- [`architecture/PRIMARY_AGENT_SPEC_SHEET.md`](architecture/PRIMARY_AGENT_SPEC_SHEET.md) — system-wide stateless-agent architecture, Primary Agent responsibilities, shared JIT memory principles, persistence, provenance, and user-control constraints.
- [`architecture/CAPABILITY_REGISTRY.md`](architecture/CAPABILITY_REGISTRY.md) — deterministic just-in-time discovery of currently installed agents/tools without preloading the full capability catalog into LLM prompts.
- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model.

## Roadmap

- [`ROADMAP.md`](ROADMAP.md) — engineering milestones from the accepted v0.5 memory baseline through stateless multi-agent integration, durable execution, and the first complete v1.0 Prometheist architecture.

## Milestones

Versioned research checkpoints:

- [`milestones/v0.4/MEMORY_KERNEL_V0.4.md`](milestones/v0.4/MEMORY_KERNEL_V0.4.md) — deterministic derived associations.
- [`milestones/v0.5/README.md`](milestones/v0.5/README.md) — final v0.5 status, accepted measurements, causal fixes, and closure state.
- [`milestones/v0.5/MEMORY_KERNEL_V0.5.md`](milestones/v0.5/MEMORY_KERNEL_V0.5.md) — original v0.5 design/experiment specification retained as research context.
- [`milestones/v0.5/SCALE_BENCHMARK.md`](milestones/v0.5/SCALE_BENCHMARK.md) — reproducible v0.5 scale-benchmark workflow.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — shared-JIT-memory/stateless-MAS milestone, including deterministic capability discovery and the later deterministic-first, bounded pgvector `SEMANTIC_CANDIDATE` recovery route.

## v0.6 validation record

- [`milestones/v0.6/experiments/V06_CONVERSATION_CONTINUITY_RESULT_2026-08-24.md`](milestones/v0.6/experiments/V06_CONVERSATION_CONTINUITY_RESULT_2026-08-24.md) — frozen multi-turn, fresh-process validation of immediate conversational continuity plus older cross-conversation JIT recall, including failures, causal fixes, and CI gates.

## v0.5 experiment record

The dated files under [`milestones/v0.5/experiments/`](milestones/v0.5/experiments/) preserve the experimental sequence used to diagnose and close the measured v0.5 failures:

1. `V05_SCALE_BASELINE_2026-08-21.md` — frozen first full-scale baseline.
2. `V05_ASSOCIATION_FIX_RESULT_2026-08-21.md` — association-activation bookkeeping correction.
3. `V05_SUPPORT_GATE_REGRESSION_2026-08-21.md` — first support-gate regression and diagnosis.
4. `V05_SUPPORT_GATE_RESULT_2026-08-21.md` — accepted support-aware evidence-admission result.
5. `V05_CANDIDATE_ROUTER_RESULT_2026-08-21.md` — accepted specificity-aware PostgreSQL candidate-router result.

These records are intentionally retained rather than collapsed into a single retrospective. They document which mechanism changed, what failed, and what was measured at each step.

## Audits

- [`audits/V05_CLOSURE_AUDIT_2026-08-21.md`](audits/V05_CLOSURE_AUDIT_2026-08-21.md) — static codebase audit performed before freezing v0.5 and beginning the multi-agent v0.6 work.
- [`audits/POST_V06_CODEBASE_REVIEW_2026-08-21.md`](audits/POST_V06_CODEBASE_REVIEW_2026-08-21.md) — post-v0.6 review of versioning, append-only enforcement, live JIT freshness scaling, CI, durable execution, and local-agent concurrency assumptions.

Audit records distinguish immediate correctness defects from deliberately deferred architecture/hardening work so later milestones do not silently inherit unresolved assumptions.

## Benchmark fixtures

Machine-readable benchmark fixtures remain in the repository-level [`benchmarks/`](../benchmarks/) directory because they are runtime test inputs rather than narrative documentation.
