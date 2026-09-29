# Canonical neighborhood before Composer sufficiency

Date: 2026-09-27. Mechanism: `canonical-local-context-v1`.
Status: targeted native structural acceptance passed; full corpus pending.

Follow-up: the native run `SELF-MEMORY-001_2026-09-27_095628.json` at `56b0469`
passed both `pf-q001` and `pf-q002`; its 276-artifact ZIP verifies. Both composed
packets include their required roots. The radio answer is faithful; the Theo
answer respects privacy but retains assistant-like phrasing. See
[`COMPOSER_COVERAGE_001.md`](COMPOSER_COVERAGE_001.md) for the next mechanism,
current branch, and learning-reuse instructions. The original command and
learning behavior below describe this experiment at its original revision.

## Frozen failure and hypothesis

Baseline: `SELF-MEMORY-001_2026-09-27_000808.json`, revision
`07f4f497f09db1bbe8faeea9320af56b03f3a3fb`, shared as `latest-benchmark(4).zip`.
The complete native run passed 2 of 10 structural probes. In particular:

| Probe | Retrieved canonical seed | Missing required context |
| --- | --- | --- |
| pf-q001, autobiographical meaning | pf-e002, meaning of the radio weekend | pf-e001, experience with her father during the outage |
| pf-q002, relational judgment | pf-e004, protecting Theo's disclosure choices | pf-e003, relationship and shared history with Theo |

Both pairs are neighboring user-authored records in their original conversations.
The hypothesis is that bounded local context supplied **before** sufficiency can
recover the missing canonical evidence even when the Composer immediately says
it has enough. This does not establish that the model will use the new evidence
correctly; structural admission and human semantic review remain distinct.

## What changed and why

- `src/prometheist/canonical_neighborhood.py` owns one deterministic operation:
  rehydrate a retrieved seed and load its nearest permitted predecessor and
  successor. Existing conversation/sequence indexing supplies the relation.
  There are no general canonical episode links in this implementation; this is
  local context recovery, not semantic episode segmentation.
- `_compose_memory_package` calls that operation before its first model decision.
  Original seed order/content is preserved. Only those original seeds are
  expanded, so additions cannot trigger an unbounded transitive walk.
- The existing response-memory item bound still applies (default 20). A full
  packet is left alone; an oversized input fails explicitly rather than losing
  original evidence. SQL range scans inspect at most 32 sequence positions in
  either direction per seed. Internal or disallowed records cannot fill neighbor
  slots, but still consume that sequence window.
- Source scope and the exclusive `before_global_seq` cutoff are enforced for
  both canonical endpoints in SQL. Neighbor search uses the canonical seed's
  metadata, not copied packet conversation/sequence values. Global initial
  retrieval can still find seeds from any conversation.
- Each addition has exact source text, its original attribution, a neighbor
  retrieval reason, and its seed pointer. The trace records direction, policy
  version, window, cutoff, and source types. It is retained through later merges
  and persisted in the existing Composer stage result. No extra model call,
  worker, event journal, or separate artifact family is added.
- The numeric constraint and experiment registries classify the window as
  **PROVISIONAL**, not calibrated. Tests and this record explain why the mechanism
  exists without changing the benchmark corpus, oracle, or expected answers.

## Evidence and limits

`tests/test_canonical_neighborhood.py` covers missing-root recovery before an
immediately sufficient Composer, source exclusions, current/future-event exclusion,
canonical seed validation, cross-conversation query context, deduplication,
original-seed preservation under saturation, one-hop expansion, replay stability,
and the sequence-window bound. Two frozen-fixture replay cases start from the
actual failed seeds above and assert recovery of exactly the required canonical
event pairs. These are retrieval regression checks, not native benchmark passes.

The development environment uses Python 3.14.7 with the locked dependencies.
SQL/contract checks run against disposable PGlite (PostgreSQL compiled to WASM)
through psycopg; native PostgreSQL and Ollama are unavailable here. The temporary
test harness disables client prepared-statement caching because PGlite multiplexes
connections onto one backend session; production code is unchanged. This cannot
establish production PostgreSQL performance, Windows resource behavior, or native
model acceptance. Native latency and response quality must be measured separately.

Validation: 36 tests passed across `test_canonical_neighborhood`,
`test_percept_response_contract`, `test_percept_response_failures`, `test_jit_memory`,
and `test_response_policy`. Repository-wide Ruff, diff whitespace checks, and the
self-memory fixture validator passed. The fixture digest remains
`bcb1fb2812f3cb3e8cbaf64cb3b8161dbf087a1c9a7eefb55bcd629ffc21e6d9`.

The baseline constraint audit already has six unregistered entries in
`model_evidence_budget`, `percept_journal`, and Composer deficit bounds. This
change registers its own new constraints and does not silently classify unrelated
pre-existing work as validated.

Known limits: neighboring records may discuss different topics; conversation
boundaries can separate related experiences; far-away roots are not recovered;
full packets have no remaining neighbor capacity. Proximity never establishes
truth. Missing standalone memories, source-policy exclusions, and Composer
sufficiency judgment remain separate mechanisms. Do not infer a 10/10 result.

## Native acceptance

From the repository root in PowerShell, using the existing dedicated benchmark
database and configured Ollama model:

```powershell
git switch compact-artifact-journal
git pull --ff-only origin compact-artifact-journal
.\scripts\run_self_memory_person_fidelity.ps1 -ProbeId @("pf-q001", "pf-q002")
```

The existing wrapper learns the self-memory record and runs only these two probes,
preserves results, and packages/stages the sharing ZIP. Learning is still required;
probe selection does not skip it. The benchmark resets its dedicated database.

Success criterion: both probes admit every required root, retain a valid artifact
chain, and receive a faithful human semantic review. Compare with the frozen run
above, not with `main` (which lacks this branch's current benchmark path). After
targeted success, run the full public corpus and holdout to check regressions and
neighbor noise. Tune the sequence window only against frozen noise/scale families;
expand any winning search boundary and preserve negative results. No optimum for
32 has been established.
