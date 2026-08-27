# RT-01 remediation — saturated WorkingState continuity

**Date:** 2026-08-27  
**Branch:** `redteam/v07-memory-continuity`  
**Frozen attack:** `tests/test_redteam_working_state_saturation.py`  
**Status:** REMEDIATED; PERMANENT REGRESSION

## Baseline defect

The attention aperture could successfully retrieve evidence newly made relevant by the current percept while a saturated 12-item WorkingState still discarded that evidence. The aperture packet exposed prior active WorkingState first and baseline historical recall second. `open_attention_aperture()` then promoted the current prompt followed by the packet order. With 12 stale active items already present, bounded truncation preserved the current prompt plus stale focus and dropped the newly recalled evidence.

Canonical memory was never lost. The failure was an attention-state promotion policy defect: a fresh stateless worker on the following turn could lose the evidence that had just mattered.

## Remediation

`open_attention_aperture()` now applies a deterministic activation-only priority order:

1. current percept;
2. packet evidence not already present in prior WorkingState, preserving JIT Memory's deterministic packet order;
3. packet evidence already active;
4. remaining prior active event IDs.

`activate_working_state()` still performs the existing canonical-ID deduplication and 12-item truncation. No bound was increased. The LLM-visible `MemoryPacket` is unchanged; only the disposable/durable activation order used to write WorkingState changed.

This makes stale focus evictable by evidence newly recalled because of the current percept while preserving boundedness, canonical provenance, stateless rehydration, and deterministic retry semantics.

`ATTENTION_APERTURE_VERSION` advanced from `v0.7-attention-aperture-v3` to `v0.7-attention-aperture-v4` because the persisted requesting-component policy semantics changed.

## Acceptance

Hosted CI #451 on commit `ab438b9667ba169f22828d8307d926fd031f5597`:

- **271 passed**
- **16 skipped**
- **1 failed**
- **42.80 seconds**

The only failure is the still-open RT-03 deep temporal crowdout attack. The unchanged RT-01 frozen attack is green. Static checks, deterministic constraint calibration, and local-model acceptance-gate collection also passed; constraint governance remained **175 discovered / 175 registered / 0 uncovered / 0 stale / 0 mismatched / 0 invalid**.

## Constitutional result

RT-01 no longer provides negative evidence against Articles 1 and 7 on the remediation branch. WorkingState remains bounded canonical activation rather than a hidden transcript or parsed semantic cache, but current attention can now deterministically displace stale focus.

The original failure remains preserved in `docs/audits/V07_RED_TEAM_2026-08-27.md` as historical evidence and in the frozen regression test as a permanent acceptance condition.
