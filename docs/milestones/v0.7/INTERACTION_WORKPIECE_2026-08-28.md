# v0.7 Interaction Workpiece / Demand-Driven Station Decision — 2026-08-28

## Decision

Prometheist's general execution primitive is now a **typed application-owned workpiece moving through a demand-driven station graph**.

The current interactive pre-cognitive/response path remains implemented through the existing five durable v0.7 stage keys for restart compatibility, but those keys are no longer treated as the universal cognitive model. The cumulative product is `InteractionWorkpiece`; each bounded station contributes one validated component and Prometheist decides what station, if any, is eligible next.

A user-facing natural-language response is optional at the architecture level.

## Why this changed

The previous transient-worker refactor successfully removed the recurrent general capability router, but discussion/testing exposed two remaining conceptual problems.

First, `PreCognitiveAssessment` still looked like the central interaction product even though it represented only acquisition/control metadata.

Second, the architecture still implicitly looked chatbot-shaped because its terminal abstraction was a final response directive/worker. Prometheist is intended to perform general persistent cognitive/execution work: future tasks may order groceries, schedule appointments, control software/devices, wait for external conditions, or perform background maintenance. Such work must not require fake response generation merely to fit an interaction pipeline.

The assembly-line model resolves both problems.

## Assembly model

One task creates one system-owned frame. The task stops only at stations it actually needs.

```text
WORKPIECE FRAME
    |
    +-> station A -> validated component A
    |
    +-> [station B only if needed] -> component B
    |
    +-> [capability/tool/action only if needed] -> component C
    |
    +-> terminalizer -> explicit terminal outcome
```

The master workpiece is not handed to every worker. Each worker profile declares a minimum packet contract and sees only a projection.

Workers cannot mutate/own the workpiece. They return one component; deterministic application code validates/attaches it and determines next-station eligibility.

## Sanity-check refinement

The design explicitly rejects the naive interpretation that “specialized workers” means “every schema field deserves a separate LLM call.”

The production rule is:

> **One bounded job per station, and no unnecessary station.**

A station earns its place only when its output changes what Prometheist can legally/usefully do next, creates a meaningful authority boundary, or repairs a measured failure.

This is why the current pre-acquisition path contains only:

1. `evidence_sufficiency_verifier`;
2. `capability_selector` only after insufficiency and only when a legal catalog exists.

Intent/claim-scope/requirement compatibility fields do not currently justify independent model calls.

## Master and component schemas

`src/jit_agent/interaction_workpiece.py` introduces `interaction-workpiece-v1`.

Current component types include:

- `PERCEPT`
- `REFERENCE_RESOLUTION`
- `ATTENTION_APERTURE`
- `EVIDENCE_SUFFICIENCY`
- `CAPABILITY_SELECTION`
- `PRE_COGNITIVE_CONTROL`
- `CAPABILITY_WORK`
- `FINAL_EVIDENCE`
- `FINAL_RESPONSE_DIRECTIVE`
- `USER_OUTPUT`
- `TERMINAL_OUTCOME`

The collection is a Pydantic discriminated union. A component simply does not exist if its station did not run.

Capability work is represented per tranche so the terminal JSON preserves causal assembly order rather than merely containing the final values.

## General terminal outcomes

The initial terminal vocabulary is:

- `RESPONSE_EMITTED`
- `ABSTAINED`
- `ACTION_COMPLETED`
- `ACTION_FAILED`
- `WAITING_EXTERNAL`
- `DEFERRED`

The schema explicitly verifies that `ACTION_COMPLETED` can be terminal with no `USER_OUTPUT` component.

The current CLI remains interactive and therefore attaches a user output. This is interface behavior, not a universal system requirement.

## Terminal JSON versus append-only durability

The user-facing conceptual model called for one completed JSON containing everything assembled along the way. That is implemented as a **materialized terminal snapshot**, not as replacement persistence.

On current terminalization Prometheist writes a deterministic `INTERACTION_WORKPIECE_SNAPSHOT` system event whose payload contains the complete typed workpiece JSON.

Underlying authoritative persistence remains append-only:

- source/internal events;
- worker claims/checkpoints/results;
- capability evidence/results;
- persisted control decisions;
- effect/idempotency records.

This preserves crash recovery and causal authority while adding one coherent completed object for audit/debug/replay/evaluation/export.

The full snapshot is not placed into WorkingState. Current activation remains bounded canonical prompt/result evidence.

## Durable stage compatibility

The existing stage keys are retained for v0.7:

- `RESOLVE_REFERENCES` initializes/carries the workpiece;
- `SELECT_CAPABILITY` attaches aperture, pre-cognitive station outputs, and application-composed control;
- `EXECUTE_CAPABILITY` attaches capability tranches, optional post-capability station/control components, final evidence, and the current interactive response directive;
- `RESPOND` remains the compatibility key for the current interface's optional output/terminalization step;
- `PERSIST_RESULT` persists the terminal workpiece snapshot plus a separate response event when user output exists.

A later protocol migration may rename/generalize these keys, but v0.7 does not mix that migration into the mechanism experiment.

## Relation to `PreCognitiveAssessment`

`PreCognitiveAssessment` remains a restart-compatible application-owned control checkpoint. It is no longer conceptualized as the entire interaction product.

The workpiece exposes the constituent current production station components plus the aggregate control checkpoint.

## Relation to `FinalResponseDirective`

`FinalResponseDirective` remains correct authority for the current interactive response path. It is now explicitly one conditional workpiece component rather than Prometheist's universal terminal contract.

Future non-language action paths should introduce action-specific authority/result components only when concrete implementations require them.

## Constitutional effect

Constitution v1.2:

- updates Article 27 so fresh semantic reassessment is demand-driven and user-facing generation is conditional;
- adds Article 30: typed workpiece assembly is system-owned and terminal response is optional.

Normative deep dive: [`../../architecture/INTERACTION_WORKPIECE.md`](../../architecture/INTERACTION_WORKPIECE.md).

## Acceptance obligations

Deterministic coverage must verify:

- exactly one originating percept;
- only actually attached components appear;
- closed discriminated component schemas;
- terminal outcome is final;
- no attachment after terminalization;
- response terminalization requires user output;
- action/deferred/waiting outcomes may omit user output;
- JSON round-trip preserves component types;
- current pre-cognitive/response/restart/WorkingState behavior remains compatible;
- constraint audit remains fully registered without inventing behavioral tunables for structural schema facts.

Native Windows/PostgreSQL/Ollama acceptance remains required after deterministic CI because the workpiece refactor is layered around the same Qwen3:4b semantic/control path whose native behavior motivated the latest decomposition.

## Non-goals

This decision does not yet implement grocery ordering, appointment booking, generic external-tool authorization, perception/salience, or arbitrary action schemas. It creates the general execution frame those future mechanisms can plug into without being forced through chatbot semantics.

Likewise, it does not persist every micro-station result as a separate event. Cheap stateless components may be recomputed before an effect-capable durability boundary; material authority remains durable before effects.
