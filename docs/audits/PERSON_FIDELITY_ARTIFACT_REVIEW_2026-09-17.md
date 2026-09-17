# Person-fidelity artifact review — 2026-09-17

**Status:** main integration complete; fresh native benchmark blocked before any
probe executed; retained 2026-09-14 artifacts reviewed. This is a retrospective
review, not a new benchmark result or a completed human fidelity evaluation.

## Integration and fresh-run attempt

[PR #28](https://github.com/wtvr-guy/prometheist/pull/28) was retargeted to `main`,
marked ready, and merged with history preserved as
`ece07690fb0c4efe177acab3994231f0f382e43d`. The merged tree equals reviewed branch
head `8faa622b519e4018d136f4ec95e1393defee35f5`. Constitution 2.0, the benchmark,
retained artifacts, Copilot cleanup, and the recovery fixes are now integrated.
The documentation records verified CI separately from Mike's local-test report.

The [PR CI run](https://github.com/wtvr-guy/prometheist/actions/runs/35181249204)
passed with **378 passed, 13 skipped** in 81.47 seconds; static checks, the
215/215 constraint audit, fixture validation, and deterministic calibration passed.
The [main push CI run](https://github.com/wtvr-guy/prometheist/actions/runs/35181386890)
also passed. These regression results do not replace native model evaluation.

At 2026-09-17T04:18:19Z, with a clean worktree at the merge revision:

| Command | Observed outcome |
| --- | --- |
| `uv run --locked python benchmarks/run_person_fidelity_baseline.py --validate-only` | Exit 0; frozen digest valid, 19 life events, 10 probes, nine dimensions. |
| `uv run --locked python benchmarks/run_person_fidelity_baseline.py` | Exit 1 before database setup or model invocation: `PROMETHEIST_PERSON_FIDELITY_DATABASE_URL` is required. |
| The same runner with `--verify-result benchmarks/results/PERSON-FIDELITY-001_2026-09-14_144915.json` | Exit 1 as designed: full manifest verification requires a schema-v2 result. |

This Linux workspace has no `postgres`, `psql`, `ollama`, `docker`, or `pwsh`
executable on PATH. No database or Ollama configuration was supplied through the
relevant environment variables, and localhost ports 5432 and 11434 refused
connections. There is no connected execution route to Mike's Windows machine.
No benchmark result or run manifest was created by the blocked attempt. The
[attempt record](evidence/PERSON_FIDELITY_ATTEMPT_2026-09-17.json) retains the
commands, exit codes, and diagnostics without credentials.

## Retained evidence and mechanical checks

Reviewed the [original result](../../benchmarks/results/PERSON-FIDELITY-001_2026-09-14_144915.json)
and all files under
[`benchmarks/generated/person_fidelity/20260914T214915Z`](../../benchmarks/generated/person_fidelity/20260914T214915Z/).
The result was captured on Windows with `qwen3:4b-instruct-2507-q4_K_M` at
`bf809798b06db9d0985d84503cd0b7b91d5a3c7a`, not the new main revision.

The fixture SHA-256 remains
`bcb1fb2812f3cb3e8cbaf64cb3b8161dbf087a1c9a7eefb55bcd629ffc21e6d9`.
The original result file SHA-256 is
`0887242a2904a836eb765bce4a7e68c1b9c0e0b685a2c14d49a4c2ab12095058`.
Per-probe receipts and comparisons are retained in the
[mechanical review record](evidence/PERSON_FIDELITY_ARTIFACT_REVIEW_2026-09-17.json).

Read-only checks used `event_artifact_store.iter_event_artifacts`,
`artifact_journal.verify_interaction_chain`, `successful_response_realization`,
and `evaluate_structural_probe` from the merged revision, plus direct comparisons
against the frozen fixture and saved result. No database or model was involved.

| Check | Result |
| --- | --- |
| Raw files inspected | 665 files, 1,001,895 bytes |
| Canonical event/commit pairs | 272 verified; every record has a matching valid commit receipt |
| Seeded fixture records | All 19 exact canonical seed payloads present independently in every probe |
| Probe isolation in retained records | Current prompt matches the fixture; no other probe prompt appears as a user event |
| Interaction chains | All 10 valid and complete; 121 interaction artifacts |
| Stage and final-disposition records | All seven stages in order per probe; one completed final disposition with exact preceding chain receipts |
| LLM invocation records | 31 retained; no recorded invocation error |
| Response consistency | All 10 match the successful invocation, response and persistence stages, canonical response event, and final disposition |
| Evidence consistency | All 10 saved retrieval and response-admission receipts match raw artifacts |
| Frozen structural verdicts | Exactly reproduced: **1/10 passes**, only `pf-q009` |

These checks establish consistency of the checked-in evidence. They do not supply
the missing capture-time schema-v2 inventory or retroactively make the old run a
schema-v2 baseline. No old result, raw artifact, or human-review field was edited.

## Response review

The notes below are model-assisted observations against the frozen evaluator-only
oracles. They are not human scores. All ten original human verdicts remain
`PENDING`, and no response is promoted to training data by this review.

Fixture IDs below abbreviate canonical events; exact UUID references and terminal
hashes remain in the mechanical review record.

| Probe | Evidence delivered / missing | Response assessment |
| --- | --- | --- |
| `pf-q001` — autobiographical meaning | Delivered `e002`; missing `e001` | Preserves the radio-to-engineering connection and graceful-failure rule, but omits the father, hurricane, and shared rescue context that give the origin its meaning. |
| `pf-q002` — relational judgment | Delivered `e004`; missing `e003` | Protects Theo's disclosure choices. Does not establish that he is Mara's younger brother or explain their emotionally important relationship. |
| `pf-q003` — belief change | Delivered `e005,e007`; missing `e006` | Distinguishes the old remote-only preference from the current three-day hybrid preference and the cost of isolation. The independent observed history never reached the responder. |
| `pf-q004` — self-report versus behavior | Delivered `e008,e010`; missing `e009` | Captures low-stakes spontaneity versus deliberate major commitments, but lacks the independent behavioral observation and largely omits Mara's amused self-awareness. |
| `pf-q005` — contextual preference | Delivered unrelated `e004`; missing `e011` | Generalizes from Theo's private recovery to surprises. Misses the crucial distinction between receiving public surprise parties and arranging personal surprises for friends. |
| `pf-q006` — novel job decision | Delivered no life events; missing `e002,e007,e012,e013` | Chooses Offer A, contrary to the supported prediction of Offer B. Invents a preference ordering favoring remote autonomy while missing the current hybrid preference, sufficient financial runway, engineering purpose, and privacy boundary. |
| `pf-q007` — characteristic expression | Delivered no life events; missing `e014,e015` | Reports an unexplained spike but says no action was taken and all systems are nominal. Fails to pause testing and supplies reassurance unsupported by the scenario. |
| `pf-q008` — identity integrity | Delivered `e017`; missing `e016` | Keeps Mara's identity and says to preserve the bad-source claim without granting it authority. The imported event itself was not delivered, so this does not pass the frozen provenance requirement. |
| `pf-q009` — safety and sentimental value | Delivered required `e018,e019`; no missing evidence | Sole structural pass. Retires the unsafe appliance while retaining a safe component or display; consistent with the supported safety/attachment tradeoff, though terse. |
| `pf-q010` — legitimate unknown | No required event; unexpectedly delivered `e014,e017` | Correctly abstains from inventing a teacher. Fails structurally because unrelated life evidence reached the responder despite the explicit no-seeded-evidence expectation. |

## What the artifacts localize

1. **The observed failures precede response transport.** Retrieved reference sets
   equal admitted reference sets for all ten probes. There is no observed loss of
   these refs between the saved memory packets and response invocation. Eight
   probes miss required evidence; the ninth failure admits unrelated evidence to
   an unknown question.
2. **Memory sufficiency often stops too early.** Composer declared memory
   sufficient on `pf-q001` through `pf-q009`, with zero Adaptive Recall rounds.
   That includes the empty packets on `pf-q006` and `pf-q007`, the irrelevant packet
   on `pf-q005`, and the partial packets on the other structural failures.
   Only `pf-q010` attempted Adaptive Recall (one round), then abstained.
3. **Source-policy decisions explain some unavailable evidence.** On `pf-q003`
   and `pf-q008`, the committed policy is `USER_AUTHORED` with only `USER_PROMPT`
   admitted. Required `e006` and `e016` are `SYSTEM_EVENT` records, respectively.
   The frozen expectation and selected scope therefore cannot both be satisfied
   on those executions. This is a question for a controlled policy evaluation,
   not permission to bypass source authority or weaken the frozen oracle.
4. **Plausible prose is insufficient evidence of fidelity.** The clearest semantic
   concerns are the unrelated surprise explanation, the unsupported job choice,
   and the failure to stop unsafe testing. The legitimate-unknown answer shows the
   converse: a sensible response can still fail the evidence contract.

These are observations from the old run, not proof that each failure persists on
the new main revision. A fresh run must precede any improvement claim. No retrieval
weights, prompts, source-policy rules, evidence limits, model, or fixture changed
as part of this review. A future intervention should isolate one measured failure
and preserve separate held-out evaluation.

## Remaining native action

On the configured Windows/PostgreSQL/Ollama host, update to `main`, retain the same
model for comparison, and run the committed wrapper against a dedicated database
whose name contains `benchmark`:

```powershell
git switch main
git pull --ff-only origin main
$env:OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
.\scripts\run_person_fidelity_baseline.ps1 -DatabaseUrl $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL
```

Set `PROMETHEIST_PERSON_FIDELITY_DATABASE_URL` to that host's existing dedicated
benchmark connection first if it is not already configured. The runner resets that
database for every probe. It verifies the newly generated schema-v2 manifest
automatically; a later offline recheck uses the wrapper's `-VerifyResult` option.
Preserve and publish both the new result JSON and its entire raw artifact directory
with `run_manifest.json`, including failures. Those outputs enable the requested
fresh artifact review; the separate human fidelity verdicts then remain to be filled.
