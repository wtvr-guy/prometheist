# v0.7 Working-State and Attention-Aperture Pivot — 2026-08-26/27

## Status

Accepted design correction inside the v0.7 release candidate. This does not pull the full future epistemic/cognitive-state roadmap into v0.7. It adds only the minimal durable active-state and default-memory-exposure mechanisms required by the frozen native continuity experiment.

## Experimental sequence

Native Windows/PostgreSQL/Ollama acceptance exposed two separate architectural failures.

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

## Research synthesis

The concept reports in `docs/concepts/` support the same separation without being treated as authority by analogy:

- `lessons_from_cognitive_neuroscience.md` identifies a bounded working state distinct from long-term memory as a major missing mechanism and emphasizes selective activation rather than full-history context.
- `lessons_from_similar_projects.md` identifies current-situation/working-state representations and memory/system separation across mature cognitive and agent architectures.

The change is justified by the observed native failures; the research synthesis helps explain why the replacement mechanism is plausible.

## Minimal v0.7 WorkingState

`InteractionWorkingState` remains deliberately small:

```text
state_id
revision
conversation_ids       # provenance/binding only
active_event_ids       # bounded canonical event pointers
```

It does not store a free-form summary, inferred truth, user profile, parsed nickname table, option table, or referential phrase vocabulary. The append-only event ledger remains authoritative.

## Attention aperture

Every percept now automatically receives a small, bounded, provenance-bearing JIT Memory packet before any model routing decision.

```text
percept + durable WorkingState
        |
        v
system-owned bounded JIT recall
        |
        v
default attention-aperture MemoryPacket
        |
        v
fresh stateless routing model
        |
        +--> NONE -> ordinary response
        |
        +--> MEMORY_ANALYSIS -> deeper/focused memory work
```

The default aperture is intentionally small rather than exhaustive. It exposes immediately relevant canonical evidence while preserving bounded context.

`MEMORY_ANALYSIS` remains an optional capability because it is an operation performed on memory. Basic memory exposure is cognitive substrate and is not model-selected.

The default registry may retain `internal_memory` for generic/historical compatibility, but the live interaction model no longer emits or selects it.

## Model-output rule

The native failures also establish a system-wide protocol preference:

> **Model-generated natural language is the representation of last resort. Use it only when natural language is genuinely the product or when no smaller mechanically verifiable representation can express the required semantics.**

Preferred order:

```text
enum / boolean / application-owned id / bounded integer
    before
mechanically verified extractive selection
    before
free-form generated natural language
```

For the live v0.7 path:

- post-aperture interaction routing returns only `NONE` or `MEMORY_ANALYSIS`;
- the model cannot emit a basic-memory option because the aperture has already occurred;
- capability IDs are application-owned;
- the model emits no capability query/input, retrieval query, entity string, executor name, event ID, explanation, or phrase rule;
- deeper memory routing returns only a scope enum plus bounded indices into an application-generated anchor catalog;
- invalid/duplicate/out-of-range indices and unexpected fields are rejected;
- final user-facing response text remains natural language because language is the product at that boundary.

The same rule applies to tests. Acceptance must not grow a hand-written English parser or keyword-slot list to decide whether model prose is semantically correct. Where the experiment needs a deterministic verdict, the fixture asks for an exact machine-verifiable value or tuple and checks source-event provenance separately.

## Revised live interaction path

```text
new percept
    -> durable interaction task
    -> load bounded durable WorkingState
    -> AUTOMATIC bounded attention-aperture recall
    -> fresh stateless enum-only post-aperture routing
       -> NONE: answer from percept + aperture packet
       -> MEMORY_ANALYSIS: focused/deeper memory retrieval/analysis
    -> fresh stateless response synthesis
    -> persist response
    -> promote surfaced canonical evidence + prompt/response into WorkingState
```

This separates:

- **WorkingState:** what canonical evidence is active now?
- **default attention aperture:** what bounded potentially relevant persistent evidence should every fresh inference be allowed to see?
- **MEMORY_ANALYSIS:** what deeper/focused historical investigation is warranted?
- **JIT Attention:** what durable task deserves execution/resources now?

No LLM invocation owns any of those states.

## Deprecations

The old `requires_persisted_context()` phrase detector remains disabled. v0.7 does not generate interaction-layer project/proper-name/recency cues through hand-maintained regex policy, and the default capability registry does not carry a continuity phrase vocabulary.

Lexical/entity/association/temporal mechanisms remain valid inside JIT Memory. Canonical user text is source data, not model-authored policy.

## Skepticism boundary

WorkingState activation and aperture retrieval are relevance operations, not truth promotion.

An active or retrieved canonical event means only that it is currently relevant enough to expose. It does not mean every proposition inside it is objectively true/current. Evidence, interpretation, user belief, world belief, corrections, contradictions, confidence, and future hypotheses remain separate concerns.

## Frozen acceptance experiment

The four-turn Kestrel continuity scenario remains the fixed experiment. The intervention is accepted only if it:

1. retrieves the pre-existing Kestrel rule on Turn 1 before model routing;
2. chooses PostgreSQL directly on Windows rather than the Docker option;
3. preserves the already-passing cross-process Oriole/Falcon and cross-conversation cases;
4. completes all four Kestrel turns without inherited model context;
5. survives fresh worker processes between stages/turns;
6. returns canonical source-event provenance;
7. keeps WorkingState and MemoryPackets bounded;
8. uses no phrase-specific continuity regexes;
9. uses no model-generated natural-language capability/search/entity fields;
10. passes the deterministic non-Ollama suite before native Ollama acceptance.

If the benchmark fails, diagnose the aperture/WorkingState/JIT-Memory boundary or constrained model protocol. Do not add another English phrase rule or generated search field merely to make the fixture green.

## Scope boundary

This remains minimal v0.7 cognition. Goals/subgoals, hypotheses, confidence, alternatives, contradictions, prediction error, episode formation, consolidation/replay, procedural memory, and richer situation assembly remain later experimentally justified mechanisms.

> **v0.7 invariant: Prometheist owns continuity and basic access to its memory; models and workers are disposable compute.**
