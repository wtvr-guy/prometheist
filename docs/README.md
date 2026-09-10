# Prometheist Documentation

This directory contains the current constitutional authorities, architecture, engineering governance, research/concept inputs, historical design records, audits, experiments, and roadmap for Prometheist.

## Constitutional governance

[`../CONSTITUTION.md`](../CONSTITUTION.md) is the highest-level normative engineering document in the repository. It collects the system-wide rules that future Prometheist implementations and audits must obey.

Every constitutional article points to one or more deep-dive authorities:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — system-owned continuity, disposable/stateless cognition, capability authority, model-output minimization, and external knowledge boundaries.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — lossless canonical durable memory, replaceable derived structures, bounded progressive recall, evidence admission, and memory scaling.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — bounded WorkingState, automatic per-percept memory activation, session-independent continuity, recurrent fresh routing, and topic resumption.
- [`architecture/SYSTEM_DETERMINISM.md`](architecture/SYSTEM_DETERMINISM.md) — current deterministic application-envelope and replay contract.
- [`architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md) — attention/resource-admission separation, safe concurrency, headroom, preemption, guarded worker claims, and durable execution.
- [`architecture/LOCAL_FIRST_PORTABILITY.md`](architecture/LOCAL_FIRST_PORTABILITY.md) — local-first/user-sovereignty, component-replaceability, and portability requirements.
- [`architecture/PERCEPT_TO_RESPONSE_PIPELINE.md`](architecture/PERCEPT_TO_RESPONSE_PIPELINE.md) — percept classes, response policy, user-prompt vs non-user-percept handling, and deterministic response requirements.
- [`engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md) — one-mechanism experimental discipline, negative-result retention, behavioral-number classification, and evidence standards.
- [`engineering/TESTING_AND_ACCEPTANCE.md`](engineering/TESTING_AND_ACCEPTANCE.md) — deterministic CI versus native acceptance, statelessness/restart/provenance/boundedness evidence, failure testing, and acceptance gates.
- [`engineering/CONSTITUTIONAL_GOVERNANCE.md`](engineering/CONSTITUTIONAL_GOVERNANCE.md) — document precedence, amendment procedure, `PASS`/`FAIL`/`GAP` audit semantics, per-article codebase audits, and implementation review policy.

Constitutional deep dives are subordinate to the Constitution and may specialize it without weakening it. Current architecture and milestone documents are subordinate to those authorities. Historical and experimental documents are retained as evidence, not as overrides.

Adoption of the Constitution does **not** assert that the current branch already passes every article. Forward-looking portability, export/restore, explicit erasure, or other not-yet-built constitutional targets remain future work unless explicitly documented otherwise.

## Current architecture

These documents define the forward architecture beginning with v0.7:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — authoritative target architecture: persistent cognitive system, resource-aware Attention Fabric, bounded WorkingState, and durable provenance.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — authoritative lossless-memory and scaling constraints: durable source memories are never replaced by derived summaries, and memory growth must remain bounded.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — current continuity model: bounded durable WorkingState owns present activation; every percept receives a small default memory aperture.
- [`architecture/SYSTEM_DETERMINISM.md`](architecture/SYSTEM_DETERMINISM.md) — current deterministic application-envelope and replay contract.
- [`architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md) — timeless normative authority for Attention Fabric, resource safety, preemption, assignment durability, and worker claims.
- [`architecture/LOCAL_FIRST_PORTABILITY.md`](architecture/LOCAL_FIRST_PORTABILITY.md) — long-lived local-first, user-sovereignty, component-replaceability, and portability requirements.
- [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) — decision record explaining the move away from a privileged Primary Agent, permanent agent hierarchy, and conversation-bound continuity.
- [`architecture/PERCEPT_TO_RESPONSE_PIPELINE.md`](architecture/PERCEPT_TO_RESPONSE_PIPELINE.md) — percept handling and response policy, including the distinction between user prompts and other percept classes.
- [`ROADMAP.md`](ROADMAP.md) — milestone path from the accepted v0.5/v0.6 baselines through the first complete attention-centric v1.0 architecture. v0.7 now includes minimal WorkingState and default aperture behavior.

There is intentionally no current `PRIMARY_AGENT_SPEC_SHEET` under `docs/architecture/`. Permanent agents are no longer first-class architectural primitives. Historical Primary-Agent material lives under `docs/history/`.

## Current protocol rules

Experimental corrections from native v0.7 acceptance now apply across the current architecture:

1. **Basic internal-memory access is substrate, not a live model-selected capability.** A fresh stateless model cannot reliably decide whether unseen memory matters before potentially relevant memory has been surfaced.
2. **Model-generated natural language is a representation of last resort.** Prefer enums, booleans, application-owned IDs, bounded integers, and mechanically verified selections for machine control.
3. **Control-plane authority is deterministic wherever it can be.** Models may make bounded semantic selections, but application-owned identity, dependencies, ordering, resource policy, retention, and replay remain deterministic.
4. **Percepts are broader than user prompts.** User prompts are one percept class; sensor observations, background state changes, and other non-conversational inputs may also be percepts.
5. **Not all percepts require a user-facing response.** Whether a response is required belongs to the deterministic intake policy for that percept class, not to the final responder.

The current live runtime wires only the explicit user-prompt percept path; other percept classes should get their own intake/runtime entrypoints rather than silently reusing `response_required=true`.

Aperture activation is intentionally higher-recall than conservative evidence admission. An activated event is potentially relevant enough to expose; it is not automatically sufficient evidence for a claim.

## Concept and research inputs

The [`concepts/`](concepts/) directory contains research and long-horizon design material. These files inform architecture but do not override the Constitution, constitutional deep dives, current architecture, or the active roadmap.

- [`concepts/lessons_from_cognitive_neuroscience.md`](concepts/lessons_from_cognitive_neuroscience.md) — mechanism-level comparison with contemporary cognitive/computational neuroscience. Particularly useful when evaluating whether a richer epistemic WorkingState should precede later milestones.
- [`concepts/lessons_from_similar_projects.md`](concepts/lessons_from_similar_projects.md) — architecture mapping against Letta/MemGPT, AIOS, Soar, ACT-R, LIDA, OpenCog/Hyperon, LangGraph, Generative Agents, and related systems.
- [`concepts/a_future_history_of_mankind.txt`](concepts/a_future_history_of_mankind.txt) — long-horizon conceptual/vision context. It is not an implementation specification.

The v0.7 WorkingState/aperture corrections illustrate the intended research discipline: concept reports suggested related mechanisms, but changes entered the release candidate only after frozen native tests and explicit behavioral regressions justified them.

## Architecture baselines

Long-lived mechanisms that remain applicable:

- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model. Associations are routing hints, never substitutes for source evidence.

These memory documents predate the attention-centric pivot. Where terminology conflicts, the Constitution and constitutional deep dives control, followed by the other current architecture documents and then the historical records.

## Historical architecture and divergent v0.6 work

- [`history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](history/PRIMARY_AGENT_SPEC_SHEET_V06.md) — archived summary of the superseded v0.6 Primary-Agent design.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted v0.6 experimental result. Its stateless-worker/JIT-Memory findings and useful conversational behavior remain regression baselines.
- [`milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) — comparison of the divergent `v0.6-capability-registry` branch against active architecture.

Historical documents describe what was built or believed at a particular milestone. They do not override current constitutional or architecture documents.

## Active milestone

- [`milestones/v0.7/README.md`](milestones/v0.7/README.md) — v0.7 scope, implementation record, release-candidate evidence, task-neutral capability execution, forced-restart acceptance, and native validation.
- [`milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md`](milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md) — dated experimental record of why phrase/entity/recency continuity heuristics and “always respond” assumptions were replaced.
- [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md) — v0.7 implementation/design record for deterministic scheduling, quantitative admission/reservations, epochs, and preemption.
- [`milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) — accepted v0.7 decision record supporting constitutional attention/resource separation.
- [`milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md`](milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md) — safe concurrency versus focused resource concentration.
- [`milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md) — implementation evidence for the constitutional guarded disposable-worker protocol.
- [`milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md`](milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md) — original Increment G durable interaction implementation record.
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

Future repository-wide architecture audits should use `CONSTITUTION.md` plus [`engineering/CONSTITUTIONAL_GOVERNANCE.md`](engineering/CONSTITUTIONAL_GOVERNANCE.md) as the governing checklist and evidence standard.

## Benchmark fixtures

Machine-readable benchmark fixtures remain in repository-level [`benchmarks/`](../benchmarks/) because they are runtime test inputs rather than narrative documentation.
