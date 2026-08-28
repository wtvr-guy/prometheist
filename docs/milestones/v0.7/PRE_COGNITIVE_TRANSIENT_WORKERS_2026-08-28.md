# v0.7 Pre-Cognitive Transient Worker Increment — 2026-08-28

## Decision

The production interaction subprocess path is changed from the recurrent fresh-model capability router introduced during Increment G to a staged pre-cognitive transient-worker architecture.

Model selection is intentionally held constant. Native acceptance remains on Qwen3:4b so architectural effects are not conflated with a model-capacity change.

## Hypothesis

Prometheist should be able to preserve obscure historical recall and current-turn continuity with lower recurrent-inference overhead by:

1. opening bounded JIT memory before semantic routing;
2. using one fresh pre-capability assessment;
3. executing deterministic capability work only when required;
4. using one fresh post-capability assessment after first-tranche work;
5. allowing at most one newly exposed follow-up tranche in scheme v1;
6. running fresh terminal readiness after that follow-up when the post assessment was non-terminal;
7. finalizing the respond/abstain decision before any final responder is invoked;
8. invoking the final responder only as a persona/language realization worker.

## Final-response clarification added during implementation

The original implementation draft still left two cognitive responsibilities inside the response worker:

- source/surface response-policy classification;
- the practical decision to emit a response or fail for insufficient admitted evidence.

That boundary was rejected. The final responder must not decide whether it should respond.

The accepted production contract is now:

```text
percept
  ↓
JIT aperture
  ↓
PRE_CAPABILITY
  ↓
optional deterministic first tranche
  ↓
optional POST_CAPABILITY
  ↓
optional bounded follow-up tranche
  ↓
FINAL_READINESS when the last assessment requested follow-up
  ↓
current-percept-only response source/surface classification
  ↓
application evidence-admission check
  ↓
persist FinalResponseDirective
  ├─ ABSTAIN → deterministic fallback/insufficient output; responder is not invoked
  └─ RESPOND → final responder + mandatory personality prompt
```

`FinalResponseDirective` has no capability-acquisition state. Once it exists, acquisition is over.

## Implementation

Primary files:

- `src/jit_agent/pre_cognitive_workers.py` — staged acquisition and exact bounded context composition;
- `src/jit_agent/pre_cognitive_response_runtime.py` — terminal readiness, source-policy finalization, durable directive persistence, and production claim/error wrapper;
- `src/jit_agent/final_response_directive.py` — closed terminal response schemas;
- `src/jit_agent/personality.py` — mandatory application-owned personality prompt and content identity;
- `src/jit_agent/durable_response_llm.py` — directive-only final synthesis path;
- `src/jit_agent/interaction_worker.py` — production subprocess entry point.

The existing five durable interaction stage keys are retained to avoid mixing a stage-protocol migration into this architectural experiment.

## Acquisition control

`PreCognitiveAssessment` remains closed and permits the model to provide only semantic classifications plus application-catalog indices. The model cannot author capability IDs, queries, event IDs, dependencies, tool arguments, order, permissions, resource policy, plans, or response prose.

The first assessment is persisted before selected capability work is authorized. If first-tranche work executes, a fresh post assessment receives composed exact evidence plus only newly legal follow-up capability choices.

## Follow-up termination

If `POST_CAPABILITY` emits terminal `RESPOND` or `ABSTAIN`, that assessment can seed finalization directly.

If it emits `ACQUIRE_CAPABILITIES`, Prometheist executes the one legal follow-up tranche and then runs a separate `FinalReadinessDecision`. That worker can emit only `RESPOND` or `ABSTAIN`; it cannot request a third capability round.

The final-readiness record is deterministically persisted and bound to the final MemoryPacket and completed capability identities before it becomes authoritative.

## Response-source policy

Historical source admissibility remains classified from the current percept only. Retrieved memory is excluded from that classifier so historical text cannot change which source role is allowed to establish the claim.

This classification is now part of pre-cognitive finalization. The final responder no longer calls the response-policy classifier.

Application code filters the final packet and capability results according to the closed policy. If the required historical source role has no admitted support, the terminal action becomes `ABSTAIN` upstream.

## FinalResponseDirective

The terminal directive persists:

- `RESPOND` or `ABSTAIN`;
- a closed abstain reason when applicable;
- intent/evidence/claim/requirement classifications;
- the finalized `ResponsePolicy`;
- an optional verbatim current-user fallback literal for abstention;
- final `memory_request_id`;
- completed capability IDs;
- follow-up execution status;
- mandatory personality-prompt version and SHA-256 digest.

The response stage validates these bindings before use.

## Mandatory personality prompt

Every **generative** final responder invocation receives an explicit non-empty application-owned personality prompt.

The prompt is separate from evidence and from the terminal control record. It may shape voice/style only; it cannot expand evidence, change response authorization, reopen capabilities, or alter source admissibility.

The finalizer records its version and SHA-256 digest in the directive. If application configuration changes the prompt between finalization and response execution, the response path fails closed instead of silently using a different persona contract.

## Abstention semantics

`ABSTAIN` never reaches the final responder.

If the current user message explicitly supplies a literal to use for unsupported evidence, the pre-cognitive fallback selector may select that exact current-message substring. Otherwise the application returns the governed generic insufficient-evidence output.

This is a deterministic response-stage consequence of an already-final decision, not a second cognition step.

## Restart semantics

Material decisions are durable before downstream use:

- pre/post assessments are bound to their evidence packet and catalog;
- final readiness is bound to final evidence/capability results;
- the final directive is bound to final evidence, capability IDs, and personality prompt identity.

Retries reuse persisted authoritative decisions instead of re-rolling model cognition after those decisions have become externally meaningful.

Diagnostic error persistence is best effort. Failure to append the ERROR event must not prevent an attempt to release the worker claim. If release itself fails, the original exception is preserved and scheduler lease expiry remains the recovery fallback.

## Review findings incorporated

The first Copilot review identified two issues:

1. an ERROR-event write could prevent worker-claim release;
2. the legacy in-band cognitive brief could enter the response system prompt after only a `dict` check.

The production finalization runtime now makes error recording and explicit release best effort so observability cannot deadlock worker liveness.

The production response path no longer uses the legacy brief for control at all. Legacy briefs are strictly schema-validated and stripped from the evidence channel; only the persisted `FinalResponseDirective` carries production response control.

## Deterministic acceptance

Required deterministic coverage includes:

- closed pre-cognitive assessment schema;
- invalid/out-of-range catalog index rejection;
- newly exposed follow-up catalog behavior;
- exact-source evidence composition/deduplication;
- terminal readiness with no capability/prose fields;
- terminal directive invariants;
- final packet/capability binding checks;
- mandatory personality-prompt identity;
- final responder rejection of `ABSTAIN`;
- malformed legacy control-brief rejection;
- best-effort error recording and claim release;
- existing restart, cross-process, hidden-transcript, provenance, epistemic-authority, response-policy, and bounded-evidence suites.

## Native acceptance

Qwen3:4b remains required for native acceptance on the development machine. Test at least:

- fast path;
- obscure historical recall;
- first-tranche success;
- follow-up recall plus fresh final readiness;
- unsupported historical request producing upstream `ABSTAIN` with no responder call;
- exact-source single-value and multi-field output;
- restart between directive persistence and response execution;
- resource safety and bounded evidence under the existing v0.7 acceptance suite.

A quantized 12–14B model is explicitly deferred to a later experiment. It is not part of this increment and must not be used to hide a mechanism failure.

## Acceptance state

Implementation is not considered accepted until deterministic CI is green and the native Qwen3:4b suite passes on the development machine. The branch/PR may be reviewed before native acceptance, but the model-dependent acceptance result remains an explicit closure gate.
