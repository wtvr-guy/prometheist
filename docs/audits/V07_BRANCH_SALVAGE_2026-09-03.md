# v0.7 Branch Salvage and Disposition

**Date:** 2026-09-03  
**Scope:** open PRs #19–#23 and consolidation into the authoritative v2 pipeline

## Decision

No open branch is merged wholesale merely to preserve its work. PR #23 is the
required audit-hardening base. PRs #19 and #22 contribute selected tests and evidence;
their obsolete runtime implementations are rejected. PRs #20 and #21 are
superseded/deferred and are closed without merge.

| PR | Branch role | Salvaged into closure candidate | Rejected/deferred | Disposition |
| --- | --- | --- | --- | --- |
| #19 | v0.7 memory-continuity red team | adversarial scenarios; saturated WorkingState ordering; deep-history anchor routing; incremental projection freshness; model-evidence byte bounds; response-persistence failure invariant | old interaction runtime, old response/capability loop, branch-specific source-filter/fallback architecture, old capability names | preserve records; close without merge after candidate publication |
| #20 | constitutional remediation | audit findings remain historical input | conflicted implementation; connection-time schema-changing DDL; portability/export/erasure work not justified as a v0.7 blocker | close without merge; re-propose one mechanism in its proper milestone |
| #21 | pre-cognitive transient workers | general disposable-worker invariant is already represented in the current guarded stage protocol | intermediate workpiece/final-readiness architecture | close without merge |
| #22 | Adaptive Memory Attention experiment | experiment records and existing `MEM-ADAPT-*` result artifacts; accepted conclusion that memory expansion is one mechanism rather than named capabilities | branch production implementation and obsolete profile/capability ontology | preserve records; close without merge |
| #23 | August 31 audit hardening | entire branch is the consolidation base: artifact-path fix, constraint gate, temperature/test alignment, dead-stage removal, and robustness fixes | none known; still subject to native acceptance and final audit | required merge only after all closure gates pass |

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

The native authority suites intentionally remain hard gates. Merely collecting or
skipping them is not evidence of safe local-model behavior.

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

This salvage does not claim that every PR #19 remediation mechanism was accepted, or
that all native adversarial behavior is already green. It establishes that valuable
attacks and measured experiment history survive while only code consistent with the
authoritative v2 architecture enters the closure candidate.
