# Interaction Continuity

**Status:** active architecture requirement. Revised 2026-08-26 after native v0.7 acceptance falsified the phrase-cue continuity approach.

## Principle

Prometheist must not require a user to manage conversations as memory namespaces, and it must not require application code to enumerate every natural-language way a user can refer to recent context.

The governing invariant is:

> **Conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Current context is system-owned durable state; older evidence is reconstructed just in time from persistent memory.**

This distinction is now explicit:

- **WorkingState** answers: which canonical events are active now?
- **JIT Memory** answers: which older persisted evidence satisfies an unresolved information need?
- **JIT Attention** answers: which durable task deserves execution/resources now?

No LLM invocation owns any of those states.

## Why the v0.7 mechanism changed

The first v0.7 release-candidate implementation attempted to reconstruct continuity directly from each current utterance. Native Ollama acceptance exposed a sequence of increasingly specific repairs: supplemental query handoff, cross-conversation scope, proper-name/entity extraction, singleton entity extraction, and temporal phrase detection.

Those repairs improved individual cases, but the pattern itself was a warning. One temporal heuristic also regressed a previously passing turn when `those approaches` was interpreted as a recency cue.

The project therefore treats the experiment as a negative result:

> **Direct utterance -> hand-maintained text/entity/recency cues -> MemoryNeed is not accepted as the general interaction-continuity architecture.**

See [`../milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md`](../milestones/v0.7/WORKING_STATE_PIVOT_2026-08-26.md).

## Minimal v0.7 WorkingState

v0.7 introduces a deliberately small `InteractionWorkingState`:

```text
state_id
revision
conversation_ids
active_event_ids
```

`active_event_ids` is a bounded set of pointers to canonical event-log entries that are currently activated by the interaction process.

WorkingState is **not**:

- a copied transcript;
- a free-form LLM summary;
- a second autobiographical memory store;
- a user-profile blob;
- a parsed table of nicknames/options/conclusions;
- a claim that the content of an active event is objectively true.

The append-only event ledger remains authoritative. WorkingState only says which source events are currently active.

## Model-output minimization

The v0.7 failures also exposed a broader control-plane rule:

> **A model should generate natural language only when natural language is the actual product. Control decisions should be represented with the smallest closed or mechanically verifiable schema that can express them.**

For the live v0.7 path:

- interaction routing returns one capability-requirement enum (`NONE`, `INTERNAL_MEMORY`, or `MEMORY_ANALYSIS`);
- capability ids are application-owned deterministic mappings from that enum;
- the model does not emit `capability_query` or `capability_input` strings;
- memory routing returns one scope enum (`ACTIVE_ONLY`, `HISTORY_ONLY`, or `ACTIVE_AND_HISTORY`) plus bounded integer indices;
- those indices refer to a deterministic anchor catalog built from the exact current task and active canonical event text;
- an index outside the supplied catalog is rejected;
- extra schema fields are rejected rather than silently ignored;
- the model never writes a retrieval query, entity string, temporal phrase rule, executor name, limit, database control, or event id.

Free-form model output remains appropriate for the final user-facing answer and other future artifacts whose purpose is language generation. It is not the default representation for system policy.

This is stronger than merely using JSON. A JSON string field can still smuggle an unconstrained natural-language control decision into the system. The preferred order is:

```text
enum / boolean / id / bounded index
    before
extractive exact-span selection
    before
free-form generated text
```

## Revised interaction path

```text
external turn
    -> durable interaction task
    -> load current WorkingState
    -> fresh stateless categorical capability routing
    -> if memory is needed, build deterministic anchor catalog from current task + active canonical events
    -> fresh stateless memory routing chooses scope enum + anchor indices only
    -> JIT Memory rehydrates active canonical events
    -> if requested, deterministic long-term recall retrieves older canonical evidence
    -> compose bounded active + historical evidence without either class starving the other
    -> fresh stateless response synthesis
    -> persist response
    -> activate current prompt/response and newly used evidence
```

A fresh worker can therefore reconstruct the present situation without inheriting an LLM context window, reverse-engineering continuity from a phrase list, or generating its own control-plane search language.

## Text cues: what is deprecated and what remains

The old interaction-layer phrase detector (`requires_persisted_context`) is deprecated and disabled in the live path. It is retained temporarily only as a compatibility symbol while pre-pivot code/tests are migrated.

Likewise, the application layer no longer owns a growing regex vocabulary for extracting special entities such as a particular project name or deciding whether words such as `just`, `those`, or `this plan` imply recency. The default capability registry no longer carries continuity phrases such as `those approaches`, `just discussed`, or `ruled out`; the live model path selects a constrained requirement that the application resolves to an exact capability id.

This does **not** deprecate lexical retrieval itself. Lexical specificity, entity/anchor matching, temporal routing, deterministic associations, and future learned candidate generators remain legitimate mechanisms *inside JIT Memory*. The distinction is:

```text
bad target:
  model/application policy writes or enumerates natural-language continuity/search phrases

accepted target:
  bounded active state
  + categorical routing
  + extractive/indexed anchors
  + deterministic evidence retrieval
```

The canonical current user text may still be used as a deterministic retrieval cue because it is user-authored source data, not model-generated policy. Selected anchor values also come from canonical text through validated indices rather than being invented by the model.

## Interaction stream, situation, and task remain distinct

Prometheist distinguishes:

1. **Interaction stream** — where/when communication occurred: UI/chat, device, source, sequence, timestamps.
2. **Working/current situation** — the bounded canonical evidence currently activated for cognition.
3. **Situation/topic associations** — broader overlapping relations among events, people, projects, causes, and episodes; richer assembly remains future work.
4. **Task/intention** — durable work Prometheist is trying to advance.

These relationships are many-to-many. A situation may span streams; a task may outlive the interaction that created it; one event may participate in several situations.

The minimal v0.7 WorkingState is not a rigid replacement `topic_id`. Rich cross-stream situation assembly remains a later mechanism.

## Conversation IDs remain provenance

`conversation_id` and `conversation_seq` remain useful for exact ordering, audit/debugging, UI grouping, and explicitly source-scoped questions such as "what did I say in this chat?"

They must not normally act as semantic memory walls.

```text
conversation != agent execution
conversation != task
conversation != attention lane
conversation != memory scope
conversation != working state
```

## Epistemic boundary

WorkingState activation must not confuse attention with truth.

If event E is active, the state asserts only:

> E is currently relevant enough to keep available.

It does not assert:

> every proposition in E is correct/current/objectively true.

Canonical evidence, corrections, provenance, contradictions, confidence, user-belief versus world-belief, and later epistemic-state mechanisms remain separate concerns. This preserves Prometheist's skepticism requirement: evidence, interpretation, belief, and derived conclusion must not silently collapse into one representation.

The constrained-output rule reinforces this boundary: a routing model may select an existing anchor or evidence scope, but it does not get to turn its own natural-language interpretation into a new authoritative fact.

## Accepted v0.6 behavioral baseline

v0.6 remains a forward behavioral baseline for:

- fresh-process execution across turns;
- use of recent dialogue plus older history;
- unrelated historical distractors;
- persisted-memory access rather than plausible guessing;
- exact source-event provenance;
- polarity/negation correctness;
- causal-source requirements;
- exact opaque-token preservation.

The v0.7 implementation must preserve those properties without retaining the Primary Agent or a hidden transcript.

## Frozen v0.7 experiment

The four-turn Kestrel continuity scenario remains the fixed compatibility experiment. The model, randomized identifiers, database, worker destruction, and provenance assertions stay fixed while the mechanism changes.

The WorkingState intervention is accepted only if it:

- preserves the already-passing restart/cross-conversation tests;
- completes the four-turn scenario;
- does not use inherited model context;
- keeps active state bounded;
- returns canonical source evidence;
- preserves conservative long-term memory admission/abstention;
- no longer depends on phrase-specific continuity regexes;
- does not require model-generated natural-language routing/search fields;
- passes the deterministic non-Ollama suite before native Ollama acceptance.

If it fails, diagnose the active-state/memory boundary or the categorical/extractive routing contract. Do not add another English phrase rule or model-generated search field simply to make the fixture green.

## Broader natural topic-resumption benchmark

Later benchmarks should include multi-day/session topic resumption, overlapping situations, corrections, ambiguous references, progressive disambiguation, causal chains, and explicit source-scoped questions.

Measurements should include referent accuracy, retrieval precision, temporal correctness, correction/supersession correctness, unnecessary clarification rate, correct clarification under genuine ambiguity, bounded context size, provenance correctness, abstention, and categorical-routing error rate.

The future goal is not a perfect rule-based coreference parser. It is a persistent cognitive system whose active situation and historical evidence remain reconstructible even when every reasoning process is destroyed.

## v1.0 requirement

A defensible v1.0 must demonstrate continuous interaction across sessions, devices, worker destruction, and model replacement. The user should experience one persistent Prometheist, while the physical boundaries of the interface remain available for provenance only.

> **Current cognitive context belongs to Prometheist itself, not to a chat transcript, worker, model context window, phrase-matching heuristic, or model-authored control string.**