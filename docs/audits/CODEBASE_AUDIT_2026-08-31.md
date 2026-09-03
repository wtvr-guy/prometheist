# Prometheist codebase audit — 2026-08-31

> **Historical audit.** Findings and test counts apply only to the audited revision
> below. PR #23 and the v0.7 consolidation candidate remediate and supersede parts of
> this code state; a final closure audit is still required on one frozen SHA.

**Audited revision:** `65f7c65` (HEAD, `main`/`origin/main`)
**Date/environment:** 2026-08-31, Windows 11 development host, PostgreSQL 16 (native service), Ollama (native, `qwen3:4b-instruct-2507-q4_K_M`)
**Scope:** full repository sweep for bugs, monkeypatches/workarounds, and inconsistencies (not a per-article constitutional walk). Complements, and does not replace, [`CONSTITUTIONAL_AUDIT_2026-08-27.md`](CONSTITUTIONAL_AUDIT_2026-08-27.md), which is the last article-by-article pass at tag `v0.7` (`ad77be3`). **50 commits landed between `ad77be3` and this revision** (a new "v2 percept-to-response pipeline" plus an independent artifact-journal/crash-recovery subsystem — `src/jit_agent/percept_response_runtime.py`, `percept_response_worker.py`, `artifact_journal.py`, `artifact_recovery.py`, `event_artifact_store.py`, `llm_artifact_store.py`, `chat_startup.py`, and a heavily rewritten `cli.py`), none of which existed at the time of the last audit. This audit focuses there, plus a full-repo grep sweep and fresh empirical tool/test runs.

**Method:** direct code reading, `git log`/`git diff` scoping, full-repo pattern search for common smells (broad excepts, TODO/FIXME, dead code, `noqa`/`type: ignore`), and — critically — **actually executing** the project's own verification tools on this revision rather than trusting prior claims or docstrings: `uv run ruff check .`, `uv run python scripts/audit_constraints.py --fail-unregistered`, and `uv run pytest -q` (full suite, real Ollama + real Postgres, 281 tests). All findings below with a specific file/line were re-verified by opening that file; no finding is copied from an unverified subagent claim (two subagent-proposed findings were investigated and discarded as false positives — see "Discarded findings" at the end).

## Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | `pytest -q` on HEAD has **8 real failures out of 281 tests**, not the "40s clean pass" recorded in repo build notes | **CRITICAL** | confirmed, reproducible |
| 2 | Artifact-journal filenames are unbounded and routinely exceed Windows path-length limits, crashing real interactions deterministically | **CRITICAL** | confirmed, reproducible, root-caused |
| 3 | `scripts/audit_constraints.py --fail-unregistered` (a required, blocking CI gate) currently fails: 3 unregistered numeric constants | **HIGH** | confirmed, reproducible |
| 4 | User-facing final-response temperature silently changed from deterministic (`0`) to non-deterministic default (`0.65`), contradicting its own test's name/contract and Article 9, with no constraint registration or doc update | **HIGH** | confirmed |
| 5 | System-prompt/test drift: `test_final_responder_gets_user_evidence_authority_and_no_trace` asserts wording no longer present in the shipped prompt | **MEDIUM** | confirmed |
| 6 | Dead/duplicated code: `percept_response_runtime.execute_claimed_percept_step` is unused (superseded by `percept_response_worker._execute_claimed_user_prompt_step`), risking silent logic drift between the two | **MEDIUM** | confirmed |
| 7 | `_execute_stage`'s final (`PERSIST_RESULT`) branch has no explicit stage guard — it is an implicit fallthrough after five `if stage is X:` checks | **MEDIUM** | confirmed |
| 8 | `artifact_recovery.resume_interaction_from_artifacts` swallows **all** `RuntimeError`s from `_stage_result`, not just the intended "stage incomplete" case | **LOW/MEDIUM** | confirmed |
| 9 | `chat_startup.py` builds a DELETE statement with an f-string table name (`# noqa: S608`) | **LOW (informational)** | confirmed, not exploitable today |
| 10 | Repo memory / historical notes are already stale relative to current HEAD | **LOW (housekeeping)** | confirmed |

No article-level constitutional `FAIL` is asserted here (that classification is the constitutional audit's job); however, Finding 1 and Finding 4 are directly relevant to Article 9 (deterministic control) and Article 25 (regression evidence must be current), and Finding 3 is a direct, active breach of the Article 24 governance gate.

---

## Finding 1 — The test suite does not currently pass (CRITICAL)

**Evidence:** `uv run pytest -q` on `65f7c65`, this machine, real Ollama + real Postgres test DB:

```
FAILED tests/test_acceptance_conversation_continuity.py::test_stateless_four_turn_continuity_survives_sessions_and_distractors
FAILED tests/test_acceptance_restart.py::test_cross_process_restart_recalls_randomized_fact[The codename for Project Oriole is {fact}.-What codename did I give Project Oriole?]
FAILED tests/test_acceptance_restart.py::test_cross_process_restart_recalls_randomized_fact[The launch code for Project Falcon is {fact}.-What launch code did I give for Project Falcon?]
FAILED tests/test_acceptance_restart.py::test_cross_process_memory_analysis_recalls_without_hidden_transcript
FAILED tests/test_constraint_governance.py::test_every_behavioral_numeric_constraint_is_registered_and_classified
FAILED tests/test_cross_conversation_memory.py::test_cross_conversation_cross_process_memory_recall
FAILED tests/test_interactive_evidence_hardening.py::test_final_responder_gets_user_evidence_authority_and_no_trace
FAILED tests/test_llm.py::test_user_facing_answers_use_a_deterministic_structured_envelope
8 failed, 273 passed in 195.61s (0:03:15)
```

Re-running the two individually-checked failures (`test_cross_process_restart_recalls_randomized_fact[...Oriole...]`, twice) reproduced the **same exception at the same stage both times** — this is a deterministic defect, not test flakiness or an environment fluke. Five of the eight failures (all the real-Ollama acceptance/cross-process tests) share one root cause: see Finding 2. Repo memory (`/memories/repo/jit_agent_prototype.md`) currently states "Full acceptance test suite ... passes in ~40s total" — that note is now **stale** and should be corrected (see Finding 10).

**Why it matters:** `[docs/audits/CONSTITUTIONAL_AUDIT_2026-08-27.md](CONSTITUTIONAL_AUDIT_2026-08-27.md)` (Article 25) asserted CI/local test evidence was clean at `ad77be3`. The 50 commits since then shipped a large new subsystem without the acceptance suite actually being kept green. Whatever the CI-hosted `ubuntu-latest` runner shows, the **native, real-Ollama acceptance path this project relies on as its primary reality check (Article 25) is currently broken on the reference development machine.**

**Severity:** CRITICAL — a broken acceptance suite means the "just-in-time memory" contract this whole system exists to prove is not currently verified to work end-to-end.

---

## Finding 2 — Artifact-journal filenames overflow Windows path-length limits (CRITICAL, root-caused)

**Evidence (exact, reproduced twice):**

```
FileNotFoundError: [Errno 2] No such file or directory:
'C:\Users\...\pytest-5\test_cross_process_restart_rec0\prometheist-artifacts\interactions\
65ca5ef3-0fc6-58fc-97f2-546fb154bfb7\.000005-llm-invocation-V2_COMPOSE_MEMORY-
a9f354c2-ac45-511f-9ea3-d3fc11bcd507-0-V2_MEMORY_SUFFICIENCY_USER_PROMPT.json.9324.tmp'
```
raised from [`artifact_journal._atomic_write_json`](../../src/jit_agent/artifact_journal.py) at the `temporary.open("wb")` call — **immediately after** `path.parent.mkdir(parents=True, exist_ok=True)` on the previous line. The parent directory is not missing (mkdir with `exist_ok=True` would not raise); the file itself cannot be created.

**Root cause:** [`llm_artifact_store.write_llm_invocation`](../../src/jit_agent/llm_artifact_store.py#L33) builds the artifact idempotency key as:

```python
artifact_key=f"llm-invocation:{stage}:{claim_id}:{invocation_index}:{kind}"
```

`stage` and `kind` are full enum *value* strings (e.g. `V2_COMPOSE_MEMORY`, `V2_MEMORY_SUFFICIENCY_USER_PROMPT`), and `claim_id` is a full UUID (36 chars). [`artifact_journal.write_interaction_artifact`](../../src/jit_agent/artifact_journal.py#L128) turns this into a filename `f"{sequence:06d}-{_safe_key(artifact_key)}.json"`, and `_atomic_write_json` further wraps it as a temp file `f".{path.name}.{os.getpid()}.tmp"`. The resulting filename alone is on the order of 120–140 characters; combined with `artifact_root()/interactions/<interaction-uuid>/` (itself ~90+ characters even under a short temp root, and every current developer/user path in this repo — including the repo's own OneDrive-nested checkout location — adds further nesting), the **full path routinely exceeds Windows' classic 260-character `MAX_PATH` limit**, which is still the default unless `LongPathsEnabled` is explicitly turned on in the registry (it is not configured by this repo's setup docs or by Python's default install). `os.open`/`io.open` on Windows surface this specific failure mode as `FileNotFoundError`, which is exactly what was observed — not a permissions or missing-directory problem.

This is not test-environment noise: `PROMETHEIST_ARTIFACT_ROOT` defaults to `.prometheist/artifacts` under the *current working directory* in real (non-test) usage — i.e. it fires identically for a real `prometheist chat` session run from this repo's own path, or any user path with moderate nesting.

**Why it matters:** This is Article 30's entire subsystem ("meaningful state transitions require independent artifact durability") silently failing closed in the worst possible way for a Windows-first, local-first project (per `docs/architecture/LOCAL_FIRST_PORTABILITY.md`, Windows is an explicitly supported native target, not an afterthought). Every capability round and every `assess_memory_sufficiency`/`compose`/`respond` LLM call after the first few artifact writes in an interaction is at risk of crashing the interaction outright with an opaque `FileNotFoundError`, five stack frames removed from any Windows-path-length explanation, surfaced to the user as `PROMETHEIST_TURN_FAILED=RuntimeError: percept worker failed at stage V2_COMPOSE_MEMORY with exit code 1`.

**Suggested remediation (not applied — read-only audit):**
- Shorten `artifact_key`/filename construction: use a short deterministic hash (e.g. first 12–16 hex chars of `uuid5`/sha256 of the full key) instead of concatenating full enum names and full UUIDs into the filename.
- Or: prefix all artifact paths with the Windows extended-length prefix (`\\?\`) when running on Windows, which lifts `MAX_PATH` to ~32,767 chars (still leaves non-Windows-extended-path tools like Explorer/some antivirus unable to read the files, so shortening the name is the more portable fix).
- Add a regression test that specifically exercises a full interaction on Windows-length-sensitive paths (e.g. assert `len(str(target_path)) < 240` inside `_atomic_write_json`, fail closed with a clear diagnostic instead of a raw `FileNotFoundError`).

**Severity:** CRITICAL — directly causes Finding 1's five acceptance-test crashes and will crash real interactive usage under normal Windows conditions once enough LLM invocations accumulate in one interaction.

---

## Finding 3 — Blocking CI gate `audit_constraints.py --fail-unregistered` currently fails (HIGH)

**Evidence (executed on HEAD):**

```
discovered=178 registered=175 uncovered=3 stale=0 mismatched=0 invalid=0
UNREGISTERED src/jit_agent/llm.py::<module>::_DEFAULT_RESPONSE_TEMPERATURE value=0.65 line=38 ...
UNREGISTERED src/jit_agent/llm.py::<module>::_MIN_RESPONSE_TEMPERATURE value=0.0 line=39 ...
UNREGISTERED src/jit_agent/llm.py::<module>::_MAX_RESPONSE_TEMPERATURE value=2.0 line=40 ...
```
Exit code 1. [`.github/workflows/tests.yml`](../../.github/workflows/tests.yml#L56) runs this exact command with no `continue-on-error`, as the "Run static checks" step, immediately after `ruff check .` (which does pass on HEAD — verified separately). This is the same tool the 2026-08-27 audit cites as authoritative evidence for Article 24 compliance ("`discovered=175 registered=175 uncovered=0 ...`" at `ad77be3`); the new `llm.py` response-temperature constants (Finding 4) were added afterward without a corresponding `benchmarks/constraint_registry.json` entry.

**Why it matters:** This is a real, currently-active CI-breaking regression on `main`, not a hypothetical. Article 24 requires every policy-relevant numeric literal to be classified in the registry before merge; this requirement is currently unmet on the tip of `main`.

**Severity:** HIGH — trivial one-line-per-constant fix, but it means the project's own governance gate is not currently green, and any push/PR against `main` right now would fail static checks.

---

## Finding 4 — User-facing response temperature silently made non-deterministic (HIGH)

**Evidence:** [`llm.py`](../../src/jit_agent/llm.py#L37-L40):

```python
_CONTROL_TEMPERATURE = 0.0
_DEFAULT_RESPONSE_TEMPERATURE = 0.65
_MIN_RESPONSE_TEMPERATURE = 0.0
_MAX_RESPONSE_TEMPERATURE = 2.0
```
`temperature_for_kind()` (line 516) returns `configured_response_temperature()` (default `0.65`, overridable via `PROMETHEIST_RESPONSE_TEMPERATURE`) for user-facing response kinds, and `_CONTROL_TEMPERATURE` (`0.0`) only for internal control-decision kinds. The existing unit test [`test_llm.py::test_user_facing_answers_use_a_deterministic_structured_envelope`](../../tests/test_llm.py#L81) still asserts:

```python
assert payload["options"] == {"num_predict": 256, "temperature": 0}
```
which now fails (`{'temperature': 0.65} != {'temperature': 0}`).

**Why it matters:** Either (a) this is an intentional design change (giving user-facing prose more variety) that was never reflected in its own test, in `benchmarks/constraint_registry.json` (Finding 3), or in any architecture doc found in this audit or the prior docs audit pass — a governance gap under Article 26 ("constitutional changes must be explicit") even if the underlying behavior itself is defensible; or (b) it is an unintentional regression (e.g. a constant meant only for a new capability accidentally became the default for the existing `respond()` path). Either way, the test whose *own name* promises "a deterministic structured envelope" no longer describes the shipped behavior, and nothing in the repository currently reconciles that contradiction.

**Severity:** HIGH — silent, undocumented behavioral drift on a determinism-sensitive path, compounded by breaking its own regression test and the CI governance gate.

---

## Finding 5 — System-prompt/test drift in interactive evidence hardening (MEDIUM)

**Evidence:**
```
AssertionError: assert "A historical USER_PROMPT is direct evidence" in
'You are a fresh disposable Prometheist final response worker. The pre-cognitive
system has already committed that a ...supplied memory or the current percept. Do not expose
internal retrieval mechanics unless the user asks about them.\n'
```
from [`tests/test_interactive_evidence_hardening.py::test_final_responder_gets_user_evidence_authority_and_no_trace`](../../tests/test_interactive_evidence_hardening.py). The v2 final-response system prompt (used by `percept_response_worker`'s response stage) was reworded at some point after this test was written/last passing, and the specific sentence the test checks for ("A historical USER_PROMPT is direct evidence...") is no longer present in the shipped prompt text.

**Why it matters:** This test exists specifically to guard an evidence-authority/no-hidden-trace guarantee that this project has previously spent real debugging effort establishing (see the "conflicting_temporal" root-cause work recorded in repo memory). A test asserting a *specific* safety property silently no longer matching the shipped prompt means that property is currently **unverified**, not merely untested — the prompt may still behave correctly, or may not; nobody has current evidence either way.

**Severity:** MEDIUM — likely just needs the assertion string updated to match the reworded prompt (or the prompt reworded back if the omission was accidental), but until resolved this specific safety guarantee has no passing regression evidence.

---

## Finding 6 — Dead, duplicated stage-execution logic (MEDIUM)

**Evidence:** [`percept_response_runtime.execute_claimed_percept_step`](../../src/jit_agent/percept_response_runtime.py#L777) is a complete, non-trivial function (claims a worker step, dispatches `_execute_stage`, records `ERROR` events on failure, releases the claim) that duplicates what [`percept_response_worker._execute_claimed_user_prompt_step`](../../src/jit_agent/percept_response_worker.py#L371) actually does in production. A repo-wide search (`src/` and `tests/`) found **zero callers** of `execute_claimed_percept_step` outside its own definition.

**Why it matters:** Two independent implementations of the same "claim → execute stage → record error → release" contract is exactly the kind of surface where a future bug fix (e.g. to error-event payload shape, or claim-release ordering) gets applied to the live path (`percept_response_worker.py`) and silently not to the dead one, or vice versa, creating confusing "it was already fixed" archaeology later.

**Severity:** MEDIUM — no runtime impact today (function is unreachable), but real maintenance-risk debt; should be deleted or the two implementations unified.

---

## Finding 7 — Implicit fallthrough for the final pipeline stage (MEDIUM)

**Evidence:** [`percept_response_runtime._execute_stage`](../../src/jit_agent/percept_response_runtime.py#L642-L739) dispatches with five explicit guards:
```python
if stage is PerceptStage.RESOLVE_REFERENCES: ...
if stage is PerceptStage.PRECOGNITIVE: ...
if stage is PerceptStage.EXECUTE_WORK: ...
if stage is PerceptStage.COMPOSE_MEMORY: ...
if stage is PerceptStage.RESPOND: ...
# no `if stage is PerceptStage.PERSIST_RESULT:` guard here — falls straight through:
response = _stage_result(conn, interaction, PerceptStage.RESPOND, scheduler_key)
...
```
`stage` is constructed via `PerceptStage(envelope.step.step_key)` just above, so today this is safe only because `PERSIST_RESULT` happens to be the last member of the `PerceptStage` enum and no sixth stage exists. There is no explicit `else: raise` or final guard.

**Why it matters:** This is exactly the kind of implicit, order-dependent control flow that Article 9 ("system control is deterministic wherever deterministic control is possible") asks the codebase to avoid in spirit, even though the current behavior happens to be correct. Any future stage inserted into the enum after `RESPOND` (rather than appended at the very end) — or any reordering — would silently execute the `PERSIST_RESULT` body for the wrong stage instead of failing loudly.

**Severity:** MEDIUM — latent robustness/maintainability defect, not a currently-observable bug. Cheap fix: `if stage is PerceptStage.PERSIST_RESULT: ... else: raise AssertionError(f"unhandled percept stage {stage}")`.

---

## Finding 8 — Overly broad `except RuntimeError` in artifact recovery (LOW/MEDIUM)

**Evidence:** [`artifact_recovery.resume_interaction_from_artifacts`](../../src/jit_agent/artifact_recovery.py#L308-L312):
```python
for stage in PERCEPT_STAGES:
    try:
        _stage_result(conn, interaction, stage, scheduler_key)
        continue
    except RuntimeError:
        pass
    ...  # re-run this stage via a fresh worker
```
[`_stage_result`](../../src/jit_agent/percept_response_runtime.py#L614-L623) only raises `RuntimeError` today for the single intended "stage incomplete" case (`load_worker_result(...)` returned `None`), so this is **not currently miscategorizing any real error** — but the catch is written broadly enough that it would silently treat *any* future `RuntimeError` from that call path (e.g. a malformed/corrupted worker-result row) as "just re-run it," potentially masking a real data problem behind a redundant re-execution instead of surfacing it.

**Severity:** LOW/MEDIUM — correct today, fragile going forward. Prefer matching on the specific message (`"is incomplete"`) or, better, a dedicated exception type (e.g. `StageIncompleteError`) instead of overloading `RuntimeError`.

---

## Finding 9 — f-string table name in a DELETE statement (LOW, informational)

**Evidence:** [`chat_startup.py`](../../src/jit_agent/chat_startup.py#L48-L51):
```python
cur.execute(
    f"DELETE FROM {table} WHERE scheduler_key = %s",  # noqa: S608
    (scheduler_key,),
)
```
`table` iterates only over the hardcoded module-level tuple `_RESET_TABLES_IN_DELETE_ORDER` (14 literal table names) — there is no user- or LLM-influenced input anywhere near this call. This is **not currently exploitable**; flagged only because the pattern (dynamic SQL + `noqa` suppression) is the kind of thing that becomes a real SQL-injection risk the moment someone refactors this to accept an external `table` argument without re-deriving from the constant tuple. Consider a defensive `assert table in _RESET_TABLES_IN_DELETE_ORDER` at the top of the loop body as cheap insurance, or switch to `psycopg.sql.Identifier(table)` for a fully injection-proof form.

**Severity:** LOW — informational only.

---

## Finding 10 — Stale repo/session memory notes (LOW, housekeeping)

`/memories/repo/jit_agent_prototype.md` currently states: *"Full acceptance test suite (19 tests incl. 2 real-Ollama cross-process restart tests + 5 FTS failure-corpus cases) passes in ~40s total on this machine"* — this is now inaccurate (Finding 1: 8 of 281 current tests fail, ~195s). This note should be corrected the next time this memory file is updated, per this repo's own working-style convention of keeping memory accurate rather than aspirational.

---

## Discarded findings (investigated and rejected as false positives)

In line with this project's own audit discipline ("always run the actual tool," "an initial exploratory pass ... incorrectly flagged ..." — see the 2026-08-27 audit's own corrections), two issues raised during this audit's initial exploration were investigated further and rejected:

1. **"`write_final_disposition_artifact` is never called from the generic orchestrator path"** — initially flagged as a HIGH finding (a hypothetical Article 30 gap). On tracing `percept_response_runtime.handle_percept_in_worker_processes`, it launches `python -m jit_agent.percept_response_worker` as a subprocess **for every stage including `PERSIST_RESULT`**, and `percept_response_worker.main()` calls `artifact_journal.write_final_disposition_artifact(...)` precisely when `stage is PerceptStage.PERSIST_RESULT`. There is no separate code path that skips this. **Rejected — not a real gap.**
2. **A grep for `## Article` in `CONSTITUTION.md` initially returned no matches**, momentarily suggesting Article 30 (cited by a subagent) did not exist. The actual heading level is `### Article N` (verified by reading the file directly); Article 30 ("Meaningful state transitions require independent artifact durability") is real and current. **Rejected as a false "fabricated article" concern.**

---

## Overall assessment

The new v2 percept-response pipeline and independent artifact-journal subsystem are well-architected in intent (hash-linked chains, idempotency keys, fail-closed conflict detection, deterministic worker-step IDs) and mostly match their own design docs (per the parallel docs-consistency pass run for this audit, which found no meaningful drift beyond a missing navigation link). However, the subsystem shipped with **a genuine, deterministic, Windows-specific crash bug (Finding 2)** that currently fails 5 of 8 broken tests, an **active CI-blocking governance-gate regression (Finding 3)**, and **an undocumented determinism regression (Finding 4)** — none of which were caught before merge because, contrary to the repo's own stated practice, the acceptance suite and `audit_constraints.py --fail-unregistered` were evidently not run clean immediately before these 50 commits landed on `main`. Recommended immediate next step: fix Finding 2 (shorten artifact filenames) and Finding 3 (register the three constants, deciding deliberately whether Finding 4's temperature change is intentional), then re-run the full suite to confirm Findings 1/5 clear.
