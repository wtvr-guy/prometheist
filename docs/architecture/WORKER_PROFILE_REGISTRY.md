# Worker Profile Registry

**Status:** current execution architecture for the pre-cognitive transient-worker scheme  
**Registry version:** `worker-profile-registry-v1`  
**Primary implementation:** `src/jit_agent/worker_profile_registry.py`

## Purpose

Prometheist exposes **capabilities** as the semantic surface describing what work may be requested. It does not expose arbitrary worker implementations to an LLM or allow a model to choose private execution identities directly.

The worker profile registry is the private application-owned execution layer beneath that capability surface.

A useful mental model is a demand-driven assembly line:

```text
interaction workpiece
    -> deterministic station routing
    -> only the stations required by this workpiece
       -> deterministic station
       -> narrow LLM station
       -> capability station
       -> policy station
       -> response station
    -> finalized response directive
```

The important rule is not merely “one job per worker.” It is:

> A production station should exist on the active path only when its output changes what the system can legally or usefully do next.

This prevents specialization from turning into gratuitous orchestration overhead.

## Capability / worker / invocation separation

A capability ID is not a worker ID, and a worker is not synonymous with one LLM call.

- **Capability** — what semantic work the system can perform.
- **Worker profile** — how one bounded execution responsibility is implemented.
- **LLM invocation** — one stateless model call that may implement a worker role.

Capabilities resolve through deterministic application-owned bindings. Composite deterministic workers may delegate only to explicitly registered narrow semantic workers.

## Demand-driven pre-cognitive assembly

The production pre-capability path no longer asks one LLM to author the complete `PreCognitiveAssessment`.

The application-owned `pre_cognitive_assessment` root is deterministic and currently delegates to only two semantic stations:

1. `evidence_sufficiency_verifier`
2. `capability_selector`

The second station is conditional.

### Fast path

```text
current percept + activated evidence
    -> evidence_sufficiency_verifier
       -> SUFFICIENT
    -> deterministic RESPOND control state
```

A supported fast-path interaction therefore still pays for only one pre-cognitive model call.

### Acquisition path

```text
current percept + activated evidence
    -> evidence_sufficiency_verifier
       -> INSUFFICIENT
    -> capability_selector
       -> legal application-catalog indices or empty
    -> deterministic ACQUIRE_CAPABILITIES or ABSTAIN control state
```

The capability selector never decides sufficiency. The sufficiency verifier never sees or selects a capability catalog. This separation is intentional containment.

## Why some apparent “components” are not stations

`PreCognitiveAssessment` retains compatibility fields such as broad intent, claim scopes, and requirement flags. They are not currently required to route acquisition or enforce the final response boundary.

Production therefore does **not** spend model calls populating them merely because the schema contains them. The new production path leaves those descriptive fields neutral (`OTHER` / empty lists) until a real downstream consumer justifies a dedicated station.

This is a deliberate anti-overengineering rule. A field is not evidence that a worker is necessary.

## Current capability roots

Current capability roots remain deterministic:

| Capability executor | Private root worker profile | Delegated LLM role |
| --- | --- | --- |
| `jit_memory` | `jit_memory_executor` | none |
| `deeper_research` | `deeper_research_executor` | `memory_research_candidate_selector` |
| `cross_reference` | `cross_reference_executor` | `cross_reference_candidate_selector` |
| `focused_recall` | `focused_recall_executor` | `focused_recall_candidate_selector` |

The model may select a legal semantic capability index only through the bounded capability-selector station. Prometheist owns the translation from that selection to concrete execution roles, dependencies, identities, ordering, resource admission, provenance, and persistence.

## Other conditional stations

The rest of the interaction already follows the same assembly principle:

- `final_readiness` runs only after the bounded follow-up path still requires a terminal sufficiency decision;
- `response_policy_classifier` runs at the response boundary because source admissibility and surface mode are operationally required;
- `fallback_literal_selector` runs only for an abstention path that may return an explicit current-input literal;
- exact-source selectors run only when the response policy selects an exact-source surface;
- candidate selectors run only inside capabilities that need semantic candidate selection;
- `final_response` runs only after a persisted `RESPOND` directive authorizes natural-language realization.

A workpiece should skip every station it does not need.

## Worker profile contract

Each worker profile declares:

- a stable private `worker_profile_id`;
- deterministic or LLM execution mode;
- a minimum packet contract listing the fields the worker may receive;
- an output-schema identity;
- a narrow system prompt for an LLM worker;
- a model-pool identity for an LLM worker;
- explicit persona access;
- delegated worker profiles for deterministic composite workers.

Packet contracts are closed by omission. Broader application state is projected into the registered field set. Missing required fields or unexpected fields fail validation.

This creates hard information apertures between stations. For example, the evidence-sufficiency verifier does not receive `capability_catalog`, while the capability selector does.

## Shared model pool and stateless inference

Every current LLM worker profile binds to the same logical model pool: `ollama-primary`.

That means Ollama may keep the configured Qwen3:4b weights resident while every station remains cognitively stateless:

- model weights may remain warm in RAM;
- each invocation receives a newly constructed prompt and bounded packet;
- no prior worker transcript or hidden conversation state is treated as continuity;
- durable continuity remains in PostgreSQL/application state.

Warm model residency reduces model-load overhead, but it does **not** make extra stations free. Prompt evaluation, generation, orchestration, and failure probability still matter. That is why station invocation remains demand-driven.

## Persona boundary

Persona access is explicit:

```text
all pre-cognitive / selector / readiness / policy workers -> persona FORBIDDEN
final natural-language response worker                  -> persona REQUIRED
```

The personality prompt controls only user-facing realization after response authority is final. It cannot create facts, change source policy, authorize capability work, or alter the `RESPOND` / `ABSTAIN` decision.

## Durability boundary

The current v0.7 design persists the **assembled material control record** before capability execution or response effects occur.

It does not yet persist every micro-station output independently. If a process dies while assembling a pre-cognitive decision, no capability side effect has occurred, so the stateless semantic stations may be rerun safely.

Per-station durable components would become justified if Prometheist later needs cross-process continuation inside a multi-station cognitive pass or if a station output itself acquires independent durable authority. Adding that complexity before such a requirement exists would be premature.

## Invariants

1. LLMs never discover or address private worker implementations directly.
2. Every public capability resolves through application-owned execution policy.
3. A worker performs one bounded responsibility.
4. A station is invoked only when its output is needed by the current path.
5. Deterministic code composes station outputs into system control authority.
6. The evidence-sufficiency station cannot select capabilities.
7. The capability-selection station cannot reassess sufficiency.
8. Worker packet contracts reject unregistered fields and missing required fields.
9. Persona access is forbidden except for the final response worker.
10. All current LLM roles share `ollama-primary` without sharing conversational state.
11. Model/backend replacement must not change durable system identity or continuity.
12. New stations require a concrete downstream consumer or measured failure mode; schema fields alone are insufficient justification.

## Testing

`tests/test_worker_profile_registry.py` and `tests/test_pre_cognitive_ollama_client.py` verify, among other things:

- all LLM profiles share the same model pool;
- only the final response profile receives persona authority;
- packet projection drops unregistered state;
- every capability resolves to a deterministic private root worker;
- pre-cognitive composition is deterministic;
- the fast path invokes only the sufficiency station;
- capability selection occurs only after insufficiency;
- the sufficiency worker cannot receive a capability catalog;
- closed specialist schemas cannot express aggregate control authority;
- duplicate set-like capability indices are canonicalized without weakening strict validation.

New deterministic workers should remain deterministic unless a measured semantic requirement justifies model inference. New LLM stations should remain conditional unless every valid path genuinely requires their output.
