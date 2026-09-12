> **Historical branch record (PR #19).** This file is preserved verbatim below as evidence of the red-team sequence. Its runtime names, implementation status, test counts, and acceptance claims apply only to the recorded branch/SHA and do not define the live v2 architecture. See `../../V07_BRANCH_SALVAGE_2026-09-03.md` for current disposition.
>
# RT-02 remediation record — incremental projection freshness

**Date:** 2026-08-27  
**Branch:** `redteam/v07-memory-continuity`  
**Parent red-team report:** `docs/audits/V07_RED_TEAM_2026-08-27.md`

## Frozen failure

The original RT-02 attack proved that ordinary attention activation established derived-memory freshness by materializing the lifetime canonical event ledger in Python, even when the lexical projection was already current.

The failing path was:

`open_attention_aperture` → `request_attention_activation` → `_ensure_projection_fresh` → `postgres_memory_kernel.load_events`.

When projection entries were missing, the same mechanism also supplied the complete historical event sequence to `derive_associations`, making association maintenance history-sized as well.

That behavior violated the intended Article 5 distinction between lifetime durable memory and bounded ordinary cognition. Keeping the model packet small is insufficient if every percept still walks the lifetime ledger before inference.

## Mechanism changed

Steady-state projection freshness is now incremental.

The implementation uses the existing disposable `memory_projection_entries` table rather than introducing another authoritative store or database. Two versioned row families form a transactional committed projection frontier:

1. the existing lexical projection; and
2. a new `association_features` projection containing only the event-local features required to find deterministic association predecessors.

The association-feature projection version is coupled directly to `ASSOCIATION_PROJECTION_VERSION`, so a future association-rule version change cannot falsely appear current.

For an ordinary freshness check the runtime now:

1. obtains the canonical target high-water mark with an indexed `MAX(global_seq)` below the current leakage cutoff;
2. reads the lexical and association-feature projection high-water marks;
3. returns immediately if committed derived state is already at or beyond the requested historical boundary;
4. treats disagreement between the two derived high-water marks as recovery/migration state and performs a disposable full rebuild rather than guessing across a possible gap;
5. otherwise loads only canonical events with `global_seq` greater than the committed frontier and below the requested cutoff;
6. inserts lexical and association-feature rows for that delta;
7. derives only association edges whose later/source event is in that delta, using indexed feature queries to find the necessary predecessor event; and
8. commits projection rows and association edges atomically, rolling the entire catch-up back on failure.

A first run against a pre-remediation v0.7 database will intentionally see lexical rows without matching association-feature rows and perform one full rebuild as migration/recovery work. Subsequent ordinary turns use the incremental path.

## Incremental association maintenance

The association-feature projection stores only disposable routing facts:

- canonical source;
- derived concepts;
- derived entity terms;
- whether the event matches a change phrase;
- whether it represents an unresolved state; and
- whether it represents a resolved state.

For the current v0.7 association rules:

- event-local vehicle acquisition/disposition edges are derived from each delta event alone;
- `PREVIOUS_STATE` uses an indexed lookup for the latest prior event from the same source sharing the relevant concept; and
- `RESOLVED_BY` uses an indexed lookup for the latest prior unresolved event sharing an entity term.

The predecessor event is then rehydrated from the canonical ledger and the existing deterministic `derive_associations` rules generate the edge. The feature index never becomes evidence or authority.

## Why a simple MAX cache was not sufficient

A standalone maximum projected sequence can lie after partial work: a later row could exist while an earlier required row or association edge is absent.

RT-02 therefore relies on a stronger transactional invariant. Lexical rows, association-feature rows, and newly derived association edges for a delta are advanced in one PostgreSQL transaction. If the transaction fails, none of the committed frontier advances. If the independently versioned lexical and feature frontiers disagree, the runtime refuses to infer a safe frontier and rebuilds disposable state.

This is still not a cryptographic integrity proof against arbitrary direct database tampering; that is a separate threat model. It is a deterministic steady-state/recovery contract for application-managed derived state.

## Regression coverage

The unchanged frozen attack remains in `tests/test_redteam_projection_freshness_bounded.py` and now passes: an ordinary aperture over an already-current projection does not call the lifetime `load_events` path.

`tests/test_projection_freshness_incremental.py` adds four mechanisms tests:

1. a clean full rebuild seeds matching lexical and association-feature high-water marks;
2. incremental `PREVIOUS_STATE` catch-up succeeds while the lifetime loader is forbidden;
3. incremental `RESOLVED_BY` catch-up succeeds while the lifetime loader is forbidden; and
4. association state produced by incremental catch-up is exactly equal to a subsequent clean full rebuild over the same canonical history.

## CI evidence

CI #447, before the final version-coupling correction, produced:

- **270 passed**
- **16 skipped**
- **2 failed**

The only failures were the intentionally unresolved RT-03 and RT-01 attacks. The unchanged RT-02 attack and all new incremental-equivalence tests passed.

A code review then identified that the association-feature projection had initially used a literal version `"1"`. That was corrected so its version derives from `ASSOCIATION_PROJECTION_VERSION`.

CI #448 on the corrected head again produced:

- **270 passed**
- **16 skipped**
- **2 failed**
- **44.28 seconds**

The only failures were again RT-03 and RT-01. Static checks, deterministic constraint calibration, and native-gate collection all passed. Constraint governance remained clean at **175 discovered, 175 registered, 0 uncovered, 0 stale, 0 mismatched, 0 invalid**.

## Current status

**Status: REMEDIATED FOR THE CONFIRMED RT-02 DEFECT.**

The original correctness/scalability defect is closed because:

- freshness no longer requires a lifetime event materialization in steady state;
- incremental association maintenance no longer receives the lifetime event list;
- the original frozen attack passes unchanged;
- the two history-dependent association rule families survive incremental catch-up with the lifetime loader forbidden;
- incremental association output equals clean full-rebuild output in the regression corpus; and
- the final rule-version coupling correction preserved the same CI result.

## Scope boundaries / remaining risks

RT-02 does not claim that all lifetime-memory operations are now bounded or that every future association rule will automatically be incrementally maintainable.

Remaining distinct concerns include:

- explicit full rebuild/migration/recovery is intentionally history-sized;
- arbitrary manual deletion/corruption of a historical derived row below both high-water marks is not detected by the high-water invariant alone;
- concurrent projection catch-up has not yet received a dedicated adversarial race test;
- new association-rule families must define bounded predecessor lookup semantics before they may participate in ordinary incremental maintenance; and
- RT-03 still demonstrates a correctness cliff in bounded candidate selection even though projection maintenance itself is now incremental.

Those are separate falsifiable mechanisms and should not be conflated with the closed RT-02 failure.

## Constitutional fit

The remediation strengthens Articles 3, 4, 5, 23, and 24. Canonical memory remains authoritative and append-only; the new feature state is explicitly disposable and version-coupled; ordinary projection maintenance is proportional to newly unprojected work rather than lifetime history; the change addresses only the demonstrated mechanism; and no arbitrary larger candidate/context bound was introduced.

