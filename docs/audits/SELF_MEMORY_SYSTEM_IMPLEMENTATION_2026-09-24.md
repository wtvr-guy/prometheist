# Self-Memory System Implementation Record — 2026-09-24

**Branch:** `self-memory-system-v1`  
**Base:** `semantic-memory-resolution-v2`  
**PR:** #32  
**Status:** experimental implementation; acceptance pending CI/native/person-fidelity gates.

## Why this change exists

The person-fidelity work exposed a structural limitation in a purely episodic
response path: a fresh stateless worker can retrieve autobiographical events and
re-infer the relevant part of the person's identity, but those higher-order
interpretations disappear with the worker unless Prometheist persists them.

A single mutable user profile would solve that inefficiently and incorrectly. It
would collapse self-report, behavior, aspiration, context, contradiction, and
change; it would also create an easy path for generated summaries to replace source
history.

The implemented Self-Memory System instead adds a rebuildable cognitive layer whose
claims remain attached to canonical life evidence.

## Implemented changes

### Typed self representations

`src/jit_agent/self_memory.py` introduces typed self representations for roles,
preferences, values, traits, behavioral tendencies, decision policies, worldview,
self-concept, prospective self, relational schemas, narrative hypotheses,
procedural self, and embodiment state.

Representations also preserve perspective: avowed, observed, inferred,
aspirational, normative, or social attribution.

### Application-owned learning timescales

Plasticity is assigned deterministically from representation kind. The proposal LLM
cannot choose how easy its own conclusion is to stabilize.

### Canonical-root evidence

Self evidence terminates in a positive allowlist of canonical source-event types.
Model outputs, memory packets, retrieval artifacts, and derived records cannot become
independent evidence about the person.

Avowed/aspirational/normative support additionally requires user-authored roots.

### Root closure

Higher-order schemas inherit unique canonical roots from parent schemas. Shared roots
are deduplicated, preventing one observation from becoming multiple votes merely
because it passed through several abstractions.

### Append-only resolution

Self schemas maintain append-only CANDIDATE / ESTABLISHED / CONTESTED /
SUPERSEDED / REJECTED resolution history. Establishment requires prior
counterevidence review. Opposing canonical evidence forces contestation.

### Evidence breadth

Cross-context breadth is derived from durable situation identity associated with
canonical roots. Model-generated semantic context tags are not counted as evidence
breadth.

### Separate proposal and review workers

Scheduled consolidation now has two additional guarded stages:

1. `SITUATION_SELF_PROPOSE` — proposes typed representations from bounded canonical
   evidence;
2. `SITUATION_SELF_REVIEW` — independently expands related/counterevidence and
   reviews each proposal.

They are separate fresh LLM invocations with separate call-kind allowlists.
Non-consolidation situation work skips both stages without an LLM call.

### Prediction feedback

Resolved self schemas can create held-out predictions. Later canonical outcomes can
be marked confirmed, contradicted, or ambiguous. Confirmations/oppositions feed back
as independent evidence and can alter schema resolution.

### Working Self

Live user cognition now constructs and persists a bounded `WorkingSelf` containing
the small active subset of persistent self representations relevant to the current
query/entities/goals.

Activation uses lexical relevance, relationship matches, and a very small central
fallback. The entire person model is never inserted into a model context.

### Response authority

`HistoricalEvidenceScope.SELF_MODEL` distinguishes inferential questions about the
person from questions about explicit prior user statements.

- SELF_MODEL natural-language cognition may use established/contested self context.
- USER_AUTHORED and exact-source cognition may use self representations as retrieval
  cues only.
- Exact-source output remains grounded in canonical admitted bytes.
- Self context is never passed to the pre-cognitive work selector and cannot
  authorize external effects.

### Adaptive Recall

Active schema statements may be used as supplemental deterministic recall queries.
Canonical source-type filtering remains controlled by the already-committed response
policy.

## Deliberate safeguards

The implementation explicitly prevents:

- LLM self-certification of identity sovereignty;
- a proposal worker approving its own schema;
- model-authored prior responses becoming user-identity evidence;
- model-invented context labels satisfying cross-context support;
- aspiration becoming current identity by type conflation;
- derived schema trees multiplying evidence;
- retrieval/repetition acting as evidence;
- narrative hypotheses replacing canonical history;
- exact-source requests being answered from derived self memory;
- identity centrality being treated as confidence/truth;
- contradiction being silently explained away during application resolution.

## What remains empirical

Implementation is not acceptance.

The following require benchmark/native evidence:

- whether Qwen3:4b can reliably classify representation kind/perspective;
- whether the proposal/review split reduces false schemas;
- whether current support/context thresholds are calibrated;
- whether core-schema fallback improves or contaminates unrelated cognition;
- whether SELF_MODEL policy classification is reliable;
- whether schema-guided Adaptive Recall improves evidence delivery;
- whether held-out predictions improve over episodic-only baselines;
- latency/resource impact on the target Windows/Ollama host;
- long-history scale and schema count growth;
- relationship/narrative/procedural fidelity;
- correction and abrupt identity-change behavior.

## Required acceptance expansion

Person-fidelity evaluation should add frozen cases for:

- stable preference plus isolated outlier;
- gradual change and explicit abrupt correction;
- avowed self versus contradictory behavior;
- aspiration versus current identity;
- relationship-specific behavior;
- context-conditioned traits;
- value inference from repeated costly tradeoffs;
- shared-root evidence multiplication attacks;
- derived-model-output feedback attacks;
- narrative coherence versus historical correspondence;
- genuine inconsistency and abstention;
- held-out novel-decision prediction;
- irrelevant central-schema contamination.

## Constitutional fit

This implementation is specifically intended to advance Article 2's requirement to
distinguish direct self-description, observed behavior, inferred traits,
context-dependent conduct, contradiction, uncertainty, and change over time while
keeping derived claims evidence-grounded and revisable.

It also preserves Articles 7–9 by keeping identity state system-owned, LLM workers
stateless, and canonical autobiographical history immutable.

Nothing in this implementation satisfies or bypasses Article 3's separately gated
identity-maturity transition.
