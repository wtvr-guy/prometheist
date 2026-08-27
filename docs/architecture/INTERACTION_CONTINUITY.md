# Interaction Continuity

**Status:** active architecture requirement. Revised 2026-08-27 from native v0.7 acceptance evidence.

**Constitutional status:** primary architecture authority for Articles 5, 6, 7, 8, 15, 16, 20, 27, and 29 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md). This document explains those constitutional rules in depth and is subordinate to the Constitution where wording conflicts.

## Governing invariant

> **Conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Current context and basic access to persistent memory are system-owned cognitive substrate.**

Three durable mechanisms remain distinct:

- **WorkingState**: which canonical events are active now?
- **JIT Memory**: which canonical persisted evidence is potentially relevant now?
- **JIT Attention**: which durable work receives execution/resources now?

No LLM call owns any of those states.

## Experimental corrections

Native acceptance rejected several earlier assumptions.

1. **Phrase-cue continuity failed as a general mechanism.** A growing vocabulary of entity/recency/reference phrases produced local fixes and regressions. The live phrase detector is therefore disabled. Minimal WorkingState now contains bounded canonical active-event IDs.
2. **Ask-before-remembering is circular.** A stateless model cannot reliably decide whether unseen memory matters when the evidence required for that decision may itself be in memory. Every percept therefore receives bounded memory activation before model routing.
3. **A capability list is not an execution schedule.** Models select requirements. Prometheist owns dependency closure, deterministic ordering, resource policy, and execution.
4. **One capability pass is too shallow.** A worker may discover after one capability round that it still lacks evidence. Capability use therefore forms a bounded recurrent loop of fresh stateless model calls.
5. **Generated search text is unnecessary control state.** Memory research now selects canonical candidates by bounded index rather than generating queries, entities, event IDs, or explanations.

These changes are architectural responses to observed failures, not Kestrel-specific patches.

## Default memory activation: broad and shallow

Every percept automatically opens a small, bounded memory context before any routing model is called.

```text
current percept
    +
bounded WorkingState event IDs
    |
    v
deterministic high-recall candidate activation
    |
    v
small initial MemoryPacket
```

The initial activation intentionally **casts a relatively wide deterministic net but exposes only a small packet**. It uses a larger bounded candidate window and no association traversal. An item means “potentially relevant enough to keep available,” not “proved sufficient evidence.”

This is cognitive substrate, not a model-selected capability.

The current v0.7 deterministic profile uses a direct candidate window of 750 and zero association hops before surfacing the bounded packet. Those numbers are registered implementation constraints, not constitutional constants; changing them requires the evidence process in [`../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md).

## Recurrent stateless capability loop

After initial activation, a fresh routing model receives:

- the original percept;
- the currently accumulated bounded MemoryPacket;
- structured summaries/results from completed capabilities;
- the currently legal application-owned capability catalog.

Its output is closed and mechanically validated:

```text
RESPOND
    capability_indices = []

or

USE_CAPABILITIES
    capability_indices = [i, ...]   # current v0.7: 1-4 unique catalog indices
```

`RESPOND` must be explicit. An omitted/invalid action does not silently become a response.

If `USE_CAPABILITIES` is selected, that LLM call ends. Prometheist then:

1. resolves the selected catalog indices;
2. expands application-owned dependencies;
3. deterministically orders runnable work;
4. executes the selected capabilities;
5. persists structured results and evidence;
6. composes the next bounded cognitive context;
7. exposes any legal follow-up capabilities;
8. invokes a **new stateless routing model call**.

The original public capabilities remain available in later rounds, so the fresh worker may reuse them. Follow-up capabilities may also become visible after prerequisite research produced usable evidence.

The current v0.7 capability loop is bounded to four capability rounds. Four is an empirical/runtime constraint, not a constitutional constant. Reaching the configured bound without an explicit `RESPOND` fails closed rather than forcing a potentially unsupported answer.

## Progressive memory focus

The internal retrieval strategy deliberately narrows candidate subjects while increasing the bounded associative neighborhood around those subjects.

### Level 1 — automatic broad activation

- happens on every percept;
- current direct candidate window: 750;
- association hops: 0;
- small bounded surfaced packet;
- high-recall activation role.

### Level 2 — `deeper_research`

Public meaning:

> **Investigate the current question further using additional persisted internal evidence around one or more currently available memory candidates.**

The fresh capability worker selects **1-4 candidate indices** from the current MemoryPacket. It does not generate search text. Prometheist resolves those indices to canonical event IDs and performs a narrower direct search with a broader association budget around each selected candidate.

Current v0.7 deterministic profile:

- direct candidate window: 350;
- association edges: up to 600;
- association hops: up to 3;
- bounded returned evidence.

These are registered implementation bounds governed by empirical constraint policy.

### Level 2b — `cross_reference`

Public meaning:

> **Investigate relationships among two or more currently available internal memory candidates, including shared, conflicting, causal, or bridging evidence.**

The worker selects **2-4 candidate indices** only. Prometheist resolves them to canonical events and performs one joint bounded associative investigation over the selected set. The model does not write a relationship description.

Current v0.7 deterministic profile:

- direct candidate window: 250;
- association edges: up to 900;
- association hops: up to 4;
- bounded returned evidence.

These are registered implementation bounds governed by empirical constraint policy.

### Level 3 — `focused_recall`

Public meaning:

> **Investigate one selected internal memory candidate with the deepest bounded association search when a specific ambiguity remains unresolved.**

`focused_recall` is hidden from the initial catalog and becomes available after broader research produces usable evidence. The worker selects exactly one candidate index from the most recent non-empty broader-research packet.

Current v0.7 deterministic profile:

- direct candidate window: 150;
- association edges: up to 1200;
- association hops: up to 5;
- bounded returned evidence.

These are registered implementation bounds governed by empirical constraint policy.

If focused recall returns no useful evidence, no response is forced. The next fresh routing worker may:

- explicitly `RESPOND` with the evidence already available;
- run `focused_recall` again against a different candidate;
- return to `deeper_research`;
- cross-reference another candidate set;
- invoke another installed capability.

The conservative evidence-admission threshold is unchanged at every research depth. Narrowing attention must not silently weaken skepticism.

## Multiple capabilities and deterministic ordering

Capability indices are a requirement set, never an execution order. Private registry metadata defines dependencies and execution priority. Prometheist computes dependency closure and applies the generic Attention ordering primitive:

```text
selected capability indices
    -> canonical capability IDs
    -> dependency closure
    -> reject missing dependencies/cycles
    -> topological order
    -> stable ready-item tie break by execution_priority, then capability_id
```

For the current v0.7 implementation, selected capabilities execute as bounded substeps inside the already admitted interaction assignment. Later releases may promote capability plan items to independently scheduled child tasks without changing the model-selection contract.

System-wide deterministic control is governed by [`SYSTEM_DETERMINISM.md`](SYSTEM_DETERMINISM.md); execution/resource authority is governed by [`ATTENTION_AND_EXECUTION_GOVERNANCE.md`](ATTENTION_AND_EXECUTION_GOVERNANCE.md).

## Final-response barrier

A user-facing response worker is summoned only after a fresh routing call explicitly chooses `RESPOND`.

The final worker receives:

- the original percept;
- the bounded accumulated MemoryPacket;
- the structured results of completed capabilities.

It does not inherit a previous LLM context window. User-facing language is generated once, after Prometheist has determined that the required evidence/work is ready.

## Minimal v0.7 WorkingState

```text
state_id
revision
conversation_ids
active_event_ids
```

`active_event_ids` are bounded pointers to canonical events. WorkingState is not a copied transcript, summary, user-profile blob, parsed nickname table, or truth store. The append-only event ledger remains authoritative.

Future WorkingState schemas may become richer only through experimentally justified structured state. They must preserve the constitutional boundedness and canonical-provenance rules.

## System-wide model-output rule

> **Model-generated natural language is the representation of last resort. Use it only when language is genuinely the product or no smaller mechanically verifiable representation can express the required semantics.**

Preferred order:

```text
enum / boolean / bounded integer / application-owned ID
    before
mechanically verified extractive selection
    before
free-form generated natural language
```

The live v0.7 control path therefore uses:

- explicit action enums;
- bounded capability indices;
- bounded MemoryPacket candidate indices;
- application-owned capability IDs, dependencies, resource policies, event IDs, and execution order;
- structured capability results.

It does **not** use model-generated capability names, queries, entities, event IDs, relationship descriptions, execution orders, dependency declarations, or explanations as machine control state.

Final user-facing response text remains free-form because language is the product at that boundary.

Tests follow the same principle. Acceptance tests must not grow hand-written English parsers or keyword-list semantic oracles. Where deterministic verification is required, tests should request machine-verifiable values and independently verify canonical source-event provenance.

## Text cues: deprecated versus valid

The old interaction-layer `requires_persisted_context()` phrase detector is deprecated and disabled. Application policy does not maintain a vocabulary for phrases such as `just`, `those approaches`, or `this plan`.

This does **not** deprecate canonical text retrieval inside JIT Memory. Lexical specificity, deterministic associations, temporal cues, canonical candidate text, and future experimentally justified candidate generators remain valid retrieval mechanisms. The rejected pattern is model/application-authored natural-language control policy, not source evidence.

## Epistemic boundary

Activation and retrieval are attention operations, not truth promotion. A surfaced event means it is relevant enough to expose. It does not mean every proposition in it is correct, current, or objectively true.

Evidence, user belief, world belief, contradictions, corrections, confidence, and derived conclusions remain distinct epistemic concerns. The Constitution requires the distinction even where a richer structured epistemic WorkingState remains future work.

## Fail-closed interaction authority

Invalid or ambiguous control output does not get repaired by guessing intent. Missing explicit `RESPOND`, out-of-range/duplicate capability indices, illegal capability requests, exhausted recurrent bounds, and insufficient historical evidence must result in the structured failure/abstention behavior defined by policy rather than fabricated readiness.

## Frozen v0.7 experiment

The Kestrel continuity scenario remains an end-to-end experiment, not a special-case rule source. It must demonstrate that:

- Turn 1 automatically exposes the pre-existing Kestrel constraint before capability choice;
- the response respects that constraint and selects PostgreSQL directly on Windows rather than Docker;
- cross-process and cross-conversation recall still work;
- every model call remains stateless;
- WorkingState and MemoryPackets remain bounded;
- provenance and opaque identifiers remain exact;
- no phrase-specific continuity rules or generated search/control text are required;
- the fresh worker can respond or run one/multiple capabilities repeatedly;
- memory research can progress broad -> candidate-focused/cross-referenced -> single-candidate focused;
- final response occurs only after explicit `RESPOND`;
- deterministic CI passes before native Ollama acceptance.

If the experiment fails, diagnose the general WorkingState/JIT-Memory/recurrent-capability boundary. Do not add another English phrase rule merely to make the fixture green.

> **Current cognitive context and basic access to persistent memory belong to Prometheist itself—not to a chat transcript, worker, model context window, phrase heuristic, or model-authored request to remember.**
