# Prometheist codebase audit remediation — 2026-08-31

**Original audit:** [`CODEBASE_AUDIT_2026-08-31.md`](CODEBASE_AUDIT_2026-08-31.md)  
**Remediation base revision:** `9f37b259af57f700bc5f915ac20cf3e34221890d` (`main` when remediation began)  
**Remediation branch:** `audit-hardening-2026-08-31`  
**Pull request:** #23, `Harden audit findings: artifacts, responder personality, temperature governance`  
**Status:** implementation complete; deterministic CI verification in progress at the time this record was created; native Windows/Ollama acceptance remains a separate required gate.

This document preserves the original audit as historical evidence while correcting its revision provenance, refining two interpretations, and recording the remediation applied to the live codebase. The original audit is not silently rewritten because doing so would erase the audit trail it was intended to create.

## 1. Provenance correction

The original audit header states that it audited revision `65f7c65`. That cannot be literally true for all findings in the final report.

Commit `2c6d55f` (`Separate expressive and control temperatures`) has `65f7c65` as its parent and introduced:

- `_DEFAULT_RESPONSE_TEMPERATURE = 0.65`;
- `_MIN_RESPONSE_TEMPERATURE = 0.0`;
- `_MAX_RESPONSE_TEMPERATURE = 2.0`;
- response-kind temperature routing.

Original Findings 3 and 4 discuss those exact post-`65f7c65` changes. Therefore the report was assembled while the audited tree moved, or its revision header was not refreshed after later changes were incorporated.

The findings themselves are still useful, but the original report must not be treated as a reproducible single-SHA audit. Future audits must freeze and record one exact revision before empirical verification begins, and all commands/results in the report must refer to that revision unless a later revision is explicitly identified.

## 2. Revised interpretation of the major findings

### Finding 1 / Finding 2 — acceptance failures and Windows artifact paths

**Original assessment:** CRITICAL.  
**Remediation assessment:** confirmed root cause; severity retained for the portability/runtime failure.

Five of the eight reported test failures were not five independent JIT-memory defects. They shared one deterministic infrastructure root cause: interaction artifact filenames embedded full stage names, claim UUIDs, invocation indices, and semantic call kinds, producing paths that could exceed ordinary Windows path limits.

Remediation changes interaction artifact filenames to a bounded deterministic artifact UUID while retaining the complete semantic `artifact_key` inside the immutable JSON envelope. The semantic key remains the idempotency identity, so shortening the filesystem presentation does not weaken provenance, retry identity, or hash-chain semantics.

A regression test now exercises a realistic long v2 LLM invocation key under a nested artifact root and verifies that the basename remains bounded independently of the semantic key.

### Finding 3 — constraint governance gate

**Original assessment:** HIGH.  
**Remediation assessment:** confirmed governance regression.

The three response-temperature constants are now classified under `LLM-NATIVE-001` as `ENVIRONMENT_CALIBRATED` values. The registry rationale explicitly includes response-temperature policy because the appropriate value depends on supported local-model behavior and must be validated natively rather than treated as a constitutional constant.

### Finding 4 — response temperature

**Original assessment:** HIGH, framed partly as a possible Article 9 determinism violation.  
**Remediation assessment:** the undocumented/test-breaking change was real, but non-zero user-facing response temperature is intentional and is not itself an Article 9 control-plane violation.

The architecture now explicitly separates:

- deterministic control/decision LLM kinds at temperature `0.0`; and
- user-facing response kinds at the response-only configured temperature, currently defaulting to `0.65`.

The final responder has no authority to decide whether to respond, retrieve memory, execute side effects, schedule work, change permissions, or mutate durable control state. A non-zero temperature therefore varies natural-language expression, not system authority.

Tests now verify both sides of the boundary: response generation receives the expressive default while a control kind remains at `0.0` even when the configured response temperature is raised.

The effective temperature is also persisted in every exact v2 LLM invocation artifact so it remains inspectable causal input rather than hidden runtime state.

### Finding 5 — final-responder prompt/evidence authority

**Original assessment:** MEDIUM prompt/test drift.  
**Remediation assessment:** upgraded in importance: the failing test exposed a real contract-wiring fragility, not merely stale wording.

The strong interactive personality prompt contains essential identity and evidence-authority rules, including the rule that a historical `USER_PROMPT` is direct evidence of what the user said and that prior model-authored responses cannot negate conflicting user-authored evidence.

Previously, the live subprocess entry point installed that prompt through an environment default before constructing the worker. Direct construction of `UserPromptLLM` did not itself guarantee the contract, which is why an integration-style test could observe the weaker fallback prompt.

Remediation makes the contract intrinsic to `UserPromptLLM` construction. The mandatory Prometheist identity/evidence prompt is always installed. A deployment-provided `PROMETHEIST_PERSONALITY_PROMPT` is appended as a `[User-configured personality]` layer instead of replacing the mandatory accuracy/evidence rules.

This preserves the intended goal: personality steers tone and expression, while evidence authority and non-hallucination rules remain mandatory.

### Findings 6–9 — maintenance and robustness cleanup

The duplicate unused `execute_claimed_percept_step` implementation was removed, leaving the artifact-aware worker path as the single stage-execution implementation.

`PERSIST_RESULT` is now an explicit `_execute_stage` branch followed by an assertion for any unhandled stage instead of relying on implicit fallthrough.

Artifact recovery now catches a `RuntimeError` only when its message is the exact current `stage incomplete` condition; unexpected runtime failures are re-raised rather than silently treated as resumable incompleteness.

The chat-startup reset now uses `psycopg.sql.Identifier` for table identifiers rather than an f-string SQL statement with a suppressed security lint warning.

## 3. Final responder contract adopted by this remediation

The final responder is deliberately personality-conditioned. The architecture does **not** seek deterministic prose.

It does seek a strict separation between expressive freedom and epistemic/control freedom:

1. Prometheist's core identity and evidence-authority system prompt is mandatory.
2. Optional deployment/user personality instructions are additive and cannot replace the core rules.
3. Response-only temperature may introduce phrasing variation.
4. Control/decision kinds remain deterministic.
5. The structured response envelope, bounded generation, thinking suppression, validation, evidence provenance, verbatim-literal preservation, and unresolved-memory handling remain intact.
6. Personality or temperature never authorizes invention of remembered facts, contradiction of authoritative evidence, or reinterpretation of deterministic control decisions.

The detailed contract is now documented in [`../architecture/FINAL_RESPONDER.md`](../architecture/FINAL_RESPONDER.md).

## 4. Exact invocation provenance extension

Because response temperature now intentionally affects expression, an invocation artifact that omitted temperature would no longer represent the exact model-call contract.

`LLM_INVOCATION` artifacts therefore now include the effective generation temperature alongside model, backend, exact system prompt, exact user/context prompt, schema, token cap, output, and error information.

The independent artifact-journal documentation has been updated accordingly.

## 5. Verification state

On the remediation branch, GitHub Actions has already independently confirmed the following gates after the code changes:

- `ruff check .` — passed after removing one stale import exposed by the dead-code cleanup;
- `scripts/audit_constraints.py --fail-unregistered` — passed;
- deterministic constraint calibration — passed;
- collection of the local-model acceptance gates — passed.

The complete Ubuntu/PostgreSQL `pytest -q` suite was still executing when this record was first written. Its final result must be recorded from the final branch SHA before the PR is considered deterministic-CI clean.

GitHub CI does **not** substitute for native acceptance. The workflow collects the Ollama-marked restart/cross-process acceptance tests but does not execute them against the project's real Windows development host, native PostgreSQL service, and native Ollama runtime.

Before merge/closure, the native machine should run at minimum:

```powershell
uv run ruff check .
uv run python scripts/audit_constraints.py --fail-unregistered
uv run pytest -q
```

and the real-Ollama acceptance subset should be allowed to execute rather than skipped. In particular, the cross-process restart/cross-conversation/continuity tests that previously failed through the Windows path bug are the critical native regression evidence.

## 6. Closure criteria

This remediation is complete only when all of the following are true on one frozen final SHA:

1. deterministic CI is green;
2. the constraint registry reports no uncovered/stale/mismatched policy numbers;
3. the full deterministic test suite is green;
4. native Windows/PostgreSQL/Ollama acceptance passes, including the previously path-failing cross-process memory cases;
5. the exact final SHA and native results are appended to this record or another immutable dated closure record;
6. PR #23 is merged only after those gates are satisfied or an explicit documented exception is made.

The purpose of this remediation is not merely to make the eight reported failures disappear. It is to restore the stronger architectural contract they exposed: portable independent durability, explicit empirical governance, deterministic control, and an expressive final responder whose personality cannot override accuracy or evidence authority.
