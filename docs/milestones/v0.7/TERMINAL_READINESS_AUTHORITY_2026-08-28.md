# v0.7 Terminal Readiness Authority — 2026-08-28

**Status:** active release-candidate correction; native Qwen3:4b revalidation required.

## Trigger

The Kestrel continuity scenario again reached 4/5 after the responder-handoff oracle and bounded negative-sufficiency confirmation were added.

Turn 2 asked:

> What profile did I attach to that Kestrel deployment rule, and what technical limitation was behind it?

The terminal responder view contained the exact canonical historical user event with both required answer components:

- the randomized `VX-...` profile token;
- `virtualization is disabled`.

Response policy was `USER_AUTHORED` + `NATURAL_LANGUAGE`, no capability result was required, and the final packet was correctly bound into the terminal workpiece. Nevertheless, the directive remained `ABSTAIN` and the visible response was `Persisted evidence is insufficient.`

## What the failed confirmation experiment established

The preceding patch gave an initial `INSUFFICIENT` result over non-empty evidence one fresh stateless confirmation inside the same `evidence_sufficiency_verifier` station.

That mechanism did not contain the Kestrel false negative. Qwen3:4b repeated the same abstract sufficiency error despite having the answer verbatim in its packet.

The experiment is therefore removed rather than preserved as a permanent retry ritual.

The lesson is architectural:

> Repeating the same semantic job is not the same as separating two genuinely different authority questions.

## Root architectural defect

`_terminal_assessment()` treated acquisition-time `PreCognitiveAssessment(disposition=ABSTAIN)` as already terminal. That bypassed the separate `final_readiness` station entirely.

This collapsed two distinct questions:

1. **Acquisition question:** Does the currently activated evidence appear sufficient, or is there useful legal capability work worth attempting?
2. **Terminal question:** Now that acquisition has ended, does the exact final evidence support a user-facing answer, or must the interaction abstain?

A false negative in question 1 was therefore able to acquire terminal authority over question 2.

## Adopted correction

The production boundary is now:

```text
pre-cognitive SUFFICIENT
    -> RESPOND fast path

pre-cognitive INSUFFICIENT
    -> capability_selector when legal work exists
    -> bounded capability work when selected
    -> otherwise acquisition ABSTAIN / no useful work selected

any acquisition path that did not already establish RESPOND
    -> fresh final_readiness over exact final evidence/capability results
    -> terminal RESPOND or ABSTAIN
```

Consequences:

- pre-cognitive `ABSTAIN` no longer means terminal user-facing abstention;
- it means acquisition found no useful additional work to perform;
- a fresh terminal-readiness judgment is mandatory before the interactive path may persist `FinalResponseDirective(action=ABSTAIN)`;
- pre-cognitive `RESPOND` remains the one-call semantic fast path and does not pay a redundant readiness call;
- the same-station negative confirmation has been removed;
- no `supported=true -> RESPOND` deterministic rewrite has been introduced;
- no Kestrel-specific natural-language parser has been introduced;
- Qwen3:4b remains fixed.

## Why this better fits the workpiece architecture

The correction follows the existing rule:

> **one bounded job per station + no unnecessary station**

`evidence_sufficiency_verifier` now has acquisition authority only. `final_readiness` owns terminal readiness only. Those are distinct jobs with distinct downstream consumers and lifecycle positions.

The final-readiness event is persisted against the exact final memory request and capability-result set before the terminal response directive is constructed, preserving restart safety and causal provenance.

## Native schema-authority failure after the boundary correction

The first native run after this authority correction produced a new and narrower failure. In both a Project Falcon seed interaction and Kestrel Turn 2, the final-readiness worker returned the substantive terminal action `RESPOND`, but also emitted an invented decision `version` such as `1.0` or `1.0.0`. The closed validator correctly rejected those invented values and the worker process failed before terminalization.

This is not evidence that terminal readiness chose the wrong semantic outcome. It exposed an information-authority mistake in the structured contract: application protocol versioning had been placed inside the model-facing `FinalReadinessDecision` JSON Schema even though the outer persisted final-readiness event already owns and validates `FINAL_READINESS_VERSION`.

The correction is therefore deterministic:

- `FinalReadinessDecision.version` remains part of the validated application object for restart/backward compatibility;
- the field is omitted from the model-facing JSON Schema;
- the application supplies the authoritative default version after model output is parsed;
- the persisted outer event continues to store and validate the protocol version;
- an explicitly wrong version in persisted/application data still fails closed.

The model now owns only the semantic fields it can legitimately judge:

```text
action: RESPOND | ABSTAIN
evidence_state: <closed terminal evidence state>
```

This follows the same constitutional principle used elsewhere in Prometheist: models may perform bounded semantic judgment, but application metadata and protocol identity remain application-owned.

## False-positive obligation

The correction must not turn non-empty relevant memory into automatic response authority.

The Kestrel native item therefore retains an embedded unsupported negative control after relevant Kestrel history is already active. The prompt asks for an office room number that was never supplied. The final packet must remain non-empty, but terminal readiness/directive must still produce `ABSTAIN`.

The release candidate is accepted only if both directions hold:

- supported Kestrel recall can recover from acquisition false-negative at terminal readiness;
- unsupported Kestrel recall remains terminally unsupported despite non-empty related evidence.

## Deterministic coverage

Deterministic tests require:

- acquisition `RESPOND` bypasses final readiness and retains the fast path;
- acquisition `ABSTAIN` always invokes fresh terminal readiness;
- final readiness may recover an acquisition false-negative to terminal `RESPOND`;
- final readiness may confirm terminal `ABSTAIN`;
- pre-cognitive insufficiency proceeds directly to capability selection without a same-station confirmation vote;
- the model-facing final-readiness schema excludes application-owned version metadata;
- the runtime actually passes only semantic readiness fields to the structured model call;
- omitted model version is supplied deterministically by the application;
- explicitly wrong persisted/application final-readiness version still fails closed.

The schema-authority correction passed deterministic CI with:

- **345 passed, 20 skipped**;
- Ruff green;
- constraint audit **175 discovered / 175 registered / 0 uncovered / 0 stale / 0 mismatched / 0 invalid**;
- exactly five native Ollama acceptance pytest items collected.

Documentation-only follow-up commits must also remain CI-green before the next native release-gate run.

## Release gate

The final release gate remains the existing five native pytest items under Windows/PostgreSQL/Ollama with Qwen3:4b fixed.

A deterministic CI pass is necessary but not sufficient. The next native run must verify the corrected authority boundary and the corrected model/application schema boundary on the actual local model.
