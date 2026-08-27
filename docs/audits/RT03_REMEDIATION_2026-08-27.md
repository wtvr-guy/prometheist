# RT-03 remediation — deep temporal candidate crowdout

**Date:** 2026-08-27  
**Branch:** `redteam/v07-memory-continuity`  
**Frozen attack:** `tests/test_redteam_deep_temporal_history.py`  
**Status:** REMEDIATED; PERMANENT REGRESSION

## Baseline defect

The PostgreSQL candidate router and the pure deterministic kernel both preferred newer canonical events when relevance evidence tied. With more same-topic records than the bounded candidate window, an old equally specific fact could be eliminated before downstream reasoning saw it at all. The frozen attack stored one original Project Falcon launch-code event, appended 814 newer same-topic decoys, and asked for the code originally given. The original event fell outside the 750-candidate newest-first window.

This was not a canonical-memory loss. It was a bounded candidate-composition failure: chronology was discarded before a stateless consumer could interpret temporal intent.

## Remediation

The remediation preserves bounded temporal alternatives without parsing English temporal words.

### PostgreSQL candidate composition

`CANDIDATE_ROUTER_VERSION` advanced from `specificity-routes-v3` to `specificity-routes-v4`.

When content cues exist and the candidate window has capacity beyond the requested output packet, the router reserves at most one output packet's worth of the existing content budget for **historical anchors**. Those anchors use the same lexical/entity specificity ordering as the ordinary content route but break otherwise equivalent matches by ascending canonical `global_seq`. The existing newest-first content and recency routes remain present. The total `candidate_limit` is unchanged.

This means deep history receives bounded representation from both chronology endpoints instead of allowing the newest endpoint to monopolize the full content window.

### Pure deterministic ranking

`memory_kernel.POLICY_VERSION` advanced from `deterministic-cues-v1` to `deterministic-cues-v2`.

For candidates with exactly equal total relevance scores, the kernel now orders the tied group as newest, oldest, next-newest, next-oldest, and so on. The first result therefore preserves the longstanding newest preference when relevance does not otherwise distinguish candidates, while a multi-item packet also preserves old temporal alternatives. Explicit temporal scoring such as `reference_time` remains authoritative because unequal scores are not reordered across score groups.

The kernel does **not** recognize words such as `originally`, `first`, `latest`, or other phrase-specific temporal vocabulary. It only avoids throwing away chronological alternatives when the evidence model itself cannot distinguish them.

## Bounds

No production breadth limit was increased:

- attention candidate limit remains 750;
- output packet limits remain unchanged;
- historical-anchor work is carved out of the existing content budget;
- SQL route fetches remain capped by `candidate_limit`.

This resolves the correctness cliff by changing bounded composition rather than moving the cliff outward.

## Acceptance

Hosted CI #455 on commit `caf556176caab23f52190ad2dfc8872adc518914`:

- **273 passed**
- **16 skipped**
- **0 failed**
- **44.26 seconds**

The unchanged frozen >750 same-topic RT-03 attack passed. A new pure-kernel regression also requires equal-relevance evidence to preserve both newest and oldest chronology endpoints. Static checks, deterministic constraint calibration, and local-model acceptance-gate collection passed. Constraint governance remained **175 discovered / 175 registered / 0 uncovered / 0 stale / 0 mismatched / 0 invalid**.

## Constitutional result

RT-03 no longer demonstrates an Article 24 correctness boundary on the remediation branch. The fixed candidate limit remains provisional under the project's calibration discipline, but correctness no longer depends on merely increasing that limit to hide deep same-topic history.

The original failure remains preserved in the v0.7 red-team report and frozen attack as historical negative evidence.
