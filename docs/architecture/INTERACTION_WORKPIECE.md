# Interaction Workpiece and Demand-Driven Station Graph

**Status:** current architectural authority beginning with the late v0.7 transient-worker refactor  
**Workpiece schema:** `interaction-workpiece-v1`  
**Primary implementation:** `src/jit_agent/interaction_workpiece.py`, `src/jit_agent/pre_cognitive_response_runtime.py`  
**Introduced:** 2026-08-28

## Purpose

Prometheist is not a chatbot execution engine and it is not a collection of persistent agents. Its general execution primitive is a **typed workpiece moving through a demand-driven graph of bounded stations**.

A workpiece represents one unit of system work. It begins with a small application-owned frame and accumulates only the validated components required by that particular task. Some stations are deterministic software, some are stateless LLM invocations, some are capability/tool executors, and future stations may represent devices, external services, or explicit human-approval gates.

The architectural rule is:

> **Each station performs one bounded responsibility, receives only the projection of the workpiece it needs, and returns one validated component. Prometheist attaches the component and decides what station, if any, is eligible next.**

There is no requirement that every workpiece visit every station.

## Workpiece versus worker versus capability

These are separate concepts.

- **Workpiece** — the cumulative application-owned typed state for one unit of work.
- **Station / worker profile** — one bounded implementation role that can contribute a component.
- **Capability** — an application-owned semantic operation that may be selected when additional work is required.
- **LLM invocation** — one possible implementation of a station; always stateless.
- **Terminal outcome** — the application-owned conclusion of the workpiece. A user-facing response is only one possible terminal product.

A worker never owns the workpiece. It sees a projection, returns a component, and disappears.

## Master schema and sub-schemas

`InteractionWorkpiece` is the master frame. It is deliberately not a giant bag of nullable untyped values. Its `components` collection is a Pydantic discriminated union of registered component schemas.

Current component families include:

- originating percept;
- reference/WorkingState availability;
- attention-aperture `MemoryPacket`;
- evidence-sufficiency station result;
- capability-selection station result when that station actually ran;
- application-composed pre-cognitive control checkpoint;
- executed capability tranches;
- final evidence packet;
- current interactive `FinalResponseDirective` when a response path is used;
- optional user-visible output;
- application-owned terminal outcome.

A simple task may contain only a few of these. A harder task may accumulate many.

Conceptually:

```text
InteractionWorkpiece
  frame
    interaction_id
    task_id
    conversation_id      # provenance, not cognitive boundary
    correlation_id

  components
    PERCEPT
    [REFERENCE_RESOLUTION]
    [ATTENTION_APERTURE]
    [EVIDENCE_SUFFICIENCY]
    [CAPABILITY_SELECTION]
    [PRE_COGNITIVE_CONTROL]
    [CAPABILITY_WORK tranche=0]
    [EVIDENCE_SUFFICIENCY phase=POST_CAPABILITY]
    [CAPABILITY_SELECTION phase=POST_CAPABILITY]
    [PRE_COGNITIVE_CONTROL phase=POST_CAPABILITY]
    [CAPABILITY_WORK tranche=1]
    [FINAL_EVIDENCE]
    [FINAL_RESPONSE_DIRECTIVE]
    [USER_OUTPUT]
    TERMINAL_OUTCOME
```

Square brackets mean conditional, not required.

## Demand-driven assembly

The station graph is application-owned. A station is invoked only when its output changes what Prometheist can legally or usefully do next.

For the current interactive fast path:

```text
PERCEPT
  -> reference/WorkingState inspection
  -> attention aperture
  -> evidence sufficiency
  -> deterministic control composition
  -> response-source/surface finalization
  -> optional response realization
  -> terminal outcome
```

For a memory-acquisition path:

```text
PERCEPT
  -> attention aperture
  -> evidence sufficiency = INSUFFICIENT
  -> capability selection
  -> deterministic capability tranche
  -> evidence sufficiency again on newly material evidence
  -> optional newly legal follow-up capability selection/work
  -> final evidence
  -> terminalization
```

For a future non-chat action path, the tail may instead be:

```text
...
  -> authorization/policy gate
  -> external action/tool station
  -> ACTION_COMPLETED
```

No final natural-language worker is required unless user-visible language is itself part of the task.

## Worker information apertures

The master workpiece is **not** handed wholesale to every worker.

Each worker profile declares a minimum packet contract. Deterministic application code projects the current workpiece/application state into that contract and rejects missing or extra fields.

Examples:

```text
evidence_sufficiency_verifier sees:
  current percept
  bounded activated/final evidence
  completed relevant results

it does NOT see:
  arbitrary system state
  personality
  scheduling authority
  capability execution internals it does not need
```

```text
capability_selector sees:
  current percept
  established evidence gap context
  legal application-owned capability catalog

it does NOT decide:
  whether evidence was sufficient
  capability IDs outside the catalog
  dependency order
  resource policy
  tool arguments
```

The workpiece therefore provides a common cumulative frame without recreating a giant LLM context window.

## Component authority

A station result is not allowed to mutate the workpiece directly.

The legal sequence is:

```text
station receives projection
        |
        v
station emits one closed component
        |
        v
Pydantic validation
        |
        v
deterministic application attachment
        |
        v
next-station eligibility / terminalization
```

LLM output is semantic input to application control, never arbitrary write access to durable state.

## Chronology

The component sequence preserves material assembly order. Capability work is recorded per tranche rather than collapsed into one summary so the final workpiece can distinguish:

```text
first capability work
  -> post-capability judgment
  -> optional follow-up capability work
```

This matters for causal audit and replay. A final snapshot that contains all values but loses their dependency/assembly order is not sufficient.

## Durability model

The terminal workpiece snapshot does **not** replace Prometheist's append-only event history.

There are two complementary representations:

1. **incremental authoritative history** — durable events, worker claims/checkpoints/results, capability evidence, and control records are persisted at their existing safety boundaries;
2. **materialized workpiece snapshot** — when a workpiece terminalizes, Prometheist persists one deterministic `INTERACTION_WORKPIECE_SNAPSHOT` JSON containing the assembled typed components.

The snapshot is the convenient complete product for audit, debugging, evaluation, replay inspection, export, and future orchestration. The append-only records remain the underlying causal authority and allow recovery before terminalization.

Micro-station outputs do not require separate database events merely because they are components. Before an effect-capable boundary, several cheap stateless station results may be accumulated and committed together as a durable control checkpoint. Once a result authorizes or records a material effect, existing append-only/idempotency rules remain authoritative.

## Terminal outcomes

Terminalization is more general than response synthesis.

`TerminalOutcomeKind` currently defines the general vocabulary:

- `RESPONSE_EMITTED`
- `ABSTAINED`
- `ACTION_COMPLETED`
- `ACTION_FAILED`
- `WAITING_EXTERNAL`
- `DEFERRED`

The schema explicitly permits a terminal action outcome with no `USER_OUTPUT` component.

This distinction is fundamental:

```text
terminal outcome != final chat response
```

Examples:

- answer a user question -> `RESPONSE_EMITTED` + `USER_OUTPUT`;
- unsupported historical request -> `ABSTAINED` + current interactive fallback output when required by the interface;
- place an authorized grocery order -> `ACTION_COMPLETED`, response optional;
- schedule an authorized appointment -> `ACTION_COMPLETED`, response optional;
- external provider unavailable but retry is expected -> `WAITING_EXTERNAL`, response optional;
- policy intentionally postpones work -> `DEFERRED`.

The current v0.7 CLI remains an interactive surface and therefore attaches user output on its terminal path. That is an interface behavior, not the universal execution architecture.

## User-visible surface

The user normally sees only the product appropriate to the interface/task, not the complete internal workpiece.

A workpiece may contain evidence packets, control components, capability results, provenance, and terminal authority while the visible result is simply:

```text
Your appointment is scheduled for Tuesday at 3:00 PM.
```

or no user-visible text at all.

Internal provenance must not be discarded merely because it is not surfaced.

## Relationship to `PreCognitiveAssessment`

`PreCognitiveAssessment` is no longer the conceptual container for the whole interaction. It is one application-composed control component inside the larger workpiece.

The current production pre-cognitive path reconstructs explicit station components for:

- `evidence_sufficiency_verifier`;
- `capability_selector` when its legal catalog was non-empty and evidence was insufficient.

The aggregate assessment remains persisted for compatibility/restart authority while the workpiece snapshot exposes the constituent station contributions and their chronology.

## Relationship to `FinalResponseDirective`

`FinalResponseDirective` remains the correct terminal authority for the **current interactive response path**. It binds response authorization, evidence/source policy, final packet identity, capability identities, fallback behavior, and personality identity before response realization.

It is not promoted into the universal terminal contract for every future Prometheist task. A non-language action may terminalize without any `FinalResponseDirective` or final response worker.

Future action-specific authorization/effect components should be added only when concrete execution paths require them.

## Relationship to WorkingState and long-term memory

The interaction workpiece is neither WorkingState nor long-term memory.

- **Workpiece** — bounded cumulative state/provenance for one unit of work.
- **WorkingState** — bounded canonical pointers representing what is currently activated across interactions.
- **Long-term memory/internal history** — append-only canonical durable evidence and system history.

The terminal workpiece snapshot may itself become useful internal history, but it must not be blindly activated as a giant replacement memory packet. Current interactive WorkingState continues to activate the user prompt and user-facing result rather than the entire terminal snapshot.

## Extension rule

The master schema is intentionally extensible, but extension is demand-driven.

Do not add speculative component types because they might someday be useful. Add a component when a real station or terminal path needs a typed product that cannot be represented by existing components.

Likewise, do not add a station merely because a schema field could be populated. A station earns its place through a concrete downstream consumer, authority boundary, or measured failure mode.

## Current implementation boundary

v0.7 implements the workpiece on the production interaction path while retaining the existing five durable stage keys. This avoids combining a durable stage-protocol migration with the worker/workpiece experiment.

Current behavior:

- `RESOLVE_REFERENCES` initializes the frame and reference-resolution component;
- `SELECT_CAPABILITY` attaches the attention aperture, reconstructed specialist outputs, and pre-capability control component;
- `EXECUTE_CAPABILITY` attaches capability tranches, optional post-capability components, final evidence, and the interactive response directive;
- `RESPOND` is retained as a durable compatibility key but acts as the current interface's optional output/terminalization station;
- `PERSIST_RESULT` persists the terminal workpiece snapshot and, when present, the separate user-facing response event.

Stage names are protocol compatibility keys, not universal cognitive concepts.

## Testing obligations

The workpiece contract must verify at least:

- exactly one originating percept;
- closed discriminated component schemas;
- components absent when their stations did not run;
- chronological first/follow-up capability tranches;
- terminal outcome is final;
- no component may attach after terminalization;
- `RESPONSE_EMITTED` requires user output;
- action/deferred/waiting terminal outcomes may exist without user output;
- JSON round-trip preserves typed components;
- terminal snapshot persistence does not replace append-only events;
- current response behavior and WorkingState regressions remain compatible.

## Architectural invariant

> **Prometheist executes work by assembling typed, provenance-bearing components onto a system-owned workpiece through only the stations that the current task requires. Workers are disposable contributors, not owners of the workpiece. Terminalization is application-owned, and user-facing language is optional because language is only one possible product of the system.**
