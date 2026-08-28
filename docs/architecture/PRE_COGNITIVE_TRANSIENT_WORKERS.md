# Pre-Cognitive Transient Workers

**Status:** current production interaction architecture on `feature/pre-cognitive-transient-workers`  
**Scheme:** `pre-cognitive-transient-workers-v1`  
**Introduced:** 2026-08-28  
**Primary implementation:** `src/jit_agent/pre_cognitive_workers.py`, `src/jit_agent/interaction_worker.py`

## Purpose

Prometheist needs reasoning depth without turning any model invocation into a persistent agent and without paying for an open-ended recurrent routing loop on ordinary interactions. The pre-cognitive transient-worker scheme separates three things that had become coupled in the earlier v0.7 interaction loop:

1. **activation and evidence acquisition** — system-owned retrieval and capability execution;
2. **cognitive control** — small fresh model calls that classify what kind of evidence/work is still needed;
3. **user-facing cognition** — one fresh response worker that receives the bounded evidence assembled for the turn.

The result is a staged cognitive pipeline in which workers are summoned for one bounded purpose, leave durable output when their result matters, and can disappear immediately afterward. Workers may be LLM-powered or ordinary deterministic software. No worker owns Prometheist's continuity.

This design is intended to reduce latency and model burden while preserving the stronger architectural properties established by the v0.7 attention pivot: stateless inference, exact provenance, deterministic execution authority, guarded resource admission, bounded memory exposure, and restart-safe durable work.

## Constitutional invariants

The scheme must preserve all of the following:

- Every LLM invocation starts with a fresh model context.
- No hidden transcript, chat context, or prior worker prompt is inherited by a later LLM invocation.
- Canonical source evidence remains exact and lossless. A worker may select or activate evidence; it may not replace canonical evidence with its summary.
- Every model-facing evidence view is bounded independently of total corpus size.
- Persistent memory is activated before model routing. A model is never asked whether unseen memory matters.
- Models may classify semantics and select bounded application-owned indices; ordinary software owns identifiers, dependency expansion, ordering, scheduling, resource admission, retry semantics, and persistence.
- Material model-control output is validated and persisted before it authorizes downstream effects.
- A retry after worker death reuses the persisted control decision instead of asking the model to make the decision again.
- Capability execution is idempotent under deterministic execution identity.
- Insufficient evidence or invalid control output fails closed.
- Resource admission remains authoritative. The worker scheme does not bypass the scheduler, claim-time admission, headroom policy, or the default one-concurrent-LLM-slot policy.

## The central distinction: cognition is not continuity

A transient cognition worker may inspect the current percept and the bounded evidence Prometheist has activated for that percept. It can classify what the task appears to require. That does not make the worker an enduring mind, agent, or conversation owner.

The durable state is outside the model:

- canonical events;
- WorkingState activation references;
- attention tasks and assignments;
- worker step identities and leases;
- memory requests and MemoryPackets;
- capability results;
- validated pre-cognitive assessments;
- response-policy records;
- the final response event.

If a worker process terminates, the system can reconstruct the next action from those records. If the same worker model is replaced, the state remains intelligible. If the local LLM is unavailable, the durable state is still valid even though model-dependent cognition cannot proceed.

## Production flow

The existing five durable v0.7 interaction stage keys are retained as a migration and recovery boundary. Their production semantics are now:

| Durable stage | Production role | LLM required? |
| --- | --- | --- |
| `RESOLVE_REFERENCES` | Inspect whether bounded WorkingState exists for the current conversation/provenance path. It does not perform English phrase detection. | No |
| `SELECT_CAPABILITY` | Open the default JIT attention aperture, then run one fresh **PRE_CAPABILITY** assessment and persist its closed decision and deterministic execution plan. | Usually yes |
| `EXECUTE_CAPABILITY` | Execute any selected first-tranche capabilities deterministically. If first-tranche work ran, compose exact bounded evidence, expose only newly legal follow-up capabilities, run one fresh **POST_CAPABILITY** assessment, and optionally execute one follow-up tranche. | Conditional |
| `RESPOND` | Run one fresh response worker over the current percept, final bounded exact-source evidence, structured capability results, and a non-evidentiary closed cognitive brief. | Yes |
| `PERSIST_RESULT` | Persist the response event and activate the new bounded WorkingState. | No |

The names `SELECT_CAPABILITY` and `EXECUTE_CAPABILITY` are retained for durable-protocol compatibility. They no longer mean “enter an unbounded recurrent router loop.”

## Common fast path

For an ordinary interaction whose current percept and initial JIT activation are sufficient:

```text
external percept
    ↓
durable intake + Attention admission
    ↓
deterministic reference/WorkingState inspection
    ↓
JIT attention aperture
    ↓
fresh PRE_CAPABILITY cognition worker
    ↓  disposition = RESPOND
fresh response worker
    ↓
deterministic persistence + WorkingState activation
```

The normal model burden is therefore two independent LLM invocations:

1. pre-cognitive assessment;
2. final response.

No capability loop is entered merely because capability machinery exists.

## Capability path

When the initial evidence is insufficient or a registered capability is required:

```text
external percept
    ↓
JIT attention aperture
    ↓
fresh PRE_CAPABILITY cognition worker
    ↓  ACQUIRE_CAPABILITIES + bounded catalog indices
application validates selection
    ↓
deterministic dependency closure and execution plan
    ↓
guarded first capability tranche
    ↓
exact bounded evidence composition
    ↓
fresh POST_CAPABILITY cognition worker
    ├─ RESPOND / ABSTAIN → response worker
    └─ ACQUIRE_CAPABILITIES
            ↓
       newly exposed follow-up catalog only
            ↓
       guarded follow-up tranche
            ↓
       response worker
```

The main interaction-control path is bounded to one pre-capability assessment and, only after first-tranche work, one post-capability assessment. The follow-up tranche does **not** recursively reopen the original capability catalog.

Capability-specific semantic selectors may still require their own transient model call. For example, deeper associative recall may ask a disposable selector to choose one or more candidates by integer index. Those selectors do not inherit the pre-cognitive worker's context and do not author retrieval queries or event IDs.

## Why there is no recurrent router loop

The previous v0.7 path allowed up to several fresh routing rounds. It respected statelessness, but it imposed a recurrent control pattern: route, execute, rebuild context, route again, potentially repeat. That had two costs.

First, ordinary latency could become dominated by multiple local-model calls rather than retrieval or response synthesis. On modest CPU-only hardware, each additional 4B inference is material.

Second, the router was being asked repeatedly to rediscover what the system could represent more cleanly as staged execution policy. Once the first tranche has completed, the legal next-step space is narrower. Prometheist can expose only capabilities newly enabled by that work instead of presenting the full original routing problem again.

The new invariant is therefore **staged fresh reassessment**, not unrestricted recurrence. Fresh cognition is still required after material capability work when a further semantic judgment is needed, but the architecture deliberately constrains where that judgment can occur.

## Closed pre-cognitive control contract

A pre-cognitive worker returns `PreCognitiveAssessment`, a Pydantic object with `extra="forbid"`. The model can output only closed fields:

- `phase` — `PRE_CAPABILITY` or `POST_CAPABILITY`;
- `disposition` — `RESPOND`, `ACQUIRE_CAPABILITIES`, or terminal `ABSTAIN`;
- `intent_mode` — broad semantic class such as `RECALL`, `ANALYZE`, `ACT`, or `RESEARCH`;
- `evidence_state` — whether current input/activated memory is sufficient or additional work is required;
- `claim_scopes` — bounded authority/evidence domains the eventual answer is expected to depend on;
- `requirement_flags` — closed requirements such as exact-source handling, temporal resolution, conflict resolution, deeper recall, cross-reference, focused recall, or fail-closed behavior;
- `capability_indices` — non-negative integer indices into the application-owned catalog supplied to that exact call.

The worker cannot author:

- capability IDs;
- tool names or implementation bindings;
- retrieval query text;
- event IDs or memory request IDs;
- dependencies;
- execution order;
- resource reservations;
- permissions;
- scheduling policy;
- retry policy;
- prose plans;
- factual answer text.

This distinction is intentional. The model supplies semantic discrimination where ordinary software cannot reliably infer intent; Prometheist retains the control plane.

## Pre-cognitive phase

Every normal percept first receives the Attention aperture. Only then does `PRE_CAPABILITY` cognition run.

Inputs are bounded and explicit:

- current user percept;
- activated MemoryPacket evidence content;
- current application-owned capability catalog;
- the phase identifier.

The worker decides whether those inputs are sufficient for a response or whether a small set of catalog capabilities is needed. Prometheist validates all selected indices, deterministically expands dependencies, creates the execution plan, and persists both the validated assessment and the exact plan.

If the model returns malformed JSON, an unknown enum, an extra free-form field, an out-of-range index, or a disposition/index contradiction, the call fails closed.

## First capability tranche

The first tranche executes only the deterministic plan produced from the persisted pre-cognitive selection.

Capability execution retains the existing v0.7 properties:

- deterministic capability execution IDs;
- deterministic memory request IDs;
- application-owned executor binding;
- dependency ordering owned by Attention/registry policy;
- exact MemoryPacket evidence;
- structured result data;
- persisted capability-result events;
- idempotent replay after restart.

Memory capabilities use the current percept as the semantic cue while selected canonical event IDs constrain associative topology. A model may select bounded candidates, but it does not create the retrieval query or event identity.

## Exact bounded context composition

After capability work, Prometheist composes the next working evidence packet from canonical `MemoryEvidence` objects. The composer:

1. places newer capability evidence before older capability evidence and the aperture packet for selection purposes;
2. deduplicates by canonical `source_event_id`;
3. copies the exact source evidence objects rather than rewriting them;
4. applies a bounded item limit;
5. records the contributing memory-request IDs in the retrieval trace.

This packet is task-local working context. It is not a canonical summary and does not replace source memory.

A future implementation may improve evidence selection, packing, or token budgeting, but it may not solve context pressure by destructively summarizing canonical history.

## Post-capability phase

`POST_CAPABILITY` cognition occurs only if first-tranche capability work actually ran.

Its inputs are:

- the current percept;
- newly composed exact bounded evidence;
- structured summaries/results of completed capabilities;
- a catalog containing only capabilities that became newly legal because of those completed results.

For the current internal-memory registry, `deeper_research` and `cross_reference` can expose `focused_recall`. The original first-tranche capabilities are not re-presented merely to create another loop.

The post-capability assessment may:

- authorize response synthesis;
- terminate in an abstention state if no legal work can establish sufficient evidence;
- request the smallest legal follow-up set from the newly exposed catalog.

If it requests follow-up work, Prometheist executes one bounded follow-up tranche. There is no third routing round in this scheme version.

## Why the response worker still exists

Pre-cognition is control, not the user-facing mind. The final response worker remains a separate fresh invocation because generation is a different task from evidence acquisition.

The responder receives:

- current user input;
- the final bounded exact-source MemoryPacket;
- admitted structured capability results;
- a small `pre_cognitive_brief` containing only closed control metadata.

The brief is explicitly non-evidentiary. It can tell the responder that the interaction was classified as recall, that exact-source handling is required, or that acquisition terminated in an insufficient-evidence state. It cannot supply unsupported facts.

The existing response-policy and evidence-authority layers remain authoritative. Pre-cognitive readiness does not override source-role filtering, exact-source validation, or fail-closed response behavior.

## Transient worker taxonomy

The architecture deliberately does not equate “worker” with “LLM.”

### Deterministic/non-LLM workers

Current examples include:

- durable intake and event persistence;
- WorkingState presence inspection;
- attention-aperture retrieval orchestration;
- schema validation;
- capability-index validation;
- dependency expansion;
- capability execution planning;
- resource probing and admission;
- claim/lease ownership;
- exact evidence composition and deduplication;
- response persistence and WorkingState activation.

These should remain ordinary software unless a semantic ambiguity genuinely requires model judgment.

### LLM-powered transient workers

Current roles include:

- PRE_CAPABILITY assessment;
- POST_CAPABILITY assessment when first-tranche work ran;
- bounded capability-specific candidate selection where required;
- final response synthesis.

Each invocation is independently constructed from durable inputs and discarded after validated output is obtained.

## Restart and crash semantics

Transient does not mean ephemeral authority.

A critical failure window exists whenever a worker obtains a model decision and then crashes before completing its durable worker step. Re-running the model in that window would allow model nondeterminism to change a decision after downstream state may already exist.

The scheme therefore persists each pre/post assessment as a deterministic `SYSTEM_EVENT` before capability effects are authorized. The event identity is derived from the interaction ID and cognitive phase. On retry, `_load_or_create_assessment()`:

1. loads the existing event;
2. verifies the scheme version and phase;
3. verifies the exact `memory_request_id` used for the decision;
4. verifies the application-owned catalog IDs;
5. validates the stored `PreCognitiveAssessment`;
6. reconstructs the deterministic execution plan and compares it with the stored plan;
7. reuses the stored decision without another model call.

If the registry or evidence context has changed incompatibly, execution fails closed rather than silently applying a stale decision.

This makes model nondeterminism a bounded inference property rather than a recovery-policy property.

## Resource behavior

This scheme does not change the constitutional resource model.

- Attention still decides priority.
- Resource admission still decides safe concurrency.
- Worker launch still requires claim-time admission.
- The host still preserves configured CPU/RAM headroom.
- Local LLM inference still defaults conservatively to one concurrent LLM slot.
- Ollama residency is still observed when estimating incremental process pressure.

The main expected resource win is not a new reservation rule. It is avoiding unnecessary model invocations and keeping each invocation's evidence view bounded.

## Model policy for this increment

The architecture change is being evaluated with the existing local Qwen3 4B configuration. The model is deliberately held constant while the mechanism changes so benchmark differences can be attributed to the worker architecture rather than a simultaneous model swap.

A quantized 12–14B model may be evaluated later if native resource measurements justify it. That is a separate experiment. A larger model must not be used to hide architectural failure or bypass the host-safety policy.

## Migration and compatibility

The new implementation is production-routed through `src/jit_agent/interaction_worker.py`, which is the subprocess entry point used by `handle_interaction_in_worker_processes()` and therefore by the CLI/native acceptance path.

The older in-process helper path in `interaction_runtime.py` is temporarily retained for regression coverage and compatibility with existing deterministic test fixtures. It still contains the earlier recurrent capability implementation. It is not the normative production cognitive path once this scheme is accepted.

Retaining the old five stage keys prevents a protocol migration from being mixed into the cognition experiment. A later cleanup can rename or collapse stages after acceptance evidence shows that the new mechanism is stable.

## Failure modes and required behavior

| Failure | Required behavior |
| --- | --- |
| malformed/extra model control field | validation failure; no capability effect |
| out-of-range capability index | fail closed |
| registry changes after persisted decision | fail closed on plan/catalog mismatch |
| worker dies after cognitive decision | reuse persisted decision; do not re-roll model cognition |
| worker dies during idempotent capability work | load/reuse persisted capability result under deterministic execution ID |
| focused recall requested without broader evidence | fail closed |
| capability returns unsupported/empty evidence | preserve structured unsupported result; later cognition/response must not invent support |
| post-capability work still insufficient | responder must obey evidence policy/abstention behavior; no recursive router loop is invented |
| resource admission denied | wait/deny under existing Attention safety policy |
| local model unavailable | durable state remains valid; model-dependent work cannot complete |

## Acceptance criteria

The scheme should not be considered complete merely because deterministic unit tests pass. Acceptance should include:

### Deterministic CI

- closed-schema rejection tests;
- invalid-index failure tests;
- exact-source composition/deduplication tests;
- follow-up catalog tests proving original capabilities are not recurrently reopened;
- restart tests proving persisted pre/post assessments are reused;
- worker-lease/retry/idempotency tests;
- existing hidden-transcript, cross-process, cross-conversation, provenance, epistemic-authority, response-policy, and bounded-evidence regression suites.

### Native Qwen3:4b acceptance

On the development machine, rerun the v0.7 local-model acceptance and red-team recall cases with telemetry. Measure at minimum:

- pass/fail correctness;
- PRE_CAPABILITY latency;
- POST_CAPABILITY latency when invoked;
- response latency;
- total turn latency;
- number of LLM invocations per turn;
- prompt/evidence size per invocation;
- peak RAM and admission behavior;
- whether Ollama remains resident or reloads;
- restart behavior across real child processes.

The mechanism is successful only if it preserves or improves correctness while materially reducing recurrent inference overhead and maintaining bounded resource use.

## What this scheme intentionally does not claim

This is not proof that two or three model calls are universally sufficient for every future task. It is an empirical architecture boundary for the current interaction/capability system. More complex durable jobs may spawn additional transient workers when their task graph requires them.

The invariant is not “never use another LLM call.” The invariant is:

> summon the smallest bounded worker needed for the current unresolved requirement, persist any material control result, and discard the worker context afterward.

Likewise, this scheme does not claim that all retrieval should be model-selected. Deterministic retrieval, exact lookup, graph traversal, filtering, validation, and evidence packing should remain non-LLM work whenever ordinary software can do them reliably.

## Relationship to other architecture documents

- [`COGNITIVE_ARCHITECTURE.md`](COGNITIVE_ARCHITECTURE.md) defines the system/worker separation and stateless cognition model.
- [`INTERACTION_CONTINUITY.md`](INTERACTION_CONTINUITY.md) defines how every percept obtains bounded persistent context and how WorkingState participates without becoming a transcript.
- [`LOSSLESS_PROGRESSIVE_MEMORY.md`](LOSSLESS_PROGRESSIVE_MEMORY.md) defines exact canonical evidence and staged bounded retrieval.
- [`ATTENTION_AND_EXECUTION_GOVERNANCE.md`](ATTENTION_AND_EXECUTION_GOVERNANCE.md) defines durable scheduling, resource admission, leases, preemption, and execution safety.
- [`SYSTEM_DETERMINISM.md`](SYSTEM_DETERMINISM.md) defines the boundary between semantic model judgment and application-owned control authority.

This document is the authoritative deep dive for the staged pre-cognitive transient-worker mechanism itself.
