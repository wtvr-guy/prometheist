# Worker Profile Registry

**Status:** current execution architecture for the pre-cognitive transient-worker scheme  
**Registry version:** `worker-profile-registry-v1`  
**Primary implementation:** `src/jit_agent/worker_profile_registry.py`

## Purpose

Prometheist exposes **capabilities** as the semantic surface describing what work may be requested. It must not expose arbitrary worker implementations to an LLM or allow a model to select private execution identities directly.

The worker profile registry is the private application-owned execution layer beneath that capability surface.

```text
semantic capability
    -> application-owned capability registration
    -> private root worker profile
       -> deterministic execution
       -> optional narrow delegated LLM worker(s)
```

This keeps capability discovery task-oriented while allowing execution roles to remain narrowly specified, replaceable, auditable, and resource-governed.

## Worker profile contract

Each worker profile declares:

- a stable private `worker_profile_id`;
- deterministic or LLM execution mode;
- a minimum packet contract listing the fields the worker is allowed to receive;
- an output-schema identity;
- a narrow system/role prompt for an LLM worker;
- a model-pool identity for an LLM worker;
- explicit persona access;
- delegated worker profiles when a deterministic composite capability needs a bounded semantic sub-operation.

The packet contract is closed by omission: broader application state is projected into the registered field set before it is considered a legal worker packet. Missing required fields or unexpected fields fail validation.

The registry therefore documents and enforces the principle that a worker should receive only the information required for its single bounded job, rather than a generic accumulated context.

## Capability/worker separation

A capability ID is not a worker ID.

Current capability roots are deterministic:

| Capability executor | Private root worker profile | Delegated LLM role |
| --- | --- | --- |
| `jit_memory` | `jit_memory_executor` | none |
| `deeper_research` | `deeper_research_executor` | `memory_research_candidate_selector` |
| `cross_reference` | `cross_reference_executor` | `cross_reference_candidate_selector` |
| `focused_recall` | `focused_recall_executor` | `focused_recall_candidate_selector` |

This means the model may select a legal semantic capability index, but Prometheist owns the translation from that semantic request to concrete execution roles, dependencies, resource admission, identifiers, and persistence.

## Current LLM worker profiles

The current registry contains narrow profiles for:

- pre-cognitive assessment;
- final readiness;
- response-policy classification;
- unsupported-evidence fallback selection;
- deeper-research candidate selection;
- cross-reference candidate selection;
- focused-recall candidate selection;
- exact-source substring selection;
- exact-source composition selection;
- final natural-language response synthesis.

These are disposable invocation roles, not persistent agents.

## Shared model pool and stateless inference

Every current LLM worker profile binds to the same logical model pool: `ollama-primary`.

That model-pool identity means the application may serve every role with the same configured local Ollama model while preserving statelessness between calls. Model-weight residency and model-context continuity are different things:

- the model weights may remain resident in RAM/VRAM inside Ollama;
- each worker invocation still receives a newly constructed prompt and bounded packet;
- no prior conversation messages, hidden worker context, or KV/cache state is treated as Prometheist continuity;
- durable continuity remains in PostgreSQL/application state.

The current production model remains Qwen3:4b for the v0.7 acceptance experiment. Using one model pool avoids repeated model swaps and gives the residency-aware resource estimator a stable target to observe.

Prometheist does not require an indefinitely pinned model. Ollama residency is operational state, not cognitive state; the resource layer may permit unloading when host pressure or future policy requires it.

## Persona boundary

Persona access is explicit in the registry.

Current rule:

```text
all pre-cognitive / selector / readiness / policy workers -> persona FORBIDDEN
final natural-language response worker                  -> persona REQUIRED
```

The personality prompt controls only user-facing realization after response authority is already final. It cannot create facts, change source policy, authorize capability work, or alter the `RESPOND`/`ABSTAIN` decision.

This separation also creates a clean baseline for any future experiment involving personalized cognition. Such an experiment would require a distinct versioned cognitive-policy/profile mechanism and benchmark evidence; it must not be introduced implicitly through the response persona or retrieved memory.

## Startup validation

The production subprocess entry point validates the capability-to-worker binding graph before model inference. A missing root binding, unknown delegated worker, duplicate profile, or structurally invalid profile fails before the interaction worker begins model-dependent execution.

## Invariants

The registry must preserve these rules:

1. LLMs never discover or address private worker implementations directly.
2. Every public capability resolves through application-owned execution policy.
3. Deterministic capability roots remain capable of delegating only explicitly registered narrow semantic sub-roles.
4. An LLM worker has a non-empty narrow role prompt and explicit model pool.
5. Deterministic workers do not carry model prompts or persona instructions.
6. Persona access is forbidden unless explicitly registered.
7. The final response worker is the only current profile with required persona access.
8. Worker packet contracts reject unregistered fields and missing required fields.
9. Shared model residency must never be confused with shared conversational state.
10. Model/backend replacement must not change durable system identity or continuity.

## Testing

`tests/test_worker_profile_registry.py` verifies:

- all LLM profiles share the single current model pool;
- only the final response profile receives persona authority;
- packet projection discards broader unregistered application state;
- packet validation rejects missing and extra fields;
- every current capability resolves to a deterministic private root worker;
- composite capabilities delegate to the intended narrow LLM profile;
- the complete capability/delegation graph validates.

The registry is an architectural control surface, not a claim that every future worker will be LLM-backed. New deterministic workers should remain deterministic unless a measured semantic requirement justifies model inference.
