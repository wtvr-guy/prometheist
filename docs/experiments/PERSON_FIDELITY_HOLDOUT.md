# PERSON-FIDELITY-002-HOLDOUT — Prospectively Frozen Holdout Person

**Status:** frozen before any person-fidelity mechanism was selected. No native
run of this fixture existed when it was sealed, and no measurement from it was
used to choose a candidate mechanism.

**Fixture:** [`../../benchmarks/person_fidelity_holdout_v1.json`](../../benchmarks/person_fidelity_holdout_v1.json)

**Digest:** `b54ec140641ac3bbe5ff25ff3c475a48124fc893dda5f1dc5255b17d6b8ca2b2`

**Subject:** Wren Adisa, wholly fictional, a wetland hydrologist. She shares no
life event, probe, prompt, vocabulary domain, or seeded event identifier with
Mara Ellison.

## Why this fixture exists

[`PERSON_FIDELITY_BASELINE.md`](PERSON_FIDELITY_BASELINE.md) requires that a
candidate person-fidelity mechanism "reproduce the improvement on a separate,
prospectively frozen holdout person." The
[fresh-run review](../audits/PERSON_FIDELITY_FRESH_REVIEW_2026-09-17.md) localized
three candidate failure mechanisms on the public baseline and directed that
separate held-out cases be frozen *before* an improvement is selected.

Measuring a change only on the ten probes that motivated it cannot distinguish a
real mechanism from fitting those ten probes. This fixture is the control for
that specific confusion.

## What it holds constant

The holdout deliberately mirrors the baseline's *structure* so the same failure
families are exercised, while sharing none of its *content*:

| Structure | Baseline | Holdout |
| --- | --- | --- |
| Life events | 19 | 19 |
| Probes | 10 over 9 dimensions | 10 over 9 dimensions |
| Observational `SYSTEM_EVENT` contradicting a self-report | `pf-e009` | `hf-e009` |
| Observational `SYSTEM_EVENT` behind a belief change | `pf-e006` | `hf-e006` |
| Untrusted identity import as `SYSTEM_EVENT` | `pf-e016` | `hf-e016` |
| Archived voice sample as `SYSTEM_EVENT` | `pf-e015` | `hf-e015` |
| Long multi-constraint novel-decision prompt | `pf-q006` | `hf-q006` |
| Open-world unknown probe | `pf-q010` | `hf-q010` |

Retaining these shapes matters because the review attributed failures to
source-policy exclusion of `SYSTEM_EVENT` records, long-prompt dilution, and
common-word admission. A holdout without those shapes could not detect whether a
repair generalizes.

## What it deliberately varies

Subject domain, vocabulary, sentence rhythm, name inventory, prompt lengths, and
the specific contradiction being probed all differ. The self-report probe tests
competitiveness rather than spontaneity; the preference probe tests public
recognition rather than surprises; the sentimental-object probe involves a
kerosene lantern rather than an espresso maker. A mechanism tuned to baseline
tokens should not transfer.

## Rules

1. This fixture is not a second baseline. It does not replace, average with, or
   override `PERSON-FIDELITY-001`.
2. It must not be edited to make a candidate mechanism succeed. A change requires
   a new digest and a new benchmark version, and invalidates its holdout role for
   any mechanism already measured against it.
3. Its human verdicts follow the same separation rule: automation judges evidence
   delivery and artifact integrity only.
4. Structural results on it are reported per probe, never as a pass threshold.

## Run it

```powershell
.\scripts\run_person_fidelity_baseline.ps1 -Holdout -ValidateOnly
.\scripts\run_person_fidelity_baseline.ps1 -Holdout
```

Results are written to `benchmarks/results/PERSON-FIDELITY-002-HOLDOUT_*.json`
and raw artifacts to `benchmarks/generated/person_fidelity_holdout/<UTC-run-id>/`,
keeping both fixtures' evidence bytes in separate trees.
