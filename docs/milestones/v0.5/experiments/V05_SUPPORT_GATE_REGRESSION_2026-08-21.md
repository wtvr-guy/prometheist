# Memory Kernel v0.5 — Support-Gate Regression (2026-08-21)

This document freezes the failed pre-benchmark regression run for the first support-aware evidence-admission implementation. No scale benchmark was run after these failures.

## Test result

- pytest: **64 passed / 3 failed**
- Failed suites:
  - `tests/test_associative_benchmark.py::test_associative_recall_improves_jordan_control_baseline`
  - `tests/test_derived_associative_benchmark.py::test_derived_associations_replace_curated_jordan_edges`
  - `tests/test_scale_benchmark.py::test_scale_runner_reproduces_base_results_after_uuid_remap[jordan_vale_v1.json-18]`

All three failures were the same Jordan regression. Associative recall fell from the verified 18/18 baseline to 15/18. The newly rejected questions were:

1. `q04` — prior employer before Northstar Labs; old Acme evidence was excluded.
2. `q11` — who claimed Jordan hated mushrooms; the Sarah Kim evidence was excluded.
3. `q15` — prior city before Spokane; the Portland/Spokane move evidence was excluded.

## Diagnosis

The first support gate treated every substantive query token as a lexical support requirement even when some of those tokens were already supplied as explicit entity cues. This double-counted entity information and made historical evidence appear artificially weak.

It also required direct lexical coverage even when the candidate had an explicit entity hit. That is too strict for a retrieval layer because relationship wording may be paraphrastic (`claimed` vs `said`) while the entity cue still correctly anchors the evidence.

Examples:

- `Where did Jordan work before Northstar Labs?` supplied `Northstar Labs` as an explicit entity. The prior Acme event should be judged on the remaining lexical content (`work`), not penalized again for lacking `Northstar Labs`.
- `Who claimed Jordan hated mushrooms?` supplied `mushrooms` as an explicit entity. The Sarah Kim event is valid entity-anchored evidence even though the relationship is phrased as `said` rather than `claimed`.
- `Where did Jordan move from before living in Spokane?` supplied `Spokane` as an explicit entity. The move event should remain admissible even when the lightweight stemmer does not normalize every paraphrastic inflection ideally.

## Correction under test

The support-aware admission mechanism remains the same experiment, but its implementation was corrected before any scale benchmark:

1. explicit entity tokens are removed from the direct lexical-support denominator;
2. an actual entity hit is treated as an independent first-class evidence cue, alongside association and temporal support;
3. broad lexical activation remains available for association seeding;
4. the unsupported Morgan vehicle-insurance case still has no non-principal entity cue, so a generic `vehicle` match alone should remain inadmissible.

Dedicated unit tests now cover:

- entity support surviving predicate paraphrase;
- explicit entity terms not diluting historical lexical support;
- generic topical `vehicle` overlap still abstaining.

No benchmark result should be attributed to this corrected implementation until the full regression suite passes locally.
