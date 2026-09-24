# Self-Memory System

**Status:** v0.8 experimental integration on `self-memory-system-v1`.
**Constitutional authority:** Articles 1–3, 7–10, 23–24, and 37 of
[`CONSTITUTION.md`](../../CONSTITUTION.md).
**Depends on:** [Semantic Memory Provenance](SEMANTIC_FACT_PROVENANCE.md),
[Lossless Progressive Memory](LOSSLESS_PROGRESSIVE_MEMORY.md),
[Interaction Continuity](INTERACTION_CONTINUITY.md), and
[Specialist Worker Modularity](SPECIALIST_WORKER_MODULARITY.md).

## Purpose

Prometheist must eventually reason from an enduring model of the person rather
than reconstructing every relevant preference, value, trait, role, or behavioral
pattern from raw autobiographical events on every interaction. That requirement
does **not** justify a mutable user-profile object or an ungrounded personality
summary.

The Self-Memory System is a derived, provenance-bearing cognitive layer above
canonical history and personal semantic memory. It is designed to preserve
several distinctions that are essential to identity fidelity:

- what the person explicitly says about themselves;
- what is directly observed;
- what is inferred across behavior;
- what the person wants to become;
- what they say they ought to be;
- what other sources attribute to them;
- what is stable versus context-dependent;
- what is current versus historical;
- what is established versus contested;
- and what is evidence versus an interpretation of evidence.

The system is inspired by the functional organization suggested by
autobiographical-memory, self-schema, working-self, complementary-learning, and
predictive-processing research. It does not claim biological equivalence.

## Layered self architecture

Prometheist does not implement one monolithic `SelfModel`. The intended
architecture is layered:

    Working Self / WorkingState
              |
              v
       Conceptual Self Graph
       roles, preferences, values,
       traits, decision tendencies,
       worldview, self-concepts
              |
              +---- Relational Self
              +---- Prospective Self
              +---- Narrative hypotheses
              +---- Procedural Self
              +---- Embodiment state
              |
              v
      Personal Semantic Memory
              |
              v
          Situations/Episodes
              |
              v
       Canonical Life Record

The canonical event ledger remains the correspondence system: what was actually
admitted as historical evidence. The self graph is the coherence/prediction
system: Prometheist's current revisable interpretation of that evidence.

Coherence never rewrites correspondence.

## Representation kinds

`SelfRepresentationKind` currently distinguishes:

- `ROLE`
- `PREFERENCE`
- `VALUE`
- `TRAIT`
- `BEHAVIORAL_TENDENCY`
- `DECISION_POLICY`
- `WORLDVIEW`
- `SELF_CONCEPT`
- `PROSPECTIVE_SELF`
- `RELATIONAL_SCHEMA`
- `NARRATIVE_HYPOTHESIS`
- `PROCEDURAL_SELF`
- `EMBODIMENT_STATE`

These are not interchangeable.

A statement such as "I want to become an AI engineer" is a prospective-self
claim, not proof that the current role is AI engineer. "I am patient" is an
avowed self-concept or trait claim, not proof of a behavioral trait. "I value
autonomy" is an avowed value claim; repeated costly choices favoring autonomy
may separately support an inferred value representation.

`RELATIONAL_SCHEMA` requires a relationship reference.
`PROSPECTIVE_SELF` requires a desired/expected/feared orientation.
`PROCEDURAL_SELF` requires a procedure reference.
`EMBODIMENT_STATE` requires an embodiment reference.

## Perspectives

Every representation has a `SelfPerspective`:

- `AVOWED` — direct self-description;
- `OBSERVED` — directly observed state or behavior without broad inference;
- `INFERRED` — a pattern inferred across evidence;
- `ASPIRATIONAL` — desired future identity;
- `NORMATIVE` — what the person says they should or ought to be/do;
- `SOCIAL_ATTRIBUTION` — an attributed view from another source.

Prometheist is allowed to retain apparently inconsistent representations at the
same time. An avowed trait and an observed behavioral tendency may disagree.
That disagreement is potentially important person-model evidence and must not
be normalized away simply to make the identity coherent.

## Application-owned plasticity

Learning rate is not chosen by the reflection model. The application assigns a
`PlasticityClass` according to representation kind:

- `FAST` — embodiment/current-state representations;
- `MEDIUM` — roles, ordinary preferences, self-concepts, prospective selves,
  relational schemas, and procedural-self representations;
- `SLOW` — values, traits, behavioral tendencies, decision policies, and
  worldview;
- `VERY_SLOW` — narrative hypotheses.

These are relative evidentiary thresholds, not wall-clock waiting periods. A
strong explicit change can still produce rapid revision. Slow classes mean that
ordinary weak evidence cannot casually rewrite highly generalized identity.

## Identity centrality is not truth

`IdentityCentrality` is independently represented as:

- `PERIPHERAL`
- `MODERATE`
- `CENTRAL`

Centrality controls activation priority. It does not make a representation more
true or more authoritative.

High-centrality schemas are also not injected wholesale into every model call.
The activation layer admits query-relevant schemas, relationship-relevant
schemas, and at most a small bounded core fallback.

## Evidence roots

`SelfEvidence` must terminate in a canonical event root. The current positive
allowlist is intentionally narrow:

- `USER_PROMPT`
- `TOOL_RESULT`
- `PERCEPT_OBSERVATION`
- `SYSTEM_EVENT`

Prior assistant/model outputs, retrieval results, memory packets, derived
representations, and working-state records cannot independently establish who
the person is.

Automatic reflection is stricter than the generic evidence API. User-authored
`USER_PROMPT` roots are eligible by default. A non-user
`PERCEPT_OBSERVATION` can seed identity learning only when the locally installed
`SourcePolicy.self_model_evidence` flag is explicitly true. The default is false,
so ordinary telemetry, scheduler observations, and unrelated sensors do not train
the person model merely because they were consolidated. External/system evidence
can still be attached through explicit provenance-aware application paths.

Direct avowed, aspirational, and normative self representations additionally
require `USER_PROMPT` roots when used as supporting evidence.

This prevents Prometheist from learning the user's identity from its own prior
descriptions of that identity.

## Derivation cannot multiply evidence

A higher-order schema may be derived from lower-order self representations, but
its support is the **union of the canonical roots** beneath those parents.

Example:

    root E1 -> value A
    root E1 -> value B
    root E2 -> value B

    A + B -> narrative C

C has independent canonical roots `{E1, E2}`, not three roots and not A/B as
new evidence.

The invariant is:

> Derived representations may transform, compress, organize, and predict from
> evidence. They may never manufacture additional independent evidence.

Retrieval count, model repetition, response inclusion, schema activation, and
being cited by another derived schema contribute zero direct truth weight.

## Resolutions and promotion

Every self representation has an append-only `SelfResolution`:

- `CANDIDATE`
- `ESTABLISHED`
- `CONTESTED`
- `SUPERSEDED`
- `REJECTED`

Promotion is application-owned.

An `ESTABLISHED` request fails or is weakened when:

- no canonical support exists;
- counterevidence has not been checked;
- opposing canonical evidence exists;
- an inferred generalized value/trait/tendency/decision-policy/narrative has
  fewer than the configured independent-root minimum;
- a slow/very-slow inferred schema lacks support from the configured number of
  independent durable source contexts.

The reflection LLM may recommend a verdict. It cannot bypass these guards.

Known opposition forces `CONTESTED` rather than allowing a model to explain
away inconvenient evidence.

## Context breadth

Cross-context breadth must be application-derived.

The proposal model may supply semantic `context_tags` describing the scope of a
claim, but those tags never count as evidence that the pattern occurred in
multiple contexts.

During consolidation, each canonical root is annotated with durable
`situation:<id>` context references from the frozen situation inputs.
`context_count` is calculated from those source contexts.

This prevents a proposer from satisfying its own generalization threshold by
inventing labels such as "work" and "relationships."

## Slow reflection path

Self formation occurs after normal semantic consolidation on scheduled/non-user
cognition. Interactive responses do not synchronously run a large identity
reflection pass.

The current guarded stage sequence adds two distinct specialists:

    semantic consolidation
        |
        v
    SELF_PROPOSE
        |
        v
    candidate representations
        |
        v
    independent Adaptive Recall
        |
        v
    SELF_REVIEW
        |
        v
    application-owned resolution

### Proposal specialist

The proposal specialist receives bounded canonical evidence and may propose:

- representation kind;
- perspective;
- statement;
- semantic context scope;
- relationship/prospective/procedure/embodiment metadata;
- identity centrality;
- exact support indices.

It does not choose plasticity and cannot establish its own proposal.

### Review specialist

The review specialist receives one candidate plus a separately retrieved
related-evidence packet. It may return:

- `ESTABLISH`
- `CONTEST`
- `REJECT`
- `KEEP_CANDIDATE`

Any opposition indices are application-validated against the exact packet and
resolved back to canonical event IDs.

Proposal and review are separate fresh LLM invocations and separate guarded
worker stages.

## Counterevidence

Every establishment attempt requires a counterevidence check.

The review retrieval uses the candidate statement plus canonical support roots
to perform bounded Adaptive Recall. Depending on how many roots are available,
the application chooses BROAD, FOCUSED, or RELATIONAL recall.

A stronger identity schema therefore does not become immune to contradiction.
Contradiction is a reason to inspect the schema more closely.

This deliberately differs from human self-consistency bias.

## Prediction and held-out outcomes

A self model should predict behavior rather than merely summarize it.

`SelfPrediction` stores a prediction made from a resolved self representation
before its outcome is known. The later canonical outcome can be recorded as:

- `CONFIRMED`
- `CONTRADICTED`
- `AMBIGUOUS`

Every prediction records a `knowledge_cutoff_global_seq`: the highest canonical
event sequence Prometheist was allowed to know when the prediction was made. An
outcome event at or before that cutoff is rejected as retrospective leakage.
This makes held-out evaluation mechanically distinct from post-hoc explanation.

Confirmed and contradicted outcomes feed back into the representation as new
canonical support/opposition evidence. A contradicted held-out prediction can
therefore move an established schema to `CONTESTED`.

Prediction counts are tracked separately from evidence count. They do not
collapse into one universal confidence score.

## Evidence metrics

The system intentionally avoids a single `confidence=0.83` identity scalar.

`SelfEvidenceMetrics` currently preserves independent dimensions:

- support-root count;
- opposition-root count;
- source-type count;
- source count;
- source-context count;
- confirmed prediction count;
- contradicted prediction count;
- ambiguous prediction count;
- first/last support times.

Future calibration may add explicit source-reliability, temporal-stability, or
selective-accuracy measures. Those should remain separately interpretable.

## Working Self

`WorkingSelf` is the interaction-local activation of persistent identity:

    current percept
        +
    current goal/entity context
        +
    persistent self graph
        |
        v
    bounded SelfContextPacket

The packet is limited and sparsely selected. Retrieval considers:

1. lexical relevance to the current percept;
2. relationship-specific matches for current entities;
3. a very small established high-centrality fallback.

The entire self graph is never injected into a model context.

This Working Self is system-owned durable state; it does not depend on an LLM
session remaining alive.

## Response-policy boundary

A new historical evidence scope, `SELF_MODEL`, separates two questions that
were previously conflated:

### USER_AUTHORED

Use for questions such as:

- "What did I say my preference was?"
- "What exactly did I call that?"
- "What did I tell you about myself?"

Derived self memory can help route retrieval, but cannot satisfy the evidence
requirement.

### SELF_MODEL

Use for inferential questions such as:

- "What do I usually prefer?"
- "What patterns do you see in how I decide?"
- "What would I probably choose?"
- "What seems central to my identity?"

Established/contested self representations may be admitted as primary derived
context for natural-language cognition.

Exact-source modes never use derived self memory as the quoted source.

## Composer and Adaptive Recall

The Composer remains a memory-sufficiency specialist.

When policy permits primary derived context, Composer receives a separately
rendered `SelfContextPacket` in addition to canonical memory. It does not
resolve whether the schema is true.

When self context is routing-only, Composer does not see it as evidence.

Adaptive Recall may use active self-schema statements as supplemental retrieval
queries even in routing-only mode. Canonical source-type admission still obeys
the current evidence policy.

Therefore:

    self schema
        -> routing
        -> canonical recall
        -> Composer

is allowed for source-restricted questions, while:

    self schema
        -> Composer/final responder

is allowed only under a policy that admits derived self conclusions.

## Final responder

For natural-language SELF_MODEL / DERIVED_INTERNAL / GENERAL_OR_CURRENT
responses, the final responder receives self context in a clearly separate
derived-evidence section.

The section explicitly identifies itself as revisable derived self-memory, not
historical quotation or independent canonical evidence.

Self context never authorizes tool/action execution and is not supplied to the
pre-cognitive capability selector.

## Relational, prospective, procedural, narrative, and embodied boundaries

The v1 representation system supports these domains without collapsing them:

- **Relational Self:** relationship-specific expectations and behavior, keyed by
  a relationship reference.
- **Prospective Self:** desired, expected, or feared future identity.
- **Procedural Self:** semantic knowledge that a procedure/skill is part of the
  person's capabilities; actual executable procedures remain in procedural
  memory/capability systems.
- **Narrative Identity:** stored only as `NARRATIVE_HYPOTHESIS`; narrative
  coherence does not convert interpretation into historical fact.
- **Embodied Self:** current state of a particular embodiment; fast-changing
  embodied state does not automatically become an enduring trait.

Goals remain primarily WorkingState/intentional state. Repeated enduring goals
may later support role/value/self-schema formation through normal evidence and
reflection.

## Identity maturity boundary

This system does **not** self-authorize the Constitution Article 3 identity
maturity transition.

A `SELF_CONCEPT` representation records evidence about the person's
self-conception. It is not authority for a transient LLM or derived schema to
declare identity sovereignty, subjective continuity, consciousness, or legal
personhood.

Any future identity-maturity transition remains a separately defined,
pre-authorized and empirically gated system transition.

## Biological inspiration and deliberate divergence

The architecture takes functional inspiration from:

- working-self models;
- distributed conceptual self knowledge;
- episodic/semantic separation;
- complementary fast/slow learning;
- replay/consolidation;
- context-sensitive trait expression;
- prediction-error-driven revision;
- selective activation.

It deliberately does **not** copy several human failure modes.

Human autobiographical memory is reconstructive. Self-coherence can bias recall,
contradictions can be rationalized away, and repeated retrieval can strengthen a
memory subjectively.

Prometheist instead preserves:

    correspondence:
        immutable canonical life history

    coherence:
        revisable semantic/self/narrative projections

Derived coherence may guide attention and prediction. It never rewrites
correspondence.

## Acceptance requirements

The Self-Memory System is not accepted merely because its schemas validate.

Release evidence must cover at least:

- explicit self-report versus observed behavior;
- aspiration versus current identity;
- stable preference plus one outlier;
- gradual and abrupt change;
- relationship/context-specific behavior;
- genuine unresolved inconsistency;
- repeated copies of the same source not multiplying evidence;
- higher-order schemas sharing canonical roots;
- counterevidence search before promotion;
- prediction confirmation and contradiction;
- source-restricted questions refusing derived substitution;
- exact-source responses remaining canonical;
- relevant self context improving person-fidelity cases;
- irrelevant central schemas not contaminating unrelated responses;
- model-response/self-reinforcement attacks;
- restart/replay of proposal and review stages;
- native Ollama evaluation of proposal/review behavior.

The highest-value eventual metric is held-out person prediction: using only
evidence available before a real decision, does the self model improve prediction
of the person's later choice, interpretation, or characteristic response without
increasing unsupported certainty?

## Current boundary

This implementation establishes the substrate, guarded reflection path,
prediction feedback, Working Self activation, and response-path admission rules.

It does not claim:

- that every canonical event is already segmented into mature autobiographical
  episodes;
- that values/traits are fully calibrated;
- that person fidelity has been demonstrated;
- that narrative identity is mature;
- that procedural memory is implemented as a complete skill-learning subsystem;
- that synthetic embodiment inputs are complete;
- or that first-person identity maturity has been reached.

Those remain empirical problems to test on top of this architecture.
