# Interaction Continuity

**Status:** active architecture requirement. Revised 2026-08-27 after native v0.7 acceptance exposed two failed continuity assumptions.

## Principle

Prometheist must not require a user to manage conversations as memory namespaces, and it must not require application code to enumerate every natural-language way a user can refer to recent or historical context.

The governing invariant is:

> **Conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Current context and access to persistent memory are system-owned cognitive substrate.**

Three mechanisms remain distinct:

- **WorkingState** answers: which canonical events are active now?
- **JIT Memory** answers: which persisted canonical evidence is potentially relevant now?
- **JIT Attention** answers: which durable work receives execution/resources now?

No LLM invocation owns any of those states.

## Experimental corrections

### Rejected mechanism 1: phrase-cue continuity

The first v0.7 release candidate reconstructed continuity from each utterance using progressively more text/entity/recency cues. Native acceptance required increasingly specific repairs and one temporal heuristic regressed an already-passing turn.

The project therefore records a negative result:

> **Direct utterance -> hand-maintained text/entity/recency rules -> MemoryNeed is not accepted as the general continuity architecture.**

WorkingState replaced that approach with a bounded set of canonical active-event IDs.

### Rejected mechanism 2: ask before remembering

A later native run exposed a deeper problem. On the first Kestrel turn, the stateless classifier saw only the current percept and selected no memory capability. The response model therefore never saw the already-persisted rule that ruled out Docker and recommended the conflicting option.

That is not a Kestrel-specific routing error. It is a circular dependency:

> **A stateless model cannot reliably decide whether unseen persistent memory is relevant when the evidence required to make that decision may itself be in persistent memory.**

Accordingly, basic internal-memory access is no longer a model-selected capability in the live interaction path.

## Attention aperture

Every percept automatically opens a small, bounded JIT Memory **attention aperture** before any model routing decision.

```text
percept
  +
durable WorkingState
  |
  v
system-owned bounded JIT recall
  |
  v
default MemoryPacket
  |
  +--> fresh stateless routing decision
          |
          +--> NONE: ordinary response from percept + aperture packet
          |
          +--> MEMORY_ANALYSIS: focus/narrow attention for deeper memory work
```

The default aperture is deliberately small. It is not intended to reconstruct all persistent history. It gives the fresh model enough immediately relevant canonical evidence to reason about the present situation while keeping context bounded.

If that aperture is insufficient, the model may request `MEMORY_ANALYSIS`. That capability can use constrained scope/index decisions to focus historical retrieval more deeply.

The distinction is:

- **basic recall exposure** = automatic cognitive substrate;
- **memory analysis** = optional operation performed on memory.

The default capability registry may retain `internal_memory` for generic or historical compatibility, but the live interaction model does not select it.

## Minimal v0.7 WorkingState

v0.7 keeps `InteractionWorkingState` deliberately small:

```text
state_id
revision
conversation_ids
active_event_ids
```

`active_event_ids` are bounded pointers to canonical event-log entries that are currently activated by cognition.

WorkingState is not a copied transcript, LLM summary, second autobiographical store, user-profile blob, parsed nickname/options table, or assertion that active content is objectively true. The append-only event ledger remains authoritative.

The default attention aperture combines the current percept with those active canonical pointers and deterministic long-term recall. Evidence surfaced through the aperture may itself be activated into WorkingState for subsequent stateless calls.

## System-wide model-output rule

Native v0.7 failures also established a broader protocol rule:

> **Model-generated natural language is the representation of last resort. Use it only when natural language is genuinely the product or when no smaller mechanically verifiable representation can express the required semantics.**

Preferred order:

```text
enum / boolean / bounded integer / application-owned id
    before
mechanically verified extractive selection
    before
free-form generated natural language
```

This is stronger than "use JSON." A JSON string field can still smuggle probabilistic natural-language policy into the control plane.

For the live v0.7 model path:

- post-aperture interaction routing returns one enum only: `NONE` or `MEMORY_ANALYSIS`;
- basic internal-memory access is not represented in that enum because it already happened;
- capability IDs are application-owned;
- the model emits no capability query/input, retrieval query, entity string, event ID, executor name, database control, explanation, or phrase rule;
- deeper memory routing returns only a closed scope enum plus bounded integer indices into an application-generated anchor catalog;
- invalid/duplicate/out-of-range indices and unexpected fields are rejected;
- final user-facing response text remains natural language because language is the product at that boundary.

Tests must follow the same philosophy. A continuity acceptance test must not grow a hand-written English parser or keyword-list semantic oracle. Where a deterministic verdict is required, the fixture should request an exact machine-verifiable value/tuple and independently verify canonical source-event provenance.

## Revised interaction path

```text
external percept
    -> durable interaction task
    -> load current WorkingState
    -> AUTOMATIC bounded attention-aperture JIT recall
    -> fresh stateless enum-only routing sees percept + aperture packet
       -> NONE: respond from that bounded evidence
       -> MEMORY_ANALYSIS: execute focused/deeper memory workflow
    -> fresh stateless response synthesis
    -> persist response
    -> activate prompt/response and surfaced canonical evidence
```

This removes the "do I need memory?" decision from a model that has not yet seen memory.

## Text cues: deprecated versus valid

The old interaction-layer phrase detector (`requires_persisted_context`) is deprecated and disabled. The application layer does not maintain a growing regex vocabulary for phrases such as `just`, `those approaches`, or `this plan`, and the default capability registry does not maintain a continuity phrase catalog.

This does not deprecate text retrieval inside JIT Memory. Canonical current text is user-authored evidence, not model-authored policy. Lexical specificity, deterministic associations, entity/anchor matching, temporal scoring, and future experimentally justified learned candidate generators remain valid internal retrieval mechanisms.

The line is:

```text
rejected:
  model/application authors or accumulates natural-language control phrases

accepted:
  canonical source text
  + bounded active state
  + deterministic candidate retrieval
  + categorical/index-based control
  + provenance-bearing evidence
```

## Epistemic boundary

Attention and retrieval are not truth claims.

An active or retrieved event means only that the event is currently relevant enough to expose. It does not mean every proposition inside it is correct, current, or objectively true.

Canonical evidence, corrections, contradictions, confidence, user-belief versus world-belief, and later epistemic-state mechanisms remain separate concerns. This preserves the project skepticism requirement: evidence, interpretation, belief, and derived conclusion must not silently collapse into one representation.

## Frozen v0.7 experiment

The four-turn Kestrel scenario remains the compatibility experiment, but the oracle itself is now machine-verifiable rather than a list of English keywords. The mechanism is accepted only if it:

- retrieves the pre-existing Kestrel constraint on Turn 1 before model routing;
- chooses the compatible PostgreSQL-on-Windows path rather than Docker;
- preserves restart/cross-conversation recall;
- survives fresh worker/model calls with no inherited transcript;
- keeps WorkingState and MemoryPackets bounded;
- preserves exact source-event provenance and opaque identifiers;
- uses no phrase-specific continuity rules or model-generated control/search text;
- permits `MEMORY_ANALYSIS` only as deeper/focused work after the default aperture;
- passes deterministic CI before native Ollama acceptance.

If it fails, diagnose the aperture/WorkingState/JIT-Memory boundary or constrained routing contract. Do not add another English phrase rule simply to make the fixture green.

## v1.0 requirement

A defensible v1.0 must demonstrate continuous interaction across sessions, devices, worker destruction, and model replacement. The user should experience one persistent Prometheist while physical interface boundaries remain provenance only.

> **Current cognitive context and basic access to persistent memory belong to Prometheist itself—not to a chat transcript, worker, model context window, phrase heuristic, or model-authored request to remember.**
