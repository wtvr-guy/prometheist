# Prometheist Epistemic Retrieval Scoping & Continuity Remediation — 2026-09-11

**Date:** 2026-09-11  
**Branch:** `closure/v0.7-v2-consolidation`  
**Status:** implementation and validation complete  
**Scope:** memory aperture retrieval, response policy scoping, assistant-output exclusion by default, and multi-turn continuity evidence.

---

## 1. Executive Summary

During full local acceptance testing on Windows/PostgreSQL/Ollama for the v0.7 closure candidate, two test failures were analyzed:

1. **Continuity Evidence Receipt (`test_stateless_four_turn_continuity_survives_sessions_and_distractors`):**
   Turn 4 asked the system to *"Name that ruled-out approach and its underlying technical reason"*, referring back to Turn 3 where the assistant ruled out Docker. The memory subsystem did not classify the prompt as requiring conversation dialogue history, so the Turn 3 assistant response was not admitted into the final response realization's evidence receipt.

2. **Assistant-Only Memory Exposure (`test_assistant_only_claim_does_not_become_user_fact_after_restart`):**
   A red-team test seeded an assistant response claiming a user fact without any supporting `USER_PROMPT`. Previously, `DEFAULT_EVIDENCE_TYPES` included `INTERACTION_RESPONSE`, exposing assistant-authored statements to memory retrieval and relying on downstream model-level prompt instructions (`MODEL_OUTPUT_ONLY is never a substitute for DIRECT_USER_TESTIMONY`) to prevent the model from treating it as a user fact.

Both issues were resolved by implementing **two-stage retrieval scoping with default exclusion of model outputs**, accompanied by deterministic detection of explicit prior-assistant references and an expanded worker contract test suite.

---

## 2. Changes Implemented and Architectural Rationale

### 2.1 Default Exclusion of Model Outputs from Memory Retrieval

**Problem:** Exposing fallible assistant outputs (`INTERACTION_RESPONSE`, `AGENT_RESPONSE`, `AGENT_RESULT`) to general memory retrieval consumes scarce evidence budget, risks confusing downstream stateless workers, and forces small models to perform epistemic trust classification on every turn.

**Solution:**
- Updated `DEFAULT_EVIDENCE_TYPES` in `src/jit_agent/jit_memory.py` to include only primary evidence: `USER_PROMPT`, `TOOL_RESULT`, and `SYSTEM_EVENT`.
- Model outputs remain durably recorded in the canonical PostgreSQL event store and artifact journal, but they are physically excluded from standard attention-aperture activation and Adaptive Recall unless the current request explicitly requires them.

### 2.2 Response Policy Scoping for Memory Activation

**Problem:** Memory retrieval occurred before or independently of the current-percept response policy, preventing retrieval from knowing whether the current request is for user facts or dialogue history.

**Solution:**
- `open_attention_aperture` and `_adaptive_recall` now accept an explicit `source_types` parameter.
- `src/jit_agent/response_policy.py` defines `source_types_for_scope(scope: HistoricalEvidenceScope) -> list[EventType]`, mapping each evidence scope to its allowed canonical event roles:
  - `USER_AUTHORED` → `[USER_PROMPT]`
  - `MODEL_OUTPUT` → `[INTERACTION_RESPONSE, AGENT_RESPONSE, AGENT_RESULT]`
  - `MIXED_CONVERSATION` → `[USER_PROMPT, INTERACTION_RESPONSE, AGENT_RESPONSE, AGENT_RESULT]`
  - `GENERAL_OR_CURRENT` → `[USER_PROMPT, TOOL_RESULT, SYSTEM_EVENT]`
- In `src/jit_agent/percept_response_runtime.py`, the pre-cognitive stage now evaluates the current-only response policy before opening the attention aperture and configures both the aperture and subsequent Adaptive Recall with the appropriate `source_types`.

### 2.3 Deterministic Prior-Assistant Reference Detection

**Problem:** Natural language prompts referring to recent assistant output (such as *"What did you tell me earlier?"*, *"Which approach did you just rule out?"*, or *"Name that ruled-out approach"*) should reliably retrieve dialogue history (`MIXED_CONVERSATION`) without depending entirely on model classification.

**Solution:**
- Added `explicit_prior_assistant_reference(prompt: str) -> bool` in `src/jit_agent/response_policy.py` matching unambiguous references to prior assistant actions, rulings, and responses.
- When detected, `_response_policy` immediately and deterministically returns `HistoricalEvidenceScope.MIXED_CONVERSATION`, ensuring dialogue history is retrieved and preserved in the final response evidence receipt.

### 2.4 Test Suite Modernization and Expanded Policy Verification

**Problem:** The previous prompt injection test (`test_redteam_memory_prompt_injection_native.py`) asserted that an injected assistant response was present in the retrieved memory packet, conflicting with the desired default exclusion. Furthermore, the response policy worker's scope decisions lacked unit test coverage across all possible input scenarios.

**Solution:**
- Removed deprecated `tests/test_redteam_memory_prompt_injection_native.py`.
- Updated `tests/test_redteam_epistemic_memory_setup.py` and `tests/test_redteam_epistemic_memory_native.py` to assert that seeded assistant claims are excluded from ordinary memory packets.
- Expanded `tests/test_user_prompt_worker_contract.py` with comprehensive tests verifying:
  - Mapping of every `HistoricalEvidenceScope` to exact retrieval event types.
  - Policy worker classification across `USER_AUTHORED`, `MODEL_OUTPUT`, `MIXED_CONVERSATION`, and `GENERAL_OR_CURRENT` prompts without access to memory.
  - Deterministic fast-path selection for explicit prior-assistant references.
- Updated `.github/workflows/tests.yml` to remove the deleted test from CI collection.

---

## 3. Verification & Results

| Test Group | Result |
| --- | --- |
| Worker & Response Policy Contract Tests (`tests/test_user_prompt_worker_contract.py`, `tests/test_response_policy.py`) | **26 passed** |
| Epistemic Setup & Hardening Tests (`tests/test_redteam_epistemic_memory_setup.py`, `tests/test_interactive_evidence_hardening.py`) | **Passed** |
| Native 4-Turn Continuity Acceptance (`tests/test_acceptance_conversation_continuity.py`) | **Passed** |
| Native Epistemic Memory Red-Team Acceptance (`tests/test_redteam_epistemic_memory_native.py`) | **Passed** |
| Ruff Linting (`ruff check .`) | **All checks passed** |
| Python / Pylance Syntax Validation | **No errors found** |
