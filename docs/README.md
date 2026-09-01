# Prometheist Documentation

This directory contains the current constitutional authorities, architecture, engineering governance, research/concept inputs, historical design records, audits, experiments, and roadmap for Prometheist.

## Constitutional governance

[`../CONSTITUTION.md`](../CONSTITUTION.md) is the highest-level normative engineering document in the repository. It collects the system-wide rules that future Prometheist implementations and audits are expected to preserve.

Every constitutional article points to one or more deep-dive authorities:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — system-owned continuity, disposable/stateless cognition, capability authority, model-output minimization, epistemic boundaries, causal provenance, and internal-memory/external-knowledge separation.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — lossless canonical durable memory, replaceable derived structures, bounded progressive recall, evidence authority, and memory-scaling invariants.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — bounded WorkingState, automatic per-percept memory activation, session-independent continuity, recurrent fresh-model routing, and rejection of phrase-specific continuity policy.
- [`architecture/SYSTEM_DETERMINISM.md`](architecture/SYSTEM_DETERMINISM.md) — deterministic control-plane authority, replay, authoritative inputs, total ordering, and prohibition on race-based durable authority.
- [`architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md) — attention/resource-admission separation, safe concurrency, headroom, preemption, guarded launch, disposable-worker recovery, and side-effect/idempotency governance.
- [`architecture/LOCAL_FIRST_PORTABILITY.md`](architecture/LOCAL_FIRST_PORTABILITY.md) — local-first/user-controlled operation, model/backend replaceability, `LLM = null` administrative substrate, modest-hardware expectations, migration, and user sovereignty.
- [`engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md) — one-mechanism experimental discipline, negative-result retention, behavioral-number classification, benchmark/calibration rules, and evidence-backed tunables.
- [`engineering/TESTING_AND_ACCEPTANCE.md`](engineering/TESTING_AND_ACCEPTANCE.md) — deterministic CI versus native acceptance, statelessness/restart/provenance/boundedness evidence, failure testing, and release gates.
- [`engineering/CONSTITUTIONAL_GOVERNANCE.md`](engineering/CONSTITUTIONAL_GOVERNANCE.md) — document precedence, amendment procedure, `PASS`/`FAIL`/`GAP` audit semantics, per-article codebase audit procedure, and constitutional PR review.

Constitutional deep dives are subordinate to the Constitution and may specialize it without weakening it. Current architecture and milestone documents are subordinate to those authorities. Historical documents preserve measured evidence and design history but cannot silently override current constitutional rules.

Adoption of the Constitution does **not** assert that the current branch already passes every article. Forward-looking portability, export/restore, explicit erasure, or other not-yet-built constitutional mechanisms may correctly appear as `GAP`s in an audit.

## Current architecture

These documents define the forward architecture beginning with v0.7:

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — authoritative target architecture: persistent cognitive system, resource-aware Attention Fabric, bounded WorkingState, automatic per-percept memory attention aperture, perception/salience, retention, optional capabilities, disposable workers, session-independent continuity, and system-owned state.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — authoritative lossless-memory and scaling constraints: durable source memories are never replaced by summaries/aggregations, derived structures remain routing aids, recall is progressive and source-backed, model context is bounded, and ordinary recall must avoid inference growth proportional to corpus size.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — current continuity model: bounded durable WorkingState owns present activation; every percept receives a small system-owned JIT Memory attention aperture before model routing; deeper memory analysis is reserved for focused work; conversations/sessions/devices remain provenance rather than cognitive boundaries.
- [`architecture/SYSTEM_DETERMINISM.md`](architecture/SYSTEM_DETERMINISM.md) — current deterministic application-envelope and replay contract.
- [`architecture/PERCEPT_TO_RESPONSE_PIPELINE.md`](architecture/PERCEPT_TO_RESPONSE_PIPELINE.md) — live v2 path from user percept through pre-cognitive work selection, memory sufficiency/adaptive recall, final response, and durable persistence.
- [`architecture/FINAL_RESPONDER.md`](architecture/FINAL_RESPONDER.md) — final-responder identity/personality, evidence authority, response-only temperature, accuracy guardrails, and exact invocation-provenance contract.
- [`architecture/IMMUTABLE_ARTIFACT_JOURNAL.md`](architecture/IMMUTABLE_ARTIFACT_JOURNAL.md) — independent immutable filesystem durability for canonical events, stage results, exact LLM invocations, inspection, interruption recovery, and database reconstruction.
- [`architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md) — timeless normative authority for Attention Fabric, resource safety, preemption, assignment, and worker-execution rules previously spread across v0.7 milestone records.
- [`architecture/LOCAL_FIRST_PORTABILITY.md`](architecture/LOCAL_FIRST_PORTABILITY.md) — long-lived local-first, user-sovereignty, component-replaceability, and portability requirements.
- [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) — decision record explaining the move away from a privileged Primary Agent, permanent agent hierarchy, rigid conversation-scoped cognition, and unconditional persistence of raw external input.
- [`ROADMAP.md`](ROADMAP.md) — milestone path from the accepted v0.5/v0.6 baselines through the first complete attention-centric v1.0 architecture. v0.7 now includes minimal active WorkingState and the default attention aperture; the post-v0.7 roadmap must be rebaselined before choosing whether richer epistemic WorkingState or perception/salience comes next.

There is intentionally no current `PRIMARY_AGENT_SPEC_SHEET` under `docs/architecture/`. Permanent agents are no longer first-class architectural primitives. Historical Primary-Agent material lives under `docs/history/`.

## Current protocol rules

Experimental corrections from native v0.7 acceptance now apply across the current architecture:

1. **Basic internal-memory access is substrate, not a live model-selected capability.** A fresh stateless model cannot reliably decide whether unseen memory matters before potentially relevant memory has been exposed. Every percept therefore receives a bounded attention-aperture activation packet first; the model may request deeper memory work only when further focus is needed.
2. **Model-generated natural language is a representation of last resort.** Prefer enums, booleans, application-owned IDs, bounded integers, and mechanically verified selections for machine control/state. Free-form model language is appropriate where language is genuinely the product. Tests must not substitute hand-maintained keyword/phrase parsers for semantic verification.
3. **Control-plane authority is deterministic wherever it can be.** Models may make bounded semantic selections, but application-owned identity, dependencies, ordering, resource policy, retention/deletion authority, permissions, validation, and replay state remain mechanically governed.

Aperture activation is intentionally higher-recall than conservative evidence admission. An activated event is potentially relevant enough to expose; it is not automatically sufficient evidence or a truth claim.

## Concept and research inputs

The [`concepts/`](concepts/) directory contains research and long-horizon design material. These files inform architecture but do not override the Constitution, constitutional deep dives, current architecture documents, or accepted experiment results by themselves.

- [`concepts/lessons_from_cognitive_neuroscience.md`](concepts/lessons_from_cognitive_neuroscience.md) — mechanism-level comparison with contemporary cognitive/computational neuroscience. Particularly relevant to durable working state, recurrent inference, episode formation, replay/consolidation, plasticity, prediction error, and the distinction between engineered provenance and biological memory.
- [`concepts/lessons_from_similar_projects.md`](concepts/lessons_from_similar_projects.md) — architecture mapping against Letta/MemGPT, AIOS, Soar, ACT-R, LIDA, OpenCog/Hyperon, LangGraph, Generative Agents, Voyager, M3-Agent, ABot-AgentOS, and related work. Use it to borrow tested mechanisms while preserving Prometheist's system-owned authority/failure model.
- [`concepts/a_future_history_of_mankind.txt`](concepts/a_future_history_of_mankind.txt) — long-horizon conceptual/vision context. It is not an implementation specification.

The v0.7 WorkingState/aperture corrections illustrate the intended research discipline: concept reports suggested related mechanisms, but changes entered the release candidate only after frozen native acceptance exposed the corresponding gaps.

## Architecture baselines

Long-lived mechanisms that remain applicable:

- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline and invariants.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded associative-recall design and provenance model. Associations are routing hints, never substitutes for source evidence.

These memory documents predate the attention-centric pivot. Where terminology conflicts, the Constitution and constitutional deep dives control, followed by the other current architecture documents and roadmap.

## Historical architecture and divergent v0.6 work

- [`history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](history/PRIMARY_AGENT_SPEC_SHEET_V06.md) — archived summary of the superseded v0.6 Primary-Agent design.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted v0.6 experimental result. Its stateless-worker/JIT-Memory findings and useful conversational behavior remain regression baselines; its Primary/specialist hierarchy is historical.
- [`milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) — comparison of the divergent `v0.6-capability-registry` branch against active v0.7 architecture.

Historical documents describe what was built or believed at a particular milestone. They do not override current constitutional or architecture documents.

## Active milestone

- [`milestones/v0.7/README.md`](milestones/v0.7/README.md) — v0.7 scope, implementation record, release-candidate evidence, task-neutral capability execution, forced-restart acceptance, and native-machine gate.
- [`milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md`](milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md) — dated experimental record of why phrase/entity/recency continuity heuristics and “ask before remembering” were rejected, and why bounded WorkingState + the automatic attention aperture replaced them.
- [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md) — v0.7 implementation/design record for deterministic scheduling, quantitative admission/reservations, epochs, preemption, and worker behavior. Its timeless normative rules are now governed by `architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`.
- [`milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) — accepted v0.7 decision record supporting constitutional attention/resource separation and safe-concurrency rules.
- [`milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md`](milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md) — safe concurrency versus focused resource concentration.
- [`milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md) — implementation evidence for the constitutional guarded disposable-worker contract.
- [`milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md`](milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md) — original Increment G durable interaction implementation record. Its phrase-based reference policy is superseded by the later WorkingState/aperture corrections above.
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

Future repository-wide architecture audits should use `CONSTITUTION.md` plus [`engineering/CONSTITUTIONAL_GOVERNANCE.md`](engineering/CONSTITUTIONAL_GOVERNANCE.md) as the governing checklist and procedure.

## Benchmark fixtures

Machine-readable benchmark fixtures remain in repository-level [`benchmarks/`](../benchmarks/) because they are runtime test inputs rather than narrative documentation.
