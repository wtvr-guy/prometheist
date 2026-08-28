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
11. the terminal snapshot complements rather than replaces append-only recovery/provenance records.

The architecture is not validated if tests cover only the current chat-like terminal path.

## Demand-driven semantic station acceptance

The current v0.7 pre-acquisition path must verify authority separation:

- `evidence_sufficiency_verifier` returns only `SUFFICIENT | INSUFFICIENT`;
- that worker cannot see/select a capability catalog;
- `capability_selector` runs only after insufficiency and only with a legal catalog;
- capability selection cannot reassess sufficiency;
- deterministic application code derives aggregate disposition/evidence state;
- the supported fast path uses only the sufficiency station;
- malformed/unknown/extra model-control fields fail closed;
- no extra station exists merely to populate compatibility metadata with no downstream consumer.

Native tests then verify whether Qwen3:4b can perform these narrow semantic roles reliably enough in the intended environment.

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

## Current v0.7 native release gate

The official native gate remains:

```powershell
.\scripts\run_v07_acceptance.ps1
```

The script validates Ollama/model availability, requires explicit acceptance opt-in and a disposable PostgreSQL test database, runs focused deterministic acceptance, runs the full deterministic non-Ollama suite, and then runs the five marked native Ollama scenarios.

The five current native scenarios cover:

- randomized Project Oriole opaque recall;
- randomized Project Falcon opaque recall;
- cross-process memory analysis without hidden transcript;
- cross-conversation/cross-process memory recall;
- four-turn stateless continuity with distractors (including the Kestrel evidence-sufficiency case).

Qwen3:4b remains fixed for this v0.7 gate. Swapping to a stronger model is a different experiment and cannot be used to hide an architectural regression.

## Release discipline

A milestone may be marked accepted only when its declared gates pass on the exact release-candidate code/docs state.

For v0.7 that means:

1. static checks and constraint audit green;
2. deterministic PostgreSQL suite green;
3. native five-scenario Qwen3:4b gate green;
4. PR/review/branch/release bookkeeping performed only afterward.

A partial pass is diagnostic evidence, not release acceptance.
