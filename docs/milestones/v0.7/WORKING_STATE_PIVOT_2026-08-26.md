# v0.7 Working-State, Default Memory, and Recurrent Capability Pivot — 2026-08-26/27

> **Historical design record.** The WorkingState and automatic-memory findings remain
> accepted, but the recurrent general capability router and separate named memory
> capabilities described below were superseded by the 2026-08-29 v2 pipeline. See
> [`../../architecture/PERCEPT_TO_RESPONSE_PIPELINE.md`](../../architecture/PERCEPT_TO_RESPONSE_PIPELINE.md).

## Status at the recorded revision

Accepted design correction inside the v0.7 release candidate. This does not pull the full future epistemic/cognitive-state roadmap into v0.7. It adds only the minimal durable active-state, default-memory-exposure, constrained recurrent capability-selection, progressive memory-research, and deterministic capability-execution mechanisms required by the frozen native continuity experiment.

## Experimental sequence

Native Windows/PostgreSQL/Ollama acceptance exposed several architectural failures.

### Negative result A — phrase-cue continuity

The first v0.7 interaction path attempted to reconstruct the current cognitive situation from each new utterance by progressively adding application-owned text cues: supplemental formulations, scope corrections, entity extraction, singleton proper-name extraction, and recency/reference-time phrase detection.

Each repair was locally defensible, but the sequence created an ever-growing vocabulary problem and one temporal heuristic regressed a previously passing turn.

> **Result A:** direct utterance -> hand-maintained phrase/entity/recency cues -> MemoryNeed is not accepted as the general continuity mechanism.

The intervention was a minimal durable `InteractionWorkingState` containing only bounded canonical active-event IDs.

### Negative result B — ask before remembering

After WorkingState and constrained routing were introduced, the Kestrel scenario exposed a deeper problem on its first active turn. The current percept explicitly mentioned Project Kestrel, Docker Compose, and PostgreSQL on Windows, while persistent memory already contained a user-authored rule forbidding Docker. The classifier nevertheless selected no memory capability because it saw only the current percept. The response worker therefore never saw the historical rule and recommended the conflicting option.

That failure is not specific to Kestrel. It reveals a circular dependency:

> **A stateless model cannot reliably decide whether unseen persistent memory is relevant when the evidence required to make that decision may itself be in persistent memory.**

> **Result B:** basic access to Prometheist's own persistent memory must not depend on a model first requesting a memory capability.

### Negative result C — model-owned execution order

Once the post-memory model is allowed to select more than one optional capability, a returned list cannot safely double as an execution plan. Dependencies, resource policy, and stable ordering are system concerns.

> **Result C:** the model selects the required capability set; Prometheist owns dependency expansion and execution order.

The registry stores private dependency/priority metadata. Prometheist expands selected capability dependencies, rejects cycles, and repeatedly chooses the highest-priority currently runnable item, recomputing readiness after every completion. Canonical capability ID is the deterministic tie-breaker.

### Negative result D — intermediate prose from capabilities

A memory-focused capability previously had a path to generate its own prose answer. That creates multiple generative boundaries and makes final composition ambiguous once several capabilities are selected.

> **Result D:** capabilities should return structured evidence/state whenever possible; user-facing natural language should be generated only by one fresh final response worker.

### Negative result E — one capability pass is too shallow

A model may discover only after a capability completes that it still lacks enough evidence to respond. A single capability-selection call followed automatically by final response therefore encodes an unjustified assumption about reasoning depth.

> **Result E:** capability use is a bounded recurrent system loop of fresh stateless model calls, not a one-shot routing decision.

Each routing call explicitly returns `RESPOND` or `USE_CAPABILITIES`. If capabilities are selected, that LLM invocation ends. Prometheist executes and persists the selected work, rebuilds bounded context, exposes any legal follow-up capabilities, then invokes an entirely fresh stateless routing call. Only an explicit `RESPOND` permits final language generation.

### Operational correction F — transient resource pressure is delay, not permission to weaken safety

Native acceptance also observed a guarded launch denied at 4092 MiB safely available versus a 4096 MiB reservation after several successful local-model calls.

The correct response is not to reduce headroom or admission thresholds. A transient resource-pressure/probe denial now receives a small bounded number of fresh claim-time observations. Structural denials remain terminal.

> **Result F:** transient safe-capacity pressure may delay/retry work; it must not silently weaken the committed resource-safety policy.

## Research synthesis

The concept reports in `docs/concepts/` support the same separation without being treated as authority by analogy:

- `lessons_from_cognitive_neuroscience.md` identifies bounded working state distinct from long-term memory and emphasizes selective activation/focused retrieval rather than full-history context.
- `lessons_from_similar_projects.md` identifies current-situation representations, bounded memory access, and system-owned orchestration across mature cognitive and agent architectures.

The changes are justified by observed native failures; the research synthesis helps explain why the replacement mechanisms are plausible.

## Minimal v0.7 WorkingState

`InteractionWorkingState` remains deliberately small:

```text
state_id
revision
conversation_ids       # provenance/binding only
active_event_ids       # bounded canonical event pointers
```

It does not store a free-form summary, inferred truth, user profile, parsed nickname table, option table, or referential phrase vocabulary. The append-only event ledger remains authoritative.

## Default memory activation — deliberately broad and shallow

Every percept automatically receives a small, bounded, provenance-bearing JIT Memory packet before any model routing decision.

```text
percept + durable WorkingState
        |
        v
wide deterministic candidate activation
        |
        v
small initial MemoryPacket
        |
        v
fresh stateless routing decision
```

The initial activation deliberately casts a wide net while surfacing only a small packet. It uses a large bounded direct candidate window and no association traversal. Its purpose is high-recall activation, not a claim that surfaced evidence is sufficient or true.

Basic memory exposure is cognitive substrate and is not model-selected.

## Recurrent capability loop

The routing model receives only system-owned bounded inputs:

- the original percept;
- the current accumulated MemoryPacket;
- structured summaries/results from completed capabilities;
- the currently legal capability catalog.

Its closed output is:

```text
RESPOND
  capability_indices = []

or

USE_CAPABILITIES
  capability_indices = [i, ...]   # 1-4 unique bounded indices
```

The model does not write capability names, queries, entities, execution order, dependencies, or explanations.

If `USE_CAPABILITIES` is selected, the model call terminates. Prometheist resolves indices, expands dependencies, deterministically executes the work, persists structured results, rebuilds bounded context, and summons a **new stateless routing call**.

The loop is capped at four capability rounds. Reaching the cap without an explicit `RESPOND` fails closed.

## Progressive memory investigation

Memory investigation narrows the number of selected candidate subjects while expanding the bounded associative neighborhood around those subjects.

### Level 1 — automatic broad activation

- every percept;
- direct candidate window: 750;
- association hops: 0;
- small bounded surfaced packet;
- high-recall activation role.

### Level 2 — `deeper_research`

Public semantic contract:

> **Investigate the current question further using additional persisted internal evidence around one or more currently available memory candidates.**

The fresh capability worker selects 1–4 candidate indices from the current MemoryPacket. Prometheist resolves them to canonical event IDs and uses those canonical events as association seeds.

Current deterministic bounds:

- direct candidate window: 350;
- association edges: up to 600;
- association hops: up to 3;
- bounded returned evidence.

### Level 2b — `cross_reference`

Public semantic contract:

> **Investigate relationships among two or more currently available internal memory candidates, including shared, conflicting, causal, or bridging evidence.**

The model selects 2–4 candidate indices only. Prometheist performs one joint associative investigation seeded by all selected canonical event IDs. It does not ask the model to generate a relationship/search description.

Current deterministic bounds:

- direct candidate window: 250;
- association edges: up to 900;
- association hops: up to 4;
- bounded returned evidence.

### Level 3 — `focused_recall`

Public semantic contract:

> **Investigate one selected internal memory candidate with the deepest bounded association search when a specific ambiguity remains unresolved.**

`focused_recall` is not in the initial catalog. It becomes available after broader research produces usable evidence. The worker selects exactly one candidate index from the most recent non-empty broader-research packet.

Current deterministic bounds:

- direct candidate window: 150;
- association edges: up to 1200;
- association hops: up to 5;
- bounded returned evidence.

If focused recall returns no useful evidence, Prometheist does not force a response. The next fresh selector can explicitly respond, focus another candidate, return to broader research, cross-reference another set, or use another capability.

The conservative evidence-admission threshold remains unchanged at all levels. Narrowing attention does not weaken skepticism or turn relevance into truth.

## Multiple capabilities and deterministic Attention ordering

Capability indices specify requirements, not order.

Prometheist uses application-owned registry metadata and the generic Attention ordering primitive:

```text
selected indices
    -> canonical capability IDs
    -> dependency closure
    -> reject missing dependencies/cycles
    -> repeatedly select highest-priority currently runnable item
    -> canonical capability-ID tie break
```

Readiness is recomputed after every completed item so newly unblocked higher-priority work can run before lower-priority work that was already runnable.

For v0.7, these capability items execute as bounded substeps of one already admitted interaction assignment. Later versions may promote them to separately scheduled child Attention tasks without changing the model-selection contract.

## Final-response barrier

Completion of a capability round does **not** automatically permit a response.

Only a fresh routing call returning explicit `RESPOND` allows the final response worker to be summoned. That final worker receives the original percept, accumulated bounded memory evidence, and structured capability results. It inherits no previous model context window.

## System-wide model-output rule

The native failures establish a system-wide protocol preference:

> **Model-generated natural language is the representation of last resort. Use it only when natural language is genuinely the product or when no smaller mechanically verifiable representation can express the required semantics.**

Preferred order:

```text
enum / boolean / application-owned ID / bounded integer
    before
mechanically verified extractive selection
    before
free-form generated natural language
```

For the live v0.7 path:

- routing returns only an explicit closed action plus bounded capability indices;
- candidate-focused memory research returns only bounded candidate indices;
- `cross_reference` returns 2–4 candidate indices;
- `focused_recall` returns exactly one candidate index;
- basic internal-memory activation is automatic and absent from the selectable catalog;
- capability IDs, dependencies, priorities, executors, resource policy, canonical event IDs, traversal depth, and ordering are application-owned;
- the model emits no generated capability query/input, retrieval query, entity string, relationship description, executor name, event ID, dependency declaration, execution order, or explanation as machine control state;
- invalid, duplicate, out-of-range, contradictory, omitted, or unexpected fields fail validation;
- capabilities return structured evidence/results rather than intermediate prose;
- final user-facing response text is the sole live free-form NL output because language is the product at that boundary.

The same rule applies to tests. Acceptance must not grow a hand-written English parser or keyword-slot list. Where the experiment needs a deterministic verdict, the fixture requests an exact machine-verifiable value/tuple and checks canonical source-event provenance independently.

## Revised live interaction path

```text
new percept
    -> durable interaction task
    -> load bounded durable WorkingState
    -> automatic wide/shallow bounded memory activation
    -> fresh stateless routing call
       -> RESPOND: proceed to final response
       -> USE_CAPABILITIES: resolve bounded indices
    -> Prometheist expands dependencies and deterministically orders execution
    -> execute selected capabilities to structured durable results
    -> compose accumulated bounded context
    -> expose legal follow-up capabilities
    -> NEW stateless routing call
       -> repeat, switch focus/capability, or explicit RESPOND
    -> after explicit RESPOND only:
       -> one fresh stateless final response synthesis
       -> persist response
       -> promote surfaced canonical evidence + prompt/response into WorkingState
```

This separates:

- **WorkingState:** what canonical evidence is active now?
- **default memory activation:** what bounded potentially relevant persistent evidence should every fresh inference see?
- **progressive memory research:** which currently surfaced canonical candidates deserve deeper associative investigation?
- **capability execution:** what required functions must run and in what system-owned order?
- **recurrent routing:** does the next fresh stateless worker have enough to respond or should it request more capability work?
- **JIT Attention:** what durable task deserves execution/resources now?
- **final response:** what user-facing language should be generated after explicit readiness?

No LLM invocation owns any of those durable states.

## Resource-pressure retry boundary

The guarded worker launcher preserves fail-closed admission. It does not lower a reservation, headroom, CPU-pressure threshold, or RAM threshold to make progress.

When a denied claim's structured resource snapshot shows transient probe failure or insufficient/unobserved capacity for that task's persisted reservation, the launcher may perform up to four fresh claim-time observations separated by a short delay. Every denial remains durably recorded. If capacity does not recover, launch still fails closed.

Denials caused by structural state—stale task/assignment, policy mismatch, live claim, terminal result, at-most-once ambiguity, and similar integrity conditions—are not retried.

## Deprecations

The old `requires_persisted_context()` phrase detector remains disabled. v0.7 does not generate interaction-layer project/proper-name/recency cues through hand-maintained regex policy, and the default capability registry does not carry a continuity phrase vocabulary.

The earlier `MEMORY_ANALYSIS` live capability name is superseded by `deeper_research`. The old intermediate memory-analysis prose-answer path is removed from the live architecture.

The earlier token-anchor/query-generating memory planner is also superseded in the live path. Memory research selects canonical packet candidates by index.

The earlier `why/reason/cause` response-layer semantic regex helper is removed. A fresh response model receives bounded canonical evidence directly rather than application code parsing a subset of English semantics.

Lexical/entity/association/temporal mechanisms remain valid inside JIT Memory. Canonical source text is evidence, not model-authored policy.

## Skepticism boundary

WorkingState activation and memory retrieval are relevance operations, not truth promotion.

An active or retrieved canonical event means only that it is currently relevant enough to expose. It does not mean every proposition inside it is objectively true/current. Evidence, interpretation, user belief, world belief, corrections, contradictions, confidence, and future hypotheses remain separate concerns.

## Frozen acceptance experiment

The four-turn Kestrel continuity scenario remains the fixed experiment. The intervention is accepted only if it:

1. retrieves the pre-existing Kestrel rule on Turn 1 before routing;
2. chooses PostgreSQL directly on Windows rather than Docker;
3. preserves already-passing cross-process Oriole/Falcon and cross-conversation cases;
4. completes all four Kestrel turns without inherited model context;
5. survives fresh worker processes between stages/turns;
6. returns canonical source-event provenance;
7. keeps WorkingState and MemoryPackets bounded;
8. uses no phrase-specific continuity regexes;
9. uses no model-generated natural-language capability/search/entity/order fields;
10. uses explicit `RESPOND` / `USE_CAPABILITIES` routing with bounded indices;
11. supports zero, one, or multiple optional capabilities and multiple fresh routing rounds;
12. can deepen, cross-reference, or focus memory candidates through index-only selections;
13. deterministically expands dependencies and orders runnable capability work;
14. does not summon the final response worker until a fresh selector explicitly chooses `RESPOND`;
15. preserves the configured resource-safety thresholds while tolerating bounded transient pressure through re-observation;
16. passes deterministic non-Ollama CI before native Ollama acceptance.

If the benchmark fails, diagnose the WorkingState/JIT-Memory/capability/recurrent-routing boundary or constrained model protocol. Do not add another English phrase rule or generated search field merely to make the fixture green.

## Scope boundary

This remains minimal v0.7 cognition. Goals/subgoals, hypotheses, confidence, alternatives, contradictions, prediction error, episode formation, consolidation/replay, procedural memory, and richer situation assembly remain later experimentally justified mechanisms.

> **v0.7 invariant: Prometheist owns continuity, basic access to its memory, progressive evidence focus, capability execution order, recurrent routing state, resource safety, and final-response readiness; models and workers are disposable compute.**
