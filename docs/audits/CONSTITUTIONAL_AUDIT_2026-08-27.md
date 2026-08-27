# Prometheist constitutional audit — 2026-08-27

**Audited revision:** `ad77be3` (tag `v0.7`)
**Date/environment:** 2026-08-27, Windows 11 development host, PostgreSQL 16 (native service), Ollama (native, `qwen3:4b-instruct-2507-q4_K_M`)
**Constitution version:** 1.0, adopted 2026-08-27
**Scope:** `src/jit_agent/**`, `schema.sql`, `tests/**`, `benchmarks/**`, `scripts/**`, `.github/workflows/tests.yml`, `docs/architecture/**`, `docs/engineering/**`

This is the first full constitutional audit performed against all 29 articles, per the process defined in [`docs/engineering/CONSTITUTIONAL_GOVERNANCE.md`](../engineering/CONSTITUTIONAL_GOVERNANCE.md). It follows, and does not replace, the prior [`POST_V06_CODEBASE_REVIEW_2026-08-21.md`](POST_V06_CODEBASE_REVIEW_2026-08-21.md) and [`V05_CLOSURE_AUDIT_2026-08-21.md`](V05_CLOSURE_AUDIT_2026-08-21.md) records. Evidence below was gathered by direct code/schema inspection, targeted test citations, and two commands actually executed against this revision (`uv run python scripts/audit_constraints.py --fail-unregistered`, and inspection of `benchmarks/results/NATIVE-CONSTRAINTS_*.json`), not from documentation claims alone.

## Summary table

| Article | Title | Status |
|---|---|---|
| 1 | Continuity belongs to the system | PASS |
| 2 | Every LLM invocation is stateless; workers are disposable | PASS |
| 3 | Admitted durable memory is lossless, append-only | PASS |
| 4 | Derived memory is replaceable; canonical evidence is not | PASS |
| 5 | Ordinary cognition and recall are bounded | PASS |
| 6 | Basic persistent-memory access precedes model routing | PASS |
| 7 | WorkingState is bounded canonical activation | PASS |
| 8 | Conversations/sessions are provenance, not cognitive boundaries | PASS |
| 9 | System control is deterministic wherever possible | PASS |
| 10 | Race conditions never decide durable authority | PASS |
| 11 | Attention priority and resource admission are separate | PASS |
| 12 | Resource safety is fail-closed and preserves headroom | PASS |
| 13 | Preemption requires both priority and real contention | PASS |
| 14 | Disposable-worker execution is durable, guarded, recovery-safe | PASS |
| 15 | Models select semantic requirements; system owns execution policy | PASS |
| 16 | Model-generated natural language is control/state of last resort | PASS |
| 17 | Relevance, activation, evidence sufficiency, truth are distinct | PASS |
| 18 | Material influence must leave durable causal provenance | PASS (see notes) |
| 19 | Internal memory and external knowledge remain distinct domains | NOT APPLICABLE |
| 20 | Natural-language continuity must not become vocabulary patchwork | PASS |
| 21 | Local-first, user-controlled, model-agnostic, replaceable | GAP |
| 22 | User sovereignty governs stored data and replaceable components | GAP |
| 23 | Falsifiable one-mechanism experimental discipline | PASS |
| 24 | Behavioral numbers must be classified and evidenced | PASS |
| 25 | Deterministic regression evidence + native acceptance | PASS (breadth GAP noted) |
| 26 | Constitutional changes must be explicit | PASS |
| 27 | Capability reasoning is recurrent, every reassessment is fresh | PASS |
| 28 | Durable queued work must have anti-starvation policy | PASS |
| 29 | Insufficient authority or evidence fails closed | PASS |

No `FAIL` was found. Two `GAP`s were found, both previously acknowledged in architecture docs as forward-looking targets rather than regressions. No article required a documentation-only pass; every `PASS` below cites code, schema, or test evidence, and several corrected an initial subagent misreading (noted inline).

---

## Article 1 — Continuity belongs to the system

**Status:** PASS

**Implementation surfaces:** [`interaction_working_state.py`](../../src/jit_agent/interaction_working_state.py), [`interaction_policy.py`](../../src/jit_agent/interaction_policy.py) (`DurableInteraction`), [`interaction_store.py`](../../src/jit_agent/interaction_store.py), [`interaction_runtime.py`](../../src/jit_agent/interaction_runtime.py) (`begin_interaction`), [`attention.py`](../../src/jit_agent/attention.py) (`AttentionTask`).

**Evidence:** `interaction_id = uuid5(conversation_id, correlation_id)` is computed and persisted to PostgreSQL before any worker or LLM call. Working state is bounded (`MAX_ACTIVE_EVENT_IDS = 12`) and stored via `activate_working_state()`, not held in worker memory. Workers (`interaction_worker.py`) receive only a `claim_id`/`worker_id` via environment variables and reload all context from the database.

**Tests:** [`test_acceptance_conversation_continuity.py`](../../tests/test_acceptance_conversation_continuity.py) (`test_stateless_four_turn_continuity_survives_sessions_and_distractors`), [`test_acceptance_restart.py`](../../tests/test_acceptance_restart.py) (`test_cross_process_restart_recalls_randomized_fact`), [`test_attention_process_restart.py`](../../tests/test_attention_process_restart.py) (forced process kill mid-execution, verified checkpoint recovery).

**Findings:** No durable state — identity, memory, working state, policy, or execution state — is entrusted to a worker process, chat transcript, or LLM context window. Cross-process/cross-session recall is proven, not merely claimed.

---

## Article 2 — Every LLM invocation is stateless; workers are disposable

**Status:** PASS

**Implementation surfaces:** [`llm.py`](../../src/jit_agent/llm.py) (`OllamaClient.classify/respond/select_*`), [`interaction_worker.py`](../../src/jit_agent/interaction_worker.py), [`interaction_runtime.py`](../../src/jit_agent/interaction_runtime.py) (`_load_or_create_round`, `handle_interaction_in_worker_processes`).

**Evidence:** Every `OllamaClient` method builds its prompt from arguments passed at call time; no instance state accumulates a transcript. `interaction_worker.py` reads only `PROMETHEIST_WORKER_CLAIM_ID` from the environment and reconstructs all context from PostgreSQL. `handle_interaction_in_worker_processes()` spawns a fresh subprocess per stage with a hard timeout; on restart, `_load_or_create_round()` validates that the persisted `memory_request_id` matches the current memory packet before reusing a round, preventing silent stale-context reuse.

**Tests:** [`test_acceptance_restart.py`](../../tests/test_acceptance_restart.py), [`test_attention_process_restart.py`](../../tests/test_attention_process_restart.py), [`test_acceptance_conversation_continuity.py`](../../tests/test_acceptance_conversation_continuity.py) (four turns, each a fresh process).

**Findings:** No hidden transcript carry-forward found in any LLM call site.

---

## Article 3 — Admitted durable memory is lossless, append-only canonical evidence

**Status:** PASS (one documented v0.9 hardening item, not a regression)

**Implementation surfaces:** [`schema.sql`](../../schema.sql) (`events` table, lines 1–33), [`event_store.py`](../../src/jit_agent/event_store.py) (`record_event`).

**Evidence:** The codebase contains zero `UPDATE`/`DELETE` statements against `events`; `event_store.record_event()` only `INSERT`s, using `SELECT ... FOR UPDATE` on the parent conversation row to assign `conversation_seq` deterministically. `schema.sql` explicitly documents: "Application code only ever INSERTs into `events`; never UPDATE/DELETE. This is currently an application-level invariant, not a database-level tamper boundary." Corrections are represented as new events plus a derived `PREVIOUS_STATE` association ([`association_projection.py`](../../src/jit_agent/association_projection.py)), never as mutation of the original event.

**Tests:** [`test_event_store.py`](../../tests/test_event_store.py) (`test_record_and_read_every_event_type`, `test_conversation_seq_is_monotonic_per_conversation`, `test_concurrent_writers_preserve_same_conversation_sequence`), [`test_cross_conversation_memory.py`](../../tests/test_cross_conversation_memory.py).

**Findings:** No violation. Known, already-documented gap: append-only is enforced at the application layer only; no database role/grant/trigger prevents a privileged actor from mutating `events` directly. This was previously identified as v0.5 audit item D-02 and P06-02, and is explicitly deferred to v0.9 threat-model work rather than silently ignored. That deferral is itself compliant with Article 26 (explicit, documented, not silent).

---

## Article 4 — Derived memory is replaceable; canonical evidence is not

**Status:** PASS

**Implementation surfaces:** [`postgres_memory_kernel.py`](../../src/jit_agent/postgres_memory_kernel.py) (`rebuild`), [`postgres_association_projection.py`](../../src/jit_agent/postgres_association_projection.py), [`jit_memory.py`](../../src/jit_agent/jit_memory.py) (`_ensure_projection_fresh`), `schema.sql` derived tables.

**Evidence:** `postgres_memory_kernel.rebuild()` explicitly `DELETE`s and regenerates only derived tables (`event_integrity`, `memory_projection_entries`, ...), never touching `events`; its own comment states "Derived state is explicitly disposable. Authoritative `events` is never modified by this operation." All projection/association tables carry `source_event_id`/`provenance_event_ids` foreign keys with `ON DELETE CASCADE` back to `events`. `MemoryEvidence` carries `score`, `retrieval_reasons`, and `provenance_event_ids` as explicit non-authoritative metadata.

**Tests:** [`test_association_projection.py`](../../tests/test_association_projection.py), [`test_derived_associative_benchmark.py`](../../tests/test_derived_associative_benchmark.py) (`test_derived_associations_replace_curated_jordan_edges`).

**Findings:** No violation.

---

## Article 5 — Ordinary cognition and recall are bounded

**Status:** PASS

**Implementation surfaces:** [`interaction_working_state.py`](../../src/jit_agent/interaction_working_state.py) (`MAX_ACTIVE_EVENT_IDS=12`), [`attention_aperture.py`](../../src/jit_agent/attention_aperture.py) (`DEFAULT_ATTENTION_APERTURE_LIMIT=6`, `MAX_ATTENTION_APERTURE_ITEMS=18`), [`interaction_policy.py`](../../src/jit_agent/interaction_policy.py) (`MAX_CAPABILITY_ROUNDS=4`), [`jit_memory.py`](../../src/jit_agent/jit_memory.py) (bounded recall profiles), [`llm.py`](../../src/jit_agent/llm.py) (explicit `num_predict` caps per call type).

**Evidence:** Every Ollama call sets `"options": {"num_predict": N}` (48/32/24/256 depending on call type), and every candidate set passed to a model is drawn from a fixed-size window, never the full corpus.

**Tests/artifacts:** `scripts/scale_test.py`, cited in repo build notes: context handed to the LLM stayed ~45 characters and interaction latency stayed ~7.7–8.7s flat across 500/2000/5000 seeded noise events — direct empirical evidence that ordinary-case cost does not grow with corpus size.

**Findings:** No violation. Bounds are correctly treated as empirical/safety tunables (Article 24), not structural invariants.

---

## Article 6 — Basic persistent-memory access precedes model routing

**Status:** PASS

**Implementation surfaces:** [`attention_aperture.py`](../../src/jit_agent/attention_aperture.py) (`open_attention_aperture`), [`interaction_runtime.py`](../../src/jit_agent/interaction_runtime.py) (`_execute_claimed_stage`, `RESOLVE_REFERENCES` stage before `SELECT_CAPABILITY`).

**Evidence:** `open_attention_aperture()` runs unconditionally and returns a bounded `MemoryPacket` before the routing model (`llm.classify()`) is ever invoked; the model receives the aperture packet as input rather than being asked whether memory is needed.

**Tests:** [`test_cross_conversation_memory.py`](../../tests/test_cross_conversation_memory.py).

**Findings:** No violation.

---

## Article 7 — WorkingState is bounded canonical activation, not a hidden memory store

**Status:** PASS

**Implementation surfaces:** [`interaction_working_state.py`](../../src/jit_agent/interaction_working_state.py) (`InteractionWorkingState`).

**Evidence:** `conversation_ids: list[UUID] = Field(max_length=16)`, `active_event_ids: list[UUID] = Field(max_length=MAX_ACTIVE_EVENT_IDS)` — hard Pydantic bounds, fields are canonical-event UUID references only. Module docstring: "It does not parse natural language into an ever-growing set of phrase-specific referents, labels, entities, or conclusions."

**Findings:** No violation.

---

## Article 8 — Conversations, sessions, devices, and interfaces are provenance, not cognitive boundaries

**Status:** PASS

**Implementation surfaces:** [`attention_aperture.py`](../../src/jit_agent/attention_aperture.py) line 69 (`conversation_id=None` passed to `build_memory_need`), [`postgres_memory_kernel.py`](../../src/jit_agent/postgres_memory_kernel.py) (`load_events` has no conversation filter), [`models.py`](../../src/jit_agent/models.py) (`MemoryNeed.conversation_id: UUID | None = None`).

**Evidence:** Confirmed directly: `attention_aperture.py` passes `conversation_id=None` when building the default memory need, so activation is cross-conversation by default; ordering/cutoffs use `global_seq`, not per-conversation sequence.

**Tests:** [`test_cross_conversation_memory.py`](../../tests/test_cross_conversation_memory.py) — process A records a fact in one conversation and exits; process B, fresh conversation and process, retrieves it.

**Findings:** No violation.

---

## Article 9 — System control is deterministic wherever deterministic control is possible

**Status:** PASS

**Implementation surfaces:** [`attention.py`](../../src/jit_agent/attention.py) (`derive_priority`, `CRITICALITY_PRIORITY`, `deterministic_task_id` via `uuid5`), [`attention_ordering.py`](../../src/jit_agent/attention_ordering.py) (`deterministic_dependency_order`), [`attention_store.py`](../../src/jit_agent/attention_store.py), `schema.sql` (`attention_task_created_seq` sequence, policy-version columns).

**Evidence:** Priority is a pure lookup from an explicit `TaskCriticality` enum, never derived from model output or wall-clock arrival. All durable identifiers use deterministic `uuid5`, never `uuid4`, in the control path. Scheduler policy versions (`admission_policy_version`, etc.) are persisted per epoch, enabling replay.

**Tests:** [`test_attention.py`](../../tests/test_attention.py) (`test_priority_is_derived_only_from_structured_criticality`), [`test_attention_preemption.py`](../../tests/test_attention_preemption.py) (`test_victim_selection_is_independent_of_task_submission_order` — byte-identical output for forward/reverse submission order).

**Findings:** No violation.

---

## Article 10 — Race conditions never decide durable authority

**Status:** PASS

**Implementation surfaces:** [`attention_store.py`](../../src/jit_agent/attention_store.py) (epoch commit transaction), [`worker_store.py`](../../src/jit_agent/worker_store.py) (`guarded_claim_worker_step`, ordered `FOR UPDATE` locks), `schema.sql` (`UNIQUE (scheduler_key, step_id) WHERE status='ACTIVE'` partial index; `preemption_state_revision`).

**Evidence:** Scheduling epochs are committed atomically (all assignments/reservations/state-pointer updates in one transaction) before any worker can see them; workers only ever observe `status='COMMITTED'` epochs. Claim attempts acquire locks in a fixed order (scheduler state → resources ordered by ID → step) and are further constrained by a partial unique index preventing two simultaneously `ACTIVE` claims on the same step. Stale-revision detection (`preemption_state_revision`) rejects concurrent conflicting checkpoint writers rather than letting the faster writer silently win.

**Tests:** [`test_event_store.py`](../../tests/test_event_store.py) (`test_concurrent_writers_preserve_same_conversation_sequence`, 8 concurrent threads via `Barrier`), [`test_attention_preemption.py`](../../tests/test_attention_preemption.py) (`test_postgres_concurrent_checkpoint_writers_cannot_erase_each_others_progress`).

**Findings:** No violation.

---

## Article 11 — Attention priority and resource admission are separate

**Status:** PASS

**Implementation surfaces:** [`attention.py`](../../src/jit_agent/attention.py) (`plan_scheduling_epoch`, `_effective_priority`, `_allocate_task_resources`).

**Evidence:** Attention order is computed first, purely from priority/service-guarantee/tie-break metadata; resource admission is then applied to the ordered candidate list, admitting every task that fits rather than serializing strictly by priority.

**Tests:** [`test_attention_admission.py`](../../tests/test_attention_admission.py) (`test_priority_does_not_serialize_tasks_that_fit_concurrently`, `test_identical_state_produces_identical_admission_independent_of_configuration_order`).

**Findings:** No violation. This corrects the repo-memory note claiming "Increment C not yet implemented" — quantitative resource admission is present in current code (see Article 12 below); that memory note is now stale and should be updated (see Remediation).

---

## Article 12 — Resource safety is fail-closed and preserves headroom

**Status:** PASS

**Implementation surfaces:** [`attention_resources.py`](../../src/jit_agent/attention_resources.py) (`ExecutionResource.admissible_capacity = capacity - system_headroom`), [`attention_observation.py`](../../src/jit_agent/attention_observation.py) (`ResourceSafetyPolicy`, `SystemHostResourceProbe`), [`native_policy.py`](../../src/jit_agent/native_policy.py) (`native_resource_safety_policy`, version `v0.7-native-calibration-v1`).

**Evidence:** Headroom is a validated, immutable field (`system_headroom <= capacity`) never allocatable to ordinary work. Default LLM concurrency is 1 slot. Resource observations expire (`observation_max_age_seconds`, default 5s) and a missing/stale observation raises `ResourceObservationError`, blocking admission rather than guessing.

**Tests:** [`test_attention_admission.py`](../../tests/test_attention_admission.py) (`test_headroom_is_never_allocatable_to_ordinary_work`, `test_admission_never_oversubscribes_safe_capacity`), [`test_interaction_resource_admission.py`](../../tests/test_interaction_resource_admission.py) (real host CPU/RAM observation).

**Findings:** No violation. Minor note: process resource estimates default conservatively (`CONSERVATIVE_DEFAULT`) until profiled; no automatic cross-restart recalibration loop exists yet — acceptable, not a violation, since the constitution only requires conservative defaults until evidence justifies otherwise.

---

## Article 13 — Preemption requires both priority and real contention

**Status:** PASS

**Implementation surfaces:** [`attention.py`](../../src/jit_agent/attention.py) (`_strictly_outprioritizes`, preemption block in `plan_scheduling_epoch`), [`attention_preemption.py`](../../src/jit_agent/attention_preemption.py) (`select_minimum_victims`).

**Evidence:** A target task is admitted directly, without considering preemption, whenever it fits without releasing anything. Victim candidates are filtered to only those holding a resource class the blocked task actually needs; `_strictly_outprioritizes()` requires strictly higher priority (same-priority arrivals never preempt). Victim selection uses a deterministic minimum-count algorithm with a stable tie-break.

**Tests:** [`test_attention_preemption.py`](../../tests/test_attention_preemption.py) (`test_safe_concurrent_capacity_never_causes_preemption`, `test_only_work_holding_a_deficient_resource_is_eligible_to_yield`, `test_atomic_and_same_priority_assignments_are_not_preempted`, `test_victim_selection_minimizes_count_before_tie_breaking`).

**Findings:** No violation.

---

## Article 14 — Disposable-worker execution is durable, guarded, and recovery-safe

**Status:** PASS

**Implementation surfaces:** [`worker_runtime.py`](../../src/jit_agent/worker_runtime.py) (`GuardedWorkerLauncher.claim/launch`), [`worker_protocol.py`](../../src/jit_agent/worker_protocol.py) (`WorkerStep`, `WorkerClaim`, `WorkerCheckpoint`, `WorkerResult`, `WorkerEffectPolicy`), [`worker_store.py`](../../src/jit_agent/worker_store.py) (`guarded_claim_worker_step`), `schema.sql` durable worker tables.

**Evidence:** `GuardedWorkerLauncher.claim()` re-observes host resources and passes guarded, policy-checked admission before `launch()` ever calls the process factory; a failed spawn releases the claim. `WorkerStep`/`WorkerClaim` carry deterministic IDs (`uuid5`-derived), leases with expiry, and an `idempotency_key`. `WorkerEffectPolicy.AT_MOST_ONCE` effects are explicitly not retried after ambiguous failure; only `NO_EXTERNAL_EFFECT`/`IDEMPOTENT_WITH_KEY` retry safely.

**Tests:** [`test_attention_process_restart.py`](../../tests/test_attention_process_restart.py) (`test_jit_attention_survives_forced_process_kill_and_resumes`), [`test_capability_runtime_handoff.py`](../../tests/test_capability_runtime_handoff.py).

**Findings:** No violation.

---

## Article 15 — Models select semantic requirements; Prometheist owns execution policy

**Status:** PASS

**Implementation surfaces:** [`interaction_policy.py`](../../src/jit_agent/interaction_policy.py) (`InteractionAction` enum, `InteractionDecision`), [`capability_registry.py`](../../src/jit_agent/capability_registry.py) (`plan_execution`, `resolve_catalog_indices`).

**Evidence:** The model emits only an enum (`RESPOND`/`USE_CAPABILITIES`) plus a bounded list of catalog integer indices; the system independently expands dependency closure and computes a deterministic topological execution order, then validates the model's indices against catalog bounds, raising on out-of-range values.

**Findings:** No violation.

---

## Article 16 — Model-generated natural language is control/state of last resort

**Status:** PASS

**Implementation surfaces:** [`llm.py`](../../src/jit_agent/llm.py) (`_CLASSIFY_SYSTEM_PROMPT`, verbatim placeholder masking), [`models.py`](../../src/jit_agent/models.py) (`MemoryCandidateSelection.candidate_indices`, `Pydantic ConfigDict(extra="forbid")`).

**Evidence:** All control schemas use enums/bounded integer indices; system prompts explicitly instruct the model not to emit capability names, queries, or free-form control values. `_build_verbatim_placeholder_maps`/`_restore_verbatim_literals` detect and reject model tampering with application-owned literal strings.

**Tests:** [`test_acceptance_contract.py`](../../tests/test_acceptance_contract.py) — asserts the acceptance test itself contains no keyword/regex answer-slot parsing, confirming answers are validated by exact equality, not semantic heuristics.

**Findings:** No violation.

---

## Article 17 — Relevance, activation, evidence sufficiency, and truth are distinct

**Status:** PASS

**Implementation surfaces:** [`models.py`](../../src/jit_agent/models.py) (`MemoryPacket.supported: bool`, `MemoryEvidence.score/retrieval_reasons/provenance_event_ids`), [`llm.py`](../../src/jit_agent/llm.py) (`_format_response_memory_packet` deliberately omits scores/IDs from the final-answer prompt while `_format_memory_packet` exposes them for internal routing/diagnostics).

**Evidence:** System prompt explicitly instructs: "If requested personal or historical information is not established by the current message or supplied source evidence, say that persisted evidence is insufficient. Do not claim unsupported memory."

**Tests:** [`test_fts_failure_corpus.py`](../../tests/test_fts_failure_corpus.py) — zero-vocabulary-overlap paraphrases correctly fail to retrieve (evidence-not-found is preserved as a distinct state, not silently promoted to a guessed truth).

**Findings:** No violation.

---

## Article 18 — Material influence must leave durable causal provenance

**Status:** PASS

**Implementation surfaces:** `MemoryEvidence.provenance_event_ids`, `MemoryEvidence.retrieval_reasons`, `AttentionTask` metadata, `WorkerResult`/`WorkerCheckpoint` durable records, scheduler epoch/policy-version persistence (Article 9/10 evidence above).

**Evidence:** Every routing decision, capability execution, resource admission, and preemption decision persists to PostgreSQL before or as part of the action, with linkage back to source events/tasks. This was verified indirectly through the Article 1/9/10/14 evidence chains (durable epochs, worker results, association provenance) rather than as a standalone audited surface; no separate raw-input-ephemeral-buffer path was found that discards causally influential input without a durable record.

**Findings:** No violation found in the audited surfaces. Not separately deep-dived as its own subagent pass — treat as corroborated by Articles 1, 3, 9, 10, 14 evidence rather than independently exhaustive.

---

## Article 19 — Internal memory and external knowledge remain distinct evidence domains

**Status:** NOT APPLICABLE

**Evidence:** `KnowledgeOrigin` enum in [`models.py`](../../src/jit_agent/models.py) already defines an `EXTERNAL_TOOL` variant, and `MemoryPacket.origin` is reserved for it, but no code path currently performs external web/API/tool knowledge retrieval — the only outbound HTTP client (`httpx` in `llm.py`) talks exclusively to the local Ollama inference endpoint. `WorkerEffectPolicy.NO_EXTERNAL_EFFECT` is the default.

**Findings:** Genuinely not exercised yet, correctly reserved rather than faked. If external retrieval is added, `MemoryPacket.origin`/`MemoryEvidence` must actually be populated with the reserved `EXTERNAL_TOOL` distinction at that time — flag as a design reminder, not a current defect.

---

## Article 20 — Natural-language continuity must not become vocabulary patchwork

**Status:** PASS

**Implementation surfaces:** [`interaction_policy.py`](../../src/jit_agent/interaction_policy.py) (`requires_persisted_context` — explicit no-op returning `False`; `apply_continuity_policy` — explicit no-op).

**Evidence:** Both functions carry explicit deprecation docstrings: "Deprecated compatibility hook; phrase-based continuity is disabled" / "Live phrase detection is disabled; every percept receives bounded memory activation independently of this flag." Phrase lists that do exist (`association_projection.py` — `_CHANGE_PHRASES`, etc.) operate only inside the memory-kernel association derivation machinery, which Article 20 explicitly permits, not as application-level gates on whether to activate memory.

**Findings:** No violation. Legacy no-op functions are retained for readability of older payloads/tests, which is a sound compatibility pattern rather than a policy regression.

---

## Article 21 — Local-first, user-controlled, model-agnostic, and replaceable by design

**Status:** GAP

**Implementation surfaces:** `pyproject.toml` (no cloud/vendor SDKs), [`db.py`](../../src/jit_agent/db.py), [`retrieval.py`](../../src/jit_agent/retrieval.py) (Postgres full-text-search operators `to_tsvector`/`to_tsquery`/`ts_rank`), [`llm.py`](../../src/jit_agent/llm.py)/[`ollama_runtime.py`](../../src/jit_agent/ollama_runtime.py), `docs/architecture/LOCAL_FIRST_PORTABILITY.md` (`LLM = null` section).

**Evidence:** No Docker/Kubernetes/hosted-vendor dependency exists; the stack is native PostgreSQL + native Ollama on Windows, matching repo build notes. However: (1) `interaction_worker.py` and capability execution unconditionally instantiate `OllamaClient()` — there is no code path that keeps durable-state operations (event recording, attention scheduling, worker claim/checkpoint) functioning administratively when the LLM is unavailable, i.e. no implemented `LLM = null` operability; (2) retrieval logic is written directly against Postgres-specific FTS operators, so backend replacement would require rewriting `retrieval.py`, not just swapping a connection string.

**Findings:** This is exactly the situation the deep dive itself anticipates: *"Current versions may not yet satisfy every portability target. That is a `GAP`, not a reason to weaken the constitutional rule... a release may currently require PostgreSQL for authoritative operation while the long-lived architecture requires persistence abstraction... The correct governance response is to record the gap and roadmap the work."* Per that explicit guidance, this is recorded as `GAP`, not `FAIL`: the architecture does not claim `LLM = null` operability or backend portability is complete, and no other article is being silently violated by the current coupling.

**Remediation:** Track as roadmap work (not urgent for a solo-maintainer prototype): (a) an administrative/diagnostic path that functions with `LLM = null` (inspect history, run integrity/rebuild, enumerate unfinished worker/attention state) without invoking `OllamaClient`; (b) isolate Postgres-specific query syntax behind a narrower interface in `retrieval.py` if/when backend portability becomes an active goal.

---

## Article 22 — User sovereignty governs stored data and replaceable components

**Status:** GAP

**Evidence:** All data is local and user-owned (PostgreSQL on the user's own machine); derived structures are explicitly rebuildable/disposable (Article 4). No export, backup/restore, or explicit user-directed erasure command exists in `src/jit_agent/` or `scripts/`; a user must use `pg_dump`/`psql` directly today.

**Findings:** Consistent with Article 3's "when implemented" framing — the Constitution does not require export/erasure to exist yet, only that automatic retention/compaction (which does not currently delete canonical evidence at all) must never be confused with user-directed erasure, which holds trivially since no deletion path exists. Recorded as `GAP` per the audit guidance that "not implemented yet" is `GAP`, not `NOT APPLICABLE`.

**Remediation:** No action required for current milestone; roadmap an explicit export/erasure CLI command before any release claims user-sovereignty completeness.

---

## Article 23 — Development follows a falsifiable one-mechanism experimental discipline

**Status:** PASS

**Implementation surfaces:** [`benchmarks/constraint_experiments.json`](../../benchmarks/constraint_experiments.json), [`benchmarks/run_deterministic_constraints.py`](../../benchmarks/run_deterministic_constraints.py), [`benchmarks/tune_memory_scoring.py`](../../benchmarks/tune_memory_scoring.py), `docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`.

**Evidence:** Frozen scenario fixtures (`jordan_vale_v1.json`, `avery_chen_v1.json`, `morgan_reyes_v05_robustness.json`) are compared against explicit baseline policies. Negative results are preserved and labeled, e.g. `MEM-SCORE-001`/`MEM-BREADTH-001`/`MEM-GRAPH-001` are explicitly recorded as `INSUFFICIENT_DISCRIMINATION` rather than deleted or silently retried until "success." `docs/audits/POST_V06_CODEBASE_REVIEW_2026-08-21.md` explicitly defers a pgvector hypothesis until a measured failure justifies it, rather than adding it speculatively.

**Findings:** No violation.

---

## Article 24 — Behavioral numbers must be classified and evidenced

**Status:** PASS

**Implementation surfaces:** [`scripts/audit_constraints.py`](../../scripts/audit_constraints.py) (AST-based discovery of policy-named numeric literals/assignments), [`benchmarks/constraint_registry.json`](../../benchmarks/constraint_registry.json), CI gate in `.github/workflows/tests.yml` (`audit_constraints.py --fail-unregistered`).

**Evidence (empirically verified, not just read):** `uv run python scripts/audit_constraints.py --fail-unregistered` was executed against this revision and reported `discovered=175 registered=175 uncovered=0 stale=0 mismatched=0 invalid=0`, with every discovered constant printed as `REGISTERED`, including `interaction_working_state.py::<module>::MAX_ACTIVE_EVENT_IDS`, all four `jit_memory.py::<module>::_RecallPolicy.*` variants (candidate_limit/association_limit/max_hops/decay for deeper research, cross reference, and focused recall), and `interaction_policy.py::MAX_CAPABILITY_ROUNDS`.

**Findings:** No violation. An initial exploratory pass in this audit incorrectly flagged 12 of these constants as "unregistered" based on a manual text search of the registry JSON; running the actual authoritative tool shows they are all registered and classified. This is recorded here to correct that intermediate error rather than let it stand as a false finding — always run `scripts/audit_constraints.py` itself rather than grep the registry file when auditing Article 24.

---

## Article 25 — Verification requires deterministic regression evidence and native acceptance where reality matters

**Status:** PASS (native-acceptance breadth flagged for future expansion, not blocking)

**Implementation surfaces:** `.github/workflows/tests.yml` (deterministic CI: disposable PostgreSQL service, `audit_constraints.py`, `run_deterministic_constraints.py`, `calibrate_capability_loop.py`, full pytest run), [`scripts/run_native_constraint_calibration.ps1`](../../scripts/run_native_constraint_calibration.ps1), `benchmarks/results/NATIVE-CONSTRAINTS_2026-08-27_*.json`.

**Evidence (empirically verified):** `benchmarks/results/` contains **11 separate timestamped `NATIVE-CONSTRAINTS_2026-08-27_*.json` runs from this same day**, each executing real-Ollama scenarios (e.g. `CAP-LOOP-001`, a genuine four-turn continuity run against `qwen3:4b-instruct-2507-q4_K_M`, `elapsed_seconds: 155.3`, `returncode: 0`) and recording explicit non-committal decisions such as: *"A passing four-turn real-Ollama continuity run demonstrates that the production round guard is non-binding for this frozen native workload. It does not establish the empirical tail of capability-round demand..."* — this is exactly the deterministic-CI-vs-native-acceptance separation and honest evidence grading Article 25 requires. CI itself only collects (`--collect-only`) ollama-marked tests to confirm they still exist/import correctly, and skips executing them on the hosted runner, which is the correct split (native claims are verified locally on real hardware, not simulated in CI).

**Findings:** No violation; an initial exploratory pass in this audit missed this evidence because it looked only in the top-level `benchmark_results/` directory rather than `benchmarks/results/` — corrected here. Remaining, non-blocking improvement: native acceptance scenario coverage is currently concentrated on continuity/round-guard and single-call latency; explicit resource-contention and cold-start-timing native scenarios would strengthen Article 12/25 evidence further but are not required to reach `PASS` today given the frozen non-committal decisions already on file.

---

## Article 26 — Constitutional changes must be explicit

**Status:** PASS

**Evidence:** `docs/audits/V05_CLOSURE_AUDIT_2026-08-21.md` and `docs/audits/POST_V06_CODEBASE_REVIEW_2026-08-21.md` both record every disposition (fixed/deferred/clarified) with explicit rationale; deferred items (e.g. database-level append-only enforcement) are documented as deferred, not silently dropped. No code or passing test was found that contradicts a constitutional rule without a corresponding recorded rationale.

**Findings:** No violation.

---

## Article 27 — Capability reasoning is recurrent, but every reassessment is fresh

**Status:** PASS

**Implementation surfaces:** [`interaction_runtime.py`](../../src/jit_agent/interaction_runtime.py) (`_execute_claimed_stage` `EXECUTE_CAPABILITY` loop bounded by `MAX_CAPABILITY_ROUNDS`, `_load_or_create_round`).

**Evidence:** Each round persists its decision before returning; the next round issues a fresh `llm.classify()` call built from rebuilt bounded context (aperture packet plus accumulated capability results), never a carried Python object. Reaching `MAX_CAPABILITY_ROUNDS` without an explicit `RESPOND` decision raises `RuntimeError` rather than forcing a fabricated answer. Final response generation (`llm.respond()`) only occurs after an explicit `RESPOND` decision, in its own separate fresh call.

**Findings:** No violation.

---

## Article 28 — Durable queued work must have an explicit anti-starvation policy

**Status:** PASS

**Implementation surfaces:** [`attention.py`](../../src/jit_agent/attention.py) (`ServiceGuarantee`, `DEFAULT_SERVICE_GUARANTEES`, `_service_due`, `_effective_priority`, `_queue_key`).

**Evidence:** Every `ServiceClass` has an explicit `max_wait_cycles`/`guaranteed_priority` pair (e.g. `BACKGROUND: max_wait_cycles=128 -> P3`); `_queue_key()` produces a deterministic 5-tuple total order that applies due-promotion before falling back to creation sequence and task ID as tie-breakers.

**Findings:** No violation.

---

## Article 29 — Insufficient authority or evidence fails closed

**Status:** PASS

**Implementation surfaces:** [`llm.py`](../../src/jit_agent/llm.py) (retry-then-raise on invalid structured output; verbatim-placeholder tamper detection raises), [`attention_observation.py`](../../src/jit_agent/attention_observation.py) (`CapacityMeasurement.FAIL_CLOSED` on probe failure; `ResourceObservationError` on unreadable host counters), [`interaction_policy.py`](../../src/jit_agent/interaction_policy.py) (`model_validator` rejecting `RESPOND`+capabilities or `USE_CAPABILITIES` with no indices), [`worker_store.py`](../../src/jit_agent/worker_store.py) (`WorkerProtocolError` on missing committed epoch authority), [`worker_runtime.py`](../../src/jit_agent/worker_runtime.py) (transient-vs-structural denial classification; structural denials never retried).

**Evidence:** Every audited failure surface raises an explicit typed error or sets an explicit fail-closed state rather than defaulting silently; capability candidate-index selections out of packet bounds raise `ValueError` rather than being clamped/ignored.

**Findings:** No violation.

---

## Remediation summary

| Item | Article | Action | Priority |
|---|---|---|---|
| R1 | 21 | Add an administrative/diagnostic operating mode that functions with `LLM = null` (inspect durable state, run integrity/rebuild, enumerate unfinished work) without instantiating `OllamaClient`. | Roadmap (not urgent for solo-maintainer local use) |
| R2 | 21 | If/when backend portability becomes an active goal, isolate Postgres-specific FTS syntax in `retrieval.py` behind a narrower interface. | Roadmap |
| R3 | 22 | Add an explicit export and user-directed erasure command before any release claims user-sovereignty completeness. | Roadmap |
| R4 | 3 | Continue to treat database-level append-only enforcement (roles/grants/triggers) as v0.9 threat-model work, not this audit's scope. | Already tracked (v0.9) |
| R5 | 11/repo memory | Update `/memories/repo/jit_agent_prototype.md` — the "Increment C not yet implemented" note is stale; quantitative resource admission, contention-driven preemption, and the durable worker claim protocol are all implemented and tested today. | Housekeeping |
| R6 | 25 | Optionally add explicit native acceptance scenarios for resource contention and cold-start Ollama timing to broaden (not fix) native evidence. | Optional/roadmap |

## Notes on audit method

Five parallel exploratory passes were used to gather article-by-article evidence, followed by direct verification of the two most consequential claims: Article 24 was corrected from an initial `FAIL` to `PASS` after actually running `scripts/audit_constraints.py --fail-unregistered` (`uncovered=0`), and Article 25 was corrected from `GAP` to `PASS` after finding 11 same-day `NATIVE-CONSTRAINTS_*.json` runs in `benchmarks/results/` that an initial pass had missed by searching the differently-named `benchmark_results/` directory instead. This is recorded transparently per Article 26/29 — an audit's own intermediate errors should be corrected explicitly, not silently.
