# Prometheist v0.7 — Durable Attention, WorkingState, and Typed Transient Execution

**Status:** release candidate. Final-head deterministic CI and native Windows/PostgreSQL/Ollama Qwen3:4b acceptance are required before v0.7 is accepted/closed.

v0.7 is the first milestone after the 2026-08-24 pivot away from a privileged Primary Agent/fixed multi-agent hierarchy. It moves durable executive/cognitive continuity into Prometheist itself and treats workers/models as disposable compute.

## Primary question

> Can Prometheist deterministically allocate durable work across bounded local resources, survive destruction of every worker/model process, preserve current activation and persistent memory continuity, acquire additional evidence through bounded fresh stations, and terminalize heterogeneous tasks without any privileged agent or persistent LLM context?

## Current v0.7 architecture

### Durable Attention Fabric

Implemented mechanisms include:

- deterministic task priority/order and service guarantees;
- dependency/interruption policy;
- explicit CPU/RAM/LLM/I/O resource requirements;
- authoritative host-resource observation;
- configured system/uncertainty headroom;
- default one-concurrent-local-LLM slot;
- atomic scheduling epochs, assignments, and reservations;
- contention-driven preemption;
- guarded claim-time resource re-observation;
- disposable-worker claims, leases, checkpoints, terminal results, idempotency/effect semantics, and restart recovery.

Attention decides what deserves execution; resource admission decides what can safely run concurrently. Priority alone is not a reason to preempt compatible work.

### WorkingState and automatic JIT aperture

Native continuity testing rejected two approaches:

1. growing phrase/entity/recency vocabularies as application continuity policy;
2. asking a fresh model whether it needs unseen memory before exposing potentially relevant memory.

The current path therefore uses:

- bounded `InteractionWorkingState` containing canonical active-event references;
- conversations/sessions/devices as provenance rather than cognitive walls;
- a small bounded high-recall JIT Memory attention aperture before semantic model judgment.

### Demand-driven transient semantic stations

The first transient-worker architecture removed recurrent general capability routing. Subsequent native Qwen3:4b testing showed that one aggregate pre-cognitive classifier still owned too many responsibilities.

The current pre-acquisition path is deliberately narrow:

```text
evidence_sufficiency_verifier
    -> SUFFICIENT | INSUFFICIENT

if INSUFFICIENT and legal catalog exists:
capability_selector
    -> bounded application-catalog indices
```

Deterministic application code derives aggregate control and owns capability identities, dependencies, execution order, resources, persistence, and effects.

The design rule is:

> **one bounded job per station + no unnecessary station**

See [`PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md`](PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md).

### Typed Interaction Workpiece

The current general execution abstraction is `interaction-workpiece-v1`.

A workpiece is an application-owned frame that accumulates only the validated components required by the current task. Stations receive minimum projections of the workpiece and return one bounded component; Prometheist validates/attaches the component and chooses the next eligible station.

Current component families include percept, reference state, attention aperture, evidence sufficiency, conditional capability selection, application-composed control, capability tranches, final evidence, the current interactive response directive, optional user output, and terminal outcome.

At terminalization the production path persists a materialized `INTERACTION_WORKPIECE_SNAPSHOT` JSON while retaining the append-only event/worker/capability/effect records underneath it.

General terminal outcomes include response, abstention, action completion/failure, waiting, and deferral. The current CLI is interactive, but the core architecture does **not** require a final response worker for future action/background tasks.

See [`INTERACTION_WORKPIECE_2026-08-28.md`](INTERACTION_WORKPIECE_2026-08-28.md).

### Capability and worker registry

Capabilities describe semantic work; private worker profiles describe bounded implementations. Every current capability resolves through application-owned deterministic roots and may delegate narrowly to a stateless LLM selector when the capability actually requires semantic judgment.

All current LLM profiles share `ollama-primary`; model weights may stay warm in Ollama while each invocation remains context-stateless.

Only the optional final natural-language response profile receives persona authority.

## Durable stage compatibility

The existing five interaction stage keys remain in v0.7 to avoid combining a durable-protocol migration with the workpiece/station experiment:

- `RESOLVE_REFERENCES`
- `SELECT_CAPABILITY`
- `EXECUTE_CAPABILITY`
- `RESPOND`
- `PERSIST_RESULT`

They now carry the same typed workpiece through the current interactive path. `RESPOND` is a compatibility key/interface station, not a claim that every Prometheist task must generate prose.

## Internal-memory investigation

The current deeper memory capability surface remains:

- `deeper_research`
- `cross_reference`
- `focused_recall`

Automatic activation is wide/shallow; selected investigation narrows subjects while increasing bounded associative depth. Canonical evidence remains exact/provenance-bearing; activation never promotes content to truth.

## Key dated records

- [`V06_INTEGRATION_INVENTORY_2026-08-25.md`](V06_INTEGRATION_INVENTORY_2026-08-25.md) — post-v0.6 integration inventory.
- [`JIT_ATTENTION_DESIGN.md`](JIT_ATTENTION_DESIGN.md) — Attention Fabric implementation sequence.
- [`RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md`](RESOURCE_ADMISSION_CLARIFICATION_2026-08-24.md) — attention priority versus resource admission.
- [`ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md`](ATTENTION_FOCUS_CONCENTRATION_2026-08-26.md) — safe parallelism versus resource concentration.
- [`INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md`](INCREMENT_F_WORKER_PROTOCOL_2026-08-26.md) — durable disposable-worker protocol.
- [`INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md`](INCREMENT_G_INTERACTION_EXECUTION_2026-08-26.md) — original durable interaction integration record; later continuity/routing mechanisms supersede parts of it.
- [`WORKING_STATE_PIVOT_2026-08-26.md`](WORKING_STATE_PIVOT_2026-08-26.md) — continuity/WorkingState negative results and pivot.
- [`PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md`](PRE_COGNITIVE_TRANSIENT_WORKERS_2026-08-28.md) — transient cognition evolution and native Qwen failure evidence.
- [`INTERACTION_WORKPIECE_2026-08-28.md`](INTERACTION_WORKPIECE_2026-08-28.md) — typed workpiece/general terminalization decision.

## Constitutional changes

Constitution v1.2 now explicitly states:

- semantic reassessment is demand-driven, bounded, and always fresh;
- workpieces/components are application-owned;
- workers receive minimum projections and cannot mutate the cumulative workpiece;
- terminalization is general and natural-language response is optional;
- the terminal workpiece JSON complements, rather than replaces, append-only causal history.

## Release gates

Do **not** call v0.7 complete or merge the transient-worker PR solely because code/docs look correct.

Required before closure:

1. static checks and fully registered constraint audit on the exact final head;
2. full deterministic PostgreSQL suite on the exact final head;
3. native Windows/PostgreSQL/Ollama Qwen3:4b acceptance through `scripts/run_v07_acceptance.ps1`;
4. review/branch/release cleanup after the native gate succeeds.

The native suite must continue to include the established restart, randomized opaque-fact, cross-process/cross-conversation, and multi-turn stateless-continuity scenarios.

For those continuity scenarios, the automated oracle now ends at the final response boundary: it reconstructs the policy-admitted `FINAL_EVIDENCE`/`FINAL_RESPONSE_DIRECTIVE` handoff from the terminal workpiece and verifies that the fresh responder had the required canonical facts and provenance. The actual Prometheist response is printed in full for human inspection but is not forced into pipe-delimited or other canned prose unless exact formatting is itself the behavior under test. See [`../../engineering/TESTING_AND_ACCEPTANCE.md`](../../engineering/TESTING_AND_ACCEPTANCE.md).

## What v0.7 deliberately does not claim

v0.7 does not yet implement general grocery ordering, appointment booking, device control, deterministic perception/salience, retention policy, semantic embedding retrieval, or the complete integrated cognitive loop.

It establishes the durable execution substrate and typed architecture those future mechanisms can plug into without reintroducing permanent agents, hidden LLM continuity, or mandatory chatbot response semantics.

## Next

After v0.7 closes, rebaseline v0.8 against native results, current WorkingState/workpiece behavior, and the neuroscience/similar-system research before adding the next major mechanism. The current default is deterministic perception/salience; richer epistemic WorkingState may move earlier only through an explicit roadmap change backed by evidence.
