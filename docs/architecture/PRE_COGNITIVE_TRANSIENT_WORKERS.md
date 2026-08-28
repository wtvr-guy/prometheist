# Pre-Cognitive Transient Workers

**Status:** current v0.7 interactive acquisition mechanism within the broader Interaction Workpiece architecture  
**Acquisition scheme:** `pre-cognitive-transient-workers-v1`  
**Interactive response contract:** `final-response-directive-v1`  
**Introduced:** 2026-08-28  
**Primary implementation:** `src/jit_agent/pre_cognitive_workers.py`, `src/jit_agent/pre_cognitive_specialists.py`, `src/jit_agent/pre_cognitive_ollama_client.py`, `src/jit_agent/pre_cognitive_response_runtime.py`

## Scope

This document describes the current v0.7 **semantic acquisition stations** used by the interactive path. It is no longer the top-level execution abstraction.

The general execution model is defined in [`INTERACTION_WORKPIECE.md`](INTERACTION_WORKPIECE.md): a typed application-owned workpiece moves through only the deterministic, LLM, capability, tool, device, or future human stations required by the current task. A user-facing response worker is optional at the system level.

Within that architecture, the current interactive path needs bounded semantic judgments about whether evidence appears sufficient for acquisition purposes and, only when it is not, what legal capability could close the gap. Terminal response/abstention authority is a separate lifecycle concern.

## Core invariants

- Every LLM invocation begins with a fresh model context.
- No hidden transcript or previous worker context is inherited.
- JIT memory activation occurs before semantic evidence judgment.
- Application code owns identifiers, ordering, dependency closure, resource admission, persistence, retries, and side effects.
- Each LLM station emits only one closed component appropriate to its bounded role.
- A station receives only its registered information aperture, not the entire workpiece.
- Material application control is persisted before capability or external effects.
- Capability execution remains deterministic/idempotent under application-owned identities.
- Resource admission remains authoritative, including CPU/RAM headroom and the current one-concurrent-LLM-slot default.
- Persona is forbidden from acquisition/control stations.
- Acquisition-time insufficiency may govern whether additional work should be attempted, but it cannot by itself become terminal abstention authority.
- Any interactive path that has not already established sufficiency receives one fresh end-of-work readiness judgment over final evidence before terminal `ABSTAIN` is authorized.
- User-facing language is optional in the general architecture and is produced only when the terminal path requires it.

## Durable stage compatibility

The existing five v0.7 durable stage keys remain unchanged:

| Durable key | Current interactive role |
| --- | --- |
| `RESOLVE_REFERENCES` | Initialize/carry the workpiece and inspect bounded WorkingState availability. |
| `SELECT_CAPABILITY` | Open the attention aperture; run the demand-driven pre-capability semantic stations; persist control/plan. |
| `EXECUTE_CAPABILITY` | Execute selected capability tranches, re-evaluate when material evidence changes, compose final evidence, and finalize the current interactive response directive. |
| `RESPOND` | Compatibility key for the current interface's optional user-output/terminalization station. The LLM responder is invoked only for an already-authorized `RESPOND`. |
| `PERSIST_RESULT` | Persist the terminal workpiece snapshot and any separate user-facing response event. |

These names are durable protocol keys, not universal cognitive stages. Future non-chat tasks do not have to conceptualize their terminal step as “responding.”

## Demand-driven semantic stations

The earlier design asked one Qwen3:4b call to produce an aggregate `PreCognitiveAssessment` containing several responsibilities at once. Native testing showed that contradictory fields could destabilize otherwise-correct recall.

The current production path separates only the decisions that have real downstream consumers.

### Evidence sufficiency

`evidence_sufficiency_verifier` receives the current percept plus bounded activated/completed evidence and returns exactly:

- `SUFFICIENT`
- `INSUFFICIENT`

It does not receive a capability catalog and cannot select work.

Its result is represented as one `EvidenceSufficiencyStationComponent` in the interaction workpiece.

The station's result is **acquisition control**, not universal terminal epistemic authority:

- `SUFFICIENT` establishes the one-call fast path and permits response finalization without another readiness vote;
- `INSUFFICIENT` permits capability selection when useful legal work exists;
- `INSUFFICIENT` plus no selected useful capability means acquisition has no further work to offer, but does **not** itself authorize terminal abstention.

Native acceptance exposed why this boundary matters. Qwen3:4b repeatedly returned `INSUFFICIENT` even when the admitted Kestrel source contained every requested value verbatim. Repeating the same sufficiency job inside the same station did not fix the false negative. That experiment was removed rather than retained as a permanent retry ritual.

### Capability selection

`capability_selector` runs only when:

1. the evidence-sufficiency station returns `INSUFFICIENT`; and
2. the application exposes a non-empty legal capability catalog for the current phase.

It returns only application-catalog indices. It cannot reassess sufficiency, author capability IDs or queries, plan dependencies/order, execute tools, or decide terminal outcome.

Its result is represented as a `CapabilitySelectionStationComponent` only when the station actually ran.

### Deterministic acquisition-control composition

Application code derives the compatibility `PreCognitiveAssessment` from the station outputs:

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

The compatibility word `ABSTAIN` in this acquisition record means **no useful additional acquisition work was selected**. It is not the final interactive response directive.

No LLM authors the aggregate disposition/evidence-state pairing.

`intent_mode`, `claim_scopes`, and `requirement_flags` remain neutral on the production path because no current consumer justifies additional LLM stations merely to populate them.

## Terminal readiness boundary

The current interactive path has a separate `final_readiness` station because the question “should more acquisition work be attempted?” is not identical to the terminal question “does the final evidence support a user-facing answer now that acquisition has ended?”

The boundary is asymmetric and demand-driven:

- acquisition `RESPOND` already established sufficiency and remains the fast path;
- acquisition `ACQUIRE_CAPABILITIES` ultimately reaches final readiness after bounded work when no later assessment already establishes sufficiency;
- acquisition `ABSTAIN` must also reach fresh final readiness before terminal abstention is allowed.

Therefore a pre-acquisition false negative cannot directly become `FinalResponseDirective(action=ABSTAIN)`.

The final-readiness worker receives only the current percept and quarantined final evidence/capability results. It cannot request more work, alter source policy, draft response prose, or call tools. Its output is persisted before the interactive response directive is created.

## Workpiece contribution

The terminal `InteractionWorkpiece` materializes both the atomic acquisition-station results and the application-composed control checkpoints.

Conceptually:

```text
ATTENTION_APERTURE
  -> EVIDENCE_SUFFICIENCY
  -> [CAPABILITY_SELECTION]
  -> PRE_COGNITIVE_CONTROL
  -> [CAPABILITY_WORK tranche=0]
  -> [EVIDENCE_SUFFICIENCY phase=POST_CAPABILITY]
  -> [CAPABILITY_SELECTION phase=POST_CAPABILITY]
  -> [PRE_COGNITIVE_CONTROL phase=POST_CAPABILITY]
  -> [CAPABILITY_WORK tranche=1]
  -> FINAL_EVIDENCE
  -> [FINAL_READINESS when acquisition did not already establish sufficiency]
  -> FINAL_RESPONSE_DIRECTIVE
```

The brackets indicate conditional work. Final readiness is persisted as its own canonical control event; the current workpiece component set continues to carry the final directive rather than duplicating every internal finalization checkpoint as a mandatory component.

The existing persisted pre/post assessment events remain authoritative restart checkpoints. The workpiece snapshot is the cumulative typed view, not a replacement for append-only history.

## Fast path

```text
percept
  -> WorkingState/reference inspection
  -> JIT attention aperture
  -> evidence_sufficiency_verifier
  -> SUFFICIENT
  -> deterministic acquisition-control composition
  -> current interactive response-policy/finalization stations
  -> optional user-output station
  -> terminal outcome
```

The pre-acquisition fast path still uses one semantic LLM call and does not invoke final readiness merely for redundancy.

## Capability / unresolved path

```text
percept + aperture
  -> evidence_sufficiency_verifier
  -> INSUFFICIENT
  -> capability_selector
  -> [selected work: deterministic capability tranche(s)]
  -> [fresh post-capability evidence_sufficiency_verifier when material evidence changed]
  -> acquisition result still unresolved or no useful work selected
  -> fresh final_readiness over final evidence
  -> RESPOND or ABSTAIN terminal authority
```

There is no unbounded recurrent model-owned router in scheme v1 and no same-station “vote until sufficient” loop.

## Why not make every field a station?

The workpiece architecture does not imply maximum decomposition.

A station belongs on the active path only when its output changes what Prometheist can legally or usefully do next. Extra LLM calls add prompt evaluation, generation, orchestration, structured-output failure surfaces, and correlated small-model error even when the model stays warm.

Therefore:

> **one bounded job per station + no unnecessary station**

Both parts matter. A second semantic judgment belongs only when it answers a genuinely different downstream question at a real authority boundary. Repeating the same classifier simply because its first answer was inconvenient is not a sound architectural substitute for separating acquisition control from terminal authority.

## Other current conditional stations

The current interactive path follows the same rule:

- `final_readiness` when acquisition ended without already establishing sufficiency;
- `response_policy_classifier` because source admissibility/surface mode must be fixed before interactive response synthesis;
- `fallback_literal_selector` only on relevant abstention paths;
- exact-source selectors only for exact-source output surfaces;
- capability-specific candidate selectors only inside capabilities that require semantic candidate choice;
- `final_response` only when the terminal path actually requires natural-language realization.

Future action/tool paths may use entirely different stations and may terminalize without any `final_response` call.

## `FinalResponseDirective`

`FinalResponseDirective` remains the correct terminal authority for the **current interactive response path**. It is one workpiece component, not Prometheist's universal terminal object.

It binds response authorization/abstention, evidence state, response source/surface policy, fallback literal, final memory-request identity, completed capability IDs, follow-up state, and personality identity.

Acquisition is over before this directive exists. An acquisition-time `ABSTAIN` value cannot be copied directly into the directive; terminal abstention requires the fresh readiness boundary described above.

A future grocery-order, appointment-booking, device-action, or background maintenance path may terminalize with action-specific authority/results and no `FinalResponseDirective` at all.

## Persona boundary

Persona controls only optional user-facing natural-language realization. It is not evidence or control authority.

All acquisition, readiness, policy, fallback, candidate-selection, deterministic, and capability-execution stations remain persona-free. The current `final_response` worker is the only profile requiring the response persona.

## Durability and crash semantics

The system distinguishes component assembly from durable authority.

Cheap stateless micro-station outputs may be assembled before the next effect-capable durability boundary. Once an assembled control record authorizes downstream capability/external effects, it is persisted and reused after restart. Terminal readiness and the terminal response directive are likewise persisted before user-facing realization. The terminal workpiece snapshot later materializes the full component sequence in one JSON object.

Append-only events, worker results, capability evidence, and idempotency/effect policy remain the underlying authoritative history.

## Resource behavior

- Attention owns task priority.
- Resource admission owns safe concurrency.
- Claims remain admission-guarded.
- CPU/RAM headroom remains reserved.
- Current local inference remains limited to one concurrent LLM slot by default.
- Current LLM stations share `ollama-primary`, allowing Qwen3:4b weights to remain warm without sharing conversational state.

Model residency is an optimization, not cognition.

## Failure containment

| Failure | Required behavior |
| --- | --- |
| malformed specialist component | fail closed; no capability effect |
| invalid capability index | fail closed |
| sufficiency station attempts capability control | impossible by schema/information aperture |
| acquisition sufficiency false-negative | may suppress unnecessary capability work, but cannot itself authorize terminal abstention |
| insufficiency with legal helpful work | expose the capability selector; do not force response from packet presence |
| insufficiency with no useful selected work | acquisition ends; run fresh final readiness before terminal response/abstention authority |
| capability selector attempts sufficiency decision | impossible by schema |
| catalog changes after persisted selection | fail closed |
| worker dies before assembled control persistence | rerun stateless semantic stations; no downstream effect existed |
| worker dies after control persistence | reuse persisted control/plan |
| final evidence/capability binding changes | fail closed |
| final readiness says `ABSTAIN` | terminal directive may abstain only after source-policy validation also completes |
| source policy requires unavailable evidence | interactive path terminalizes as `ABSTAINED` |
| final response worker is invoked without response authority | invariant violation; fail closed |
| personality binding changes | fail closed |
| local model unavailable | durable state remains valid; model-dependent station cannot complete |

## Acceptance

Deterministic CI must cover closed specialist schemas, demand-driven station invocation, separated information apertures, deterministic aggregate acquisition-control composition, the one-call sufficient fast path, direct progression from acquisition insufficiency to capability selection without same-station confirmation, fresh terminal-readiness invocation after acquisition `ABSTAIN`, recovery from acquisition false-negative when final readiness finds support, confirmed terminal abstention when final readiness still finds support insufficient, bounded follow-up exposure, exact evidence composition, terminal directive invariants, workpiece assembly/terminalization, and existing restart/provenance/epistemic/resource regressions.

Native Windows/PostgreSQL/Ollama acceptance remains the v0.7 release gate with Qwen3:4b held constant. The Kestrel scenario specifically verifies both directions: a supported historical question must not be terminally blocked by an acquisition false-negative, while an unsupported question over non-empty related evidence must still terminalize as `ABSTAIN`.

## Non-goals

This mechanism does not:

- make model context stateful;
- replace PostgreSQL durability;
- make every possible schema section mandatory;
- require every interaction to invoke every worker;
- make response generation universal;
- expose private worker IDs as model-owned routing authority;
- remove resource admission;
- introduce unbounded agent recursion;
- swap models to hide architectural weakness.

The general architecture is the workpiece. This document defines only the current bounded semantic-acquisition stations used by one important execution path.