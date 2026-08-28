# Prometheist Documentation

This directory contains the current constitutional authorities, architecture, engineering governance, roadmap, active milestone records, research inputs, audits, and historical evidence for Prometheist.

## Document precedence

Use this order when documents disagree:

1. [`../CONSTITUTION.md`](../CONSTITUTION.md)
2. constitutional deep dives/current architecture authorities
3. current roadmap and active milestone documentation
4. dated experiment/decision records
5. historical architecture records

Historical documents preserve what was built, measured, or believed at a particular point. They do not silently override current architecture.

## Current architecture

The 2026-08-24 through 2026-08-28 refactor replaced the old Primary-Agent/fixed-MAS mental model with a persistent system whose durable state belongs to Prometheist itself.

### Core execution authorities

- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — top-level current architecture: system-owned continuity, Attention Fabric, WorkingState, JIT memory, typed workpieces, demand-driven stations, capabilities, epistemic boundaries, general terminalization, and optional user-facing language.
- [`architecture/INTERACTION_WORKPIECE.md`](architecture/INTERACTION_WORKPIECE.md) — the current general execution primitive: one typed application-owned workpiece accumulates only the validated components needed by a task; stations receive minimum projections and contribute one bounded component; terminal response is optional.
- [`architecture/WORKER_PROFILE_REGISTRY.md`](architecture/WORKER_PROFILE_REGISTRY.md) — private worker/station registry beneath the workpiece and public capability surfaces: deterministic vs LLM roles, minimum packet contracts, model-pool identity, delegated subworkers, persona isolation, and demand-driven invocation.
- [`architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md) — current v0.7 interactive semantic-acquisition subsystem within the workpiece architecture. The production pre-acquisition path uses a single-purpose evidence-sufficiency worker and invokes capability selection only after insufficiency.

### Continuity and memory authorities

- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — bounded WorkingState, automatic JIT attention aperture before semantic model judgment, session-independent continuity, and rejection of phrase-specific continuity policy.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — canonical append-only evidence, rebuildable derived memory, progressive bounded recall, provenance, and scaling invariants.
- [`architecture/MEMORY_KERNEL.md`](architecture/MEMORY_KERNEL.md) — deterministic Memory Kernel baseline.
- [`architecture/ASSOCIATIVE_MEMORY.md`](architecture/ASSOCIATIVE_MEMORY.md) — bounded association graph/retrieval mechanics; associations remain routing evidence, not replacement memory.

### Control, resource, and portability authorities

- [`architecture/SYSTEM_DETERMINISM.md`](architecture/SYSTEM_DETERMINISM.md) — deterministic control-plane/replay authority and prohibition on race-based durable decisions.
- [`architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md) — task priority versus safe resource admission, concurrency, headroom, preemption, guarded launch, worker recovery, and side-effect/idempotency governance.
- [`architecture/LOCAL_FIRST_PORTABILITY.md`](architecture/LOCAL_FIRST_PORTABILITY.md) — local-first/user-controlled operation, model/backend replaceability, `LLM = null` administrative substrate, modest-hardware expectations, migration, and user sovereignty.
- [`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) — decision record for removing the privileged Primary Agent/fixed agent hierarchy as the target architecture.

## Constitutional governance

[`../CONSTITUTION.md`](../CONSTITUTION.md) is the supreme repository-wide engineering policy. Version 1.2 explicitly establishes:

- system-owned continuity and work-in-progress;
- stateless LLMs/disposable workers;
- bounded canonical memory/WorkingState;
- deterministic control/resource/effect authority;
- demand-driven fresh semantic reassessment;
- typed system-owned workpiece assembly;
- minimum worker information apertures;
- explicit general terminal outcomes;
- optional natural-language response rather than chatbot-shaped execution.

Supporting governance:

- [`engineering/CONSTITUTIONAL_GOVERNANCE.md`](engineering/CONSTITUTIONAL_GOVERNANCE.md) — amendment/audit procedure and `PASS`/`FAIL`/`GAP` semantics.
- [`engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md) — one-mechanism experimental discipline, negative-result retention, numeric constraint classification, and benchmark/calibration requirements.
- [`engineering/TESTING_AND_ACCEPTANCE.md`](engineering/TESTING_AND_ACCEPTANCE.md) — deterministic CI versus native acceptance and required restart/provenance/boundedness/failure evidence.

## Current protocol rules

The live v0.7 architecture currently follows these rules:

1. **Basic internal-memory access is substrate.** Every percept gets a bounded JIT attention aperture before semantic model judgment.
2. **The cumulative product is a typed workpiece.** Different tasks attach different components; the master schema does not force every station to run.
3. **Workers receive projections.** A worker never receives the whole workpiece merely because the workpiece contains it.
4. **One bounded job per station; no unnecessary station.** A station earns its place through a real downstream consumer, authority boundary, or measured failure.
5. **Workers contribute; Prometheist attaches.** Worker output is validated before deterministic application code attaches it or authorizes next work.
6. **Semantic acquisition is currently split narrowly.** Evidence sufficiency is one binary station; capability selection runs only after insufficiency and sees only legal catalog indices.
7. **Capabilities are not workers.** Models may select semantic capability indices; application code owns worker identity, dependencies, ordering, resource policy, persistence, and effects.
8. **Material authority is durable before effects.** Cheap stateless micro-station results may be recomputed before an effect boundary; authoritative control is persisted before downstream effects.
9. **Terminalization is broader than response.** Action completion, action failure, waiting, deferral, abstention, and emitted response are distinct terminal outcomes.
10. **The terminal workpiece snapshot complements append-only history.** The single JSON gives a complete audit/replay view but does not replace incremental causal events/checkpoints/results.
11. **Natural language is last-resort machine state/control.** Free-form language is appropriate when language itself is the product.
12. **Persona is response-only.** No acquisition, scheduling, evidence, action, or policy worker receives user-facing persona authority.

## Active milestone: v0.7

Start with [`milestones/v0.7/README.md`](milestones/v0.7/README.md).

Key dated records:

- [`milestones/v0.7/INTERACTION_WORKPIECE_2026-08-28.md`](milestones/v0.7/INTERACTION_WORKPIECE_2026-08-28.md) — decision/implementation record for the typed workpiece, station assembly, terminal snapshot, and non-chat terminalization model.
- [`milestones/v0.7/PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md`](milestones/v0.7/PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md) — evolution from recurrent routing to staged/demand-driven single-purpose semantic workers while Qwen3:4b remains fixed.
- [`milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md`](milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md) — native-test evidence rejecting phrase/entity continuity heuristics and “ask before remembering.”
- [`milestones/v0.7/JIT_ATTENTION_DESIGN.md`](milestones/v0.7/JIT_ATTENTION_DESIGN.md) — implementation record for scheduling/resources/epochs/preemption.
- [`milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](milestones/v0.7/RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) — priority versus resource-admission distinction.
- [`milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md`](milestones/v0.7/ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md) — safe concurrency versus focused resource concentration.
- [`milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](milestones/v0.7/INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md) — guarded disposable-worker protocol.
- [`milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md`](milestones/v0.7/INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md) — original durable interaction integration record; parts of its routing/continuity design are explicitly superseded by later records.
- [`milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) — what was preserved/adapted from divergent v0.6 work.

The release candidate is not accepted until deterministic CI is green on the final head **and** native Windows/PostgreSQL/Ollama Qwen3:4b acceptance passes.

## Roadmap

[`ROADMAP.md`](ROADMAP.md) is the current path to v1.0. The post-v0.7 sequence remains intentionally rebaselinable as new cognitive evidence emerges; do not silently combine major mechanisms simply because they fit the long-term vision.

## Accepted baselines

- [`milestones/v0.5/README.md`](milestones/v0.5/README.md) — accepted deterministic memory robustness/scale baseline.
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md) — accepted shared-JIT-memory/stateless-worker baseline; its Primary Agent hierarchy is historical.

## Concept and research inputs

Research informs architecture but does not override current normative documents by itself.

- [`concepts/lessons_from_cognitive_neuroscience.md`](concepts/lessons_from_cognitive_neuroscience.md) — working state, attention, recurrent inference, consolidation, prediction error, and engineered-versus-biological memory mechanisms.
- [`concepts/lessons_from_similar_projects.md`](concepts/lessons_from_similar_projects.md) — comparisons with memory/agent/OS/cognitive architectures and reusable mechanisms.
- [`concepts/a_future_history_of_mankind.txt`](concepts/a_future_history_of_mankind.txt) — long-horizon vision context, not implementation specification.

## Historical architecture

- [`history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](history/PRIMARY_AGENT_SPEC_SHEET_V06.md) — archived v0.6 Primary Agent architecture.

There is intentionally no current Primary Agent spec under `docs/architecture/`. Permanent agents are no longer first-class Prometheist primitives.

## Audits and experiments

Dated experiments and [`audits/`](audits/) preserve negative results, historical codebase states, and the causal path to current architecture. Future constitutional audits should use `CONSTITUTION.md` plus [`engineering/CONSTITUTIONAL_GOVERNANCE.md`](engineering/CONSTITUTIONAL_GOVERNANCE.md) as the governing checklist.

Machine-readable benchmark fixtures live under repository-level [`benchmarks/`](../benchmarks/) because they are runtime inputs rather than narrative documentation.
