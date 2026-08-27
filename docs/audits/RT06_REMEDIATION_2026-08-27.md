# RT-06 remediation record — bounded model-facing evidence

**Date:** 2026-08-27  
**Branch:** `redteam/v07-memory-continuity`  
**Parent red-team report:** `docs/audits/V07_RED_TEAM_2026-08-27.md`

## Frozen failure

The native/deterministic red-team baseline demonstrated that a `MemoryPacket` containing one canonical event with approximately 2 MB of text could be serialized into the next LLM prompt in full. The item-count bound therefore did not constitute a real cognitive-context bound.

The defect is specific to the disposable model-facing representation. It does **not** justify truncating, rewriting, or deleting canonical evidence.

## Mechanism changed

RT-06 introduces a fail-closed model-facing evidence budget while preserving canonical memory unchanged.

`ModelEvidenceBudget` governs two distinct limits:

- a per-evidence-item UTF-8 byte ceiling; and
- an aggregate UTF-8 byte ceiling for the disposable evidence supplied to one model invocation.

The production interaction worker now uses `BudgetedEvidenceBoundOllamaClient`, which layers these bounds on top of the RT-05 evidence/instruction transport boundary.

Before inference, the runtime validates:

1. every selected `MemoryEvidence.content` item;
2. the aggregate memory-evidence content;
3. each structured capability-result payload using its deterministic compact JSON representation;
4. memory and capability-result content against one shared aggregate budget; and
5. the final rendered evidence payload including metadata/formatting overhead.

If the selected evidence cannot fit, the invocation raises `ModelEvidenceBudgetExceeded` before the HTTP model call. The current mechanism intentionally fails closed rather than silently clipping canonical content.

## Canonical-memory invariant

The byte budget applies only to the ephemeral view presented to an LLM. It does not impose a canonical event-size limit and does not alter the append-only event ledger.

A future mechanism may expose a bounded chunk, excerpt, or other derived representation of a large canonical event, but such a representation must remain non-authoritative, rebuildable, provenance-linked to the canonical event, and separately tested. RT-06 does not introduce that second mechanism.

## Frozen attack coverage

`tests/test_redteam_memory_item_size_bound.py` retains the original approximately 2 MB single-item attack but now exercises the production model boundary. A fake HTTP client raises if inference is attempted, proving the oversize guard must fire first.

`tests/test_model_evidence_budget.py` additionally freezes:

- per-item overflow;
- aggregate overflow across multiple individually valid items;
- aggregate pressure shared between memory and capability results;
- governed environment override behavior;
- invalid/non-positive configuration; and
- the structural requirement that the per-item ceiling cannot exceed the aggregate ceiling.

## Numeric governance

The **existence of a finite model-facing evidence bound is an architectural requirement** under Constitution Article 5. The exact byte ceilings are not constitutional constants.

The initial defaults are:

- `DEFAULT_MAX_EVIDENCE_ITEM_BYTES = 16 * 1024`;
- `DEFAULT_MAX_EVIDENCE_TOTAL_BYTES = 64 * 1024`.

These values remain provisional environment/model tunables, not verified optima. `LLM-NATIVE-001` explicitly includes `max_model_evidence_item_bytes` and `max_model_evidence_total_bytes`, with native scenario families for oversized single items, aggregate memory pressure, capability-result pressure, multibyte UTF-8 evidence, and largest supported useful context.

The calibration objective is to preserve required-evidence coverage and valid model behavior while guaranteeing finite prompt cost. Boundary-selected values must be expanded/retested before any claim that the exact ceilings are optimal.

The static constraint audit passes. The arithmetic-form defaults above are not automatically discovered by the scanner, so they must not be treated as implicitly verified merely because that gate is green. Their calibration obligation remains explicit in `LLM-NATIVE-001` and this record.

## Acceptance evidence

Native Windows/PostgreSQL/Ollama acceptance on 2026-08-27:

- `tests/test_model_evidence_budget.py`
- `tests/test_redteam_memory_item_size_bound.py`
- `tests/test_evidence_bound_llm.py`

Result: **10 passed in 2.86 seconds**.

Native model-path regression acceptance under the default budget:

- `tests/test_ollama_response_native.py`
- `tests/test_redteam_memory_prompt_injection_native.py`
- `tests/test_redteam_memory_authority_corpus_native.py`

Result: **8 passed in 98.72 seconds**.

Hosted CI run #431 on the same branch passed static checks, deterministic constraint calibration, and all non-native tests except the three intentionally unresolved frozen failures RT-01, RT-02, and RT-03. Suite result: **265 passed, 16 skipped, 3 failed**. The RT-06 and RT-05 regressions were green.

## Current status

**Status: REMEDIATED FOR THE CONFIRMED RT-06 DEFECT; EXACT BYTE CAPS REMAIN PROVISIONAL CALIBRATION TUNABLES.**

The original correctness defect is closed because:

- the 2 MB single-item exploit now fails closed before inference;
- aggregate and capability-result overflow paths are deterministically bounded;
- ordinary native Ollama response behavior passes under the default budget;
- RT-05 authority-boundary acceptance remains green under the budgeted production worker; and
- constraint-governance bookkeeping is clean.

This status does **not** assert that 16 KiB/64 KiB are optimal ceilings. Later `LLM-NATIVE-001` calibration may change those values without reopening RT-06 so long as the finite fail-closed invariant and regression suite remain intact.

## Scope boundaries / remaining risks

This mechanism closes the direct path by which one selected canonical event can expand an LLM prompt without bound. It does **not** claim to solve every large-input problem:

- the current user percept itself is not yet bounded by this evidence budget;
- a large canonical event may still be materialized by retrieval/database/Python code before the model boundary;
- fail-closed behavior means an oversized legitimate event cannot yet be used until a bounded derived representation exists;
- UTF-8 bytes provide a deterministic runtime-independent bound but are not identical to model tokens.

Those are separate measurable mechanisms and should not be silently bundled into RT-06.

## Constitutional fit

The mechanism preserves Articles 3, 4, 5, 23, 24, and 29: canonical evidence remains lossless; only disposable derived/model-facing state is bounded; the one measured context-explosion failure receives one narrow mechanism; numeric defaults remain governed tunables rather than constitutional magic numbers; and oversize evidence fails closed instead of crossing the model boundary unchecked.
