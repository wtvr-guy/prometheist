# Explicit Composer evidence coverage

Date: 2026-09-27. Status: implemented candidate; native model acceptance pending.
Parent: `2bf7c60` on `experiment/compact-artifact-journal`.

## Evidence motivating this change

The preceding canonical-neighborhood change passed both targeted structural
probes in `SELF-MEMORY-001_2026-09-27_095628.json`, revision `56b0469`.
Its sharing ZIP verified with 276 inventoried artifacts. The composed packets
recover the required radio-weekend and Theo relationship roots. The first answer
uses the formative event and its meaning faithfully; the second respects Theo's
privacy, although its assistant-like framing still needs separate response-style
work. These two results do not establish whole-corpus acceptance.

The earlier full run at `07f4f49` also shows a separate problem: Composer's private
decomposition is not visible in its boolean/deficit output. `pf-q006` eventually
approves incomplete context for a novel decision. `pf-q005` and `pf-q007` already
report insufficiency, but their deficits do not lead retrieval to the missing
personal evidence. It would be inaccurate to describe every failure as an
immediate, premature sufficient verdict.

The hypothesis is that requiring explicit source coverage within the same model
call will improve both missing-evidence detection and the resulting recall cue.
Learning reuse below is independent benchmark tooling, allowing the cognitive
change to be evaluated against an identical learned state.

## Contract

`src/prometheist/composer_coverage.py` renders a single numbered catalog of
canonical sources and admitted derived self context. Each source retains its
authority class; routing-only self context does not enter the catalog. Both
`PerceptLLM` and the worker's `UserPromptLLM` use this contract for `SELF_MODEL`
historical requests. Other routes keep their existing contract.

For example, the model may return:

```json
{"requirements": [
  {"need": "work location", "evidence_index": 0},
  {"need": "financial priorities", "evidence_index": null}
]}
```

Python validates the catalog indices and derives an insufficient decision with
`financial priorities` as the next Adaptive Recall cue. The model cannot attach
an overriding `sufficient=true`. All requirements must have source indices for a
sufficient result. Empty lists, duplicate requirements, invalid indices and extra
fields are rejected. Repeated invalid output uses the existing fail-closed path.

The prompt asks for independent personal requirements, ordinary short search
phrases, and the most useful missing requirement first. It distinguishes given
facts about a new hypothetical scenario from the person's missing priorities,
preferences or communication patterns. The bounds of six requirements and 80
characters per need are registered as provisional, not calibrated. The existing
256/384-token retry budget and bounded recall loop remain in place.

There is no additional specialist, model call, or artifact family. Existing LLM
invocation artifacts preserve raw coverage output and the ordered evidence refs.
Benchmark reporting now also reads the final composed packet: previously, a root
added by canonical-neighborhood expansion could be structurally present yet
still appear in `missing_required_fixture_event_ids` because that report read only
the earlier persisted request packets. The structural oracle itself is unchanged.

Python enforces structural coverage only. The model can still omit a necessary
requirement or cite an irrelevant existing source. It cannot infer semantic truth
from an integer index. Native semantic review is therefore required.

## Frozen learning reuse

The PowerShell wrapper now defaults to reusing `.tmp/latest-benchmark.zip` when
it exists. The Python runner also accepts `--learning-bundle PATH`. The ZIP already
contains the complete learning journals, so no extra learning pass or new
snapshot artifact is required for an existing compatible run.

`benchmarks/learning_checkpoint.py` verifies the ZIP inventory and receipts,
fixture identity/version/digest, model name, and matching result/manifest metadata.
It replays only committed self-memory records under `artifacts/learning`, validates
their hashes and current schemas/policy, and requires the reconstructed snapshot
to match the original result's `snapshot_sha256` exactly. All probe subtrees are
excluded. Original learning files are copied byte for byte into the new run for
continued provenance. The result distinguishes fresh learning from reuse and
records the original learning revision and source bundle hash.

The successful `56b0469` run reconstructs to
`8dc0e88b2d9cbe891dc98cc2d3b0e6f9d3e2a19804532320f6a74575e52d6988`:
14 representations, 15 evidence records, 14 resolutions, and no edges/predictions.
Each probe still resets the dedicated database, reseeds canonical history, and
restores the same frozen snapshot. Consolidation model calls are skipped entirely
on reuse; probe inference still runs normally.

Use `-FreshLearning` when changing learning behavior, the corpus, the model, or
when explicitly evaluating learning variance. Reuse deliberately freezes learning
across code revisions; schema/policy compatibility does not prove that new learning
code would produce the same state. The stored model name cannot detect weights
replaced underneath the same Ollama tag. Incompatible bundles fail rather than
silently starting another expensive learning phase. The first run without a
bundle learns normally. For a different corpus, including holdout, choose a
matching `-LearningBundle` or use `-FreshLearning`.

## Validation and native acceptance

Local validation: 23 pure contract/checkpoint tests, 59 SQL/worker/policy checks,
and 7 existing ZIP handoff tests passed (89 total). The SQL tests use disposable
PGlite through psycopg with client prepared-statement caching disabled only in
the temporary harness. Native PostgreSQL, Windows PowerShell, and Ollama are not
available in this environment. Repository-wide Ruff and whitespace checks pass.
The constraint audit registers both new bounds and reports five pre-existing
uncovered entries, with no stale, mismatched, or invalid entries.

Contract tests cover missing requirements reaching recall before approval,
invalid-index retries in both Composer paths, authority catalog ordering and
routing-only exclusion. Checkpoint tests replay latest committed heads in both
journal layouts, reject incomplete/incompatible state, preserve source bytes,
exclude probe state, and check the composed-packet reporting correction. These
tests do not establish native model quality.

From the repository root with the existing dedicated benchmark database and
Ollama configuration:

```powershell
git switch experiment/compact-artifact-journal
git pull --ff-only origin experiment/compact-artifact-journal
.\scripts\run_self_memory_person_fidelity.ps1 -ProbeId @("pf-q005", "pf-q006", "pf-q007")
```

This runs only contextual preference, novel decision, and characteristic
expression probes, reusing the latest ZIP's learning. It packages and stages the
new sharing ZIP as before. Add `-FreshLearning` to rebuild learned state, or pass
`-LearningBundle "path\to\saved-run.zip"` to freeze a specific earlier run.

Success requires valid coverage outputs, retrieval of missing required evidence,
and faithful human-reviewed answers. Inspect the requirement/source mapping and
deficits, not just the structural score. After targeted success, run the full
public corpus and a separately learned holdout to assess regressions. Source
policy exclusions (including `pf-q008`), retrieval paraphrase limitations, and
final-response voice remain separate possible failure mechanisms. No native
passes for this candidate are claimed yet.
