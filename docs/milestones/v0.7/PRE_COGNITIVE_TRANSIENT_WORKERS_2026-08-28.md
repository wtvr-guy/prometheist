# v0.7 Pre-Cognitive Transient Worker Increment — 2026-08-28

## Decision

The production interaction path is being changed from the recurrent fresh-model capability router introduced during Increment G to a staged pre-cognitive transient-worker scheme.

The change is intentionally isolated from model selection. Native acceptance remains on the current Qwen3 4B Ollama configuration so the mechanism can be evaluated without simultaneously changing model capacity.

## Problem being tested

The prior recurrent router satisfied statelessness, but it could spend several local-model invocations deciding whether to perform more capability work. On the development machine, repeated 4B inference is a significant part of end-to-end latency. The architectural question is whether Prometheist can preserve deep, obscure recall and current-turn continuity by staging evidence acquisition before response synthesis rather than repeatedly asking a general router what to do next.

The hypothesis is:

> A bounded JIT aperture plus one pre-cognitive assessment, deterministic staged acquisition, one post-capability reassessment when work actually ran, and a fresh responder can preserve reasoning depth while materially reducing recurrent inference overhead.

## Implementation boundary

This increment deliberately preserves the existing durable five-stage interaction protocol so that worker identity, leases, restart recovery, scheduler assignments, and existing persistence tables do not change in the same experiment.

Production subprocess execution now routes through:

- `src/jit_agent/pre_cognitive_workers.py`
- `src/jit_agent/interaction_worker.py`

The older recurrent implementation remains in `interaction_runtime.py` temporarily for deterministic regression fixtures and compatibility. The CLI/native subprocess path uses the new scheme.

## New cognitive control contract

`PreCognitiveAssessment` is a closed Pydantic schema. The worker may emit only:

- cognitive phase;
- disposition (`RESPOND`, `ACQUIRE_CAPABILITIES`, `ABSTAIN`);
- broad intent mode;
- evidence state;
- bounded claim scopes;
- bounded requirement flags;
- integer indices into the application-owned catalog.

It cannot author queries, capability IDs, tool arguments, event IDs, dependencies, execution order, resource policy, or prose plans.

## Staged execution

### Fast path

1. Persist percept and obtain Attention assignment.
2. Inspect bounded WorkingState availability.
3. Open the automatic JIT attention aperture.
4. Run one fresh `PRE_CAPABILITY` cognition worker.
5. If evidence is sufficient, run one fresh response worker.
6. Persist response and activate WorkingState.

Expected primary LLM calls: 2.

### Capability path

1. Run the same initial path through `PRE_CAPABILITY`.
2. Validate selected catalog indices and build the deterministic dependency plan.
3. Execute first-tranche capabilities under existing guarded worker/resource policy.
4. Compose a bounded packet of exact canonical evidence without rewriting source content.
5. Expose only capabilities newly enabled by the completed tranche.
6. Run one fresh `POST_CAPABILITY` cognition worker.
7. Optionally execute one newly exposed follow-up tranche.
8. Run one fresh response worker.

Expected primary routing/synthesis LLM calls: 3 when post-capability cognition is needed, plus any bounded capability-specific candidate selector calls.

## Restart safety

A pre/post cognitive decision is material control state. It is therefore persisted before downstream capability effects.

Each phase uses a deterministic event identity derived from the interaction ID. A retry verifies:

- scheme version;
- phase;
- memory request used as input;
- capability catalog IDs;
- validated assessment schema;
- deterministic execution plan.

If the event exists, the worker reuses it rather than invoking the model again. This prevents a crash after model inference from re-rolling a nondeterministic control decision.

## Evidence safety

The new context composer only copies existing `MemoryEvidence` objects and deduplicates canonical source IDs. It does not generate summaries or synthetic replacement memories. The current bound remains a working-context implementation value, not a retention rule.

The response worker remains subject to the existing evidence-authority, exact-source, response-policy, and model-facing evidence-budget layers. A pre-cognitive `RESPOND` classification is not authority to fabricate unsupported history.

## Resource policy

No resource-safety rule changes in this increment:

- Attention owns priority;
- admission owns concurrency;
- launch-time claims are still guarded;
- OS/user headroom remains reserved;
- local inference defaults to one LLM slot;
- Ollama runtime residency remains part of the admission estimate.

The expected efficiency improvement comes from fewer unnecessary model calls, not weaker admission.

## Constitution amendment

This experiment required an explicit amendment to Constitution Article 27. The old article required recurrent capability reasoning. Version 1.1 replaces that mechanism-level requirement with the invariant that semantic reassessment must be fresh, bounded, staged, and application-authorized whenever newly acquired evidence requires another judgment.

The authoritative deep dive is [`../../architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](../../architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md).

## Deterministic tests added

`tests/test_pre_cognitive_workers.py` covers:

- rejection of free-form/extra model-control fields;
- disposition/index invariants;
- out-of-catalog failure;
- compatibility mapping for legacy fake clients;
- follow-up catalog narrowing;
- exact evidence preservation and source-ID deduplication.

Existing worker/restart, evidence-budget, epistemic-authority, response-policy, cross-process, and memory-continuity tests remain regression requirements.

## Native acceptance required

This increment is not accepted until Qwen3:4b is exercised on the development machine. Native testing should record:

- correctness on the current v0.7 acceptance suite;
- the red-team obscure-memory cases that motivated the change;
- LLM invocation count per interaction;
- pre-cognitive, post-cognitive, response, and total latency;
- prompt/evidence size per invocation;
- RAM/headroom and Ollama residency behavior;
- forced process death/restart around persisted cognitive decisions.

Do not upgrade to a 12–14B model as part of this acceptance run. A larger quantized model is a separate future experiment after this mechanism has a clean Qwen3:4b baseline.
