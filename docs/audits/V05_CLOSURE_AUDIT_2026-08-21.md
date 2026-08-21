# Prometheist v0.5 Closure Code Audit — 2026-08-21

## Status

**Static audit complete. Code fixes prepared on `v05-closure-audit`; local regression verification pending.**

This audit was performed after the accepted Memory Kernel v0.5 scale result and before beginning v0.6. Its purpose is to distinguish defects that should be closed now from architectural work that belongs to later milestones.

The audit reviewed the repository structure, authoritative event store, Primary Agent orchestration, legacy Retrieval Service, deterministic Memory Kernel, associative projection/recall, PostgreSQL adapter, scale tooling, schema, test database setup, and representative regression/acceptance tests. Repository-wide searches were also used to check for obvious TODO/FIXME markers, broad exception handling, stale version assumptions, and accidentally committed secrets.

This is a static code audit. Because the project has no configured GitHub CI, runtime correctness of the closure patch must be established by the local pytest suite on the development machine.

## Closure defects fixed on the audit branch

### A-01 — Association traversal could cross the global-sequence cutoff

**Severity:** correctness / historical-leakage risk  
**Disposition:** fixed; regression pending local execution

`associative_recall_from_postgres()` bounded its direct candidate set with `before_global_seq`, but the persisted association projection was rebuilt over the complete event ledger. Association traversal could therefore select an EVENT target newer than the cutoff, and `_load_events_by_ids()` could fetch that target without reapplying the boundary.

That violates the intended temporal invariant: a historical/current-turn query must not receive evidence that did not yet exist at the requested global-sequence boundary.

The closure patch:

- passes `before_global_seq` into persisted association loading;
- rejects association edges whose EVENT source or target does not precede the cutoff;
- reapplies the cutoff when canonical events are fetched by ID;
- adds a regression test proving a future vehicle-acquisition event cannot be surfaced before its `global_seq`.

### A-02 — `source_types` was enforced after bounded candidate truncation

**Severity:** correctness / bounded-recall risk  
**Disposition:** fixed; regression pending local execution

The pure kernel respects `CueState.source_types`, but PostgreSQL candidate composition did not apply the restriction inside its entity, lexical, or recency routes. Disallowed event types could therefore consume a small candidate window and be discarded only after the valid allowed evidence had already been excluded.

The closure patch applies source-type restrictions inside every candidate route before truncation and ensures only allowed directly activated candidates seed EVENT association traversal.

A regression test uses a one-event candidate limit with a valid `SYSTEM_EVENT` target and newer `USER_PROMPT` confusers to ensure the allowed evidence survives.

### A-03 — Pytest database isolation was incomplete

**Severity:** test reliability / destructive-safety risk  
**Disposition:** fixed; regression pending local execution

The existing pytest session fixture redirected the suite to `jit_agent_test`, but:

- it truncated only once per session;
- it omitted `memory_association_entries`, which has no FK cascade from `events`;
- it had no database-name safety gate before destructive setup.

This allowed state to accumulate across tests and could leave stale association rows from prior tests. It also relied solely on environment redirection to protect the development database.

The closure patch:

- verifies that the selected database name contains `test` or `benchmark` before schema/destructive operations;
- applies the schema once per session;
- truncates authoritative and derived test state before every test;
- explicitly includes `memory_association_entries`.

## Audit observations intentionally deferred

The following are not v0.5 closure blockers. They should remain visible because they define later engineering work.

### D-01 — The user-facing Primary Agent still uses the legacy Retrieval Service

`primary_agent.py` calls `jit_agent.retrieval`, which uses PostgreSQL structured filters and full-text search. The verified Memory Kernel and its associative PostgreSQL path currently evolve alongside that MVP path rather than sitting behind the live Primary Agent interface.

This is the central v0.6 integration task, not a v0.5 defect: create a stable shared JIT Memory contract and allow multiple stateless agents to consume the verified memory subsystem.

### D-02 — Append-only history is application-enforced, not database-enforced

Application code writes canonical events through `record_event()` and the schema documents `events` as append-only, but the database does not currently prevent a sufficiently privileged role from executing UPDATE or DELETE against canonical history.

Before v1.0, production hardening should use database permissions and/or another explicit mechanism so the append-only invariant is enforced below application convention.

### D-03 — Integrity metadata is useful consistency evidence, not an external immutable anchor

The current hash chain detects disagreement between canonical events and the derived `event_integrity` rows. However, `rebuild()` intentionally regenerates the chain from the current ledger. An actor able to alter authoritative rows and rebuild derived state can therefore create a new internally consistent chain.

Additionally, the Memory Kernel canonical hash shape is narrower than the full `Event` schema and does not currently include every event metadata field.

Before treating integrity as strong tamper evidence against a database-level adversary, Prometheist should define its threat model and, if required, introduce independent anchoring/authorization controls.

### D-04 — Dense association-graph scaling is not characterized

The 50k scale benchmark contains very large event histories but only a handful of derived associations per persona. It strongly tests candidate routing under event noise; it does not establish performance or ranking behavior for hundreds or thousands of simultaneously reachable association edges.

Dense/ambiguous relationship graphs belong in a later memory-generalization benchmark rather than being inferred from the v0.5 scale result.

### D-05 — No repository CI is configured

The project currently relies on the local development machine for PostgreSQL pytest and benchmark verification. This has been adequate for rapid prototype research, but v1.0 should have a reproducible automated regression path for deterministic tests and an explicit strategy for database-backed tests.

No CI system is being added during v0.5 closure because infrastructure should not be introduced merely for convention; it should be designed around the local-first/PostgreSQL constraints deliberately.

### D-06 — Package version and research-milestone version are not the same thing

`pyproject.toml` and `uv.lock` currently identify the Python package as `0.4.0`, while the memory research milestone is v0.5. This is not a runtime error, but the project should decide before public release whether package versions track research milestones or use an independent release scheme.

No version bump is included in this audit because changing package metadata without a defined versioning policy would create noise rather than clarity.

### D-07 — Local test credentials are embedded in the default test DSN

`tests/conftest.py` includes the prototype-local `jit_agent_test` DSN as a convenience fallback. It is not a production secret and the repository is private, but public/professional distribution should prefer environment-controlled credentials or documented local bootstrap configuration.

### D-08 — Some older module comments still describe vector retrieval as a presumed future step

The legacy Retrieval Service and older architecture documents contain language written before v0.5 demonstrated that deterministic routes were sufficient for the measured failures. The architectural rule now is stricter: semantic/vector retrieval is a candidate mechanism only after a frozen benchmark demonstrates a failure that warrants it.

This is documentation debt, not a functional defect.

### D-09 — Some older comments reference superseded numbered spec sections

The Primary Agent specification was substantially rewritten after v0.5. A few code comments still cite old section numbers. The underlying design principle remains correct, but future edits should reference the principle/document rather than fragile section numbers.

### D-10 — `ignored_terms` normalization is not perfectly uniform across layers

The pure kernel's lexical scorer normalizes each ignored string as one value, while candidate/associative paths tokenize ignored values. Current benchmark construction passes principal names as individual tokens, so the accepted v0.5 results are unaffected. A future API cleanup should make the semantic contract uniform and version the retrieval policy if scoring behavior changes.

## Positive audit findings

The audit also confirmed several useful properties of the current codebase:

- authoritative event persistence is centralized in `event_store.record_event()`;
- deterministic IDs/order/metadata are owned by application code rather than LLM output;
- canonical event rebuilds do not rewrite `events`;
- memory projections and associations remain explicitly disposable;
- association provenance is retained;
- candidate and association traversal remain bounded;
- the destructive scale benchmark already contains a database-name safety gate;
- checked-in generated scale corpora/results are excluded through `.gitignore`;
- no repository TODO/FIXME/HACK/XXX markers were found in the code search performed for this audit;
- no obvious committed API keys/tokens were found in repository code search;
- the project remains free of unnecessary orchestration/vector/distributed-system dependencies.

## Verification required before merge

The closure patch changes PostgreSQL routing and pytest setup. It must not be merged based on static reasoning alone.

Run, in order:

```powershell
uv run pytest tests/test_postgres_memory_kernel.py -v
uv run pytest -v
```

If both pass, the closure PR can be marked ready and merged. The 10k/50k scale benchmark does not need to be automatically rerun for these specific fixes because the frozen scale workload does not use `before_global_seq` or `source_types`, and the candidate-limit/ranking mechanism exercised by that workload is otherwise unchanged. A scale rerun remains optional if additional assurance is desired.

## Closure decision

After the local regression suite passes and the audit branch is merged, Memory Kernel v0.5 should be considered **closed and frozen**.

Further work should begin under v0.6 rather than continuing to tune already-passing v0.5 corpora.