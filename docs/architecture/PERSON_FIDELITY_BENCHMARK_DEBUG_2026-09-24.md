# Person-Fidelity Benchmark Debugging — 2026-09-24

## Scope

This note records the diagnosis and corrections made after the 2026-09-24
PERSON-FIDELITY-001 and PERSON-FIDELITY-002-HOLDOUT native runs produced poor
structural evidence-delivery results.

The failed runs remain immutable benchmark evidence. They are not deleted,
rewritten, or reclassified as successful.

## What the failed runs actually measured

The native PERSON-FIDELITY-001/002 runner seeds canonical life events and then
immediately asks each probe through the production user-prompt pipeline. It resets
the benchmark database before every probe.

That remains a useful episodic-retrieval baseline, but after Self-Memory System v1
it is no longer a complete test of Prometheist's person model. The failed
2026-09-24 artifacts show that every inspected probe entered the response pipeline
with an empty `self_context`. No scheduled consolidation, Self-Schema Proposal, or
Self-Schema Review had run before the probes.

Therefore those runs primarily measured:

1. deterministic episodic attention-aperture retrieval;
2. Composer sufficiency judgment;
3. Adaptive Recall when Composer requested it; and
4. final response realization.

They did **not** measure whether the newly implemented Self-Memory System could
learn, retrieve, and apply durable self representations.

## Failure modes found

### 1. SELF_MODEL Composer could accept empty personal evidence

The most severe control-flow defect was visible in novel-decision and
characteristic-expression probes. The response-policy worker correctly classified
the request as `SELF_MODEL`, the aperture returned no useful personal history, but
the Composer could still return `sufficient=true`.

That suppressed Adaptive Recall. The final responder then independently enforced
the historical-source requirement and returned the generic insufficient-evidence
literal.

The two stages were therefore asserting contradictory conditions:

- Composer: historical evidence is sufficient;
- final responder: no admissible historical/self evidence exists.

### 2. Composer stopped on answer-shaped partial memories

Several probes retrieved one relevant or adjacent autobiographical statement and
the Composer immediately stopped. Examples include later summaries without the
formative episode, one side of a temporal change, or a self-description without
the observed behavior needed to reconcile it.

The old Composer prompt tested broad semantic answerability. Person-fidelity
questions need a stricter condition: all material personal-evidence slots must be
filled before recall stops.

### 3. Verbose prompts expose a lexical scoring limitation

The deterministic lexical scorer normalizes token overlap by the complete query.
A long natural-language question can therefore dilute one highly diagnostic term
below the fixed evidence threshold. A direct memory containing "surprise" was an
example: it could lose to an unrelated memory that happened to share several
generic prompt words.

This is real retrieval behavior, but it should not be "fixed" by arbitrarily
lowering the global threshold. The current scoring constants are explicitly
empirical tunables whose prior benchmark did not discriminate among many
alternatives. The immediate architectural correction is to ensure that
SELF_MODEL Composer deficits trigger Adaptive Recall with a short,
semantically-specific query. Lexical scoring should be recalibrated separately by
a discriminating retrieval experiment rather than tuned against one person-fidelity
fixture.

### 4. Final-response artifact refs overstated routing-only self influence

The responder correctly rendered self memory only when its admission was
`PRIMARY_DERIVED_CONTEXT`, but the artifact evidence-ref list included
`self:<representation-id>` for routing-only packets as well.

That did not change model behavior, but it made causal audit metadata claim that
evidence influenced the responder when it had not actually been shown to the
model. The artifact refs now mirror the rendered evidence channel.

### 5. Self-evidence time needed a real observation-time axis

Canonical event `created_at` is database admission time. A historical life event
can be learned later. SelfEvidence therefore cannot use canonical insertion time
as both observation time and knowledge time.

Self-reflection now resolves source observation time from durable percept metadata
when available (and from the synthetic fixture's explicit `occurred_at` in the
benchmark), while retaining canonical event `created_at` as `known_at`.

This preserves the intended distinction:

- `observed_at`: when the represented event/state occurred or was observed;
- `known_at`: when Prometheist acquired the canonical evidence.

## Production corrections

### SELF_MODEL historical-completeness Composer

`SELF_MODEL` requests now use a dedicated Composer contract. The worker remains
narrow: it still returns only `sufficient` and `memory_deficit`; it does not
synthesize identity or answer the user.

The contract requires complete material slots for classes such as:

- autobiographical meaning;
- relational judgment;
- temporal change;
- self-report versus observed behavior;
- context-dependent preference;
- novel decisions;
- characteristic expression; and
- identity-integrity conflicts.

Ordinary/general/current-prompt Composer behavior is unchanged.

### Deterministic empty-evidence guard

For a request that application policy has already classified as `SELF_MODEL`,
an empty canonical packet plus empty admitted self-context cannot terminate as
sufficient even if the small Composer model emits the wrong boolean.

The system forces bounded Adaptive Recall instead.

### Exact responder provenance

`self:<id>` artifact references are emitted only when the corresponding self
context is `PRIMARY_DERIVED_CONTEXT` and was actually rendered into the final
responder's evidence channel.

### Fail closed after bounded historical recall is exhausted

A history-dependent request now treats the Composer's terminal
`memory_sufficient=false` as a control result, not a suggestion. The final
responder does not synthesize an answer from a merely non-empty but explicitly
incomplete historical packet. It first checks for an explicit current-message
fallback literal and otherwise returns the generic insufficient-evidence response.

This is especially important for legitimate unknowns: unrelated autobiographical
material is no longer enough to authorize answer generation merely because some
memory was retrieved.

### Specific historical facts are not Self-Memory by default

The response-policy contract now distinguishes a specific remembered personal fact
from a derived person-model conclusion. A question such as a remembered person's
name, place, date, possession, or event detail is `USER_AUTHORED` when prior
testimony would have to establish it. `SELF_MODEL` remains reserved for derived
preferences, values, traits, behavioral tendencies, relationships, decision
patterns, prospective identity, and narrative themes.


## New benchmark: SELF-MEMORY-001

`benchmarks/run_self_memory_person_fidelity.py` uses the same frozen synthetic
person fixture but adds the missing learning phase.

The experiment performs:

1. reset a dedicated benchmark database;
2. seed the fictional life history as canonical evidence;
3. form production situations using the fixture's real conversation contexts;
4. execute one production scheduled consolidation task;
5. run the production Self-Schema Proposal specialist;
6. run the separate production Self-Schema Review specialist;
7. snapshot the resulting immutable self-memory heads;
8. reset the database before every probe;
9. reseed the identical canonical life record;
10. restore the frozen learned self-memory snapshot;
11. ask the probe through the ordinary production user-prompt pipeline.

The snapshot is used only to avoid re-running the same expensive learning phase
for every isolated probe. Each probe still starts from identical pre-probe state
and cannot contaminate another probe.

### Context-breadth validity

Self-Memory has guards requiring some generalized slow schemas to have evidence
from multiple contexts. The benchmark therefore maps fixture events from the same
fixture conversation to the same production situation identity. Two statements
from one conversation cannot masquerade as two independent contexts merely because
they are separate events.

### Transitive provenance scoring

A self representation is derived context, not a new independent fact. When a
probe's responder consumes `self:<representation-id>`, the benchmark expands that
reference to the representation's canonical support/opposition roots before
structural scoring.

The result records both:

- direct responder evidence refs; and
- rooted/transitive canonical evidence refs.

This prevents a correct self-schema answer from being falsely marked as missing its
source evidence while preserving the distinction between direct episodic recall and
derived self-model influence.

## Follow-up native smoke run: universal contesting

The first native `SELF-MEMORY-001` smoke run reached the production learning
pipeline and formed 14 self representations, but all 14 resolved to `CONTESTED`.
Consequently no core established self representations were available for Working
Self fallback and the four smoke probes reported zero activated self memories.

The review path exposed an application-level defect. Counterevidence recall was
focused from the candidate's support roots, so the review packet could contain the
same canonical events already recorded as `SUPPORTS`. The model's
`opposition_indices` were then trusted directly and those roots could be written
again as `OPPOSES`. A single canonical event could therefore count on both sides
of the same proposition, and any opposition root forces an attempted established
schema to `CONTESTED`.

Corrections:

- canonical support roots and independently retrieved related/counterevidence are
  now separate reviewer channels;
- support roots are removed from the packet whose indices may be selected as
  opposition;
- the durable self-evidence layer rejects opposite polarity for the same
  representation/root pair;
- `CONTEST` structured output requires at least one concrete opposition index;
- if no valid opposing root survives application validation, a contest request
  remains `CANDIDATE` rather than manufacturing `CONTESTED`.

The same run also exposed a benchmark-only manifest bug: the legacy artifact
inventory expected `<probe>/events`, whereas the self-memory runner uses
`learning/...` and `probes/<probe>/...`. SELF-MEMORY now has its own strict
inventory validator for those two layouts. Failed pre-fix artifact trees remain
preserved.

## What remains deliberately unchanged

The global memory lexical score and the `0.15` admission threshold have **not**
been retuned from these person-fidelity results. Doing so would optimize against
the evaluation fixture and violate the repository's empirical-tunable discipline.

A follow-up MEM-SCORE discriminating experiment should include the failure shapes
exposed here: long paraphrases, one rare diagnostic term, generic-word distractors,
legitimate unknowns, temporal alternatives, and characteristic-expression queries.

## Running the experiments

The legacy episodic baseline remains useful and should continue to be run:

```powershell
.\scripts\run_person_fidelity_baseline.ps1
.\scripts\run_person_fidelity_baseline.ps1 -Holdout
```

The new Self-Memory experiment can be run directly:

```powershell
uv run --locked python benchmarks/run_self_memory_person_fidelity.py
uv run --locked python benchmarks/run_self_memory_person_fidelity.py --holdout
```

A dedicated benchmark PostgreSQL database is still mandatory through
`PROMETHEIST_PERSON_FIDELITY_DATABASE_URL`; its database name must contain
`benchmark`.

The structural result is still not a person-fidelity verdict. Final responses
require human review against the frozen oracle.
