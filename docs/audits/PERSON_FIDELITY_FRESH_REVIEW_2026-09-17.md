# Fresh person-fidelity baseline review — 2026-09-17

**Verdict:** the native run completed and its full artifact bundle verifies after
repairing a reversible line-ending conversion in Git transport. The frozen
structural score remains **1/10**. The same evidence-selection failures recur on
the current baseline; passing regression tests did not resolve them.

## Run and evidence identity

- Result: [`PERSON-FIDELITY-001_2026-09-16_215839.json`](../../benchmarks/results/PERSON-FIDELITY-001_2026-09-16_215839.json).
- UTC capture: `2026-09-17T04:58:39.337366+00:00`. The filename uses the native host's local date/time.
- Tested revision: `9f1cc3c5c9c2085af8cd41008b8ad0c0ce329af7`.
- Evidence published by Mike in `5a6efd2c0e48b00c9a675243d0b7f686a91f034c`.
- Environment: Windows 11, Python 3.12.10, `qwen3:4b-instruct-2507-q4_K_M`, dedicated `prometheist_fidelity_benchmark` database.
- Frozen fixture: `bcb1fb2812f3cb3e8cbaf64cb3b8161dbf087a1c9a7eefb55bcd629ffc21e6d9`, unchanged.
- Raw bundle: [`20260917T045839Z`](../../benchmarks/generated/person_fidelity/20260917T045839Z/).
- [Mechanical checks and deterministic replay](evidence/PERSON_FIDELITY_FRESH_REVIEW_2026-09-17.json).

## Sharing defect found and corrected

The first offline verification of the pushed result failed with
`artifact manifest SHA-256 does not match the result receipt`. The native
summary/manifest writer used text mode with platform-dependent newlines. The
uploaded summary had CRLF endings; Git contained LF copies of both the summary
and manifest. Their parsed JSON content was unchanged.

The manifest in commit `5a6efd2` had SHA-256
`1cacbac3b46d673f6122683f2102f0ed298ccc1187fffa91ea0f032ac7e0767a`.
Restoring only CRLF endings produces exactly the existing result receipt:
`82e3bec31f086d76e3887e8f08e4fdd39318d90e2b58fa86126e1217cc664b36`,
455,260 bytes. Every one of the 665 raw event/interaction files already matched
its recorded byte hash and size; none needed repair.

This correction restores the manifest's original recorded bytes and the exact
summary bytes supplied in Mike's attachment. It does not recalculate receipts
to bless different content. The restored summary SHA-256 is
`54a62e193dc74ef6e6ddfd8f1acf26b879b42a0fa51b6dfda50fe7617fcd78e1`.
The normalized versions remain available in Git history. No JSON values, natural
responses, verdicts, canonical events, or invocation payloads were changed.

The accompanying fix:

- writes future results and manifests in exclusive binary mode as UTF-8 with LF,
  matching the existing raw-journal writers;
- disables Git text conversion for benchmark results, generated evidence, and
  runtime artifacts, preserving historical CRLF and LF bytes across hosts;
- tests UTF-8/LF output under simulated Windows text defaults and tests Git
  staging/checkout with automatic line-ending conversion enabled and disabled;
- adds a CI gate that verifies this complete retained schema-v2 bundle after checkout.

These changes repair evidence portability. They do not change retrieval,
Composer, response policy, inference prompts, the model, or the frozen fixture.

## Independent verification

The production offline verifier now returns **`VALID_COMPLETE`**:

| Check | Result |
| --- | --- |
| Raw inventory | 665 files, 1,001,161 bytes; exact file set, sizes, and hashes match |
| Canonical event mirrors | 272 event/commit pairs verified |
| Interaction journals | 10 valid, complete chains; zero missing or invalid interactions |
| Stage boundaries | All seven stages and one completed final disposition per probe |
| Model calls | 31 recorded invocations; no recorded invocation error |
| Responses | All ten agree across successful model output, response stage, persistence stage, canonical event, and final disposition |
| Seeded life record | All 19 exact fixture events independently present per probe |
| Evidence receipts | Retrieved/admitted refs match raw records and the summary on all ten probes |
| Structural outcomes | Recomputed exactly: `pf-q009` passes; the other nine fail |

All ten structural-evidence records and all ten retrieval records are identical
to the 2026-09-14 run. Three response texts are identical (`q001`, `q009`, `q010`);
the other seven vary in wording. The repeated evidence pattern is stronger
evidence of a stable selection problem than the aggregate score alone.

## Per-probe response review

These are model-assisted observations against the frozen oracles, not substituted
human scores. The original human-review fields remain `PENDING`, and raw outputs
remain `UNREVIEWED_RAW_EVIDENCE`.

| Probe | Delivered / missing fixture evidence | Response assessment |
| --- | --- | --- |
| `q001`: engineering origin | `e002` / missing `e001` | Correctly links engineering to a radio experience and graceful failure, but omits the father and hurricane context that supply its personal meaning. |
| `q002`: Theo's privacy | `e004` / missing `e003` | Protects Theo's control over disclosure; misses his role as Mara's younger brother and the history behind her protectiveness. |
| `q003`: remote-work belief change | `e005,e007` / missing `e006` | Gives the supported old-to-current preference and isolation rationale, but receives no independent observation of the intervening behavior. |
| `q004`: spontaneity | `e008,e010` / missing `e009` | Mostly captures contextual deliberation, but lacks the observed decision record and ends with an overbroad claim that Mara is spontaneous by nature. |
| `q005`: surprises | Unrelated `e004` / missing `e011` | Explains Theo's privacy instead of Mara's actual distinction between receiving public surprise parties and creating thoughtful private surprises for friends. |
| `q006`: job choice | No life events / missing `e002,e007,e012,e013` | Chooses Offer A. The fixture supports Offer B given the financial runway, hybrid preference, privacy boundary, and engineering values. This is a substantive failure, not merely missing provenance. |
| `q007`: characteristic project message | No life events / missing `e014,e015` | Produces generic diagnostics, speculates about fault sources, and never explicitly pauses testing. Misses the supported safety decision and communication pattern. |
| `q008`: identity integrity | `e017` / missing `e016` | Rejects the false rename and retains Mara's identity, but does not explicitly preserve the bad-source event. The imported event was excluded from its evidence. |
| `q009`: espresso-maker decision | Required `e018,e019` / none missing | Sole structural pass. Retires the unsafe appliance while preserving a safe component or display, consistent with the supported safety/attachment tradeoff. |
| `q010`: unknown teacher | No required evidence; unrelated `e014,e017` admitted | Correctly acknowledges that the teacher's name is unknown. Structural failure comes from irrelevant evidence admission, not a fabricated name. |

Thus **1/10 structural passes does not mean nine wholly wrong answers**. It does
mean the required evidence contract fails on nine probes, with clear semantic
failures among them. No semantic aggregate is substituted for the pending reviews.

## Where the failures occur

### 1. Lexical selection loses relevant context and admits common-word matches

Replaying the unchanged deterministic scorer over **all 19 canonical life
events**, with each probe's recorded initial cue and source policy, reproduces
every initial memory packet exactly. The observed omissions therefore remain
even when every fixture event is supplied to the scorer. The six-item packet
limit was not reached on any probe.

The current total score is dominated here by query-token coverage, weighted by
0.78, with a minimum total of 0.15. No entity, time, or conversation cue contributed
to these initial packets. Concrete failures:

- `q005`: the correct surprise record scores **0.11143** from `like,surprise`, below
  the cutoff. Theo's unrelated recovery record scores **0.22286** from
  `answer,give,than,would` and is selected.
- `q006`: the 33 distinct query tokens dilute overlap with each individual life
  event. The best record, the current hybrid preference, scores **0.11818**, so
  all records are excluded.
- `q007`: the best event score is **0.039**, below the cutoff; no life evidence is
  delivered to the style task.
- `q010`: the word `name` alone gives both the identity record and the writing-style
  record **0.26**, so unrelated evidence is admitted to the unknown question.

The trace field `candidates_considered` counts candidates surviving the scorer's
source/score filters. A zero there does not establish that the database returned
no rows. The replay above avoids relying on that misleading interpretation.

### 2. Composer treats missing personal evidence as sufficient

For `q001` through `q009`, Composer returned `sufficient=true` on its first call;
Adaptive Recall ran zero rounds. This includes the empty packets for job choice
and writing style, and the irrelevant Theo packet for surprises. Consequently,
the existing stronger retrieval path never had an opportunity to recover their
missing evidence.

The current prompt correctly permits general questions to be answered without
historical memory, but the observed worker applies that allowance to questions
whose answer depends on Mara's prior preferences, values, or voice. The runtime
then follows that decision. This is a separate failure from the lexical scores.

Only `q010` received `sufficient=false`, attempted one Adaptive Recall round, made
no progress in event IDs, and stopped with an explicit deficit. The final responder
then abstained correctly while still receiving the irrelevant prior packet.

### 3. Source-policy selection excludes required observations

For `q003` and `q008`, the source-policy worker selected `USER_AUTHORED`; application
code consequently allowed only `USER_PROMPT` records. Required `e006` (observed
isolation) and `e016` (the untrusted import) are `SYSTEM_EVENT` records. They are
ineligible under those committed decisions regardless of retrieval rank.

The allowlist is enforcing the selected policy. The issue to evaluate is the
policy decision for personal-history synthesis, while preserving explicit user
source restrictions and keeping untrusted content outside instruction authority.
The benchmark oracle is not a runtime instruction to bypass that boundary.

## Additional incomplete attempt

The push also preserves `20260917T045500Z`: 244 raw files, 103 verified event/commit
pairs, and four valid interaction-chain prefixes. Probes `q001`–`q003` have final
dispositions. `q004` ends after `V2_RESOLVE_REFERENCES` and has no final disposition.
There is no run manifest or compact result for that attempt. The retained records
do not establish why execution stopped; it is kept as incomplete evidence and
is not combined with the completed run's score.

## Next controlled work

The current evidence supports three separate experiments: lexical relevance that
resists common-word matches and long-prompt dilution; Composer discrimination of
general answerability from personal-evidence sufficiency; and source-policy
selection for mixed personal evidence. Change one mechanism at a time, keep this
fixture/model/budget baseline fixed, and freeze separate held-out cases before
selecting an improvement. Do not lower a cutoff or edit expected evidence merely
to make these ten probes pass.

The immediate transport defect is corrected in this change. The cognitive failure
patterns are now localized and preserved as the negative baseline for subsequent
controlled work. The native benchmark does not need repeating to recover the
original manifest, whose restored bytes already match its recorded hash.

## Validation of the transport correction

- Benchmark contract tests: **21 passed**, including Windows text-output and Git
  staging/checkout byte-preservation regressions.
- Full schema-v2 artifact verification: **`VALID_COMPLETE`**.
- Ruff and `git diff --check`: passed.
- Raw event/interaction files and fixture content: unchanged.

CI additionally verifies the retained bundle from a fresh checkout, including its
manifest receipt. Native cognition was executed by Mike at the recorded revision;
this review did not rerun Ollama or replace the result with a simulated run.
