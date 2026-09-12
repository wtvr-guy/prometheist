# Specialist Worker Modularity

**Constitutional authority:** implements Article 31 of
[`../../CONSTITUTION.md`](../../CONSTITUTION.md) and is subordinate to the
Constitution.

**Applies to:** every LLM-backed worker, stage contract, model invocation, retry,
handoff artifact, and future non-user-percept pipeline.

## Principle

An LLM worker is disposable semantic compute for one coherent decision. It is not a
container into which adjacent reasoning tasks are placed for convenience.

Prometheist therefore separates roles when they differ in any of these ways:

- output schema or decision authority;
- required evidence classes or provenance boundary;
- failure, retry, or stopping semantics;
- resource/model requirements;
- downstream consumer;
- audit question answered by the result.

Sharing transport, validation, artifact-writing, or deterministic helper code does
not merge semantic roles. Shared infrastructure should remain ordinary reusable
software beneath narrow stage contracts.

## Required worker contract

Every LLM-backed stage must declare:

1. one named semantic responsibility;
2. its bounded authoritative inputs and separately quarantined evidence;
3. one application-owned output contract, or mutually exclusive realization modes
   that produce the same stage outcome;
4. which model call kinds the stage may invoke;
5. its retry/reassessment boundary;
6. its durable result and causal provenance;
7. its resource estimate and admission requirements.

A guarded worker must fail closed if it attempts to invoke a model role assigned to
another stage. Repeated calls are permitted only for validation retries or bounded
reassessment of the same semantic question. They do not authorize a second role.

## Current user-prompt specialists

The implemented v2 user-prompt path uses these process boundaries:

| Stage | Responsibility | LLM use |
|---|---|---|
| Reference resolution | Expose deterministic WorkingState availability | None |
| Evidence policy | Select historical source scope and response surface from the current prompt only | One policy role, with bounded validation retries |
| Work triage | Select required non-memory capability indices from the admitted aperture | One work-selection role, with bounded validation retries |
| Capability execution | Execute the committed application-owned plan | None in the stage itself; invoked capabilities own their contracts |
| Memory composition | Judge memory sufficiency and name only the missing memory semantics | One Composer role, freshly reassessed across bounded Adaptive Recall rounds |
| Response realization | Produce exact-source or natural output under the committed policy | One realization mode per path, with bounded validation retries |
| Result persistence | Persist and emit the completed disposition | None |

The evidence-policy result is an immutable stage artifact. Work triage, Adaptive
Recall, the Composer, and response realization inherit that exact policy. They may
not reclassify it.

## Percept triage for non-user inputs

Scheduled tasks, triggered events, anomaly flags, sensor observations, and other
non-user percepts need a dedicated **Percept Triage Specialist** when their next
semantic action cannot be established deterministically. Its job is limited to
classifying the perceived situation into an application-owned action/response plan
and naming required evidence domains. It does not retrieve evidence, judge whether
retrieved evidence is sufficient, execute work, or generate user-facing language.

Explicit user prompts do not delegate `response_required` to this specialist; their
intake contract sets it to true. Non-user response behavior remains governed by each
percept class's deterministic intake policy wherever possible.

## When to split a worker

Split a worker when it makes two independently testable semantic decisions, needs
two unrelated schemas/prompts, consumes evidence unnecessary for one of its duties,
or produces intermediate state that another component should be able to inspect,
retry, replace, or reuse independently.

Do not split deterministic formatting into an LLM worker, create specialists before
a concrete semantic need exists, or treat every helper function as a worker. The
boundary is semantic authority and resource lifetime, not source-file size.

## Enforcement and audit

Current enforcement consists of:

- one fresh guarded process per durable percept stage;
- an application-owned stage-to-specialist registry;
- a fail-closed allowlist of LLM call kinds for every stage;
- independent evidence-policy and stage-result artifacts;
- regression tests covering stage-role completeness, cross-role rejection, and
  exact policy inheritance without reclassification.

A constitutional audit must identify every production LLM invocation site and map
it to one specialist contract. An unmapped call, a stage allowed to invoke another
stage's role, or a single worker performing independent semantic decisions is a
failure of Article 31.
