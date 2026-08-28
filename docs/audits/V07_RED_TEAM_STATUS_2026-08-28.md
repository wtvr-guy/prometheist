# Prometheist v0.7 red-team status — 2026-08-28

This document is a current-status addendum to `V07_RED_TEAM_2026-08-27.md`. The earlier audit remains preserved as chronological evidence of the attack/remediation sequence and should not be rewritten to erase intermediate failures.

## Current status

All six architectural defects ultimately confirmed by the v0.7 red-team are remediated on `redteam/v07-memory-continuity` with their attacks preserved as regressions:

- RT-01 — saturated WorkingState continuity: remediated.
- RT-02 — lifetime-ledger projection freshness work: remediated.
- RT-03 — deep same-topic endpoint crowdout: remediated for the demonstrated failure mechanism; arbitrary middle-history/as-of addressing is not claimed.
- RT-04 — assistant-memory epistemic self-poisoning: remediated on the configured native Ollama model.
- RT-05 — retrieved-memory prompt injection: remediated on the configured native Ollama model.
- RT-06 — oversized model-facing memory evidence: remediated for the demonstrated unbounded-context defect; exact byte ceilings remain provisional tunables.

The separate current-user exact-output regression discovered during RT-05 is also remediated on the configured native model through application-validated source-extractive output.

## RT-04 final evidence

The original RT-04 probe was initially inconclusive because the assistant-only assertion was not retrieved. After the retrieval precondition was repaired, native testing confirmed a real epistemic defect: a retrieved `INTERACTION_RESPONSE` could be promoted into a user fact despite no supporting `USER_PROMPT`.

Prompt-level source labels were insufficient. The final mechanism therefore uses a fresh current-prompt-only closed response policy to classify admissible historical source roles, then application code physically filters inadmissible events before final synthesis. Unsupported-history fallback selection is a separate current-percept-only decision whose proposed value is accepted only when it is a verbatim substring of the current percept. Both control decisions are durably recorded as causal `SYSTEM_EVENT` provenance.

Final native focused acceptance:

```text
uv run pytest -q -m ollama \
  tests/test_redteam_epistemic_memory_native.py \
  tests/test_redteam_current_fallback_selector_native.py

5 passed in 69.02s
```

See `RT04_REMEDIATION_2026-08-28.md` for the mechanism and constitutional interpretation.

## Exact-output evidence

The exact-output regression is no longer solved by prompt wording alone. For exact source-derived answers, a constrained semantic selector identifies a bounded admitted source and verbatim substring; application code validates substring membership and returns source bytes directly. The latest model-sensitive run before the final fallback-only correction had one failure out of nine tests, and that sole failure was RT-04 fallback spelling. The exact-output regression and RT-05 authority regressions were green.

## Hosted deterministic state

CI #491 on branch head `628e7b309f259b85ea13b1830e005c891019864e` is green:

- **292 passed**
- **20 skipped**
- **0 failed**
- **47.79 seconds**
- static checks passed;
- deterministic constraint calibration passed;
- local-model acceptance gates collect correctly;
- constraint governance: **175 discovered / 175 registered / 0 uncovered / 0 stale / 0 mismatched / 0 invalid**.

PR #19 has no review threads or submitted reviews as of this checkpoint.

## Remaining acceptance gates

The remaining work is acceptance, not remediation of a currently known deterministic defect:

1. Run the complete model-sensitive authority/output regression set on the final code state.
2. Run native restart/cross-process/cross-conversation continuity gates.
3. Run the complete native test suite.
4. Perform a fresh Constitutional Audit against the remediated branch while preserving the first audit unchanged.
5. Resolve any substantive review findings discovered before merge.
6. Only after those gates should PR #19 leave draft and be considered for merge.

## Claim boundary

The red-team supports the narrower architectural proposition that completely stateless LLM/worker invocations can recover and use durable experience across processes and conversations without carrying an ever-growing transcript.

It does not establish that every possible query over arbitrary lifetime history is solved at constant cost, that arbitrary as-of temporal addressing is complete, or that all future epistemic conflict classes are exhausted.
