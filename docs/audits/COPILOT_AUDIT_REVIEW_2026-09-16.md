# Copilot audit review — 2026-09-16

## Scope and verdict

Reviewed commit `afd49a2b20483b193f784d9c41e03dfb73e6dbba` against its parent
`e7497eb`, on `person-fidelity-baseline`: all 26 changed files, the affected runtime
paths and tests, Constitution 2.0, and the current specialist, situation, testing,
and independent-artifact contracts. This is a review of that change and adjacent
execution gaps, not a new all-37-articles constitutional certification.

The cleanup is broadly sound. Keep it. The three execution/recovery defects below
predate Copilot's commit; its audit did not close them. No retrieval scoring,
person-fidelity fixture, canonical historical evidence, model selection, resource
threshold, database schema, or constitutional article is changed by this follow-up.

## What Copilot changed

| Area | Change and assessment |
| --- | --- |
| Current documentation | Corrected the benchmark status, Git-visible artifact policy, and coexistence of user-prompt and non-user situation pipelines. Marked v0.2/v0.3 memory documents as historical. These changes agree with the code and retained evidence. |
| Database row contracts | Added `db.require_row` and explicit checks around queries expected to return a row, covering event, interaction, attention, worker, projection, recovery, and benchmark paths. Missing rows now have attributable failures; SQL parameters and query semantics remain unchanged. |
| Shared memory contract | Added `MemoryContext`, describing the six fields used by Composer/Adaptive Recall. Both durable interaction envelopes and situation tasks legitimately satisfy it. No hidden transcript or extra model responsibility is introduced. |
| Worker specialization | Allowed the shared transport constructor to accept either pipeline's stage enum, while retaining separate runtime guards. Assignment IDs and task classes are narrowed before use. `TriageDecision` already rejects contradictory work-required/task-class combinations before execution. |
| Resource and numeric typing | Made platform load-average availability explicit and preserved numeric comparison's exclusion of booleans. These are useful contract clarifications, not independent evidence of native resource safety. |
| CLI and audit tooling | Rejected non-object JSON payloads explicitly, narrowed optional AST nodes, and preserved the five-coefficient tuple type used in deterministic calibration. |

The commit message reports 382 native test passes and 48-to-zero Pylance errors.
Those local results were not rerun on Mike's Windows/Ollama machine in this review.
Independently retrieved GitHub run
[35065467689](https://github.com/wtvr-guy/prometheist/actions/runs/35065467689)
reports **369 passed, 13 skipped**, with static checks and deterministic calibration
passing. These are distinct evidence sets.

The claimed pre-existing heartbeat `UnboundLocalError` was not reproduced: the
previous expired-lease branch raises before reaching the return, while the live
branch assigns its result. The new explicit checks are reasonable hardening, but
the commit message alone does not establish the claimed failure. Likewise, the
previous macOS probe already raised on an unavailable load average.

## Defects fixed in this review

### 1. A clean worker exit could masquerade as durable completion

`run_situation_task` previously checked only the subprocess exit code before moving
to the next stage and eventually marking the scheduler task completed. It could
return `None` for a missing completion record after releasing task resources.

The supervisor now requires a durable result after every stage and compares its
output and evidence references with the independent stage artifact. Before terminal
completion it checks all six handoffs, their canonical completion record, and hash
chain integrity. Missing or conflicting evidence raises explicitly. This implements
Articles 20, 35, and 36 without changing stage semantics.

Regression coverage includes a fake worker that exits zero without producing any
result, and missing, changed-output, and changed-reference artifact copies.

### 2. Non-user situations never published final-disposition manifests

Each situation stage had an artifact, but the pipeline lacked the manifest required
by Article 36. Consequently a completed silent situation still appeared incomplete
to artifact inspection.

The supervisor now publishes a final disposition with the actual terminal stage,
`SITUATION_PERSIST`, before marking the task completed. Manifest-write failures leave
the completed stages available for recovery. Polling also repairs an interrupted
progress write after scheduler completion, when no worker assignment remains.

The PostgreSQL regression suite exercises real fresh workers with `LLM=null`,
injects failures at manifest and progress publication, and verifies recovery without
repeating completed actions or changing earlier artifact hashes.

### 3. Repeating final-disposition publication conflicted with itself

The shared writer included every current artifact in its evidence list. On retry,
that list included the manifest being retried, changing its payload and triggering
an immutable-content conflict. A pure regression test reproduced this on the
reviewed commit.

The writer now uses the original prefix preceding an existing manifest. Identical
retries preserve its ID and hash, including after later diagnostic artifacts.
Conflicting response content still fails closed. Existing user-prompt callers keep
their original terminal-stage label by default; situation callers supply theirs.

## Verification and remaining evidence

- Local locked environment installed from the unchanged `uv.lock`.
- `ruff check .` and `git diff --check`: passed.
- Pure tests: **23 passed**, including six new manifest/handoff cases.
- Existing artifact, specialist, user-prompt, evidence-budget, authority,
  memory-merge, and response-failure regressions: **51 passed**. This selected
  database-free group used `--noconftest` to omit the root suite's mandatory
  PostgreSQL setup; no PostgreSQL-dependent test was counted as a pass.
- Constraint inventory: **215 discovered / 215 registered**, no uncovered, stale,
  mismatched, or invalid entries.
- Frozen person-fidelity fixture digest: unchanged and valid.
- Deterministic calibration: completed; all four families still report
  `INSUFFICIENT_DISCRIMINATION`. This does not establish optimal tuning.
- The local review host has no PostgreSQL server. Remote CI subsequently ran
  the full suite, including three new PostgreSQL integration cases and the
  extended silent situation test. Its first result and follow-up are below.

## Publication status

The first push was blocked by automatic approval review; Mike then explicitly
authorized publication. Shell Git had no push credentials, so the connected GitHub
app published the exact reviewed tree (`b929e5e3a6befc5b1a784097ac001a38f63817c3`)
as `e82020b`, equivalent in content to local commit `423ad14`.

The first follow-up [CI run](https://github.com/wtvr-guy/prometheist/actions/runs/35155858400)
reported **377 passed, 13 skipped, 1 failed**. The progress-recovery test exposed
two details: an empty candidate page first wraps the cursor, and an action outcome
can supersede the candidate snapshot before the previous task's progress write is
repaired. The dispatcher now finalizes the previously active completed task before
admitting a newer snapshot. The test checks recovery across cursor wrap, the
canonical progress record, and that retrying the older task cannot regress the
latest progress head. The failed run is retained as negative evidence.

### Completion evidence — 2026-09-17

The corrected commit is `23ef8d8d84baf3d5838a4389abbd8635c446e1b3`
(tree `30337c7ce99ba1b5b4b21562ebabb6c09f3190f5`, identical to the local
review commit `edb0d82`). Its [CI run 35156310628](https://github.com/wtvr-guy/prometheist/actions/runs/35156310628)
passed: **378 passed, 13 skipped in 72.84 seconds**. Ruff, the **215/215**
constraint inventory, frozen fixture validation, and deterministic calibration
also passed. This verifies the completion/recovery corrections under CI's
PostgreSQL and deterministic-worker environment. The skipped model/native tests
are not counted as passes.

Mike subsequently reported, "All tests are passing." This is recorded as a
user-reported passing local run. No native log, exact tested revision, test count,
model digest, or hardware measurements accompanied that report, so this audit
does not infer them or turn CI's skips into native passes. Native performance and
person-fidelity acceptance still require their own attributable artifacts.

Mike authorized documentation completion and integration into `main` on
2026-09-17. [PR #28](https://github.com/wtvr-guy/prometheist/pull/28) is the
integration record for Constitution 2.0, the frozen benchmark and retained
artifacts, Copilot's cleanup, and these reviewed recovery fixes. The branch and
PR status should be checked there rather than inferred from this dated record.

The native person-fidelity result remains **1/10 structural passes**, with every
human verdict pending. It is schema v1 and lacks the schema-v2 run manifest. A fresh
native run and human review remain necessary; this cleanup is not evidence of
improved identity fidelity or native Windows/Ollama behavior.

Follow-up: PR #28 merged into `main` as `ece0769`, with PR and main CI passing.
The [2026-09-17 artifact review](PERSON_FIDELITY_ARTIFACT_REVIEW_2026-09-17.md)
records the blocked fresh-run attempt and complete read-only inspection of the
retained 2026-09-14 evidence.
