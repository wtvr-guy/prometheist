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

## Revised interaction path

```text
external turn
    -> durable interaction task
    -> load current WorkingState
    -> fresh stateless semantic classification / memory planning
    -> JIT Memory rehydrates active canonical events first
    -> unresolved historical need falls through to deterministic long-term recall
    -> fresh stateless synthesis
    -> persist response
    -> activate current prompt/response and newly used evidence
```

A fresh worker can therefore reconstruct the present situation without inheriting an LLM context window and without reverse-engineering continuity from a phrase list.

## Text cues: what is deprecated and what remains

The old interaction-layer phrase detector (`requires_persisted_context`) is deprecated and disabled in the live path. It is retained temporarily only as a compatibility symbol while pre-pivot code/tests are migrated.

Likewise, the application layer no longer owns a growing regex vocabulary for extracting special entities such as a particular project name or deciding whether words such as `just`, `those`, or `this plan` imply recency.

This does **not** deprecate lexical retrieval itself. Lexical specificity, entity matching, temporal routing, deterministic associations, and future learned candidate generators remain legitimate mechanisms *inside JIT Memory*. The distinction is:

```text
bad target:
  application policy enumerates natural-language continuity phrases

accepted target:
  bounded active state + semantic MemoryNeed planning + deterministic evidence retrieval
```

Historical query/entity formulations may be proposed by a fresh stateless semantic memory-planning call. They are bounded structured inputs to JIT Memory, not durable model state and not system policy.

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
- passes the deterministic non-Ollama suite before native Ollama acceptance.

If it fails, diagnose the active-state/memory boundary. Do not add another English phrase rule simply to make the fixture green.

## Broader natural topic-resumption benchmark

Later benchmarks should include multi-day/session topic resumption, overlapping situations, corrections, ambiguous references, progressive disambiguation, causal chains, and explicit source-scoped questions.

Measurements should include referent accuracy, retrieval precision, temporal correctness, correction/supersession correctness, unnecessary clarification rate, correct clarification under genuine ambiguity, bounded context size, provenance correctness, and abstention.

The future goal is not a perfect rule-based coreference parser. It is a persistent cognitive system whose active situation and historical evidence remain reconstructible even when every reasoning process is destroyed.

## v1.0 requirement

A defensible v1.0 must demonstrate continuous interaction across sessions, devices, worker destruction, and model replacement. The user should experience one persistent Prometheist, while the physical boundaries of the interface remain available for provenance only.

> **Current cognitive context belongs to Prometheist itself, not to a chat transcript, worker, model context window, or phrase-matching heuristic.**
