# Testing and Acceptance

**Status:** constitutional engineering deep dive.  
**Constitutional authority:** implements Article 25 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md).

Prometheist is defined by behavioral invariants, not documentation claims. A mechanism is not accepted merely because code looks plausible, unit tests pass, or one local-model run happens to succeed.

## Core rule

> **Deterministic regression evidence and representative native acceptance are complementary. Use each only for claims it can actually establish.**

CI is the repeatable gate for deterministic behavior. Native/deployment-machine testing is required when the claim depends materially on real local models, operating-system processes, databases, resource pressure, or host-specific behavior.

Neither substitutes for the other.

## Testing layers

### Unit and contract tests

Verify small deterministic functions and closed interfaces:

- schemas/validation;
- deterministic identities/order/state transitions;
- scoring/admission formulas;
- capability contracts;
- worker packet projections;
- station output schemas;
- typed workpiece component/terminal invariants;
- exact-output/current-authority validation;
- resource-policy calculations;
- retry/idempotency rules.

### Component integration tests

Verify behavior across real persistence/control boundaries where practical:

- event storage/retrieval;
- memory projection/canonical dereference;
- scheduler epochs/reservations;
- worker claims/checkpoints/results;
- WorkingState;
- capability registry/runtime;
- workpiece carry-forward/materialized snapshot persistence;
- complete workpiece payload plus bounded semantic snapshot projection;
- transaction rollback/restart reconstruction.

### End-to-end acceptance tests

Verify user/system-level architectural claims:

- cross-turn/session/process continuity;
- stateless model calls;
- automatic memory activation before semantic judgment;
- bounded worker information apertures;
- exact provenance;
- demand-driven station invocation;
- capability acquisition/reassessment without hidden recurrent context;
- policy-admitted final-responder evidence contains the facts/provenance required by the current task;
- conversational prompts remain natural unless exact formatting is itself the behavior under test;
- optional response behavior and terminal outcomes;
- process destruction/recovery;
- resource admission/safe execution.

### Benchmarks and calibration

Measure quality/cost/safety tradeoffs and justify empirical constraints under [`EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](EMPIRICAL_CONSTRAINT_GOVERNANCE.md).

## Deterministic CI responsibilities

CI should establish behavior reconstructable from controlled inputs, including:

- deterministic IDs/total ordering;
- dependency gating and capability execution order;
- synthetic resource admission/preemption;
- atomic persistence/rollback;
- restart/replay equivalence;
- idempotency/retry semantics;
- bounded packet/workpiece-projection contracts;
- source provenance;
- unknown-fact abstention on frozen fixtures;
- no hidden transcript fields in worker contracts;
- pre-cognitive station authority separation;
- workpiece chronology and terminalization;
- action-like terminal outcomes that require no user-output component;
- terminal snapshot persistence without replacing append-only causal history;
- full canonical workpiece payload with bounded semantic projection so nested workpiece contents do not recursively become ordinary recall evidence;
- enumerated exact-output contracts that require an admitted source substring to equal one complete current-authority allowed literal;
- static constraint audits and other repository governance checks.

## Native acceptance responsibilities

Native testing is required when behavior depends materially on:

- actual CPU/RAM pressure;
- local-model cold/warm inference;
- model structured-output behavior;
- real OS process creation/destruction;
- PostgreSQL behavior in the intended local deployment;
- filesystem/network timing relevant to safety/recovery;
- lease expiry/recovery under the real OS;
- environment-calibrated resource thresholds;
- model schema compliance, latency, token budgets, and retries.

A passing native run is evidence about the tested environment; it does not prove universal behavior on every host.

## Statelessness acceptance

Because every LLM invocation is constitutionally stateless, tests must prove absence of hidden continuity rather than merely observe correct answers.

Useful patterns:

- fresh processes between turns/stages;
- separate LLM calls with no inherited messages/KV/chat context;
- cross-process recall after destroying the previous worker;
- cross-session/conversation recall without transcript injection;
- restart from PostgreSQL/application state only;
- opaque tokens/facts that cannot be guessed from model priors;
- exact source-event provenance assertions.

A helper that secretly carries previous messages invalidates the statelessness claim.

## Workpiece/station acceptance

The typed workpiece architecture creates specific obligations.

Tests should establish that:

1. every workpiece has one originating percept;
2. a station contributes only its registered closed component type;
3. components for stations that never ran are absent;
4. workers receive registered minimum projections rather than the master workpiece by default;
5. deterministic application code—not workers—attaches components and chooses next-station eligibility;
6. capability tranches retain causal chronology around fresh semantic reassessment;
7. no component may attach after terminalization;
8. `RESPONSE_EMITTED` requires user output;
9. action/failure/wait/defer terminal paths may omit user output;
10. terminal workpiece JSON round-trips with type identity intact;
11. the terminal snapshot complements rather than replaces append-only recovery/provenance records;
12. the complete snapshot remains available for audit while its semantic projection stays bounded and does not duplicate nested evidence into later ordinary recall.

The architecture is not validated if tests cover only the current chat-like terminal path.

## Demand-driven semantic station acceptance

The current v0.7 pre-acquisition path must verify authority separation between acquisition and terminalization:

- `evidence_sufficiency_verifier` returns only `SUFFICIENT | INSUFFICIENT`;
- that worker cannot see/select a capability catalog;
- a `SUFFICIENT` result remains the one-call acquisition fast path;
- `INSUFFICIENT` proceeds directly to `capability_selector` when a legal catalog exists;
- no same-station confirmation/re-vote is inserted merely because the first semantic result was inconvenient;
- capability selection cannot reassess sufficiency;
- deterministic application code derives aggregate acquisition disposition/evidence state from the station outputs;
- malformed/unknown/extra model-control fields fail closed;
- no extra station exists merely to populate compatibility metadata with no downstream consumer.

The critical lifecycle rule is separate:

- pre-cognitive `ABSTAIN` means no useful additional acquisition work was selected;
- it is not terminal response authority;
- any interactive path that has not already established `RESPOND` must receive one fresh `final_readiness` judgment over the final evidence/capability results before terminal `ABSTAIN` is authorized;
- final readiness cannot request additional capabilities, alter source policy, or draft the answer;
- its persisted result must bind to the exact final evidence packet/capability result set used for finalization.

This rule exists because native Qwen3:4b acceptance repeatedly demonstrated a false-negative acquisition judgment even when the final packet directly contained every requested historical answer component. Repeating the same acquisition classifier inside the same station did not contain the failure. The correct boundary is to distinguish **whether more acquisition work should be attempted** from **whether the final evidence now supports an answer**.

The application still must not rewrite `INSUFFICIENT` to `SUFFICIENT` merely because a packet is non-empty or marked supported. The separate terminal judgment preserves that epistemic boundary without allowing one acquisition false negative to become terminal authority.

The lifecycle separation also creates a native false-positive obligation: after relevant history is already active, an unsupported question with a non-empty final evidence packet must still terminalize as `ABSTAIN`. The fix is not accepted if it merely trades false negatives for fabricated support.

Native tests then verify whether Qwen3:4b can perform these distinct narrow semantic roles reliably enough in the intended environment.

## Final-response native acceptance boundary

For continuity/retrieval acceptance, the machine-verifiable oracle belongs at the **handoff into the final response worker**, not at one arbitrarily canned rendering of the user's answer.

The terminal `InteractionWorkpiece` already preserves the information needed to reconstruct that handoff: the current percept, `FINAL_EVIDENCE`, capability tranches, `FINAL_RESPONSE_DIRECTIVE`, and visible `USER_OUTPUT`. Native acceptance may therefore rebuild the same policy-admitted evidence projection used by production response realization and assert that:

- the directive authorizes `RESPOND` when the scenario expects a supported answer;
- the directive references the exact final evidence packet that reached response realization;
- required canonical source-event IDs survive source-policy filtering;
- required opaque values/facts are present in admitted evidence or admitted capability results;
- conversational prompts that do not request an exact format retain `NATURAL_LANGUAGE` surface authority when that is part of the scenario;
- an unsupported negative-control prompt still receives `ABSTAIN` even when relevant-but-insufficient memory keeps the final packet non-empty;
- the generated response is printed in full for human inspection.

The native continuity gate should **not** normally assert exact equality against user-facing prose. A correct answer may be phrased in multiple natural ways. Requiring a pipe-delimited or otherwise canned sentence merely because it is easy for pytest to compare trains the acceptance suite toward machine-shaped interaction rather than the system Prometheist is intended to become.

This intentionally separates two claims:

1. **architectural continuity claim** — did a fresh stateless responder receive the correct authorized evidence after the relevant process/session/history boundaries? This is machine-gated.
2. **response-realization quality claim** — did the local model express that evidence coherently, faithfully, and naturally? The actual output remains visible and may be evaluated by dedicated response-quality benchmarks, human review, or later semantic/contradiction evaluation rather than being silently conflated with memory continuity.

A visibly incorrect answer after a passing responder-handoff assertion is valuable diagnostic evidence: it isolates the defect to response realization instead of making retrieval, routing, source authority, and prose generation indistinguishable behind one string-equality failure.

## Exact response-surface acceptance

Exact-output behavior remains an application authority boundary **when exactness is actually part of the task**. It is not the default testing strategy for ordinary human-facing conversation.

When the current percept explicitly enumerates a finite closed set of legal outputs, tests should establish that:

- the response-policy worker sees only current authority when identifying the closed set;
- every `allowed_output_literal` is validated as a verbatim substring of the current percept;
- the closed set is persisted inside response authority before realization;
- an exact-source selector may choose only admitted evidence;
- the selected source bytes must equal one complete allowed literal when such a set exists;
- a larger source sentence that merely contains the correct literal is rejected and may be retried within the existing bounded retry policy;
- no extra semantic worker is introduced merely to enforce a constraint that application validation can enforce directly.

Appropriate exact-output tests include opaque identifiers that must not mutate, machine-to-machine contracts, explicit user requests for exact formatting, deterministic fallback literals, and the exact-source machinery itself. These tests should not force unrelated conversational acceptance scenarios into robotic output formats.

## Restart and destruction are first-class conditions

Persistent architecture must assume processes die.

Tests should destroy/restart between meaningful boundaries and prove that:

- committed control is reused rather than rerolled;
- capability/effect identities remain deterministic;
- partial process failure does not mutate canonical history;
- leases/claims recover correctly;
- terminal workpiece snapshot can be reconstructed from persisted stage outputs when necessary;
- no response/action effect is duplicated after restart.

Cheap micro-station outputs need not each be independently durable if no effect/authority boundary has been crossed; rerunning fresh stateless calls is acceptable there. Once a decision authorizes material downstream effects, its durable checkpoint is mandatory.

## Epistemic acceptance

Retrieval success is not enough. Tests must distinguish:

- relevant activation versus evidence sufficiency;
- user statement/belief versus world fact;
- historical versus current state;
- correction/supersession;
- unsupported unknowns;
- internal memory versus external/tool evidence.

Unknowns may remain unknown. A test is not improved by rewarding a fabricated confident answer.

## Resource-safety acceptance

Deterministic tests should exhaustively exercise resource math/ordering with controlled snapshots. Native tests should then verify behavior under the actual host's CPU/RAM/Ollama/PostgreSQL/process conditions.

Transient resource pressure may delay/re-observe. Tests must not lower configured headroom/thresholds merely to force progress.

## Failure diagnostics

Acceptance failures should emit the **smallest causal slice that explains the failed contract**, not serialize the entire canonical ledger or workpiece by default.

A useful native continuity failure record normally contains:

- the failing conversation/correlation identity;
- the current prompt and visible output;
- canonical source events the responder-handoff assertion expected to be available;
- the policy-admitted final MemoryPacket candidates with source ID/type, score, and bounded content;
- admitted capability results when relevant;
- the terminal response directive relevant to the turn.

The complete append-only history and terminal workpiece remain persisted in PostgreSQL for deeper forensic inspection. Compact diagnostics are an index into that canonical evidence, not a replacement for it.

This distinction matters operationally: dumping a complete workpiece that itself contains MemoryPackets and prior workpiece data can obscure the actual defect, create enormous failure reports, and make derived state look more authoritative than the source event that caused the failure.

## Current v0.7 native release gate

The official native gate remains:

```powershell
.\scripts\run_v07_acceptance.ps1
```

The script validates Ollama/model availability, requires explicit acceptance opt-in and a disposable PostgreSQL test database, runs focused deterministic acceptance, runs the full deterministic non-Ollama suite, and then runs the five marked native Ollama scenarios.

The five current native test items cover:

- randomized Project Oriole opaque recall;
- randomized Project Falcon opaque recall;
- cross-process memory analysis without hidden transcript;
- cross-conversation/cross-process memory recall;
- one Kestrel scenario containing four supported conversational continuity turns plus an unsupported Kestrel-attribute negative control after relevant history is active. The negative control must `ABSTAIN` while retaining a non-empty final evidence packet.

For the supported continuity turns, automated pass/fail is based on the final responder's policy-admitted evidence/authority rather than canned final prose. Every actual Prometheist response is printed during the native run for human inspection. The embedded unsupported control is machine-gated on terminal abstention because abstention itself is the behavior under test.

Qwen3:4b remains fixed for this v0.7 gate. Swapping to a stronger model is a different experiment and cannot be used to hide an architectural regression.

## Release discipline

A milestone may be marked accepted only when its declared gates pass on the exact release-candidate code/docs state.

For v0.7 that means:

1. static checks and constraint audit green;
2. deterministic PostgreSQL suite green;
3. native five-test-item Qwen3:4b responder-handoff gate green, including the non-empty-evidence unsupported negative control and visible inspection of generated responses;
4. PR/review/branch/release bookkeeping performed only afterward.

A partial pass is diagnostic evidence, not release acceptance.