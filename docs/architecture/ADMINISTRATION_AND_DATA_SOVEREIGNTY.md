# LLM-Free Administration and Data Sovereignty

**Status:** implemented constitutional support surface.  
**Constitutional authority:** Articles 3, 18, 21, 22, and 29 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md).  
**Primary implementation:** `src/jit_agent/admin.py`, `src/jit_agent/admin_cli.py`, `src/jit_agent/canonical_event_guard.py`.

Prometheist's cognitive path may depend on a local model, but its durable identity and administrative control plane do not. The `prometheist-admin` entry point intentionally imports no LLM client and performs deterministic operations directly against durable state.

## Administrative surface

```text
prometheist-admin inspect
prometheist-admin history [--rows N] [--conversation-id UUID]
prometheist-admin unfinished [--rows N]
prometheist-admin verify
prometheist-admin rebuild
prometheist-admin export PATH
prometheist-admin restore PATH --confirm RESTORE-INTO-EMPTY-PROMETHEIST
prometheist-admin erase-all --confirm ERASE-ALL-PROMETHEIST-DATA
```

`inspect`, `history`, and `unfinished` read authoritative state without model inference. `verify` checks the canonical-event integrity chain. `rebuild` regenerates disposable memory projections from canonical events.

## Logical export and restore

`export` writes a versioned JSON bundle containing every current Prometheist durable/derived table plus a SHA-256 digest over the logical table payload. The format preserves canonical UUIDs, global/conversation ordering, task/worker state, policy provenance, and derived state. It is deliberately logical rather than a PostgreSQL physical dump so it can serve as a future backend-migration boundary.

`restore` is fail-closed: the bundle version/table set/digest must verify, the target must be empty, an exact confirmation string is required, dependency order is restored deterministically, and sequences are repaired after canonical identifiers/order are restored.

A physical `pg_dump` remains a valid operator backup, but it is no longer the only supported way to move Prometheist state.

## Canonical-event mutation boundary

Ordinary Prometheist operation is append-only. `canonical_event_guard.ensure_canonical_event_guard()` installs a PostgreSQL statement trigger as soon as the `events` table exists. The database rejects every UPDATE and rejects DELETE/TRUNCATE unless an explicit owner-erasure transaction is active.

The same guard is recorded explicitly in `migrations/0001_canonical_event_guard.sql`. This supersedes the older `schema.sql` header that described append-only storage as application-enforced only.

The guard is a database DML boundary, not a claim that a PostgreSQL superuser/database owner cannot intentionally alter its own schema or disable a trigger.

## Explicit owner-directed erasure

`erase-all` is separate from retention, compaction, projection rebuild, and correction semantics. It requires the exact confirmation token and sets `prometheist.user_erasure=on` only for the destructive transaction. This grants DELETE/TRUNCATE authority but never UPDATE authority. The complete current Prometheist store is erased atomically and sequences reset.

## Retrieval portability boundary

The legacy Retrieval Service now depends on the `RetrievalBackend` protocol. PostgreSQL full-text syntax lives in `PostgresFullTextRetrievalBackend`, while `retrieval.search()` owns only the stable request/result orchestration contract. A future backend can implement the protocol without reproducing PostgreSQL FTS syntax inside the service layer.

PostgreSQL remains the current authoritative reference implementation. The logical export format provides a database-neutral state-transfer boundary without inventing an unneeded second production database today.

## Acceptance evidence

Deterministic tests cover LLM-free administration, canonical-event mutation rejection, explicit erasure authorization, export→erase→restore identity/order, tampered-export rejection, retrieval-backend delegation, and a dedicated causal-provenance path from user percept through task/assignment/epoch/resource observation/worker results to routing decision and response.

Native calibration also contains explicit resource-contention and Ollama cold/warm-start scenarios. Those scenarios must execute on the intended Windows/PostgreSQL/Ollama host before their environment-sensitive evidence is accepted.
