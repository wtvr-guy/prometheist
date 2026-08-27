# Prometheist Documentation

This directory contains the current architecture, research/concept inputs, historical design records, audits, experiments, and roadmap for Prometheist.

## Current architecture

These documents define the forward architecture beginning with v0.7:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — authoritative target architecture: persistent cognitive system, resource-aware Attention Fabric, perception/salience, retention, capabilities, disposable workers, session-independent interaction continuity, and system-owned continuity.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — authoritative lossless-memory and scaling constraints: durable source memories are never replaced by summaries/aggregations, derived structures remain routing aids, recall is progressive and source-backed, model context is bounded, and ordinary recall must avoid inference growth proportional to corpus size.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — current continuity model: bounded durable WorkingState owns present activation; JIT Memory resolves older evidence; conversations/sessions/devices remain provenance rather than cognitive boundaries. Revised after the 2026-08-26 native acceptance experiment rejected phrase-specific continuity policy.
- [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) — decision record explaining the move away from a privileged Primary Agent, permanent agent hierarchy, rigid conversation-scoped cognition, and unconditional persistence of raw external input.
- [`ROADMAP.md`](ROADMAP.md) — milestone path from the accepted v0.5/v0.6 baselines through the first complete attention-centric v1.0 architecture. v0.7 now includes minimal active WorkingState; the post-v0.7 roadmap must be rebaselined before choosing whether richer epistemic WorkingState or perception/salience comes next.

There is intentionally no current `PRIMARY_AGENT_SPEC_SHEET` under `docs/architecture/`. Permanent agents are no longer first-class architectural primitives. Historical Primary-Agent material lives under `docs/history/`.

## Concept and research inputs

The [`concepts/`](concepts/) directory contains research and long-horizon design material. These files inform architecture but do not override current architecture documents or accepted experiment results by themselves.

- [`concepts/lessons_from_cognitive_neuroscience.md`](concepts/lessons_from_cognitive_neuroscience.md) — mechanism-level comparison with contemporary cognitive/computational neuroscience. Particularly relevant to durable working state, recurrent inference, episode formation, replay/consolidation, plasticity, prediction error, and the distinction between engineered provenance and biological memory.
- [`concepts/lessons_from_similar_projects.md`](concepts/lessons_from_similar_projects.md) — architecture mapping against Letta/MemGPT, AIOS, Soar, ACT-R, LIDA, OpenCog/Hyperon, LangGraph, Generative Agents, Voyager, M3-Agent, ABot-AgentOS, and related work. Use it to borrow tested mechanisms while preserving Prometheist's system-owned authority/failure model.
- [`concepts/a_future_history_of_mankind.txt`](concepts/a_future_history_of_mankind.txt) — long-horizon conceptual/vision context. It is not an implementation specification.

The 2026-08-26 WorkingState correction is an example of the intended research discipline: the concept reports suggested a mechanism, but the mechanism was pulled into v0.7 only after a frozen native acceptance test exposed the corresponding architectural gap.

## Architecture baselines

Long-lived mechanisms that remain applicable:

- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model. Associations are routing hints, never substitutes for source evidence.

These memory documents predate the attention-centric pivot. Where terminology conflicts, the current architecture documents listed above and the roadmap define the system-level architecture; `LOSSLESS_PROGRESSIVE_MEMORY.md` specifically controls durable-memory fidelity/scaling rules.

## Historical architecture and divergent v0.6 work

- [`history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](history/PRIMARY_AGENT_SPEC_SHEET_V06.md) — archived summary of the superseded v0.6 Primary-Agent design.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted v0.6 experimental result. Its stateless-worker/JIT-Memory findings and useful conversational behavior remain regression baselines; its Primary/specialist hierarchy is historical.
- [`milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) — comparison of the divergent `v0.6-capability-registry` branch against active v0.7 architecture.

Historical documents describe what was built or believed at a particular milestone. They do not override current architecture documents.

## Active milestone

- [`milestones/v0.7/README.md`](milestones/v0.7/README.md) — v0.7 scope, implementation record, release-candidate evidence, task-neutral capability execution, forced-restart acceptance, and native-machine gate.
- [`milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md`](milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md) — dated experimental record of why phrase/entity/recency continuity heuristics were rejected and replaced with bounded durable active canonical-event state.
- [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md) — deterministic scheduler invariants, quantitative admission/reservations, atomic epoch assignments, contention preemption, and durable worker claims/checkpoint recovery.
- [`milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) — distinction between attention priority and safe concurrent hardware-resource admission.
- [`milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md`](milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md) — safe concurrency versus focused resource concentration.
- [`milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md) — agent-neutral worker steps, guarded claim-time admission, leases, checkpoints, idempotent recovery, terminal results, and process-launch boundary.
- [`milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md`](milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md) — original Increment G durable interaction implementation record. Its phrase-based reference policy is superseded by the later WorkingState pivot above.
- [`milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) — migration policy for the divergent v0.6 continuity/capability work.

## Accepted milestones

- [`milestones/v0.4/MEMORY_KERNEL_V0.4.md`](milestones/v0.4/MEMORY_KERNEL_V0.4.md) — deterministic derived associations.
- [`milestones/v0.5/README.md`](milestones/v0.5/README.md) — final v0.5 status, accepted measurements, causal fixes, and closure state.
- [`milestones/v0.5/MEMORY_KERNEL_V0.5.md`](milestones/v0.5/MEMORY_KERNEL_V0.5.md) — original v0.5 design/experiment specification retained as research context.
- [`milestones/v0.5/SCALE_BENCHMARK.md`](milestones/v0.5/SCALE_BENCHMARK.md) — reproducible v0.5 scale-benchmark workflow.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted shared-JIT-memory and stateless-worker integration result.

The v0.5 and v0.6 documents are intentionally preserved as historical evidence. Architectural changes alter their forward interpretation, not their measured results.

## Experiment records and audits

Dated experiment records preserve the sequence of hypotheses, failures, fixes, and measurements rather than collapsing them into retrospective claims.

Audit records under [`audits/`](audits/) similarly describe the repository at the time of each audit and may refer to superseded architecture.

## Benchmark fixtures

Machine-readable benchmark fixtures remain in repository-level [`benchmarks/`](../benchmarks/) because they are runtime test inputs rather than narrative documentation.
