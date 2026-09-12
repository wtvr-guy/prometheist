# v0.7 Remote Branch Inventory

**Date:** 2026-09-03
**Repository:** `wtvr-guy/prometheist`  
**Comparison base:** `main` at `9f37b259af57f700bc5f915ac20cf3e34221890d`

## Outcome

**Closure update (2026-09-12):** the listed obsolete branches, the later v0.8
integration branch, and the superseded PR #26/#27 branches were deleted after the
integrated v0.8 baseline was published to `main`. `main` is now the sole remote
branch. The immutable `v0.7-closure` tag preserves the final v0.7 baseline, and
the historical `v0.7` tag was not moved.

At the time of this inventory, the remote contained 28 branches. Three remained
active and had to be retained until integration:

- `main`;
- `audit-hardening-2026-08-31`, the required PR #23 integration branch;
- `closure/v0.7-v2-consolidation`, the draft PR #24 closure candidate.

The other 25 refs are eligible for deletion. PRs #19–#22 have disposition notes and
are closed without merge. Required PR #19/#22 evidence is preserved in the closure
candidate, and the remaining branches are merged history, obsolete architecture, or
abandoned experiment/temp refs.

No remote branch was moved and no tag was changed during this inventory. In
particular, the historical `v0.7` tag remains immutable.

## Fully behind `main`

GitHub reported zero commits ahead for these 13 branches:

| Branch | Ahead | Behind |
| --- | ---: | ---: |
| `audit/v0.5-prebenchmark-fixes` | 0 | 489 |
| `feature/memory-kernel-v0.4` | 0 | 492 |
| `fix/postgres-authoritative-storage` | 0 | 511 |
| `memory-kernel-v0.5-robustness` | 0 | 444 |
| `memory-kernel-v0.6-mas` | 0 | 431 |
| `post-v06-audit-cleanup` | 0 | 407 |
| `primary-agent-spec-refresh` | 0 | 440 |
| `repo-hygiene-docs` | 0 | 442 |
| `v0.6-closure-docs` | 0 | 417 |
| `v0.6-memory-cue-fallback` | 0 | 422 |
| `v0.6-primary-cue-regression` | 0 | 431 |
| `v0.7-jit-attention` | 0 | 57 |
| `v05-closure-audit` | 0 | 435 |

## Closed PR source branches

These refs are divergent by commit identity, but their v0.7 disposition is complete:

| Branch | Ahead | Behind | Evidence decision |
| --- | ---: | ---: | --- |
| `constitutional-audit-remediation` | 1 | 55 | PR #20 closed; implementation rejected/deferred |
| `experiment/adaptive-memory-attention` | 64 | 55 | PR #22 records preserved; production branch rejected |
| `feature/pre-cognitive-transient-workers` | 206 | 55 | PR #21 architecture superseded by v2 |
| `redteam/v07-memory-continuity` | 91 | 55 | PR #19 tests/hardening selectively ported; history preserved |

## Divergent historical and temporary refs

These branches have unique commit identities but no remaining authority over the
closure candidate. Their applicable results are already represented by later
history, the authoritative v2 branch, or retained benchmark/document evidence.

| Branch | Ahead | Behind | Classification |
| --- | ---: | ---: | --- |
| `artifact-store-v0.1` | 1 | 513 | superseded artifact prototype |
| `memory-kernel-v0.3-associative` | 17 | 514 | superseded historical milestone branch |
| `reranker-tokenid-fix-temp` | 44 | 406 | temporary semantic-retrieval experiment |
| `tmp-unused` | 44 | 406 | duplicate temporary ref |
| `v0.6-capability-registry` | 67 | 406 | superseded Primary Agent/capability architecture |
| `v0.6-semantic-benchmark-work` | 48 | 406 | historical semantic benchmark work |
| `v0.6-semantic-instruction-benchmark-temp` | 47 | 406 | temporary experiment ref |
| `v0.6-semantic-instruction-benchmark-temp2` | 47 | 406 | duplicate temporary experiment ref |

## Resolved deletion blocker

The available connector initially exposed no branch/ref deletion operation, so this
inventory truthfully recorded cleanup as incomplete. After the closure baseline and
v0.8 integration were safely published to `main`, authenticated Git access deleted
the exact listed references. The closure and active-development branch cleanup is
complete.

Do not move or replace either `v0.7` or `v0.7-closure`.
