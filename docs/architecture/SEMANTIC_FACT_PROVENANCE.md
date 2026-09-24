# Semantic Fact Provenance

**Status:** constitutional architecture deep dive.
**Constitutional authority:** implements Articles 9, 10, 11, 23, and 24 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md), as detailed in [`LOSSLESS_PROGRESSIVE_MEMORY.md`](LOSSLESS_PROGRESSIVE_MEMORY.md).
**Applies to:** durable beliefs about a subject/property derived from consolidated evidence; not canonical events, and not the bounded per-page situation projections that already exist in `consolidation.py`.

`situations.py` and `expectations.py` already give Prometheist a temporal-fact model with confidence, an explicit validity interval, and a `supersedes` pointer -- but it is scoped to one bounded, overlapping *situation window* (structured percepts such as sensor/process observations). `consolidation.py`'s scheduled pages already aggregate repeated observations with exact `support_percept_ids` provenance -- but each page's projection is disposable, bounded to that page, and deliberately makes "no universal claim."

Neither mechanism answers a longer-lived question central to Prometheist's digital-self mission: *what does Prometheist currently believe about a subject's property, across every page and every conversation, and how did that belief change over time?* `semantic_memory.py` answers that question without adding a new kind of memory store, a new event type, or any change to canonical history.

## Design lineage

This follows two pieces of external prior art, adapted rather than copied wholesale (see the module's own docstring for the exact upstream files reviewed):

- **Graphiti** (`getzep/graphiti`, `graphiti_core/edges.py`) represents a derived assertion as an `EntityEdge` carrying `fact`, `episodes` (provenance), and a bi-temporal `valid_at`/`invalid_at` (real-world validity) versus `expired_at` (system time) split. Graphiti is backed by a mutable graph database, so it implements invalidation by updating the old edge's fields in place. Prometheist's append-only constitution forbids editing a historical record, so this module keeps the bi-temporal idea (`valid_from` real-world time, `asserted_at` system time) but never mutates an existing fact: the old fact's implicit end of validity is always the *newer* fact's `valid_from`, discoverable through `supersedes` without rewriting anything -- the same non-destructive pattern `situations.Situation.supersedes` and `expectations.Expectation.supersedes` already use.
- **Mem0** (`mem0ai/mem0`, `mem0/memory/main.py`) moved its extraction pipeline to an "additive" model: new candidate memories always get added, and reconciliation against existing memories is a separate step, rather than having extraction itself silently rewrite or delete history. `derive_semantic_fact` mirrors that split with a pure `reconcile_fact` classification step kept separate from the one place that actually persists a new record.

Unlike both, reconciliation here is fully **deterministic** (exact `(subject, property)` identity, not vector/LLM similarity) because the evidence is already a structured `Observation` (`percept_context.py`) rather than free text.

## Data model

```text
SemanticFact
├── fact_id
├── subject / property / value / unit          (percept_context.Observation shape)
├── confidence
├── derived_from      durable evidence ids (percept ids), same space as
│                     consolidation.py's existing support_percept_ids
├── derivation_method  e.g. "consolidation/v1"
├── valid_from         when the evidence says this became true
├── asserted_at        when Prometheist derived this belief (system time)
├── supersedes          fact_id this replaces, or null
└── relation            INITIAL | CORROBORATES | SUPERSEDES | CONTRADICTS
```

A fact is never mutated once written. `reconcile_fact` classifies a new candidate against the current head deterministically:

```text
no current fact for (subject, property)          -> INITIAL
same (value, unit) as the current fact            -> CORROBORATES  (no new record)
different value, evidence time >= current.valid_from  -> SUPERSEDES
different value, evidence time <  current.valid_from  -> CONTRADICTS
```

`CORROBORATES` deliberately creates nothing: re-observing an unchanged truth must not spam a growing chain of identical facts. `CONTRADICTS` still creates a new record -- neither belief is discarded, matching the Constitution's "contradictions and unknowns must remain visible" rule -- but, as a practical default, the most recently *learned* value still becomes the queryable head so that ordinary lookups return an answer rather than an ambiguity.

## Storage

Facts are persisted through the existing `cognitive_store` append-only mechanism (`record_kind="semantic_fact"`, keyed by a deterministic hash of `(subject, property)`). This reuses infrastructure rather than adding a new one:

- `cognitive_heads` continues to expose only the *current* fact for fast lookup (`current_semantic_fact`);
- every past revision remains exactly reconstructable from canonical `events`, never deleted, via the new general-purpose `cognitive_store.record_history(kind, key)` primitive;
- `semantic_fact_history` / `semantic_fact_as_of` build on that to answer "what was believed at any past moment" without a chain walk, since among facts whose `valid_from` is not after the query time, the one with the latest `valid_from` was necessarily in effect.

## Where it is derived today

`consolidation.py`'s scheduled `consolidate_page` is the only current caller. For each bounded page, after building its existing disposable per-page projection, it separately re-partitions the same evidence **by exact subject** (the page's own projection intentionally aggregates every subject sharing a property/unit; a durable belief must never blur two subjects' evidence together) and calls `derive_semantic_fact` once per subject/property whose value is unambiguous within that page. A page where one subject's own evidence disagrees with itself (`variation_present`-equivalent at the per-subject level) is left unresolved for a later page or a future reflection worker, rather than guessing.

This is fully deterministic and runs inside the already-durable, already-claimed `EXECUTE` situation-worker stage; it adds no new LLM call, no new pipeline stage, and no change to the existing projection's shape (`semantic_facts` is an additive key in `consolidate_page`'s return value).

## Inspection

```powershell
uv run prometheist memory-fact --subject "person:mike" --property "preferred_drink"
```

prints the current fact and its complete history, oldest first, as JSON.

## What this deliberately does not do yet

- **No free-text extraction.** Turning a conversational sentence into a structured `Observation` remains a separate, LLM-backed concern. This module only formalizes what happens once a candidate observation already exists (from a structured percept today; from a future extraction step later).
- **No reflection/generalization layer.** A higher-order belief synthesized by an LLM from many episodes (in the spirit of Generative Agents' reflections or MemoryOS's consolidation) is a natural future consumer of `derive_semantic_fact` -- it would supply its own `derivation_method` and a genuinely later `asserted_at` than `valid_from` -- but adding that worker means adding a new specialist role to a live pipeline, which is out of scope here.
- **No retrieval wiring.** `SemanticFact` is not yet surfaced to the Composer/Adaptive Recall path that answers user prompts; today it is reachable only through direct calls and the `memory-fact` CLI. Wiring it into live retrieval is future work with its own review, since it touches the same evidence-authority machinery `epistemic_authority.py` already governs carefully.
