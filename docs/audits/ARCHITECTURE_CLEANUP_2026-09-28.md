# Architecture cleanup and integration audit — 2026-09-28

## Frozen inputs and branch disposition

Starting main: `9eaf1887e71a6b238ce6cbcdff98b3862644bae0`.
Integration parent: `5ef55d02194b1818a5b4d7c5ae5ab13bc455e829`.

| Remote branch | Disposition |
|---|---|
| composer-v3-observability | Already an ancestor of main; no separate merge needed |
| constitutional-amendment-v2 | Already an ancestor of main |
| mechanism-artifact-path-budget | Already an ancestor of main |
| person-fidelity-baseline | Already an ancestor of main |
| semantic-memory-resolution-v2 | Included in the integration parent |
| self-memory-system-v1 | Included in the integration parent |
| compact-artifact-journal | Included in the integration parent |
| experiment/compact-artifact-journal | Integrate its useful accumulated work and preserved experiments; replace the superseded live Composer/requirements mechanism in this change |

The latest branch extends main, so a normal history-preserving integration can
include all useful ancestors without conflict resolution or force pushes. Keep
historical branches and negative benchmark evidence; branch deletion is unnecessary.

Retained work includes semantic/self-memory provenance, temporal source policy,
resource admission, exact canonical source links, bounded neighbors, compact
append-only event/percept journals, verified benchmark packaging, and the
`prometheist` package/runtime rename. Runtime personal artifacts are already
ignored; deliberately shareable synthetic evidence remains in the tracked ZIP.

## Explicit governing change

Constitution 2.1 replaces Article 33's Composer loop with deterministic bounded
retrieval and updates Article 37's examples. All other invariants remain in force.
New protocol versions reject stale incomplete stage packages rather than guessing
how to reinterpret them. No admitted canonical evidence is deleted.

## Implementation

See [Fixed retrieval](../architecture/FIXED_RETRIEVAL.md) and
[Private imprint setup](../engineering/IMPRINTING_SETUP.md).

The new evidence-selection policy is provisional, not a measured fidelity gain.
Run a frozen-learning comparison to isolate retrieval. Relearning with the revised
self-review contract is a separate experimental variable. Subject-specific
preferences, traits, history, sensor readings, and credentials are not introduced
into this public core.

## Validation scope

- Before edits: 68 pure policy/unit tests passed on the integration parent.
- Composer/requirements implementation tests were retired with their production contracts; source-policy, canonical-source, and responder regressions remain.
- Replacement tests cover fixed route order, continuation after an empty route, missing focus, deterministic replay IDs, source/cutoff filtering, temporal/opposition diversity, byte budgets, provenance deduplication, authoritative work-result handoff, empty-history abstention, registry coherence, review status exclusion, and private profile separation.
- The local environment has Python 3.14.7 and locked dependencies. PostgreSQL and Ollama are not available locally; native model quality and Windows resource acceptance are not established here.
- Integration testing exposed a lexical navigation gap when learned paraphrases omitted original source cues. Navigation now matches admissible linked canonical text as well as learned statements/tags; the frozen source-delivery oracle remains unchanged. Historical Composer ablations use their own experimental role rather than the production retrieval stage.
- First profile activation requires an empty unbound database. Invalid self-review output cannot reuse a supporting root as opposition or partially record opposition before validation completes.
- GitHub CI must pass before main integration. Native Windows/Ollama acceptance remains a separate user-host gate. Neither static tests nor successful source delivery proves imprint fidelity.
