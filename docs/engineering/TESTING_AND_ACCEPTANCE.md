# Testing and Acceptance

**Status:** constitutional engineering deep dive.  
**Constitutional authority:** implements Article 25 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md).

Prometheist's architecture is defined by behavioral invariants, not by documentation alone. A rule is not treated as verified merely because the implementation looks plausible or a narrow unit test passes.

## Core rule

> **Deterministic regression evidence and representative native acceptance are complementary. Use each where it can actually establish the claim being made.**

CI is the primary repeatable regression gate for deterministic behavior. Native/deployment-machine testing is required when the claim materially depends on real hardware, local models, operating-system processes, databases, resource pressure, or other environment-specific behavior.

Neither substitutes for the other.

## Testing layers

Prometheist should maintain several layers of evidence rather than one undifferentiated test suite.

### Unit and contract tests

Verify small deterministic functions and closed interfaces:

- schemas and validation;
- deterministic identity/order functions;
- state transitions;
- scoring/admission formulas;
- capability contracts;
- resource-policy calculations;
- retry/idempotency rules.

### Component integration tests

Verify subsystem behavior across actual persistence boundaries where practical:

- event storage/retrieval;
- memory projection and canonical dereference;
- scheduler epochs/reservations;
- worker claims/checkpoints/results;
- interaction WorkingState;
- capability registry/runtime;
- transaction rollback and restart reconstruction.

### End-to-end acceptance tests

Verify the architectural claim a user/system actually depends on:

- cross-turn and cross-session continuity;
- stateless model calls;
- automatic memory activation;
- bounded cognitive context;
- exact provenance;
- one-pass pre-cognitive non-memory work selection and deterministic execution;
- bounded Composer/Adaptive Recall memory reassessment;
- direct work-result handoff and mandatory explicit-user response;
- process destruction/recovery;
- resource admission and safe execution.

### Benchmarks/calibration

Measure quality/cost/safety tradeoffs and justify empirical constraints. These are governed by [`EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](EMPIRICAL_CONSTRAINT_GOVERNANCE.md).

## Deterministic CI responsibilities

CI should establish behavior that can be reproduced from controlled inputs.

Examples include:

- deterministic IDs and total ordering;
- dependency gating and capability execution order;
- synthetic resource admission/preemption;
- atomic persistence and rollback;
- restart/replay equivalence;
- idempotency/retry semantics;
- bounded packet/context contracts;
- source-provenance relationships;
- unknown-fact abstention on frozen fixtures;
- protection against hidden conversation transcripts in contracts;
- static audits for constraints and constitutional/documentation invariants when implemented.

Synthetic snapshots are valuable precisely because they let the suite force edge cases repeatably.

## Native acceptance responsibilities

Some claims cannot be established by CI simulation.

Native testing is required when behavior depends materially on:

- actual CPU/RAM pressure;
- local-model cold/warm startup and inference;
- host-specific process behavior;
- PostgreSQL/local database behavior outside synthetic mocks;
- filesystem/network timing where it affects safety/recovery;
- process destruction and lease expiry under the real OS;
- environment-calibrated thresholds;
- model schema compliance, token limits, latency, or retry behavior.

A passing native run is evidence about the tested environment. It does not replace deterministic regression tests or prove universal safety on every host.

### Artifact-first review of model behavior

Natural-language model quality is not reduced to one privileged wording merely to
make native pytest green or red. For response scenarios, the automated native gate
establishes structural facts:

- the expected canonical source events were retrieved;
- the immutable interaction chain is valid and complete;
- the successful `V2_RESPOND` invocation artifact links the exact canonical event
  references actually admitted to that model call;
- inadmissible source references are absent where source policy can decide that
  mechanically;
- transport, schema, bounds, retries, and non-empty response requirements hold.

The native run prints the user prompt, Prometheist response, response-realization
kind, interaction/artifact IDs, and admitted evidence references. A human reviewer
then judges whether the response is accurate, relevant, and appropriately expressed.
Both parts are required: artifact receipt without a good answer is not a semantic
pass, and a good-looking answer without the required evidence lineage is not a
continuity pass.

Exact textual assertions remain appropriate when exact text is itself the real
product contract, or for a closed control/security property such as a valid enum,
catalog index, forbidden poison token, or canonical identifier. Tests must not add
artificial “return exactly this tuple” instructions solely to manufacture a prose
oracle for an otherwise natural conversation.

## Statelessness acceptance

Because “every LLM invocation is stateless” is constitutional, acceptance must prove the absence of hidden continuity—not merely show that answers happen to be correct.

Tests should be designed so that required information exists only in canonical durable state and must be reconstructed through the supported system boundary.

Useful patterns include:

- fresh processes between turns/stages;
- separate LLM calls with no inherited messages;
- cross-process recall after terminating the previous worker;
- cross-session/conversation recall without supplying a transcript;
- restart from PostgreSQL/canonical storage only;
- opaque-token cases that cannot be guessed from model priors;
- assertions over exact source-event provenance.

If a test helper secretly carries earlier messages into a later call, the test does not establish Prometheist continuity.

## Restart and destruction are first-class test conditions

A persistent system should assume processes die.

Tests should deliberately destroy:

- workers before completion;
- workers after checkpoints;
- workers around side-effect boundaries;
- scheduler/controller processes;
- percept stage workers between durable v2 stage boundaries;
- model processes where practical.

After restart, the system should reconstruct authority from durable state alone, respecting leases, retries, idempotency, checkpoints, assignments, WorkingState, and terminal results.

A recovery path tested only by graceful shutdown is incomplete.

## Provenance is part of correctness

A correct-looking answer without correct evidence lineage is not a full pass for memory-dependent behavior.

Where a fixture depends on stored history, acceptance should verify:

- the canonical source event(s) actually retrieved;
- the exact ordering/scope applied;
- correction/supersession behavior where relevant;
- no unsupported source was silently promoted;
- evidence references survive process/session boundaries.

For factual memory tests, source-event provenance should be checked independently of model prose whenever possible.

## Boundedness is part of correctness

A feature does not pass merely because it returns the right answer if it violates bounded-context architecture to do so.

Relevant acceptance metrics/assertions include:

- maximum WorkingState size;
- maximum MemoryPacket size;
- maximum UTF-8 bytes per memory/work item and across rendered model evidence;
- maximum total LLM input/context under the tested policy;
- number of model calls;
- candidate/evidence work performed;
- association depth/breadth;
- peak resource use;
- latency under corpus growth.

Scale tests should freeze query families while increasing corpus size so hidden context or inference growth becomes visible.

## Negative and abstention cases

Prometheist must be tested on what it should **not** do.

Suites should include:

- unknown facts;
- insufficient evidence;
- ambiguous references;
- contradictory/superseded history;
- high-overlap distractors;
- invalid model control outputs;
- stale resource observations;
- missing dependencies;
- oversubscription;
- ambiguous external effects after crashes;
- unavailable optional capabilities;
- historical memory content attempting to acquire current instruction authority;
- forged raw-model control sequences attempting to break out of evidence transport;
- assistant-only claims attempting to become user facts;
- exact-source selectors returning altered or non-source values;
- oversized individual evidence records;
- saturated WorkingState and deep-history candidate crowding;
- projection freshness work that accidentally scales with lifetime history.

Fail-closed behavior and correct abstention are positive test outcomes when evidence/authority is insufficient.

## Tests must not encode brittle natural-language policy

Acceptance tests must not become a second application implementation made of keyword lists and English parsers.

Where a deterministic verdict is needed, prefer:

- exact IDs;
- enums;
- numeric tuples;
- canonical evidence references;
- model-invocation artifact links to the canonical evidence actually admitted;
- explicitly requested machine-verifiable values when exactness is the real user
  contract;
- mechanically validated structured output.

Model-facing prose fixtures are still necessary to test natural interaction. The oracle should not depend on hand-maintained phrase matching when a structural assertion is available.

## Frozen regression scenarios

When a real failure exposes an architectural bug, the smallest representative scenario should become a permanent regression fixture before the fix is accepted.

The sequence is:

```text
observe failure
 -> freeze reproducible scenario
 -> verify baseline fails
 -> change one mechanism
 -> rerun same scenario + existing suite
 -> preserve result and negative evidence
```

Do not rewrite the fixture merely to make the new mechanism look successful unless the original oracle itself was demonstrated to be invalid.

## Historical baselines

Accepted milestone results remain evidence even after architecture changes.

A later architecture should preserve or improve the useful behavior established by earlier accepted baselines unless an explicit experiment shows that the prior behavior was invalid or the invariant was intentionally amended.

Historical tests whose assertion depends on a superseded implementation detail may be archived or rewritten around the underlying invariant. The measured historical record should remain visible.

## Resource-sensitive acceptance

Resource safety requires both synthetic and real-host evidence.

CI should be able to prove, from controlled snapshots:

- no reservation exceeds declared safe capacity;
- deterministic victim selection;
- headroom formulas are applied;
- stale/failed observations reject work;
- atomic assignment/reservation publication;
- worker launch is denied before spawn when admission fails.

Native acceptance should measure, on representative deployment-class hardware:

- actual process/model/database peaks;
- cold/warm local-model behavior;
- concurrent workloads;
- host responsiveness;
- pressure-induced denial/recovery;
- forced process failure/restart.

Changing safety thresholds because a native test is inconvenient is not acceptance. The threshold must be recalibrated through the empirical-governance process.

## Model-dependent acceptance

A local/model-backed test should record enough environment identity to interpret the result, such as:

- model/runtime name and version/digest where available;
- prompt/schema revision;
- relevant generation limits/settings;
- host/runtime state required by the benchmark;
- raw result artifact for calibration runs.

A model-dependent pass is not automatically transferable to a different model.

## Release evidence

A release/milestone claim should identify its evidence gate explicitly.

At minimum, where applicable:

1. deterministic test suite passes;
2. static audits pass;
3. migrations/schema bootstrap are verified;
4. frozen end-to-end architectural acceptance passes;
5. required native calibration/acceptance passes on the intended environment;
6. all release-required empirical constraints have result artifacts;
7. known skips/gaps are documented rather than silently counted as passes.

A skipped environment-dependent test is not evidence that the feature works. It is a statement that the test did not run.

For v0.7 closure, deterministic CI and native acceptance must refer to the same
frozen candidate SHA. The Windows gate is
`scripts/run_v07_acceptance.ps1`; it enables both required-acceptance environment
flags, runs the deterministic regression suite, and then executes every
`ollama`-marked test. Invoke it as
`scripts/run_v07_acceptance.ps1 -ExpectedCommit <full-sha>`. Before any tests, the
script rejects a detached branch, dirty tree, or SHA mismatch; it prints the named
branch and full SHA at start and again on PASS. A closure record must state the tested
SHA, host, PostgreSQL version/database purpose, Ollama runtime/model identity,
pass/fail/skip counts, and retained result artifact. Collection alone is not
execution.

## Constitutional audit tests

Future constitutional audits should prefer executable checks when an article can be mechanized.

Examples:

- scan LLM call sites for inherited transcript parameters;
- trace durable authority to PostgreSQL/canonical stores rather than process globals;
- verify canonical memory rows are not replaced by summaries;
- inspect worker launch surfaces for guarded admission;
- verify control-plane model schemas contain no unconstrained generated IDs/order fields;
- inspect resource decisions for persisted snapshots/policy versions;
- check active contexts against configured bounds;
- execute forced-restart acceptance.

Not every constitutional rule can be proved statically, but every rule should have a documented evidence strategy.

See [`CONSTITUTIONAL_GOVERNANCE.md`](CONSTITUTIONAL_GOVERNANCE.md).

## Evidence hierarchy

For a behavioral claim, prefer:

1. reproducible test/benchmark artifact tied to a revision;
2. current implementation and schema inspection;
3. current architecture documentation;
4. historical experiment records;
5. design intent or conversation history.

Intent motivates a test; it does not replace one.

## Invariant

> **Prometheist treats architectural claims as things to falsify under controlled, restart-heavy, provenance-aware tests—not as assumptions that become true because they were written down.**
