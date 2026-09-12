# Prometheist Documentation

## Authority order

1. [`../CONSTITUTION.md`](../CONSTITUTION.md)
2. constitutional deep dives under [`architecture/`](architecture/) and
   [`engineering/`](engineering/)
3. current architecture documents
4. active milestone records and [`ROADMAP.md`](ROADMAP.md)
5. dated audits, experiments, and historical milestone records

Historical text preserves evidence but cannot silently override a current authority.
Adoption of a constitutional rule also does not imply that every implementation gap
is already closed; audits must distinguish `PASS`, `FAIL`, and `GAP`.

## Current architecture

- [`architecture/PERCEPT_TO_RESPONSE_PIPELINE.md`](architecture/PERCEPT_TO_RESPONSE_PIPELINE.md) — authoritative implemented v2 interaction path: deterministic user response requirement, pre-cognitive non-memory work selection, memory-only Composer, Adaptive Recall, direct work-result handoff, and final responder.
- [`architecture/COGNITIVE_ARCHITECTURE.md`](architecture/COGNITIVE_ARCHITECTURE.md) — complete system boundary, durable authority, stateless cognition, WorkingState, attention/execution, and implemented/deferred mechanisms.
- [`architecture/INTERACTION_CONTINUITY.md`](architecture/INTERACTION_CONTINUITY.md) — cross-process/session continuity, attention aperture, Adaptive Recall, evidence authority, and failure/acceptance rules.
- [`architecture/FINAL_RESPONDER.md`](architecture/FINAL_RESPONDER.md) — mandatory identity/evidence contract, additive personality, response-only sampling, and invocation provenance.
- [`architecture/SPECIALIST_WORKER_MODULARITY.md`](architecture/SPECIALIST_WORKER_MODULARITY.md) — one semantic responsibility per LLM worker, split criteria, runtime guards, and non-user percept triage boundary.
- [`architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](architecture/LOSSLESS_PROGRESSIVE_MEMORY.md) — exact canonical evidence, replaceable derived structures, bounded recall, and memory-scaling constraints.
- [`architecture/IMMUTABLE_ARTIFACT_JOURNAL.md`](architecture/IMMUTABLE_ARTIFACT_JOURNAL.md) — independent append-only artifacts, interruption recovery, verification, and database reconstruction.
- [`architecture/SYSTEM_DETERMINISM.md`](architecture/SYSTEM_DETERMINISM.md) — replayable control authority and prohibition on race-based durable decisions.
- [`architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md) — attention/resource separation, headroom, preemption, guarded launch, recovery, and effects.
- [`architecture/LOCAL_FIRST_PORTABILITY.md`](architecture/LOCAL_FIRST_PORTABILITY.md) — local ownership, replaceability, administrative operation, portability, and user sovereignty.

[`architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](architecture/ARCHITECTURAL_PIVOT_2026-08-24.md) is the dated decision record that retired permanent agents and conversation-scoped cognition. It remains explanatory history, not a newer authority than the v2 pipeline.

## Engineering governance

- [`engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md) — one-mechanism experiments, numeric-constraint classification, benchmark rules, and native calibration.
- [`engineering/TESTING_AND_ACCEPTANCE.md`](engineering/TESTING_AND_ACCEPTANCE.md) — deterministic versus native gates, provenance, statelessness, failure injection, and release evidence.
- [`engineering/CONSTITUTIONAL_GOVERNANCE.md`](engineering/CONSTITUTIONAL_GOVERNANCE.md) — amendments, document precedence, and per-article audit procedure.

## Active transition

- [`milestones/v0.7/README.md`](milestones/v0.7/README.md) — consolidated v0.7 architecture and hard closure gate.
- [`milestones/v0.7/CLOSURE_STATUS.md`](milestones/v0.7/CLOSURE_STATUS.md) — truthful gate-by-gate status; v0.7 remains open until native acceptance and final audit finish.
- [`audits/V07_BRANCH_SALVAGE_2026-09-03.md`](audits/V07_BRANCH_SALVAGE_2026-09-03.md) — selective disposition of PRs #19–#24.
- [`audits/V07_NATIVE_ACCEPTANCE_2026-09-03.md`](audits/V07_NATIVE_ACCEPTANCE_2026-09-03.md) — failed full native run, six release-blocking failures, evidence limits, and replacement mechanism.
- [`audits/V07_REMOTE_BRANCH_INVENTORY_2026-09-03.md`](audits/V07_REMOTE_BRANCH_INVENTORY_2026-09-03.md) — remote-ref comparison, keep/delete classification, and deletion-tool blocker.
- [`ROADMAP.md`](ROADMAP.md) — active v0.8 perception/salience integration, with richer Epistemic WorkingState deferred to a separate experiment.
- [`milestones/v0.8/README.md`](milestones/v0.8/README.md) — implemented percept contracts, specialist integration, and remaining boundaries.
- [`milestones/v0.8/HYPOTHESIS.md`](milestones/v0.8/HYPOTHESIS.md) — perception experiment and honest freeze status.
- [`audits/V08_CLOSURE_INTEGRATION_2026-09-12.md`](audits/V08_CLOSURE_INTEGRATION_2026-09-12.md) — change-by-change rationale, branch ancestry, research, tests, and remaining specification gap.
- [`experiments/history/EPISTEMIC_WORKING_STATE_PROPOSAL_2026-09-03.md`](experiments/history/EPISTEMIC_WORKING_STATE_PROPOSAL_2026-09-03.md) — preserved earlier, unfrozen proposal; no longer the active v0.8 scope.

## Research and experiment evidence

- [`concepts/lessons_from_cognitive_neuroscience.md`](concepts/lessons_from_cognitive_neuroscience.md) — mechanism-level research input; it motivates hypotheses but does not override experiments.
- [`concepts/lessons_from_similar_projects.md`](concepts/lessons_from_similar_projects.md) — comparison with related cognitive and agent systems.
- [`experiments/README.md`](experiments/README.md) — current disposition of preserved PR #22 Adaptive Memory Attention/Composer records.
- [`audits/history/pr19/`](audits/history/pr19/) — preserved PR #19 red-team chronology with historical-status banners.

Raw accepted benchmark/calibration results live under `../benchmarks/results/`.
Ordinary `.prometheist/artifacts` runtime output stays local and ignored; reviewable
evidence must be deliberately preserved with provenance and a tested revision.

## Historical architecture

- [`history/PRIMARY_AGENT_SPEC_SHEET_V06.md`](history/PRIMARY_AGENT_SPEC_SHEET_V06.md)
- [`milestones/v0.6/README.md`](milestones/v0.6/README.md)
- [`milestones/v0.5/README.md`](milestones/v0.5/README.md)

Several dated v0.7 increment records describe intermediate implementations. Their
headers identify them as historical/superseded where necessary. The live path never
depends on their old router, memory-capability, or agent terminology.

- [Situation cognition and operator guide](architecture/SITUATION_COGNITION.md)
