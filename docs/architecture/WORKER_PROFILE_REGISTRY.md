# Worker Profile Registry

**Status:** current private execution registry beneath the Interaction Workpiece/capability architecture  
**Registry version:** `worker-profile-registry-v1`  
**Primary implementation:** `src/jit_agent/worker_profile_registry.py`

## Purpose

Prometheist separates the cumulative **workpiece**, public semantic **capabilities**, private **worker profiles**, and individual **LLM invocations**.

```text
InteractionWorkpiece
    -> application-owned next-station eligibility
       -> deterministic worker profile
       -> LLM worker profile
       -> capability/tool worker profile
       -> future device/human gate
    -> one validated component
    -> deterministic attachment to workpiece
```

A capability describes what work may be requested. A worker profile describes how one bounded responsibility is implemented. An LLM invocation is only one possible implementation mechanism for a worker profile.

The registry prevents models from discovering or addressing arbitrary implementation identities directly.

## Assembly rule

The workpiece architecture adds a second requirement to specialization:

> **A worker should have one bounded job, and a station should be invoked only when its output changes what Prometheist can legally or usefully do next.**

“Everything gets its own LLM” is not the design. Deterministic software remains preferred when deterministic software can perform the responsibility correctly.

## Worker profile contract

Each profile declares:

- stable private `worker_profile_id`;
- deterministic or LLM execution mode;
- minimum packet contract;
- output-schema identity;
- narrow system prompt for LLM workers;
- model-pool identity for LLM workers;
- explicit persona access;
- explicitly registered delegated workers for deterministic composite roles.

Packet contracts are closed by omission. Application code projects broader workpiece/system state into the registered packet; missing required fields or extra fields fail validation.

The master workpiece is therefore **not** a master LLM prompt.

## Capability / worker / invocation / component separation

- **Capability:** application-owned semantic work that may be requested.
- **Worker profile:** private implementation contract for one bounded station.
- **LLM invocation:** one fresh stateless inference used by some worker profiles.
- **Component:** the typed product returned by a station and attached by Prometheist.
- **Workpiece:** cumulative application-owned aggregate of the components required by one unit of work.

The model may select legal capability indices when a capability-selection station is invoked. Prometheist owns translation to execution identities, dependencies, order, resource admission, provenance, persistence, and effects.

## Current pre-cognitive profiles

The application-owned `pre_cognitive_assessment` composition currently relies on:

1. `evidence_sufficiency_verifier` — binary sufficiency only;
2. `capability_selector` — catalog indices only and only after insufficiency.

The sufficiency worker does not receive the capability catalog. The capability selector cannot declare sufficiency. Their terminal workpiece components preserve those distinct outputs while `PreCognitiveAssessment` remains the restart-compatible application-composed control record.

Intent, claim-scope, and requirement metadata do not currently justify separate production LLM stations merely because corresponding compatibility fields exist.

## Current capability roots

| Capability executor | Private root profile | Delegated LLM role |
| --- | --- | --- |
| `jit_memory` | `jit_memory_executor` | none |
| `deeper_research` | `deeper_research_executor` | `memory_research_candidate_selector` |
| `cross_reference` | `cross_reference_executor` | `cross_reference_candidate_selector` |
| `focused_recall` | `focused_recall_executor` | `focused_recall_candidate_selector` |

Capability roots remain deterministic. Narrow semantic candidate selection is delegated only where the capability actually requires it.

## Other conditional LLM profiles

Current registered LLM roles include:

- `evidence_sufficiency_verifier`;
- `capability_selector`;
- `final_readiness`;
- `response_policy_classifier`;
- `fallback_literal_selector`;
- deeper-research/cross-reference/focused-recall candidate selectors;
- exact-source substring/composition selectors;
- `final_response` for optional natural-language realization.

These are disposable roles, not persistent agents.

The presence of a profile in the registry does not mean every workpiece invokes it.

## Shared model pool

Current LLM profiles bind to `ollama-primary`.

That permits one configured local model such as Qwen3:4b to remain resident while each invocation remains stateless:

- model weights may stay warm;
- each station receives a newly constructed prompt and bounded packet;
- prior model/worker context is not continuity;
- PostgreSQL/application state and the typed workpiece carry continuity/provenance.

Warm residency reduces load overhead but does not make inference free, so demand-driven invocation remains required.

## Persona boundary

Persona access is explicit.

Current rule:

```text
semantic/control/capability/readiness/policy workers -> persona FORBIDDEN
final natural-language response worker              -> persona REQUIRED when invoked
```

This does **not** mean every terminal workpiece requires a response worker. A future action path may terminalize with `ACTION_COMPLETED`, `WAITING_EXTERNAL`, `DEFERRED`, or another governed outcome and never invoke `final_response`.

When natural-language response is required, persona shapes expression only after authority/evidence policy is already final.

## Workpiece attachment authority

Worker profiles do not mutate the master workpiece.

```text
worker packet projection
    -> worker output component
    -> schema validation
    -> deterministic application attachment
    -> next-station eligibility
```

This applies equally to LLM and deterministic/component-producing stations. Application code is the only component assembler.

## Durability boundary

Component existence and durable authority are related but not identical.

Cheap micro-station outputs may be accumulated before the next effect-capable checkpoint. Material control is persisted before downstream effects. At terminalization the complete `InteractionWorkpiece` is persisted as one JSON snapshot in addition to the append-only event/result history underneath it.

Per-micro-station database events are not mandatory unless a station's output independently acquires durable authority or recovery requires continuation from that exact micro-step.

## Startup validation

Production startup validates capability-to-worker bindings and delegated-profile identities before inference. Missing roots, unknown delegates, duplicates, invalid LLM prompts/model pools, or invalid persona contracts fail before model-dependent execution.

## Invariants

1. LLMs never discover/address arbitrary private worker implementations.
2. Public capabilities resolve through application-owned execution policy.
3. A worker performs one bounded responsibility.
4. A station runs only when its output is needed by the current workpiece path.
5. Workers receive projections, not the whole master workpiece by default.
6. Workers return components; deterministic application code attaches them.
7. Deterministic code composes durable system-control authority.
8. Evidence sufficiency cannot select capabilities.
9. Capability selection cannot reassess sufficiency.
10. Packet contracts reject unregistered/missing fields.
11. Persona is forbidden except for optional user-facing natural-language realization.
12. Shared model residency never implies shared conversational state.
13. Model/backend replacement does not change durable system identity/continuity.
14. New stations require a real consumer, authority boundary, or measured failure mode; schema fields alone are insufficient justification.
15. Terminalization is broader than response generation.

## Testing

Registry/workpiece tests should verify:

- one shared current LLM model pool;
- response-only persona access;
- packet projection drops unregistered state;
- capabilities resolve to deterministic roots;
- delegated selectors are narrow;
- fast-path pre-cognition uses only sufficiency;
- capability selection occurs only after insufficiency;
- specialist schemas cannot express each other's authority;
- master workpiece components are discriminated/typed;
- outputless action terminalization is legal;
- a user-response component is present only when the terminal path requires one.

New deterministic roles should stay deterministic unless semantic ambiguity demonstrably requires inference. New LLM roles should remain conditional unless every valid workpiece path genuinely requires their output.
