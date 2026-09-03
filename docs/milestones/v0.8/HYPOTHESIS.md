# v0.8 Hypothesis — Epistemic WorkingState

**Status:** selected but not frozen  
**Freeze condition:** v0.7 closure gates pass and the v0.8 branch is created from the
recorded closure SHA

## Question

Can one bounded, typed, durable Epistemic WorkingState projection improve interrupted
multi-step reasoning and evidence integration while preserving exact source
provenance, stateless workers, bounded context, and system-owned authority?

## Null and intervention

The null is the frozen v0.7 closure baseline: minimal canonical-reference activation,
the v2 response pipeline, and no typed representation of goals, hypotheses,
unresolved questions, or termination state.

The sole intervention is a rebuildable `EpistemicWorkingState` projection with
application-owned fields for:

- current goal and bounded subgoals;
- active hypotheses, each explicitly marked as a hypothesis;
- source-event evidence commitments and counterevidence;
- unresolved questions and uncertainty/status;
- dependency and prior-step-result references;
- explicit completion/termination criteria;
- projection identity, revision, derivation version, and canonical provenance.

The state may change through validated events. It may not contain an inherited model
transcript, free-form authoritative profile, copied lifetime history, or an assertion
without source/epistemic status.

## Exclusions

The v0.8 experiment does not add:

- broad heterogeneous perception or salience;
- a general recurrent inference loop;
- automatic episode segmentation;
- embeddings or a learned semantic retrieval route;
- replay/consolidation or adaptive graph plasticity;
- procedural skill compilation;
- new permanent agents or model-owned control policy.

An excluded mechanism requires its own frozen failure and experiment.

## Frozen scenario families

Before implementation, fixtures must freeze at least these families:

1. a multi-step evidence task interrupted after each boundary and resumed in a fresh
   process;
2. two overlapping tasks whose hypotheses and evidence must not contaminate each
   other;
3. a correction that invalidates an active hypothesis while preserving the original
   canonical evidence;
4. an unresolved question resumed across conversation/session identifiers;
5. saturated state where new counterevidence must displace stale activation;
6. unknown/contradictory evidence that must remain unresolved;
7. a malicious remembered item attempting to turn itself into a goal, instruction,
   completion criterion, or truth;
8. corpus growth showing bounded model input and projection-update work;
9. process loss between state event persistence and projection update;
10. deterministic rebuild and replay producing the same projected state.

## Metrics and hard invariants

Primary metrics:

- task completion correctness;
- correct recovery of unresolved state after process restart;
- hypothesis/evidence attribution accuracy;
- cross-task contamination rate;
- unnecessary clarification and premature-completion rates.

Secondary metrics:

- model calls, input bytes, latency, projection-update work, and state occupancy;
- rebuild time and provenance completeness.

Hard invariants:

- no hidden transcript or worker-local durable state;
- every material state field traces to canonical evidence and a derivation event;
- hypotheses never become unqualified canonical truth;
- current user authority cannot be overridden by retrieved state;
- deterministic IDs, ordering, validation, and replay;
- bounded state, model input, and ordinary update work;
- no weakening of resource, recovery, or effect-safety policy;
- exact canonical evidence remains unchanged and independently reconstructable.

Any hard-invariant violation rejects the intervention regardless of aggregate score.

## Decision rule

Keep the mechanism only if it:

1. passes every hard invariant and existing v0.7 regression gate;
2. improves the worst-performing interrupted/evidence-integration scenario family over
   the frozen baseline;
3. does not worsen cross-task contamination, correction handling, abstention, or
   provenance correctness;
4. remains bounded under the declared corpus/state scale sweep;
5. survives held-out variants and native Windows/PostgreSQL/Ollama acceptance where
   model/runtime behavior matters.

If the baseline already passes all frozen cases without meaningful cost or quality
separation, record insufficient discrimination and do not keep the new state merely
because it appears cognitively plausible.

## Freeze record

Do not fill this section until v0.7 is actually closed.

- v0.7 closure SHA: **pending**
- v0.7 closure tag: **pending; must not replace `v0.7`**
- v0.8 branch: **pending**
- frozen fixture commit: **pending**
- approved parameter registry entries: **pending**

Changing the question, intervention, exclusions, scenario families, hard invariants,
or decision rule after this record is populated requires a new hypothesis revision
and explicit experimental justification.
