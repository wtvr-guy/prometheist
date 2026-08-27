# v0.7 Working-State Continuity Pivot — 2026-08-26

## Status

Accepted design correction inside the v0.7 release candidate. This does not pull the full future epistemic/cognitive-state roadmap into v0.7. It adds only the minimal durable active-state mechanism required to test natural stateless continuity without phrase-specific application policy.

## Why this changed

The native Windows/PostgreSQL/Ollama acceptance gate repeatedly exposed the same architectural weakness in different forms. The v0.7 interaction path attempted to reconstruct the current cognitive situation directly from each new utterance by progressively adding application-owned text cues:

- canonical and supplemental query formulations;
- conversation-scope corrections;
- explicit entity extraction;
- singleton proper-name extraction;
- recency/reference-time phrase detection.

Each individual repair was locally defensible, but the sequence created an undesirable pattern: a new natural-language failure tended to require another term, phrase, or regex rule. One repair also regressed a previously passing turn when a temporal heuristic fired on `those approaches`. This is evidence against the hypothesis that natural interaction continuity should be primarily reconstructed from a hand-maintained vocabulary of surface forms.

The important result is therefore a negative one:

> **The v0.7 acceptance experiment did not support direct utterance -> phrase/entity/recency cues -> MemoryNeed as a sufficiently general continuity mechanism.**

That result is retained rather than tuned away.

## Research synthesis that informed the replacement

Two concept reports added to `docs/concepts/` independently point toward the same missing mechanism:

- `lessons_from_cognitive_neuroscience.md` identifies the absence of an explicit durable working state, distinct from autobiographical/long-term memory, as one of Prometheist's largest mechanism-level gaps. It recommends durable working state plus bounded recurrent inference rather than forcing long-term retrieval to reconstruct the entire present situation on every inference call.
- `lessons_from_similar_projects.md` identifies current-situation / working-state representations in Soar, LIDA, related cognitive architectures, and durable agent runtimes as mature precedents worth borrowing while preserving Prometheist's system-owned continuity and disposable-worker model.

These are design inputs, not appeals to analogy. The change is justified by the observed acceptance failure and remains subject to the project's experimental rule.

## New v0.7 hypothesis

> **Natural stateless interaction continuity requires a bounded durable representation of which canonical events are currently active, separate from long-term memory retrieval.**

The minimal v0.7 mechanism is `InteractionWorkingState`.

It deliberately does **not** store a free-form summary, inferred truth, user profile, parsed nickname table, option table, or an ever-growing vocabulary of referential phrases. Its initial state is only:

```text
state_id
revision
conversation_ids       # provenance/binding only
active_event_ids       # bounded canonical event pointers
```

The active set is an activation record, not a second memory store. Canonical event content remains authoritative in the append-only event ledger.

## Execution model

The revised continuity path is:

```text
new interaction
    -> load bounded durable WorkingState
    -> fresh stateless capability classification / memory planning
    -> JIT Memory rehydrates active canonical event IDs first
    -> unresolved historical need falls through to deterministic long-term retrieval
    -> fresh stateless response synthesis
    -> persist response
    -> promote newly used canonical evidence + current prompt/response into WorkingState
```

This separates three concerns:

- **WorkingState:** what canonical evidence is active now?
- **JIT Memory:** what older persisted evidence is relevant to the unresolved need?
- **JIT Attention:** what durable task deserves execution/resources now?

No LLM invocation owns any of those states.

## Deprecation of phrase-specific continuity policy

The old `requires_persisted_context()` phrase detector is deprecated and disabled in the live path. The interaction runtime now checks whether durable WorkingState exists rather than trying to infer continuity from a list of English phrases.

Likewise, v0.7 no longer generates interaction-layer `Kestrel`/proper-name/recency cues through hand-maintained regex policy. Historical `MemoryNeed` entities/query formulations are proposed by a fresh stateless semantic memory-planning call and then passed into deterministic JIT Memory. The deterministic lexical/entity/association routes inside JIT Memory remain valid long-term-memory mechanisms; what is deprecated is application policy that attempts to enumerate natural-language continuity expressions.

## Skepticism / epistemic boundary

WorkingState must not silently promote interpretation into fact.

An active event pointer means only:

> this canonical event is currently relevant/active.

It does **not** mean:

> every statement in this event is objectively true.

JIT Memory rehydrates canonical source evidence, and later epistemic working-state milestones may add explicit claim/hypothesis/confidence/counterevidence structures. v0.7 intentionally does not smuggle those future semantics into a text summary.

## Scientific-method acceptance

Baseline A is the now-observed direct-cue design. Intervention B is durable active-event WorkingState.

Keep the model, database, hardware, randomized tokens, process-destruction requirements, and four-turn Kestrel scenario fixed. The intervention is accepted only if it:

1. preserves the already-passing cross-process Oriole/Falcon and cross-conversation cases;
2. completes the four-turn Kestrel scenario without inherited model context;
3. survives fresh worker processes between stages/turns;
4. returns canonical source-event provenance;
5. does not depend on phrase-specific continuity regexes;
6. keeps active state bounded;
7. preserves abstention and conservative long-term evidence admission;
8. does not regress deterministic non-Ollama tests.

If the same frozen benchmark still fails, inspect the WorkingState/JIT-Memory boundary rather than adding another phrase rule. A broader mechanism is justified only by a measured failure.

## Scope boundary

This is **minimal v0.7 active state**, not full epistemic cognition.

Deferred work still includes goals/subgoals, hypotheses, confidence, alternatives, contradictions, prediction error, episode formation, consolidation/replay, procedural memory, and richer situation assembly. Those mechanisms should be introduced one at a time under frozen experiments.

The v0.7 invariant remains:

> **Prometheist owns continuity; models and workers are disposable compute.**

The correction makes that invariant more literal: even the current cognitive context is now explicit system state rather than something reconstructed from a worker's linguistic guesswork.
