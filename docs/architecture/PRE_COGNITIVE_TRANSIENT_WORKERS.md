# Pre-Cognitive Transient Workers

**Status:** current production interaction architecture on `feature/pre-cognitive-transient-workers`  
**Acquisition scheme:** `pre-cognitive-transient-workers-v1`  
**Terminal response contract:** `final-response-directive-v1`  
**Introduced:** 2026-08-28  
**Primary implementation:** `src/jit_agent/pre_cognitive_workers.py`, `src/jit_agent/pre_cognitive_response_runtime.py`, `src/jit_agent/durable_response_llm.py`, `src/jit_agent/interaction_worker.py`

## Purpose

Prometheist needs reasoning depth without allowing any model invocation to become a persistent agent and without paying for an open-ended recurrent router loop. The pre-cognitive transient-worker architecture decomposes one interaction into disposable workers that each perform one bounded job from explicitly reconstructed durable state.

The architecture separates four concerns:

1. **activation and evidence acquisition** — deterministic retrieval and capability execution;
2. **pre-cognitive control** — fresh bounded semantic judgments about what work is still required;
3. **terminal response authorization** — an application-owned decision that the interaction will either respond or abstain, including the final evidence-source and surface-form policy;
4. **persona/language realization** — a fresh final responder that is invoked only after response authorization is already final.

Workers may be LLM-powered or ordinary deterministic software. No worker owns Prometheist's continuity. Continuity belongs to durable state.

## Constitutional invariants

The scheme must preserve all of the following:

- Every LLM invocation begins with a fresh model context.
- No hidden transcript, chat context, or previous model state is inherited by another invocation.
- Canonical evidence remains exact and lossless; model summaries never replace source memory.
- Every model-facing evidence view is independently bounded.
- JIT memory activation occurs before semantic routing. A model is never asked whether unseen memory matters.
- Models may make bounded semantic classifications and select application-owned indices. Ordinary software owns identifiers, dependencies, ordering, execution, permissions, resource admission, retry semantics, provenance, and persistence.
- Material model-control output is schema-validated and persisted before it can authorize downstream effects.
- A crash retry reuses a persisted material control decision rather than silently re-rolling it after downstream effects exist.
- Capability execution remains deterministic/idempotent under application-owned execution identity.
- Invalid control output, inconsistent evidence bindings, or insufficient support fail closed.
- Resource admission remains authoritative, including CPU/RAM headroom and the default one-concurrent-LLM-slot policy.
- **The decision to respond or abstain belongs entirely to the pre-cognitive system. The final responder never makes that decision.**
- **Every generative final responder invocation receives one explicit non-empty application-owned personality prompt.**

## Cognition is not continuity

A transient cognition worker can inspect a current percept plus a bounded evidence packet and return a semantic judgment. That does not make it a persistent agent.

Durable state remains external to the LLM:

- canonical events;
- WorkingState activation references;
- attention tasks and assignments;
- worker step identities and leases;
- memory requests and MemoryPackets;
- capability results;
- persisted pre/post assessments;
- persisted final-readiness decisions when needed;
- persisted `FinalResponseDirective` records;
- response events.

A worker can disappear immediately after producing its validated result. A later worker reconstructs everything it is allowed to know from durable application state.

## Production flow

The existing five v0.7 durable stage keys remain for migration/restart compatibility. Their current production semantics are:

| Durable stage | Production role | LLM required? |
| --- | --- | --- |
| `RESOLVE_REFERENCES` | Inspect bounded WorkingState availability. No phrase-based continuity detection. | No |
| `SELECT_CAPABILITY` | Open the JIT attention aperture and run one fresh `PRE_CAPABILITY` assessment. Persist the validated assessment and deterministic plan. | Usually yes |
| `EXECUTE_CAPABILITY` | Execute selected first-tranche work. If needed, run fresh `POST_CAPABILITY` cognition and one bounded follow-up tranche. Then finalize and persist a terminal `FinalResponseDirective`. | Conditional |
| `RESPOND` | Read the already-finalized directive. `ABSTAIN` bypasses the final responder. `RESPOND` invokes a pure synthesis worker with the mandatory personality prompt. | Only for authorized generative responses |
| `PERSIST_RESULT` | Persist the user-facing result and update bounded WorkingState. | No |

The production subprocess entry point is `interaction_worker.py`, which routes through `pre_cognitive_response_runtime.py`. The older direct executor in `pre_cognitive_workers.py` remains a compatibility implementation and is not the normative production response boundary.

## Fast path

For a normal interaction whose current percept and initial JIT activation are sufficient:

```text
percept
  ↓
durable intake + Attention admission
  ↓
JIT attention aperture
  ↓
fresh PRE_CAPABILITY worker
  ↓ terminal RESPOND/ABSTAIN assessment
current-percept-only response-policy classification
  ↓
persist FinalResponseDirective
  ├─ ABSTAIN → deterministic fallback/insufficient result; no final responder
  └─ RESPOND → fresh final responder + mandatory personality prompt
                 ↓
              persistence
```

A normal generative turn therefore needs one pre-cognitive LLM call plus one final response LLM call. Response-source policy classification is also a fresh bounded model operation today, but it is part of pre-cognitive finalization, not response synthesis.

## Capability path

When more work is required:

```text
percept
  ↓
JIT aperture
  ↓
PRE_CAPABILITY
  ↓ ACQUIRE_CAPABILITIES
validated application-owned indices
  ↓
deterministic dependency closure / plan
  ↓
first capability tranche
  ↓
exact bounded evidence composition
  ↓
POST_CAPABILITY
  ├─ terminal RESPOND/ABSTAIN
  │       ↓
  │   final directive
  │
  └─ ACQUIRE_CAPABILITIES
          ↓
     newly exposed follow-up catalog only
          ↓
     one bounded follow-up tranche
          ↓
     fresh FINAL_READINESS worker
          ↓ RESPOND/ABSTAIN only; no capabilities legal
     current-percept-only response policy
          ↓
     persist FinalResponseDirective
          ├─ ABSTAIN → no final responder
          └─ RESPOND → final responder
```

The important correction is the final-readiness step after a requested follow-up tranche. A `POST_CAPABILITY` decision that requests more work is not itself permission to respond afterward. Once that work finishes, one fresh terminal worker evaluates the completed evidence and may emit only `RESPOND` or `ABSTAIN`.

There is no third capability-routing round in scheme v1.

## Closed acquisition control

`PreCognitiveAssessment` has `extra="forbid"` and exposes only:

- `phase`: `PRE_CAPABILITY` or `POST_CAPABILITY`;
- `disposition`: `RESPOND`, `ACQUIRE_CAPABILITIES`, or `ABSTAIN`;
- broad `intent_mode`;
- closed `evidence_state`;
- bounded `claim_scopes`;
- bounded `requirement_flags`;
- integer `capability_indices` into the exact application-owned catalog supplied to that call.

It cannot author capability IDs, queries, event IDs, tool arguments, dependency order, resource reservations, retry policy, prose plans, factual claims, or response text.

## Follow-up exposure

The first post-capability assessment sees only capabilities newly made legal by successful first-tranche work. Original first-tranche capabilities are not simply re-presented to create a recurrent loop.

Today, broader internal research can expose focused recall. Future capability families may expose other follow-ups, but the same rule applies: the system exposes a bounded legal next-step surface derived from durable completed work.

## Final readiness

`FinalReadinessDecision` is a separate closed schema. It exists because after the one allowed follow-up tranche there must still be a semantic judgment about whether the acquired evidence is enough.

It can emit only:

- `RESPOND` or `ABSTAIN`;
- one closed evidence-state value.

It cannot request another capability, write a query, write response prose, alter source policy, or create a plan.

The decision is persisted with a deterministic event identity bound to:

- the final MemoryPacket's `memory_request_id`;
- the completed capability IDs;
- the final-readiness schema version.

A retry reuses that record instead of asking the model again after it has become authoritative.

## Current-percept-only response policy belongs upstream

Historical source admissibility and final surface mode are still classified from the **current user percept only**. Retrieved memory is deliberately excluded from that classifier so historical text cannot alter which source role is allowed to establish the requested claim.

The resulting closed `ResponsePolicy` determines:

- allowed historical source role (`USER_AUTHORED`, `MODEL_OUTPUT`, `EXTERNAL_TOOL`, `SYSTEM_RECORD`, `DERIVED_INTERNAL`, `MIXED_CONVERSATION`, or `GENERAL_OR_CURRENT`);
- surface mode (`NATURAL_LANGUAGE`, `EXACT_SOURCE_SUBSTRING`, or `EXACT_SOURCE_COMPOSITION`).

That classification now occurs during pre-cognitive finalization. The final responder does **not** run another response-policy classifier.

Application code then physically filters the final packet and capability results according to that policy. If the requested historical source role has no admitted support, the final action becomes `ABSTAIN` before the response stage can invoke a responder.

## FinalResponseDirective

`FinalResponseDirective` is the terminal application-owned authority object between pre-cognition and response synthesis.

It includes only validated closed/control data plus application-owned evidence bindings:

- `action`: `RESPOND` or `ABSTAIN`;
- a closed abstain reason when applicable;
- final intent/evidence/claim/requirement classifications;
- the already-finalized `ResponsePolicy`;
- an optional current-user fallback literal for `ABSTAIN`;
- the exact final `memory_request_id`;
- the completed capability IDs;
- whether follow-up work executed;
- the required personality-prompt version and SHA-256 digest.

There is deliberately no `ACQUIRE_CAPABILITIES` state in this object. Once the directive exists, acquisition is over.

The directive is persisted as a deterministic `SYSTEM_EVENT` before the response stage can use it. On retry, the application verifies the evidence binding, capability list, personality-prompt version, and personality-prompt digest before reusing it.

## Respond vs. abstain ownership

This boundary is strict:

- `ABSTAIN`: the application does not invoke the generative final responder. It emits an explicitly requested current-user fallback literal when one exists; otherwise it emits the governed generic insufficient-evidence result.
- `RESPOND`: the final responder is invoked. It is not allowed to abstain, request more evidence, change source scope, change surface mode, or reopen capability work.

If a `RESPOND` directive reaches synthesis but the supplied packet no longer matches its `memory_request_id`, the capability-result list changed, the personality prompt changed, or policy-admitted support disappeared, the responder path raises and fails closed. It does not reinterpret the task.

## Mandatory personality prompt

Persona realization is explicitly separated from evidence and control.

`src/jit_agent/personality.py` provides one non-empty application-owned personality prompt for every generative final response invocation. The default prompt can be replaced through governed application configuration, but the finalizer records both its version and SHA-256 digest in the directive. The responder verifies both before inference.

The final model-facing system authority is therefore assembled from four distinct parts:

1. response safety/epistemic system contract;
2. mandatory personality prompt;
3. persisted terminal `FinalResponseDirective`;
4. quarantined admitted evidence plus the current percept in their existing authority-separated channels.

The personality prompt may control voice/style. It may not create facts, expand evidence, change source admissibility, initiate capability work, or reconsider the `RESPOND` decision.

Personality is never reconstructed from arbitrary retrieved historical text. A future personalized-prompt builder may itself be application-owned and versioned, but it must still produce an explicit prompt artifact before response synthesis.

## Exact-source responses

Exact-source substring/composition modes remain mechanically constrained. The model may select exact admitted source spans under the existing validation rules, but the application returns validated source bytes rather than allowing free-form prose to rewrite an exact value.

Those selector calls are not an alternate response-authorization path. The terminal directive has already authorized `RESPOND` and fixed the surface policy before exact-source selection occurs.

## Evidence composition

After capability work, Prometheist composes bounded task-local context from exact `MemoryEvidence` objects:

1. capability evidence is considered before the original aperture evidence;
2. items are deduplicated by canonical `source_event_id`;
3. source content is copied exactly rather than summarized;
4. the view remains bounded;
5. contributing memory-request IDs are recorded in the retrieval trace.

This is a disposable working view, not canonical memory.

## Worker taxonomy

### Deterministic/non-LLM workers

Examples include:

- durable event intake;
- WorkingState inspection;
- JIT aperture orchestration;
- schema validation;
- capability-index validation;
- dependency closure and execution planning;
- resource probing/admission;
- claim/lease management;
- evidence composition/deduplication;
- source-policy filtering;
- terminal directive construction/persistence;
- response persistence.

### LLM-powered transient workers

Current roles include:

- `PRE_CAPABILITY` assessment;
- `POST_CAPABILITY` assessment after first-tranche work;
- `FINAL_READINESS` only after the follow-up path remains non-terminal;
- current-percept-only response-policy classification;
- focused current-fallback selection only when an abstention requires it;
- capability-specific candidate selectors where semantically necessary;
- final natural-language synthesis after a `RESPOND` directive.

Every call is independent and reconstructed from explicit inputs.

## Restart and crash semantics

Transient compute does not imply transient authority.

Material control records are persisted before downstream use. Persisted pre/post assessments are evidence/catalog-bound and reused on retry. Final readiness is final-packet/capability-bound and reused. `FinalResponseDirective` is final-packet/capability/personality-bound and reused.

Diagnostic error recording is best effort. If an error event itself cannot be written, that failure must not prevent worker-claim release. Claim liveness is more important than secondary observability. Explicit claim release is also best effort so the original worker exception is preserved; lease expiry/recovery remains the scheduler fallback.

## Resource behavior

This increment does not weaken resource governance.

- Attention chooses priority.
- Resource admission chooses safe concurrency.
- Claims are admission-guarded.
- configured CPU/RAM headroom remains reserved;
- local LLM inference remains conservatively limited to one concurrent LLM slot by default;
- Ollama residency is considered by the resource estimator.

The architectural efficiency gain comes from bounded staged cognition and avoiding unnecessary recurrent model calls, not from relaxing safety margins.

## Model policy

Qwen3:4b remains the native acceptance model for this increment. The worker architecture must demonstrate its value without simultaneously changing the model.

A quantized 12–14B model may be benchmarked later as a separate resource/performance experiment. Model growth must not be used to conceal an architectural failure, and no model may bypass host-safety admission.

## Failure modes

| Failure | Required behavior |
| --- | --- |
| malformed/extra pre-cognitive field | validation failure; no downstream effect |
| invalid capability index | fail closed |
| registry changes after persisted selection | fail closed |
| worker dies after persisted assessment | reuse persisted assessment |
| follow-up completes after `POST_CAPABILITY=ACQUIRE_CAPABILITIES` | run fresh final-readiness cognition before response authorization |
| final readiness says `ABSTAIN` | never invoke final responder |
| source policy requires unavailable historical role | create `ABSTAIN` directive upstream |
| malformed legacy `pre_cognitive_brief` | schema rejection; never inject into system prompt |
| final packet/capability binding differs from directive | fail closed |
| personality prompt version/digest differs from directive | fail closed |
| responder receives `ABSTAIN` | invariant violation; fail closed |
| error-event persistence fails while handling worker exception | continue to claim-release attempt; preserve original exception |
| local model unavailable | durable state remains valid; model-dependent work cannot finish |

## Acceptance criteria

Deterministic CI should cover:

- closed pre-cognitive schemas;
- invalid-index rejection;
- bounded follow-up exposure;
- exact evidence composition/deduplication;
- terminal readiness schema with no capability surface;
- `FinalResponseDirective` terminal invariants;
- source/evidence binding validation;
- mandatory personality prompt identity/binding;
- rejection of `ABSTAIN` by the final responder;
- malformed legacy control-brief rejection;
- best-effort error recording and claim release;
- existing restart, cross-process, hidden-transcript, provenance, epistemic-authority, response-policy, and bounded-evidence regressions.

Native acceptance must then run with Qwen3:4b on the development machine. Important scenarios include:

- fast-path conversational response;
- obscure historical recall recovered through staged internal retrieval;
- first-tranche capability result sufficient at `POST_CAPABILITY`;
- follow-up recall requiring fresh final readiness;
- unsupported historical request producing upstream `ABSTAIN` with no responder call;
- exact-source substring and multi-field composition;
- process restart between final directive persistence and response execution;
- personality-prompt drift detection;
- bounded evidence and host-resource safety under the existing v0.7 acceptance suite.

## Non-goals

This increment does not:

- change the canonical event schema;
- replace PostgreSQL persistence;
- make model context stateful;
- allow LLMs to author arbitrary tool calls or retrieval queries;
- remove resource admission;
- introduce unbounded multi-agent recursion;
- swap away from Qwen3:4b;
- claim that a 12–14B model is currently required;
- make the personality prompt factual evidence.

The architectural objective is specific: Prometheist should gather exactly as much durable evidence and capability output as the current task requires, using disposable staged workers, and arrive at a terminal response decision **before** the final persona-bearing response worker is summoned.
