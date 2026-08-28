# Pre-Cognitive Transient Workers

**Status:** current production interaction architecture on `feature/pre-cognitive-transient-workers`  
**Acquisition scheme:** `pre-cognitive-transient-workers-v1`  
**Terminal response contract:** `final-response-directive-v1`  
**Introduced:** 2026-08-28  
**Primary implementation:** `src/jit_agent/pre_cognitive_workers.py`, `src/jit_agent/pre_cognitive_specialists.py`, `src/jit_agent/pre_cognitive_ollama_client.py`, `src/jit_agent/pre_cognitive_response_runtime.py`, `src/jit_agent/interaction_worker.py`

## Purpose

Prometheist needs reasoning depth without allowing any LLM invocation to become a persistent agent. All model calls remain stateless; continuity lives in durable PostgreSQL/application state.

The production interaction architecture is best understood as a **demand-driven assembly line**. An interaction is a workpiece. Deterministic application logic routes that workpiece only through the specialized stations required to produce the components needed for the next legal step. Some stations are ordinary software; some are stateless LLM workers.

A worker is not valuable merely because it is specialized. A station belongs on the production path only when its output changes what the system can legally or usefully do next.

## Core invariants

- Every LLM invocation begins with a fresh model context.
- No hidden transcript, previous worker context, or model-session continuity is inherited.
- Canonical evidence remains exact and lossless.
- JIT memory activation occurs before semantic evidence judgment.
- Application code owns identifiers, ordering, dependency closure, resource admission, persistence, retries, and side effects.
- LLM workers may emit only closed outputs appropriate to one bounded semantic role.
- Material application control is persisted before capability execution or response effects.
- Capability execution remains deterministic/idempotent under application-owned identities.
- Resource admission remains authoritative, including CPU/RAM headroom and one-concurrent-LLM-slot default.
- The final responder never decides whether to respond, acquire more work, or abstain.
- Only the final user-facing response worker receives the personality prompt.

## Durable stage protocol

The existing five v0.7 durable stage keys remain unchanged for restart/migration compatibility:

| Durable stage | Current production role |
| --- | --- |
| `RESOLVE_REFERENCES` | Inspect bounded durable working-state availability. |
| `SELECT_CAPABILITY` | Open the JIT attention aperture; run demand-driven pre-cognitive stations; persist assembled assessment and deterministic execution plan. |
| `EXECUTE_CAPABILITY` | Execute selected first-tranche work; re-evaluate evidence; optionally run one bounded follow-up tranche; compose final evidence. |
| `RESPOND` | Use the already-persisted terminal directive; bypass responder for `ABSTAIN`; invoke pure synthesis only for `RESPOND`. |
| `PERSIST_RESULT` | Persist user-facing result and update bounded WorkingState. |

The stage names are durable protocol keys. They are not one-to-one mappings to LLM workers.

## Demand-driven pre-cognitive assembly

The old pre-cognitive design asked one LLM to emit an aggregate `PreCognitiveAssessment` containing disposition, evidence state, intent, claim scopes, requirement flags, and capability indices. Native Qwen3:4b testing showed that this coupled too many semantic responsibilities into one structured call: a wrong or contradictory field could destabilize otherwise-correct behavior.

Production now separates the operational decisions.

### Station 1: evidence sufficiency

The `evidence_sufficiency_verifier` receives:

- current percept;
- phase;
- bounded activated evidence;
- completed capability-result context when present.

It returns exactly one closed semantic value:

- `SUFFICIENT`
- `INSUFFICIENT`

It does **not** receive a capability catalog and therefore cannot select work.

### Station 2: capability selection

The `capability_selector` is invoked only when:

1. evidence was judged `INSUFFICIENT`; and
2. the application has a non-empty legal capability catalog for the current phase.

It receives the current task/evidence plus the exact numbered application-owned catalog and returns only legal capability indices.

It cannot reassess sufficiency, author capability IDs or queries, plan dependency order, execute tools, or decide `RESPOND` / `ABSTAIN`.

### Deterministic composition

Application code derives the aggregate control state:

```text
SUFFICIENT
    -> RESPOND
    -> CURRENT_INPUT_SUFFICIENT or ACTIVATED_MEMORY_SUFFICIENT

INSUFFICIENT + selected legal capability indices
    -> ACQUIRE_CAPABILITIES
    -> MORE_INTERNAL_EVIDENCE_REQUIRED

INSUFFICIENT + no selected legal capability
    -> ABSTAIN
    -> INSUFFICIENT_AFTER_AVAILABLE_WORK
```

No LLM invocation authors the aggregate disposition/evidence-state pairing.

`PreCognitiveAssessment` remains the durable compatibility/control envelope. Descriptive fields that are not currently required for routing or response-boundary enforcement (`intent_mode`, `claim_scopes`, `requirement_flags`) are left neutral rather than forcing unnecessary LLM calls onto every interaction.

## Fast path

A supported recall or current-input task follows:

```text
percept
  ↓
Attention admission
  ↓
JIT attention aperture
  ↓
evidence_sufficiency_verifier
  ↓ SUFFICIENT
deterministic RESPOND assessment
  ↓
response-policy station
  ↓
persist FinalResponseDirective
  ↓
final response / exact-source station as required
  ↓
persistence
```

The common pre-cognitive fast path therefore still requires only **one** LLM call before response finalization. Specialization does not automatically add latency.

## Capability path

When initial evidence is insufficient:

```text
percept + JIT aperture
  ↓
evidence_sufficiency_verifier
  ↓ INSUFFICIENT
capability_selector
  ↓ legal indices
application-owned execution plan
  ↓
first capability tranche
  ↓
exact bounded evidence composition
  ↓
evidence_sufficiency_verifier
  ├─ SUFFICIENT -> deterministic RESPOND
  └─ INSUFFICIENT
        ↓
     capability_selector only if a newly legal follow-up catalog exists
        ↓
     one bounded follow-up tranche
        ↓
     fresh terminal final-readiness decision
```

There is no unbounded recurrent routing loop in scheme v1.

## Why not make every field a worker?

The architecture explicitly rejects that approach.

A schema field does not justify an LLM station. Each additional model call adds:

- prompt-evaluation cost;
- generation cost;
- orchestration overhead;
- another structured-output failure surface;
- another opportunity for correlated error from the same small model.

Warm Ollama model residency removes repeated weight-loading cost, but it does not make inference free.

Therefore a station is added only when there is a concrete downstream consumer or a measured failure mode that the separation addresses.

## Other existing conditional stations

The same rule applies after acquisition:

- `final_readiness` runs only after follow-up acquisition requires a fresh terminal decision;
- `response_policy_classifier` runs because source admissibility/surface mode must be fixed before synthesis;
- `fallback_literal_selector` runs only on relevant abstention paths;
- exact-source substring/composition selectors run only when response policy requires them;
- capability-specific candidate selectors run only inside capabilities requiring semantic candidate choice;
- the persona-bearing `final_response` worker runs only after `RESPOND` is already authorized.

A workpiece skips every station it does not need.

## FinalResponseDirective

`FinalResponseDirective` remains the terminal application-owned authority object between cognition/acquisition and response synthesis.

It binds:

- `RESPOND` or `ABSTAIN`;
- closed abstain reason when applicable;
- evidence state and compatibility metadata;
- current-percept-derived response source/surface policy;
- optional current-user fallback literal;
- exact final `memory_request_id`;
- completed capability IDs;
- follow-up-executed state;
- personality-prompt version and SHA-256 digest.

There is no `ACQUIRE_CAPABILITIES` state in this object. Acquisition is over before the directive exists.

## Response boundary

`ABSTAIN` means the final generative responder is never invoked. The application emits an allowed explicit current-input fallback literal when available; otherwise it emits the governed insufficient-evidence response.

`RESPOND` means synthesis is authorized. The final responder cannot:

- reopen capability acquisition;
- change source policy;
- change surface mode;
- abstain;
- alter evidence bindings.

Exact-source modes mechanically constrain output to admitted source bytes/fragments.

## Personality boundary

Only the final natural-language response worker receives the application-owned personality prompt. All pre-cognitive, readiness, policy, fallback, and candidate-selection workers are persona-free.

Personality controls expression only. It is not evidence and cannot change routing, sufficiency, source authority, or acquisition permission.

## Durability and crash semantics

The v0.7 durability boundary remains the assembled material control record.

If the process dies while running internal pre-cognitive semantic stations, no capability execution has yet been authorized or performed. Those stateless calls may therefore be rerun safely on restart. Once the assembled assessment/plan is persisted, retries reuse it rather than silently rerolling cognition after downstream effects exist.

Prometheist does **not** yet persist every micro-station output independently. That would be justified only if a station output acquires independent durable authority or cross-process continuation inside a multi-station pass becomes a real requirement.

## Resource behavior

- Attention owns task priority.
- Resource admission owns safe concurrency.
- Claims remain admission-guarded.
- CPU/RAM headroom remains reserved.
- Local inference remains limited to one concurrent LLM slot by default.
- All current LLM stations share `ollama-primary`, allowing Qwen3:4b weights to remain warm across stateless calls.

Shared model residency is an operational optimization, not cognitive continuity.

## Failure containment

| Failure | Required behavior |
| --- | --- |
| malformed specialist schema | fail closed; no capability effect |
| invalid capability index | fail closed |
| duplicate set-like capability indices | canonicalize exact duplicates, then validate |
| sufficiency worker tries to select capability | impossible by schema/information aperture |
| capability selector tries to declare sufficiency | impossible by schema |
| catalog changes after persisted selection | fail closed |
| worker dies before assembled assessment persistence | rerun stateless semantic stations; no downstream effect existed |
| worker dies after assessment persistence | reuse persisted assessment/plan |
| final packet/capability binding changes | fail closed |
| source policy requires unavailable evidence | upstream `ABSTAIN` |
| responder receives `ABSTAIN` | invariant violation; fail closed |
| personality version/digest changes | fail closed |
| local model unavailable | durable state remains valid; model-dependent work cannot complete |

## Acceptance criteria

Deterministic CI must verify:

- closed specialist schemas;
- demand-driven station invocation;
- no capability catalog in the sufficiency worker aperture;
- capability selection only after insufficiency;
- deterministic composition of `RESPOND` / `ACQUIRE_CAPABILITIES` / `ABSTAIN`;
- invalid-index rejection;
- bounded follow-up exposure;
- exact evidence composition/deduplication;
- terminal `FinalResponseDirective` invariants;
- response-source/personality bindings;
- existing restart, provenance, epistemic-authority, bounded-evidence, and worker-registry regressions.

Native Windows/PostgreSQL/Ollama acceptance remains the release gate with Qwen3:4b. The model is intentionally unchanged so architectural improvements are measured without confounding model replacement.

## Non-goals

This scheme does not:

- make model context stateful;
- replace PostgreSQL durability;
- expose arbitrary worker IDs to LLMs;
- allow LLMs to author arbitrary retrieval queries/tool calls;
- remove host-resource admission;
- introduce unbounded multi-agent recursion;
- require every possible component/station on every interaction;
- swap away from Qwen3:4b to hide architectural weakness.

The objective is a conditional assembly graph: each interaction receives exactly the semantic and deterministic work required to become a safe, evidence-bound terminal response directive—and no more.
