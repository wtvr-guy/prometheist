# Interaction Continuity

**Status:** active architecture requirement; revised 2026-08-28 after native v0.7 continuity evidence and the typed-workpiece refactor.  
**Constitutional status:** primary deep dive for bounded session-independent continuity, Articles 5–8, 20, 27, and related portions of Articles 15, 16, 29, and 30.

## Governing invariant

> **Conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Current activation and basic access to persistent memory are system-owned cognitive substrate.**

Four durable mechanisms remain distinct:

- **WorkingState** — which canonical events/results are active now?
- **JIT Memory** — which canonical persisted evidence is potentially relevant now?
- **JIT Attention** — which durable work receives execution/resources now?
- **Interaction Workpiece** — what typed components have been assembled for the current unit of work?

No LLM call owns any of them.

## Experimental corrections

Native v0.7 work rejected several earlier assumptions.

1. **Phrase-cue continuity failed as a general mechanism.** Growing vocabularies of entity/recency/reference phrases produced local fixes and regressions. The live phrase detector is disabled; bounded WorkingState uses canonical event IDs.
2. **Ask-before-remembering is circular.** A stateless model cannot decide whether unseen memory matters when the evidence required for that decision may itself be in memory. Every percept therefore receives bounded JIT activation before semantic judgment.
3. **A capability list is not an execution schedule.** Models may select bounded legal semantic requirements/indices; Prometheist owns identities, dependencies, order, resources, persistence, and effects.
4. **A recurrent general router is not the production executive mechanism.** Repeated broad model routing concentrated latency/control authority. v0.7 now uses application-defined demand-driven stations at material evidence boundaries.
5. **One aggregate pre-cognitive classifier owned too much.** Native Qwen3:4b behavior showed that incorrect/contradictory sufficiency metadata could derail otherwise-correct retrieval. Evidence sufficiency and conditional capability selection are now separate single-purpose stations; deterministic application code composes aggregate control.
6. **Generated search/control prose is unnecessary.** Memory research selects canonical candidates/indices and application-owned capabilities rather than generating queries, IDs, dependencies, or execution plans.
7. **Response is not the universal terminal concept.** The current interactive surface may emit language, but the general workpiece can terminalize as action completion/failure, waiting, deferral, abstention, or emitted response.

These are general architectural corrections derived from observed failures, not Kestrel-specific patches.

## Default memory activation: broad and shallow

Every percept automatically opens a small bounded memory context before semantic model cognition.

```text
current percept
    +
bounded WorkingState event IDs
    |
    v
deterministic high-recall candidate activation
    |
    v
small provenance-bearing MemoryPacket
    |
    v
workpiece ATTENTION_APERTURE component
```

The aperture deliberately casts a relatively wide deterministic candidate net while exposing only a small packet. A surfaced item means “potentially relevant enough to expose,” not “proved sufficient” or “true.”

This is cognitive substrate, not a model-selected capability.

Current v0.7 breadth/depth values are governed implementation constraints under [`../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md), not constitutional constants.

## Demand-driven semantic continuation

After the aperture, the current interactive acquisition path asks the smallest semantic question that has a real downstream consumer.

### Evidence sufficiency station

`evidence_sufficiency_verifier` receives the current percept plus bounded activated/completed evidence and returns only:

```text
SUFFICIENT | INSUFFICIENT
```

It does not receive capability-selection authority.

### Conditional capability selection

Only after `INSUFFICIENT`, and only if the application exposes a legal catalog, `capability_selector` returns bounded application-catalog indices.

It does not decide whether evidence was sufficient and does not own execution order/dependencies/resources.

### Deterministic continuation

Prometheist then derives:

```text
SUFFICIENT
    -> current path may terminalize/respond

INSUFFICIENT + selected legal capability work
    -> deterministic capability tranche
    -> newly composed bounded evidence
    -> fresh sufficiency judgment

INSUFFICIENT + no useful legal work
    -> abstain/fail/wait/defer according to current authority/policy
```

After first-tranche capability work, a fresh sufficiency worker sees the newly material evidence. Newly legal follow-up capabilities may be exposed once, as defined by the current v0.7 stage topology. If the bounded follow-up path still needs a terminal semantic judgment, a fresh `final_readiness` worker is used.

There is no hidden inherited model context and no open-ended model-owned recurrent loop.

## Progressive memory focus

Internal retrieval narrows candidate subjects while increasing bounded associative depth.

### Automatic broad activation

- every percept;
- high-recall direct candidate activation;
- no deep association traversal;
- small surfaced packet.

### `deeper_research`

Investigates additional persisted internal evidence around one or more currently available memory candidates. A narrow selector chooses canonical candidate indices; application code resolves canonical IDs and runs bounded deeper retrieval.

### `cross_reference`

Investigates relationships among multiple currently available candidates. A selector chooses bounded canonical candidate indices; application code performs the joint associative search.

### `focused_recall`

Becomes legal only after broader research exposes a specific unresolved candidate. A selector chooses one canonical candidate for the deepest bounded association traversal.

Exact current candidate/association/hop limits remain governed tunables documented by code/constraint registry, not hard architectural rules.

At every depth, evidence-admission skepticism remains unchanged. More attention does not make evidence more true.

## Multiple capabilities and deterministic ordering

Capability indices are requirements, never an execution schedule.

```text
selected capability indices
    -> application-owned capability IDs
    -> dependency closure
    -> cycle/missing-dependency rejection
    -> deterministic ready-set ordering
    -> resource admission
    -> execution
    -> structured result/evidence component
```

The current v0.7 implementation executes selected capability work as bounded substeps inside the admitted interaction assignment. Future releases may promote capability work to separately scheduled child tasks without changing the semantic-selection contract.

## Interaction Workpiece continuity

The typed `InteractionWorkpiece` is the cumulative task-local product, not a memory scope.

It can contain:

- the originating percept;
- WorkingState/reference availability;
- attention-aperture evidence;
- atomic semantic station results;
- application-composed control checkpoints;
- chronological capability tranches;
- final evidence;
- current interactive response authority when applicable;
- optional user output;
- terminal outcome.

Workers receive only minimum projections of this object. The complete workpiece is not fed wholesale to a model merely because it exists.

At terminalization Prometheist persists one materialized workpiece snapshot in addition to append-only causal records. The terminal snapshot is useful audit/replay state but is not blindly promoted into WorkingState or used as a replacement memory packet.

See [`INTERACTION_WORKPIECE.md`](INTERACTION_WORKPIECE.md).

## Current interactive response boundary

For the current CLI/chat-like surface, a `FinalResponseDirective` is created only after acquisition/readiness/source policy are final. It is a conditional workpiece component.

If the directive authorizes natural-language response, the fresh final response worker receives only admitted evidence/results, the directive, current percept, and response persona. It cannot reopen acquisition or change source policy.

If the path abstains, deterministic fallback output may be attached for the interactive interface without invoking the final generative responder.

This is **not** the universal terminal architecture. A future action task may complete with no `FinalResponseDirective` and no user-output component.

## Minimal WorkingState

The current v0.7 WorkingState remains intentionally small:

```text
state_id
revision
conversation_ids
active_event_ids
```

`active_event_ids` are bounded pointers to canonical events. WorkingState is not a copied transcript, summary, user-profile blob, parsed entity table, truth store, or workpiece snapshot.

Future richer WorkingState requires experimentally justified structured state and must preserve boundedness/canonical provenance.

## Model-output rule

> **Model-generated natural language is representation of last resort for machine state/control.**

Preferred order:

```text
enum / boolean / bounded integer / application-owned ID
    before
mechanically verified extractive selection
    before
free-form generated language
```

The live control path therefore uses closed station schemas, bounded capability/candidate indices, application-owned IDs/dependencies/resources/order, typed workpiece components, and structured results.

Free-form language remains appropriate only when language itself is the product.

## Text cues: deprecated versus valid

The old interaction-layer phrase detector is deprecated/disabled. Application control does not maintain special English rules for phrases such as “just,” “those approaches,” or “this plan.”

This does not deprecate canonical text retrieval inside JIT Memory. Lexical specificity, deterministic associations, temporal cues, canonical candidate text, and future empirically justified retrieval mechanisms remain valid inside memory.

The rejected pattern is phrase-specific application control, not textual evidence retrieval.

## Epistemic boundary

Activation, retrieval, sufficiency, and truth remain distinct.

A surfaced event may represent:

- user statement/belief;
- system history;
- corrected/superseded information;
- current or historical evidence;
- contradiction/counterevidence;
- uncertain/derived interpretation.

Prometheist must not silently collapse those categories because an item was retrieved or activated.

## Fail-closed continuity authority

Invalid/ambiguous station output, illegal/out-of-range capability selection, changed persisted bindings, unsupported historical evidence, unresolved action authority, or exhausted legal work must produce explicit failure/abstention/wait/defer/reconciliation behavior. Do not guess past missing authority to preserve conversational smoothness.

## Frozen native continuity obligations

The Kestrel scenario remains a general end-to-end experiment. It must demonstrate that:

- a prior Kestrel constraint/profile can be recalled without hidden transcript;
- relevant evidence is present before semantic sufficiency judgment;
- cross-process/cross-conversation continuity survives;
- opaque identifiers remain exact;
- WorkingState/MemoryPackets/workpiece projections remain bounded;
- no phrase-specific application continuity rules are required;
- the sufficiency station correctly recognizes directly present answer components;
- capability selection occurs only if current evidence is actually insufficient;
- user-facing output is generated only after current interactive authority is final;
- deterministic CI is green before native Ollama acceptance is treated as release evidence.

If the scenario fails, diagnose the general WorkingState/JIT-Memory/workpiece/station boundary. Do not add another English phrase rule or force response because a packet is merely marked supported.

> **Current cognitive context and basic access to persistent memory belong to Prometheist itself—not to a chat transcript, worker, model context window, phrase heuristic, or model-authored request to remember.**
