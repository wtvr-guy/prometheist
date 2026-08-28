# v0.7 Pre-Cognitive Transient Workers — 2026-08-28

**Status:** active release-candidate mechanism; deterministic/native revalidation required after the typed-workpiece integration.

## Purpose

This record preserves why v0.7 moved from recurrent general capability routing to staged/demand-driven ephemeral semantic workers while keeping Qwen3:4b fixed.

Current normative architecture lives in:

- [`../../architecture/INTERACTION_WORKPIECE.md`](../../architecture/INTERACTION_WORKPIECE.md)
- [`../../architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](../../architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md)
- [`../../architecture/WORKER_PROFILE_REGISTRY.md`](../../architecture/WORKER_PROFILE_REGISTRY.md)

## Starting problem

The first post-pivot disposable interaction implementation still used a recurrent general model router. It was stateless, but one local model repeatedly handled broad intent/routing/control responsibilities and could become both the latency driver and a concentrated failure point.

The first transient-worker revision replaced that loop with bounded pre/post semantic reassessment, deterministic capability tranches, a terminal `FinalResponseDirective`, response-only persona, and a private worker-profile registry.

## Native Qwen3:4b evidence

Native Windows/PostgreSQL/Ollama acceptance initially reached 4/5:

- randomized Project Oriole recall — pass;
- randomized Project Falcon launch-code recall — pass;
- cross-process memory analysis — pass;
- cross-conversation cross-process recall — pass;
- four-turn stateless continuity — fail.

The failing Kestrel turn was diagnostically important: the JIT `MemoryPacket` already contained the needed historical rule, the profile token, and the immediately previous interaction. Retrieval/continuity had succeeded. The aggregate pre-cognitive model call nevertheless chose terminal abstention.

That isolated the failure to semantic evidence-sufficiency/control judgment rather than memory retrieval.

## Failed consistency-validator experiment

A subsequent patch tried to enforce a cross-field semantic invariant: `INSUFFICIENT_AFTER_AVAILABLE_WORK` was treated as valid only with terminal `ABSTAIN`.

Native acceptance then regressed from 4/5 to 0/5 because Qwen3:4b could emit a useful operative disposition alongside semantically inconsistent metadata. Failing the entire interaction on that inconsistency turned one unreliable classifier field into a process-wide failure.

That validator was removed. The negative result is retained:

> Application code should enforce hard schemas/authority boundaries, but should not invent brittle semantic cross-field invariants for a small-model aggregate classification merely because the combination looks logically inelegant.

## Intermediate reconsideration experiment

A bounded “supported packet reconsideration” call was introduced for `ABSTAIN + nonempty supported MemoryPacket`. It did not force response; it gave a fresh stateless worker one chance to reread exact activated evidence.

That was safer than deterministic semantic rewriting, but discussion exposed a cleaner architectural response: stop asking one model call to judge evidence sufficiency and simultaneously author the rest of the aggregate control record.

## Demand-driven decomposition

The current pre-acquisition path now has only two semantic stations with real downstream consumers.

### `evidence_sufficiency_verifier`

Returns only:

```text
SUFFICIENT | INSUFFICIENT
```

It does not see/select the capability catalog and cannot author disposition, response prose, execution policy, or unrelated metadata.

### `capability_selector`

Runs only after the evidence-sufficiency station's final insufficiency result and only when a legal catalog exists. Returns only bounded application-catalog indices.

It cannot reassess sufficiency, author capability IDs/queries, schedule execution, or decide terminal response.

### Deterministic composition

Application code derives:

```text
SUFFICIENT -> RESPOND
INSUFFICIENT + legal selected work -> ACQUIRE_CAPABILITIES
INSUFFICIENT + no useful legal work -> ABSTAIN
```

Compatibility fields without a current operational consumer remain neutral rather than creating mandatory extra LLM stations.

This preserves the fast path at one pre-acquisition semantic call while containing failures inside much smaller responsibilities.

## Assembly-line sanity check

The decomposition is intentionally **not** “one LLM per field.”

The governing rule became:

> **one bounded job per station + no unnecessary station**

Warm Ollama residency lowers model-load overhead but does not make inference free. Extra calls still add prompt evaluation, generation, structured-output failure surfaces, and correlated model error.

A new station must therefore have a concrete downstream consumer, authority boundary, or measured failure mode.

## Workpiece generalization

The discussion then identified that even the phrase “final response flow” was too narrow for Prometheist.

The current implementation now carries a typed `InteractionWorkpiece` across the durable interaction stages. The atomic sufficiency/capability-selection results become explicit workpiece components; the aggregate `PreCognitiveAssessment` remains an application-owned restart checkpoint.

The workpiece can terminalize into response, abstention, action completion/failure, waiting, or deferral. A final natural-language worker is optional at the architecture level.

See [`INTERACTION_WORKPIECE_2026-08-28.md`](INTERACTION_WORKPIECE_2026-08-28.md).

## Responder-handoff oracle rebaseline

The native continuity suite was then changed so ordinary conversational scenarios no longer pass or fail on one canned final sentence. Instead, each supported scenario reconstructs the policy-admitted handoff to the completely fresh final response worker from the terminal workpiece and machine-checks the required canonical source events and answer components. The generated response remains visible during native pytest for human inspection.

This rebaseline was intended to localize failures cleanly among retrieval, control/source authority, and response realization rather than conflating all three behind exact string equality.

The first native run after that change again reached 4/5, and the new oracle worked as intended.

The four passing scenarios were:

- randomized Project Oriole recall;
- randomized Project Falcon launch-code recall;
- cross-process memory analysis;
- cross-conversation cross-process recall.

The conversational Kestrel scenario failed at its second active turn. The current percept asked for two historical facts: the profile attached to the Kestrel deployment rule and the technical limitation behind it. The final policy-admitted memory contained the exact canonical historical user event:

```text
For Project Kestrel, never use Docker; deploy PostgreSQL directly on Windows because virtualization is disabled. I track that constraint under profile VX-81A9BFA8.
```

The admitted packet therefore directly contained both requested answer components:

- the randomized profile token;
- `virtualization is disabled`.

Response policy was also correct for the task: `USER_AUTHORED` + `NATURAL_LANGUAGE`. No capability result was needed. Nevertheless, the persisted final directive was `ABSTAIN`, producing `Persisted evidence is insufficient.`

This localized the failure much more tightly than the earlier tests could:

> Retrieval, canonical provenance, source-policy admission, and final evidence composition all succeeded. The remaining defect was a false-negative semantic judgment inside evidence sufficiency/control.

The historical seed interaction's own user-facing response had also abstained, but that did not imply data loss. The canonical historical `USER_PROMPT` was persisted independently, Turn 1 successfully recalled it, and Turn 2's final responder view again contained that same source event.

## Bounded negative sufficiency confirmation

The measured Kestrel false negative justifies a narrow reliability mechanism inside the existing `evidence_sufficiency_verifier` station.

The adopted rule is asymmetric:

1. a first `SUFFICIENT` remains the final station result and preserves the one-call fast path;
2. a first `INSUFFICIENT` over non-empty activated or capability evidence receives one fresh stateless confirmation pass inside the same station;
3. the confirmation re-evaluates from scratch and is explicitly reminded that a historical source statement itself can support the current question even when it is not already phrased as an answer;
4. if confirmation recovers to `SUFFICIENT`, the capability selector does not run;
5. only confirmed insufficiency may proceed to capability selection;
6. empty-evidence insufficiency does not automatically receive another model vote merely because negative decisions are inconvenient.

This deliberately does **not** implement `supported=true -> RESPOND`, does not parse Kestrel-specific wording deterministically, does not add a third semantic station, and does not swap Qwen3:4b for a stronger model.

The confirmation is an implementation detail of the same bounded evidence-sufficiency station and contributes only one final `EvidenceSufficiencyStationComponent` to the workpiece. Moving confirmation before capability selection is important: if a second read recovers to `SUFFICIENT`, the workpiece must not claim a selector ran when it did, nor omit a selector component after actually invoking one.

This is the practical meaning of the assembly-line rule in this case: a station may use a bounded internal retry when measured unreliability in its own one job warrants it, but that does not justify a new checker station or an unbounded voting chain.

## Worker/profile boundary

Current LLM profiles share `ollama-primary`, allowing Qwen3:4b weights to remain resident while every call still receives a newly constructed stateless context.

Persona remains forbidden for semantic/control/capability workers and required only for the optional natural-language final response worker.

Capabilities remain distinct from workers: capability IDs are public semantic operations; private worker profiles implement bounded roles beneath application-owned execution policy.

## Release policy

Do not merge the transient-worker PR merely because deterministic CI passes.

The final gate remains:

1. final-head deterministic CI and constraint audit;
2. native Windows/PostgreSQL/Ollama Qwen3:4b five-scenario acceptance;
3. review/branch cleanup only after the native gate succeeds.

The next native run must determine whether one fresh confirmation is enough to contain the measured non-empty-evidence false-negative without weakening legitimate unknown-fact abstention. If it is not, the next mechanism must again be justified by the new trace rather than by adding a general classifier, deterministic natural-language patchwork, or arbitrary model swap.
