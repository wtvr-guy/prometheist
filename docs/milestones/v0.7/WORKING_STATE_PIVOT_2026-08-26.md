# v0.7 Working-State, Default Memory, and Capability-Routing Pivot — 2026-08-26/27

## Status

Accepted design correction inside the v0.7 release candidate. This does not pull the full future epistemic/cognitive-state roadmap into v0.7. It adds only the minimal durable active-state, default-memory-exposure, constrained capability-selection, and deterministic capability-execution mechanisms required by the frozen native continuity experiment.

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

The registry now stores private dependency/priority metadata. Prometheist expands selected capability dependencies, rejects cycles, and deterministically topologically orders ready work by execution priority and canonical capability ID.

### Negative result D — intermediate prose from capabilities

A memory-focused capability previously had a path to generate its own prose answer. That creates multiple generative boundaries and makes final composition ambiguous once several capabilities are selected.

> **Result D:** capabilities should return structured evidence/state whenever possible; one fresh final response worker should generate the user-facing language after every required capability has completed.

## Research synthesis

The concept reports in `docs/concepts/` support the same separation without being treated as authority by analogy:

- `lessons_from_cognitive_neuroscience.md` identifies a bounded working state distinct from long-term memory as a major missing mechanism and emphasizes selective activation rather than full-history context.
- `lessons_from_similar_projects.md` identifies current-situation/working-state representations, bounded memory access, and system-owned orchestration across mature cognitive and agent architectures.

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

## Default memory exposure

Every percept now automatically receives a small, bounded, provenance-bearing JIT Memory packet before any model capability-selection decision.

```text
percept + durable WorkingState
        |
        v
system-owned bounded JIT recall
        |
        v
initial MemoryPacket
        |
        v
fresh stateless capability selector
        |
        +--> capability_indices = [] -> final response
        |
        +--> capability_indices = [i, j, ...]
                -> deterministic capability execution plan
                -> complete every capability
                -> final response
```

The initial packet is intentionally small rather than exhaustive. It exposes immediately relevant canonical evidence while preserving bounded context.

Basic memory exposure is cognitive substrate and is not model-selected.

## `deeper_research`

The optional internal-memory investigation capability is named `deeper_research` rather than after the internal "attention aperture" metaphor.

Its public semantic contract is:

> **Investigate the current question further using additional persisted internal evidence when the initially supplied context is insufficient.**

`deeper_research` returns structured evidence. It does not produce an intermediate prose answer.

The default registry may retain `internal_memory` for generic/historical compatibility, but the live interaction model does not emit or select it.

## Multiple capabilities and deterministic scheduling

The capability selector receives an application-owned bounded catalog and may return zero, one, or multiple integer indices.

Those indices specify **requirements**, not order.

Prometheist constructs a persisted `CapabilityExecutionPlan` using application-owned registry metadata:

```text
selected indices
    -> canonical capability IDs
    -> dependency closure
    -> validate dependencies
    -> reject cycles
    -> topological order
    -> stable priority + capability-ID tie break
```

The response stage is downstream of the complete capability-execution stage. It verifies that every planned capability produced a durable result in the scheduler-owned order before the final response worker is summoned.

The final bounded evidence context is composed only after this barrier has been satisfied.

## Model-output rule

The native failures establish a system-wide protocol preference:

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

- capability routing returns only bounded integer indices into an application-owned catalog;
- `[]` means respond after the current evidence is ready;
- a non-empty list means one or more capabilities are required;
- the model does not control capability order;
- basic internal-memory access is not represented in the catalog because it already happened;
- capability IDs, dependencies, execution priorities, executors, and resource policy are application-owned;
- the model emits no capability query/input, retrieval query, entity string, executor name, event ID, explanation, dependency declaration, execution order, or phrase rule;
- deeper-research routing returns only a scope enum plus bounded indices into an application-generated anchor catalog;
- invalid/duplicate/out-of-range indices and unexpected fields are rejected;
- capability execution returns structured evidence rather than intermediate prose;
- final user-facing response text is the sole live free-form NL output because language is the product at that boundary.

The same rule applies to tests. Acceptance must not grow a hand-written English parser or keyword-slot list to decide whether model prose is semantically correct. Where the experiment needs a deterministic verdict, the fixture asks for an exact machine-verifiable value or tuple and checks source-event provenance separately.

## Revised live interaction path

```text
new percept
    -> durable interaction task
    -> load bounded durable WorkingState
    -> automatic bounded JIT recall
    -> fresh stateless capability selector sees percept + initial MemoryPacket + catalog
       -> []: no optional capability
       -> [indices...]: optional capabilities required
    -> Prometheist expands dependencies and deterministically orders execution
    -> execute all planned capabilities to durable structured results
    -> barrier: verify every planned result exists
    -> compose bounded final evidence context
    -> one fresh stateless response synthesis
    -> persist response
    -> promote surfaced canonical evidence + prompt/response into WorkingState
```

This separates:

- **WorkingState:** what canonical evidence is active now?
- **default memory exposure:** what bounded potentially relevant persistent evidence should every fresh inference be allowed to see?
- **deeper research:** what additional persisted evidence should be investigated?
- **capability execution plan:** what required functions must run, and in what system-owned order?
- **JIT Attention:** what durable task deserves execution/resources now?
- **final response:** what user-facing language should be generated after all required evidence/work is ready?

No LLM invocation owns any of those durable states.

## Deprecations

The old `requires_persisted_context()` phrase detector remains disabled. v0.7 does not generate interaction-layer project/proper-name/recency cues through hand-maintained regex policy, and the default capability registry does not carry a continuity phrase vocabulary.

The earlier `MEMORY_ANALYSIS` live capability name is superseded by `deeper_research`. The old intermediate memory-analysis prose-answer path is removed from the live architecture.

The earlier `why/reason/cause` response-layer semantic regex helper is also removed. A fresh response model receives the bounded canonical evidence directly rather than application code trying to parse a subset of English semantics.

Lexical/entity/association/temporal mechanisms remain valid inside JIT Memory. Canonical user text is source data, not model-authored policy.

## Skepticism boundary

WorkingState activation and memory retrieval are relevance operations, not truth promotion.

An active or retrieved canonical event means only that it is currently relevant enough to expose. It does not mean every proposition inside it is objectively true/current. Evidence, interpretation, user belief, world belief, corrections, contradictions, confidence, and future hypotheses remain separate concerns.

## Frozen acceptance experiment

The four-turn Kestrel continuity scenario remains the fixed experiment. The intervention is accepted only if it:

1. retrieves the pre-existing Kestrel rule on Turn 1 before capability selection;
2. chooses PostgreSQL directly on Windows rather than the Docker option;
3. preserves the already-passing cross-process Oriole/Falcon and cross-conversation cases;
4. completes all four Kestrel turns without inherited model context;
5. survives fresh worker processes between stages/turns;
6. returns canonical source-event provenance;
7. keeps WorkingState and MemoryPackets bounded;
8. uses no phrase-specific continuity regexes;
9. uses no model-generated natural-language capability/search/entity/order fields;
10. supports zero/one/multiple optional capability selections through bounded indices;
11. deterministically expands dependencies/orders capability execution;
12. does not summon the final response worker until all planned capabilities have completed;
13. passes the deterministic non-Ollama suite before native Ollama acceptance.

If the benchmark fails, diagnose the WorkingState/JIT-Memory/capability-planning boundary or constrained model protocol. Do not add another English phrase rule or generated search field merely to make the fixture green.

## Scope boundary

This remains minimal v0.7 cognition. Goals/subgoals, hypotheses, confidence, alternatives, contradictions, prediction error, episode formation, consolidation/replay, procedural memory, and richer situation assembly remain later experimentally justified mechanisms.

> **v0.7 invariant: Prometheist owns continuity, basic access to its memory, capability execution order, and final-response readiness; models and workers are disposable compute.**