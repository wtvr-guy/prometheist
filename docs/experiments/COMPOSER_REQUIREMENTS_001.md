# Fixed personal-memory requirements before evidence matching

Date: 2026-09-28. Status: implemented candidate; native acceptance pending.
Parent: `aab8127` on `experiment/compact-artifact-journal`.

## Frozen evidence and honest score boundary

Both supplied ZIPs verify. The targeted run
`SELF-MEMORY-001_2026-09-27_223535.json` (revision `80ec83c`) has 342 inventoried
artifacts and passes 2/3 structural checks: pf-q005 and pf-q006. The full run
`SELF-MEMORY-001_2026-09-27_224831.json` (revision `c070632`) has 804 artifacts and
passes 7/10; pf-q003, pf-q007 and pf-q008 fail. The intervening commits changed
only `.tmp/latest-benchmark.zip`, so the application code is identical in both
runs. The full bundle is preserved in parent `aab8127`.

All probe artifact chains are complete and valid, with no execution/artifact
errors. Both runs reused the same learning snapshot:
`8dc0e88b2d9cbe891dc98cc2d3b0e6f9d3e2a19804532320f6a74575e52d6988`,
containing 14 representations (6 candidate, 8 established), originally learned at
`56b0469`. This change also verifies/restores that exact snapshot from the full ZIP.

These are evidence-delivery scores, not answer-fidelity scores. Manual review
finds additional problems even among structural passes:

- pf-q005 loses the giver/recipient distinction. Canonical evidence says Mara
  dislikes surprise parties aimed at her and enjoys arranging private surprises
  **for friends**. Both answers blur this into appreciating thoughtful surprises.
- pf-q006 chooses B in both runs, but the targeted answer is only one sentence
  and omits the requested tradeoff. Its generation stops normally at 14 tokens.
  The full answer is longer but omits the explicit twelve-month runway versus
  nine-month threshold. Both use response temperature 0.65; the full run retries
  a 256-token length termination and then stops normally after 297 tokens with
  the existing 512-token retry allowance. Explanation completeness remains
  unreliable despite the previous wording change.
- pf-q002 protects Theo's disclosure rights but invents "only he and I know the
  full story" and imports a physical-safety value from an unrelated appliance
  memory. It also switches to assistant commentary about "the user".
- pf-q004 retrieves the relevant self-report, observed planning, and contextual
  reconciliation, but overstates them as a "curated image" and not acting on gut
  feeling in any significant way. Those judgments exceed the source.

## Mechanism failure selected for this experiment

The source-navigation experiment works at its tested boundary: all required roots
reach Composer for pf-q005, pf-q006, and pf-q007. It cannot force good coverage
judgments or faithful final responses.

For pf-q003, Composer receives all three required remote-work memories on its
first call. Its source catalog has the earlier preference at index 0, observed
isolation/low energy/slower judgment at index 1, and the later hybrid preference
and explicitly acknowledged cost of isolation at index 2. Nevertheless it returns:

```json
{"requirements": [
  {"need": "what I used to believe about remote work", "evidence_index": 0},
  {"need": "what I prefer now about remote work", "evidence_index": 2},
  {"need": "what changed my mind about remote work", "evidence_index": null}
]}
```

A recall round adds no needed evidence and the same negative verdict recurs.
The final worker correctly obeys the negative gate and withholds history; the
answer becomes the generic insufficient-evidence response.

For pf-q007, the first catalog contains a surprise-party memory and unrelated
values. Composer invents requirements about trust in others' intentions and being
the center of an event. After recall, both the stated work style and actual
project-channel message are present at catalog indices 5 and 6. The observed
message names a checksum anomaly and stops deployment pending an explanation.
Composer still marks "personal reaction to unexplained technical events" missing,
while retaining an unrelated reducing-suffering requirement. There are three
Composer calls and two recall rounds in both runs.

For pf-q009, the sentimental attachment and explicit safety exception are present
before the first Composer call. It nevertheless asks for a remembered response
or decision about fire risk, then eventually approves after three Composer calls
and two recalls. The full probe takes 266.0 seconds and expands to 12 canonical
memories. An extra requirement-planning call is therefore a cost to measure, not
an assumed speed improvement.

The hypothesis: generating requirements while reading the candidate evidence
anchors requirements to incidental topics and encourages treating a predicted
answer as a missing remembered fact. Separating current-only requirement selection
from source matching should reduce this drift. Allowing joint source support also
represents causal/temporal comparisons more naturally than one source per slot.
This is not yet proof that either model decision will be semantically correct.

## Changed contract

`PerceptStage.MEMORY_REQUIREMENTS` is a separate guarded stage after evidence
policy. For SELF_MODEL only, `PerceptLLM.plan_memory_requirements` receives the
current request and an empty quarantined-evidence channel. It produces a typed,
immutable `MemoryRequirements` list. It cannot inspect retrieved text, self
representations, work results, or prior model dialogue. Other source scopes skip
this model call. The requirement result uses the existing durable stage journal
and is recovered without repeating inference after publication.

Composer now receives that exact committed list on every recall round. It returns
only a mapping of requirement indices to source indices, for example:

```json
{"coverage": [
  {"requirement_index": 0, "evidence_indices": [0]},
  {"requirement_index": 1, "evidence_indices": [2]},
  {"requirement_index": 2, "evidence_indices": [1, 2]}
]}
```

This is an illustrative mapping, not a captured native result. Multiple memories
can jointly supply one requirement. `[]` means missing support. Python checks:

```python
if set(by_requirement) != set(range(len(requirements.requirements))):
    raise ValueError("coverage must match every fixed requirement exactly once")
```

Duplicate slots, invented slots, missing slots, invalid/duplicate source indices,
and attempted requirement rewrites fail validation. The first empty slot's
**committed** need becomes the recall cue. Composer cannot change which facts it
is trying to establish after seeing a new packet. It still must determine whether
particular sources support the requirements; Python cannot infer that from indices.

The six-requirement and 80-character bounds remain unchanged and provisional.
The new planner uses the existing 256/384-token constrained-decision retry pattern
as a provisional empirical budget: at most two attempts, with no new concurrency.
Coverage retains the same token allowances and bounded recall policy. Support
list length is structurally bounded by catalog size; slot count equals plan size.
No canonical text, source policy, retrieval scoring, response prompt, learned
state, or benchmark oracle changes. Requirements are retained for audit in the
Composer package but are not added to the final responder's evidence prompt.

The stage-to-role guard permits requirement inference only in its new stage;
Composer cannot call it. The interaction protocol advances from v11 to v12 so an
unfinished older stage graph is rejected instead of silently reinterpreted. This
does not invalidate the separately verified learning snapshot. The non-user
situation pipeline continues using its existing generic sufficiency contract.

## Remaining independent failures

pf-q008 selects USER_AUTHORED, excluding imported PERCEPT_OBSERVATION pf-e016.
It retrieves the corrective user statement pf-e017, then twice produces:

```json
{"sufficient": true, "memory_deficit": "user's statement about real name being Nadia Cross"}
```

`MemorySufficiencyDecision.validate_contract` rejects that contradictory control
output, so the runtime withholds history without performing recall. Correcting the
multi-source authority policy and the generic decision schema is a separate
experiment. This patch does not claim to fix pf-q008.

The response distortions above require separate work on evidence relevance and
faithful realization. Structural 7/10 does not establish absence of semantic
regressions. A successful Composer result does not excuse an invented final claim.

## Verification and next native run

115 tests pass: 45 pure coverage/planning/checkpoint checks, 68 existing retrieval,
worker, policy, transport and recovery regressions, and 2 new database-backed
stage-handoff checks using chat and raw-generate transports. The database tests
use disposable PGlite with psycopg prepared-statement caching disabled only in the
temporary test harness. Native Ollama/Windows inference has not been run here.
Ruff and whitespace checks pass. The constraint audit has five pre-existing
uncovered entries and zero stale, mismatched or invalid entries.

The focused comparison is pf-q003 and pf-q007 for false rejection, and pf-q009
for unnecessary recall. From the repository root:

```powershell
git switch experiment/compact-artifact-journal
git pull --ff-only origin experiment/compact-artifact-journal
.\scripts\run_self_memory_person_fidelity.ps1 -ProbeId @("pf-q003", "pf-q007", "pf-q009")
```

The wrapper reuses learning from `.tmp/latest-benchmark.zip`. No fresh learning is
needed for this change. Success requires relevant current-only requirements,
correct source mappings, faithful answers and acceptable total latency; it is not
established by deterministic tests alone. Inspect the new V2_MEMORY_REQUIREMENTS
stage and subsequent coverage maps. After the targeted comparison, all SELF_MODEL
probes (001–007 and 009) and then the full suite/holdout remain regression gates.
