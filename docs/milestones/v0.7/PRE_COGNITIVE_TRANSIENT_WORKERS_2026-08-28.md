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

Runs only after insufficiency and only when a legal catalog exists. Returns only bounded application-catalog indices.

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

If native evidence still shows the binary sufficiency station cannot correctly identify directly present answer components, the next candidate mechanism should be narrowly justified by that evidence (for example explicit requested-component coverage), not another general classifier or arbitrary model swap.
