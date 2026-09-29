# Recover canonical sources through learned self-memory

Date: 2026-09-27. Status: deterministic source-recovery replay passed; native
Composer and response acceptance pending.

## Frozen failure

`SELF-MEMORY-001_2026-09-27_111434.json` ran revision `d971214` on the native Windows
host with `qwen3:4b-instruct-2507-q4_K_M`. Its ZIP verifies with 342 inventoried
artifacts; all three interaction chains are valid and complete. The run scored
0/3 on structural evidence delivery. Commit `4d56250` preserves the failed ZIP.

| Probe | What the trace establishes | Actual final response |
| --- | --- | --- |
| pf-q005 | Composer reports missing surprise evidence. Two recall rounds never recover pf-e011. | Persisted evidence is insufficient. |
| pf-q006 | Composer immediately accepts four derived statements rooted in pf-e007/e012/e013. The engineering principle at pf-e002 is absent. | Offer B |
| pf-q007 | Composer reports missing communication evidence. Recall searches new-scenario details and unrelated values; pf-e014/e015 never arrive. | Persisted evidence is insufficient. |

Learning reuse succeeded. The run used the original 14-representation snapshot
from `56b0469`, hash
`8dc0e88b2d9cbe891dc98cc2d3b0e6f9d3e2a19804532320f6a74575e52d6988`,
without another consolidation pass. The frozen test fixture retains that exact
snapshot, its digest, source bundle hash and origin metadata. Original raw
evidence remains in the historical ZIP.

## Why the prior coverage change was insufficient

Explicit coverage makes a missing slot mechanically visible but cannot make the
model discover a requirement it has omitted. In pf-q006 it essentially relabels
the four supplied self statements as four requirements and cites each one. Every
index is valid, so `missing is None` is true. Python cannot prove that this
model-authored list is semantically complete.

In pf-q005/pf-q007 the verdict is already correctly insufficient. Retrieval,
rather than a malformed Composer response, is the immediate blockage. The first
surprise deficit is `personal history of reaction to unexpected events`; its
original cue word `surprises` has disappeared. The first message deficit asks
for prior unexplained hardware anomalies, although the task needs communication
style applicable to a new situation. The next message deficit does contain
`project message style in final hardware testing context`, but that longer cue
still fails the conservative lexical evidence gate.

The old lexical scoring contains:

```python
coverage = len(unique_query & event_tokens) / len(unique_query)
```

For the surprise question, 14 distinct cue terms give the correct record only
2/14 coverage, or `0.78 * 2/14 = 0.1114` total score. That misses the `0.15`
activation threshold. Theo's privacy record matches four incidental terms and
scores `0.2229`, so it survives instead. This is query-length dilution and lexical
overlap, not a semantic judgment that Theo is more relevant.

Learned memory already contains helpful pointers, but `_search_self_candidates`
allows only `ESTABLISHED` and `CONTESTED` statements into its self-context view.
The surprise preference and engineering principle are `CANDIDATE`. Excluding an
unestablished belief from primary self context is reasonable; failing to use its
stored source pointer for navigation is the missing mechanism.

The previous fallback is also indirect:

```python
return [item.statement for item in packet.items]
```

Those self-context statements become supplemental text queries. `request_memory`
stops at the first nonempty query result. In both failing recall loops, the
surveillance statement retrieves its own source and becomes the focus for the
next association search. That is a valid source of an unrelated value, not the
missing surprise preference or observed message. The bounded no-progress loop
then stops. More Composer output tokens would not fix this source-discovery path.

## Implemented retrieval mechanism

`src/prometheist/self_memory_navigation.py` adds one bounded navigation operation:

1. Search current learned statements and their existing topic tags using an OR
   full-text query. Compound words contribute separate cues: `grid-resilience`
   can activate a `resilience` tag. No phrase-specific synonyms, benchmark IDs,
   expected answers, new embeddings, or additional LLM worker are introduced.
2. Consider at most eight matching representations. `CANDIDATE`, `ESTABLISHED`
   and `CONTESTED` can navigate; rejected/superseded hypotheses cannot. Only the
   imprinted self's records participate. A GIN index supports topic lookup.
3. Follow existing evidence links to exact source events:

   ```sql
   JOIN events e ON e.event_id = (link.payload->>'root_event_id')::uuid
   ```

   This compares stored identifiers. It does not require the source to repeat
   the summary's wording. An indexed link lookup supplies both supporting and
   opposing roots, with their relations preserved.
4. Apply the selected source policy and exclusive history cutoff in SQL before
   candidate truncation. The representation, resolution, link and source must
   all precede that cutoff. Disallowed roots cannot fill the candidate budget.
5. Add exact source text within the existing response packet limit of 20,
   retaining original seeds. Take one root per representation before taking
   another from the same representation. Each candidate reads at most one packet
   worth of roots; returned context and transient root materialization are bounded.

The route runs before the first SELF_MODEL Composer assessment, using the current
question. If recall is needed, it also searches the current deficit before the
legacy association route. Newly found canonical roots receive the existing
one-hop neighbor expansion. Previously added neighbors never seed a recursive
walk. A round that gains source evidence returns it for a fresh Composer check;
otherwise the existing recall stages and no-progress bound remain in force.

The navigation function returns canonical `MemoryEvidence`, not promoted
`SelfContextItem` claims. It never rewrites a representation or its resolution.
Provenance identifies the representation event, resolution event, evidence-link
event, relation and canonical root. The existing Composer stage artifact retains
the trace, including empty attempts. Packet merging now preserves both base and
expansion traces. No separate artifact family is added.

The conservative lexical score and direct-evidence thresholds remain unchanged.
This change uses the learned source index where textual rediscovery was failing.
The eight-candidate bound is explicitly provisional in the constraint registry.

## Measured replay and limits

Production SQL and composition replay now recover all required roots for the
three frozen failures. Surprise and novel-decision roots reach even a Composer
stub that immediately approves. The message replay supplies the exact successive
deficits from the failed run and recovers stated style plus its observed example
within two recall rounds. Expected fixture IDs are used only for test assertions.
They are never provided to production navigation.

Eleven new regression cases cover the frozen failures, compound/tag lookup,
unchanged candidate status, exact source bytes, source restrictions before
truncation, rejected/superseded hypotheses, learned-link cutoff, opposing evidence,
deduplication, saturation and unknown cues. Together with self-memory,
canonical-neighborhood, worker, policy and recall checks, 84 SQL/contract tests
pass. Another 23 pure coverage/checkpoint tests pass. Ruff and whitespace checks
pass. The constraint audit registers the new bound and positive-capacity invariant;
its five previously uncovered entries remain.

SQL tests run through psycopg against disposable PGlite, with client prepared
statement caching disabled only in the temporary development harness. Native
PostgreSQL, Windows and Ollama quality/performance remain unverified here.

The route cannot recover a concept that learning never represented or whose
description/tags do not overlap the cue. A wrong learned topic can activate an
irrelevant source. Packet saturation and candidate ranking can still exclude a
useful source. A current head changed after a historical cutoff is excluded,
rather than reconstructed retrospectively by this ordinary bounded path.
Navigation is not truth and does not repair the model's semantic coverage judgment.

## Native rerun

```powershell
git switch experiment/compact-artifact-journal
git pull --ff-only origin experiment/compact-artifact-journal
.\scripts\run_self_memory_person_fidelity.ps1 -ProbeId @("pf-q005", "pf-q006", "pf-q007")
```

Reuse learning for this experiment: no learning behavior or snapshot schema has
changed. The existing wrapper uses the latest verified ZIP by default. Inspect
the new `SELF_MEMORY_ROOT` routes, final composed source IDs, Composer requirement
assignments, and final answers. After targeted success, test the full public and
holdout corpora and freeze noise/scale families before tuning bounds.

The separate final-response wording experiment addresses pf-q006's missing
explanation. It cannot change retrieved source IDs or the structural evidence
score. Source recovery must be credited only to this navigation mechanism;
response-quality effects require separate native review.
