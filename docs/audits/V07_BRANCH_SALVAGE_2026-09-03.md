# v0.7 Branch Salvage and Disposition

**Date:** 2026-09-03  
**Scope:** PRs #19–#24 and consolidation into the authoritative v2 pipeline

## Decision

No branch is merged wholesale merely to preserve its work. PR #23 is the required
audit-hardening base. PRs #19 and #22 contributed selected tests and evidence; their
obsolete runtime implementations were rejected. After the 2026-09-03 native run
falsified the initial belief that prompt-level authority guidance was sufficient,
PR #19's current-only source policy and evidence-bound transport were selectively
ported into the v2 runtime. PRs #20 and #21 remain superseded/deferred. PRs #19–#22
remain closed without merge.

| PR | Branch role | Salvaged into closure candidate | Rejected/deferred | Disposition |
| --- | --- | --- | --- | --- |
| #19 | v0.7 memory-continuity red team | adversarial scenarios; saturated WorkingState ordering; deep-history anchor routing and pure-kernel temporal diversity; incremental projection freshness; model-evidence byte bounds; response-persistence failure invariant; current-only response policy, source-role filtering, evidence-channel isolation, Qwen control escaping, and validated exact-source output adapted to v2 after native failure | old interaction runtime, old recurrent response/capability loop, and old capability names | closed without merge on 2026-09-03; selected mechanism ported, records preserved |
| #20 | constitutional remediation | audit findings remain historical input | conflicted implementation; connection-time schema-changing DDL; portability/export/erasure work not justified as a v0.7 blocker | closed without merge on 2026-09-03; re-propose one mechanism in its proper milestone |
| #21 | pre-cognitive transient workers | general disposable-worker invariant is already represented in the current guarded stage protocol | intermediate workpiece/final-readiness architecture | closed without merge on 2026-09-03 |
| #22 | Adaptive Memory Attention experiment | experiment records and existing `MEM-ADAPT-*` result artifacts; accepted conclusion that memory expansion is one mechanism rather than named capabilities | branch production implementation and obsolete profile/capability ontology | closed without merge on 2026-09-03; records preserved |
| #23 | August 31 audit hardening | entire branch is the consolidation base: artifact-path fix, constraint gate, temperature/test alignment, dead-stage removal, and robustness fixes | none known; still subject to native acceptance and final audit | required merge only after all closure gates pass |
| #24 | authoritative v2 consolidation | all accepted production changes, current-v2 tests, current documentation, and explicit evidence disposition | no native-acceptance claim | draft child PR onto #23; remediation hosted CI green, native revalidation pending |

## Post-consolidation native correction

The first full local gate executed all 14 selected Ollama tests: 8 passed and 6
failed. The failures covered a mutated application placeholder, missed
cross-conversation recall, unnecessary external-work selection, two historical
authority cases, and one retrieved assistant prompt-injection case. This is negative
evidence against relying on prompt wording alone to preserve authority boundaries on
the configured local model.

The initial table rejected PR #19's source-filter/fallback architecture as
branch-specific. That disposition was too broad. The old runtime and capability loop
remain rejected, but the independently useful boundary mechanism is now adapted to
the authoritative v2 stages:

- response source/surface policy is classified from the current percept only;
- application code physically filters historical event roles;
- memory is transported separately as quarantined evidence before current authority;
- Qwen control sequences in evidence/current data are escaped;
- exact answers are selected as source substrings, validated, and returned
  mechanically;
- initial aperture evidence is retained ahead of later adaptive expansions.

Changing this disposition is intentional scientific correction: the frozen native
failure supplied the evidence that the narrower mechanism was necessary.

The exact-SHA follow-up at `6e371a33350260b6e458ae4c16e4fd27ffac1dad`
passed 11 of 14 native cases. All previously failing memory-authority and
prompt-injection cases passed. Two remaining response failures were caused by the
test harness forcing natural continuity questions into exact tuples; one produced a
poor echoed answer despite the required evidence being present, and one exact-source
selector failed because a multi-source answer is not a single contiguous substring.
Those fixtures now use natural prompts, assert canonical evidence admission through
the immutable response-invocation artifacts, print answers for human judgment, and
reserve exact automation for genuine control/security contracts.

## Ported production changes

### WorkingState saturation

Activation ordering now gives the current prompt and newly recalled evidence priority
over stale prior activation. This preserves a strict item bound without allowing a
full old state to block new relevant context.

### Deep temporal history

PostgreSQL candidate routing reserves a bounded historical-anchor budget. An old
same-topic fact therefore remains reachable despite more recent lexical ties than the
ordinary candidate window, without claiming arbitrary lifetime/as-of completeness.

### Projection freshness

Association feature projection now tracks durable high-water marks and incrementally
processes only the tail required to derive new relations. A full deterministic rebuild
seeds matching marks. Steady-state per-percept freshness no longer reads the lifetime
event ledger.

### Model evidence bounds

Memory items, structured work results, and final rendered evidence are checked against
explicit per-item and aggregate UTF-8 byte limits before any v2 model call. Oversize
fails closed and canonical durable evidence is left unchanged.

### Failure atomicity

Failure to persist the final response event records an interaction error and releases
the worker claim; it never publishes a terminal success for a response that does not
exist durably.

### Response evidence boundary

The v2 pre-cognitive worker and Composer now receive remembered content in a
separate evidence channel rather than concatenated into the current user message.
Before final response, a fresh current-only policy selects an application-owned
event-role scope. Inadmissible roles are removed, and exact-output contracts use
validated source extraction rather than model-regenerated opaque values. Invocation
artifacts record the separate current/evidence payloads, transport layout, and
canonical event references for admitted memory.

## Ported regression scenarios

Current-v2 tests include:

- `tests/test_redteam_working_state_saturation.py`;
- `tests/test_redteam_deep_temporal_history.py`;
- `tests/test_projection_freshness_incremental.py`;
- `tests/test_redteam_projection_freshness_bounded.py`;
- `tests/test_model_evidence_budget.py`;
- `tests/test_redteam_memory_item_size_bound.py`;
- `tests/test_percept_response_failures.py`;
- `tests/test_redteam_epistemic_memory_setup.py`;
- `tests/test_redteam_epistemic_memory_native.py`;
- `tests/test_redteam_memory_authority_native.py`;
- `tests/test_redteam_memory_prompt_injection_native.py`.

Deterministic coverage also includes `tests/test_epistemic_authority.py`,
`tests/test_response_policy.py`, `tests/test_evidence_bound_transport_v2.py`, and
`tests/test_response_memory_merge.py`.

The native authority suites intentionally remain hard gates. Merely collecting or
skipping them is not evidence of safe local-model behavior.

Hosted workflow [run #717](https://github.com/wtvr-guy/prometheist/actions/runs/33810504804)
passed on exact-SHA follow-up commit
`6e371a33350260b6e458ae4c16e4fd27ffac1dad`: 280 tests passed and 14
environment-marked native tests skipped. The first native run executed 14 tests and
failed 6 without establishing its revision. The follow-up established the exact SHA
and clean branch, then passed 11 and failed 3. The artifact-first replacement still
requires hosted and native structural evidence plus human response review on the
exact final PR head.

## Evidence retained

The PR #19 chronological audit/remediation records are under
[`history/pr19/`](history/pr19/). They are preserved without rewriting historical
claims, preceded by a banner that prevents them from becoming current architecture.

The PR #22 decision records are under
[`../experiments/history/pr22/`](../experiments/history/pr22/). The repository already
contains the associated raw `MEM-ADAPT-*` result artifacts in `benchmarks/results/`.

Normal `.prometheist/artifacts` output is not evidence storage and is no longer
tracked. Deliberately retained evidence must name its provenance and revision.

## Claim boundary

This salvage does not claim that every PR #19 remediation mechanism was accepted or
that native adversarial behavior is green. It establishes that valuable attacks,
measured failures, and the independently justified evidence-bound mechanism survive
while only code adapted to the authoritative v2 architecture enters the closure
candidate.
