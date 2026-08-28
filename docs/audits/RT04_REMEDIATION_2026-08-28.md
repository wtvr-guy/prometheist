# RT-04 remediation — epistemic source authority

**Date:** 2026-08-28  
**Branch:** `redteam/v07-memory-continuity`  
**Baseline attack:** `tests/test_redteam_epistemic_memory_native.py`  
**Generalized fallback corpus:** `tests/test_redteam_current_fallback_selector_native.py`

## Defect

The repaired RT-04 probe deterministically retrieved an assistant-authored `INTERACTION_RESPONSE` asserting a user preference even though no supporting `USER_PROMPT` existed. On the configured native Ollama model, the responder initially promoted that assistant assertion into a supposed user fact.

This was an epistemic source-authority defect: retrieval established that Prometheist had previously emitted the assertion, not that the user had established the embedded claim.

A first remediation that added source-role metadata to the model-facing evidence was insufficient. The configured 4B model still treated the assistant assertion as user truth. That negative result is preserved in the red-team history.

## Final remediation

The final mechanism moves authority enforcement out of free-form response generation.

1. A fresh stateless response-policy classifier sees **only the current user percept**, never retrieved memory, and selects a closed `HistoricalEvidenceScope` plus `ResponseSurfaceMode`.
2. Application code maps that scope to allowed canonical event types and physically removes inadmissible historical events before final synthesis. For user-authored-history questions, only `USER_PROMPT` evidence may establish the claim.
3. Assistant/model history is not deleted or globally censored. It remains admissible when the current question is actually about prior model output.
4. If a required historical scope has no admitted evidence, the system fails closed.
5. Unsupported-history fallback handling is a separate current-percept-only control decision. A focused selector may identify a requested fallback literal, but application code accepts it only when it is a verbatim substring of the current user percept.
6. The broad response policy and focused fallback selection have separate semantic ownership. The response policy cannot smuggle or override the fallback literal.
7. Both the response policy and focused fallback selection are persisted as deterministic `SYSTEM_EVENT` provenance linked to the interaction correlation, worker claim, and step.

Canonical event bytes remain unchanged throughout. The authority/fallback machinery operates on disposable model-facing views and application-owned control state.

## Exact-output companion fix

A separate model-sensitive regression discovered during RT-05 showed that the model could choose the correct authoritative value yet wrap it in prose despite an exact/no-extra-text request.

For exact source-derived responses, Prometheist now uses a constrained semantic selection (`source_index`, `verbatim_value`) over the **already admitted** evidence packet. Application code validates that the selected value is literally present in that canonical source and returns the source substring directly rather than trusting free-form generation to reproduce the required surface form.

This keeps semantic interpretation with the model while moving exact reproduction to deterministic code.

## Acceptance evidence

Hosted CI #490 on response-control policy v3:

- **292 passed**
- **20 skipped**
- **0 failed**
- **45.87 seconds**
- constraint governance: **175 discovered / 175 registered / 0 uncovered / 0 stale / 0 mismatched / 0 invalid**

Native Windows/PostgreSQL/Ollama focused acceptance after final fallback separation:

```text
uv run pytest -q -m ollama \
  tests/test_redteam_epistemic_memory_native.py \
  tests/test_redteam_current_fallback_selector_native.py

5 passed in 69.02s
```

The RT-04 native test additionally verifies that:

- the assistant-only assertion was actually retrieved;
- the current-prompt-only policy selected `USER_AUTHORED`;
- the poisoned assistant value did not appear in the answer;
- the exact current fallback was returned; and
- the focused fallback decision was durably recorded as the same literal.

The generalized native corpus varies source-role labels and fallback phrasing so acceptance is not specific to the literal string `USER_PROMPT only; otherwise INSUFFICIENT`.

## Constitutional interpretation

- **Article 15:** the LLM interprets semantic intent only through a closed schema; application code owns the authority consequence.
- **Article 17:** provenance and truth are separated. Assistant output can prove what the model emitted, but cannot by itself establish user testimony.
- **Article 18:** model-authored control decisions that govern evidence admission/fallback behavior are durable causal provenance.
- **Article 20:** no production English keyword parser was added for `USER_PROMPT`, `otherwise`, `INSUFFICIENT`, or equivalent phrases.
- **Article 29:** unsupported historical claims fail closed after deterministic source filtering.

## Status

**REMEDIATED ON CONFIGURED NATIVE MODEL; PERMANENT REGRESSION.**

This closes the demonstrated assistant-self-poisoning mechanism. It does not prove every possible epistemic conflict across every future source class; cross-source conflict matrices remain a legitimate future red-team surface.
