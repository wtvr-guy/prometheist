# v0.7 Closure Status

**Status:** not closed  
**Integration note added:** 2026-09-12 (the gate evidence below is historical)

| Gate | Status | Evidence |
| --- | --- | --- |
| PR #23 audit-hardening base incorporated | complete remotely | draft [PR #24](https://github.com/wtvr-guy/prometheist/pull/24) targets PR #23's `audit-hardening-2026-08-31` branch |
| PR #19/#22 selective salvage | revised after native evidence | PR #19's source-authority/evidence-isolation mechanism is now selectively ported into v2; PR #22 remains evidence-only |
| Superseded runtime/policy/capabilities removed | complete remotely | static source scan, exact Git-tree publication, and hosted test collection |
| Runtime artifacts untracked/ignored | complete remotely | `.gitignore` plus tracked deletions in PR #24 |
| Current docs rebaselined | complete on branch | updated for both 2026-09-03 native runs and the corrected artifact-first/human-review contract |
| Ruff | passing on preceding candidate | hosted workflow [run #717](https://github.com/wtvr-guy/prometheist/actions/runs/33810504804) on `6e371a33350260b6e458ae4c16e4fd27ffac1dad`; replacement run pending |
| Constraint registry audit | passing on remediation | 166 discovered / 166 registered / zero uncovered, stale, mismatched, or invalid |
| Pytest collection | passing locally | 295 tests collected; 14 native scenarios selected; replacement hosted execution pending |
| Full PostgreSQL pytest | passing on preceding candidate | run #717: 280 passed, 14 environment-marked native tests skipped in 42.60s; replacement execution pending |
| Native Windows/PostgreSQL/Ollama structural gate | **pending on replacement** | exact SHA `6e371a3...` ran all 14: 11 passed, 3 failed in 504.40s; exact-prose response oracle has now been replaced by invocation-artifact evidence checks |
| Human native response review | **pending** | judge every printed natural response only after the artifact-first structural gate passes on the exact replacement SHA |
| Final constitutional/codebase audit | pending | perform only after deterministic and native gates are green |
| PR #19–#22 disposition | complete | each PR has a disposition note and was closed without merge on 2026-09-03 |
| Remote branch inventory | complete; deletion blocked | 28 refs classified in `docs/audits/V07_REMOTE_BRANCH_INVENTORY_2026-09-03.md`; available connector has no ref-delete operation |
| PR #23 merge | blocked | requires all preceding hard gates |
| Closure tag | blocked | create a new tag after merge; never move `v0.7` |
| v0.8 development integration | explicitly authorized 2026-09-12 | closure implementation merged into the existing perception branch; this does not close v0.7 or freeze a hypothesis |

The failed run is summarized in
[`../../audits/V07_NATIVE_ACCEPTANCE_2026-09-03.md`](../../audits/V07_NATIVE_ACCEPTANCE_2026-09-03.md).
The first run exposed placeholder mutation, one unnecessary work selection,
continuity recall loss, and historical authority/prompt-injection failures. The
exact-SHA follow-up reduced that set to three and demonstrated that the remaining
response tests still imposed an obsolete exact-prose oracle even though their
response artifacts contained the required evidence. The replacement script requires
an expected full SHA and a clean named branch, prints structural artifact receipts,
and ends by requiring explicit human review of the natural answers.

PR #24's next checks are authoritative only for the exact remediation head. A
skipped native test, a local collection pass, a previous green workflow, or a
documentation claim does not change the milestone status.

The [v0.8 integration record](../../audits/V08_CLOSURE_INTEGRATION_2026-09-12.md)
tracks the later combined branch. Historical numbers above must not be presented
as test results for that branch.
