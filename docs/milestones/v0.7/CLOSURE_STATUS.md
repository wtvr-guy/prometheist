# v0.7 Closure Status

**Status:** closed 2026-09-12
**Closure baseline:** `39a3223c38f1b1f8fae7f9e667c6cd7460774ffe` (`v0.7-closure`)
**Successor:** v0.8 is the active development milestone.

The maintainer closed v0.7 after local acceptance. The table below preserves the
previous gate evidence and branch disposition as historical context; it is not an
active v0.8 acceptance checklist.

| Gate | Status | Evidence |
| --- | --- | --- |
| PR #23 audit-hardening base incorporated | complete remotely | draft [PR #24](https://github.com/wtvr-guy/prometheist/pull/24) targets PR #23's `audit-hardening-2026-08-31` branch |
| PR #19/#22 selective salvage | revised after native evidence | PR #19's source-authority/evidence-isolation mechanism is now selectively ported into v2; PR #22 remains evidence-only |
| Superseded runtime/policy/capabilities removed | complete remotely | static source scan, exact Git-tree publication, and hosted test collection |
| Runtime artifacts untracked/ignored | complete remotely | `.gitignore` plus tracked deletions in PR #24 |
| Current docs rebaselined | complete on branch | updated for both 2026-09-03 native runs and the corrected artifact-first/human-review contract |
| Ruff | complete at closure | maintainer-confirmed local v0.7 acceptance |
| Constraint registry audit | complete at closure | subsequent integrated validation found 215 discovered / 215 registered / zero gaps |
| Pytest collection | complete at closure | maintainer-confirmed local v0.7 acceptance |
| Full PostgreSQL pytest | complete at closure | maintainer-confirmed local v0.7 acceptance |
| Native Windows/PostgreSQL/Ollama structural gate | historical evidence retained | the 2026-09-03 replacement-gate discussion remains below; it is not an active v0.8 checklist |
| Human native response review | historical evidence retained | no longer an active v0.8 checklist |
| Final constitutional/codebase audit | accepted at closure | maintainer closed the frozen v0.7 baseline on 2026-09-12 |
| PR #19–#22 disposition | complete | each PR has a disposition note and was closed without merge on 2026-09-03 |
| Remote branch inventory | complete | all 31 obsolete remote branches were deleted after `main` received the integrated baseline |
| PR #23 merge | complete | integrated into `main` through the preserved v0.7 history |
| Closure tag | complete | `v0.7-closure` points to `39a3223c38f1b1f8fae7f9e667c6cd7460774ffe`; historical `v0.7` was not moved |
| v0.8 development integration | complete | v0.8 is merged into `main` and is the active development milestone |

The failed run is summarized in
[`../../audits/V07_NATIVE_ACCEPTANCE_2026-09-03.md`](../../audits/V07_NATIVE_ACCEPTANCE_2026-09-03.md).
The first run exposed placeholder mutation, one unnecessary work selection,
continuity recall loss, and historical authority/prompt-injection failures. The
exact-SHA follow-up reduced that set to three and demonstrated that the remaining
response tests still imposed an obsolete exact-prose oracle even though their
response artifacts contained the required evidence. The replacement script requires
an expected full SHA and a clean named branch, prints structural artifact receipts,
and ends by requiring explicit human review of the natural answers.

PR #24's former next checks remain attached to that historical closure candidate.
They do not alter the closed v0.7 baseline or the active v0.8 milestone.

The [v0.8 integration record](../../audits/V08_CLOSURE_INTEGRATION_2026-09-12.md)
tracks the later combined branch. Historical numbers above must not be presented
as test results for that branch.
