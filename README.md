# Prometheist

**Persistent identity and attention for stateless intelligence.**

Prometheist is an experimental, local-first cognitive architecture built around one
constraint: every LLM invocation is stateless. Models and worker processes are
disposable compute; memory, identity, attention, working state, interaction
continuity, policy, and durable authority belong to Prometheist itself.

> Continuity belongs to the system, not to a model context window, chat session,
> named agent, or worker process.

## Status

- **v0.5** is the accepted deterministic Memory Kernel baseline.
- **v0.6** is the accepted historical stateless-worker/JIT-Memory baseline. Its
  Primary Agent/specialist hierarchy is no longer current architecture.
- **v0.7** is an open closure candidate. The exact-SHA remediation run on
  2026-09-03 passed 11 of 14 native tests and showed that the remaining response
  tests still used a superseded exact-prose oracle. The corrected gate now proves
  evidence delivery from invocation artifacts and leaves natural response quality
  to explicit human review.
- **v0.8** is the active predictive-situation development branch,
  `copilot/implement-v08-milestone`. It incorporates the v0.7 closure implementation,
  including guarded specialist roles, evidence scoping, and artifact-first acceptance.
  Integration does not declare v0.7 closed or the salience heuristics calibrated.

The existing `v0.7` Git tag is historical and must not be moved. A distinct closure
tag will identify the later, fully accepted v0.7 baseline.

The integration is reviewed in draft [PR #25](https://github.com/wtvr-guy/prometheist/pull/25).
The [integration record](docs/audits/V08_CLOSURE_INTEGRATION_2026-09-12.md)
records both parent revisions, conflict resolutions, validation, research context,
and the remaining specification gap. Historical closure work remains recorded in
[PR #24](https://github.com/wtvr-guy/prometheist/pull/24) and
[PR #23](https://github.com/wtvr-guy/prometheist/pull/23).

## Authoritative user-prompt pipeline

Explicit user prompts deterministically require a response. The pre-cognitive LLM
selects only non-memory work. Persistent-memory sufficiency belongs solely to the
v2 Composer, and deterministic Adaptive Recall performs bounded expansion when the
Composer identifies a deficit. Completed work/tool results bypass the Composer and
reach the final responder directly.

1. Persist the user prompt, normalize its percept, and derive advisory salience.
2. Resolve bounded WorkingState availability in ordinary software.
3. Run a fresh evidence-policy specialist on the current prompt only; persist its
   historical source scope and response surface.
4. Open the bounded memory aperture within that scope, then select non-memory work
   with a fresh work-triage specialist when the executable catalog is nonempty.
5. Execute the application-owned capability plan through durable workers.
6. Run the memory-only Composer; expand through bounded deterministic Adaptive
   Recall and fresh Composer reassessment when necessary.
7. Pass admitted memory and authoritative work results directly to a fresh final
   responder, with exact-source validation where required.
8. Persist the response and immutable final-disposition manifest.

Other percept classes may deterministically require no user-facing response. No LLM
decides whether an explicit user prompt deserves one.

The superseded recurrent `RESPOND`/`USE_CAPABILITIES` interaction runtime and the
separate named memory capabilities are not part of the live system. Adaptive Recall
uses architecture-neutral `BROAD`, `ASSOCIATIVE`, `RELATIONAL`, and `FOCUSED`
retrieval stages internally; those stages are not exposed capabilities.

## Implemented foundations

- append-only PostgreSQL event history with deterministic global ordering;
- immutable, hash-linked filesystem artifacts independent of PostgreSQL;
- bounded provenance-bearing JIT Memory and support-aware evidence admission;
- incremental derived-memory projection freshness with rebuild support;
- bounded active WorkingState containing canonical event references;
- deterministic task priority, resource admission, reservations, epochs, and
  contention-driven preemption;
- guarded disposable-worker claims, leases, checkpoints, recovery, and idempotent
  terminal results;
- a single authoritative percept-to-response runtime;
- five normalized percept kinds, three modalities, bounded intake segments, and
  advisory salience persisted with the user interaction and artifact journal;
- a durable current-only evidence-policy specialist followed by one-pass
  pre-cognitive external-work triage with application-owned capability IDs and
  dependency ordering;
- bounded Adaptive Recall and a memory-only Composer;
- single-decision response policy, application-enforced historical source filtering,
  quarantined evidence transport, exact-source output, additive personality, and
  exact invocation provenance;
- per-item and aggregate byte limits before evidence reaches a model;
- deterministic, restart, scale, failure-injection, and adversarial regression tests.

Canonical evidence is never replaced by a projection or summary. Associations,
indexes, WorkingState activation, and response packages are derived or bounded views,
not substitute memories and not automatic truth claims.

## Core invariants

1. LLM invocations inherit no hidden transcript.
2. Conversations, sessions, devices, and interfaces are provenance, not default
   cognitive boundaries.
3. Basic persistent-memory activation occurs before model work selection.
4. Each guarded LLM worker owns one coherent semantic responsibility.
5. Models select bounded semantic requirements; ordinary software owns identity,
   ordering, dependencies, resources, permissions, retries, and durable effects.
6. Attention priority and safe resource admission are separate decisions.
7. Work results and memory evidence retain distinct authority and provenance.
8. Invalid control output, missing evidence, stale resources, and ambiguous effects
   fail closed.
9. Ordinary model inputs and inference counts remain bounded as history grows.
10. Runtime artifacts stay local and ignored; selected audit/benchmark evidence is
   preserved explicitly under `docs/` or `benchmarks/results/`.
11. A mechanism enters the roadmap only through a frozen, falsifiable experiment.

The complete normative rules live in [`CONSTITUTION.md`](CONSTITUTION.md).

## Quick start

Requirements: Python 3.12+, `uv`, PostgreSQL, and Ollama for model-backed paths.

```powershell
git clone https://github.com/wtvr-guy/prometheist.git
cd prometheist
git switch copilot/implement-v08-milestone
uv sync --frozen
$env:DATABASE_URL = "postgresql://USER:PASSWORD@localhost:5432/jit_agent"
psql $env:DATABASE_URL -f schema.sql
uv run prometheist
```

One non-interactive prompt:

```powershell
uv run prometheist --once "What constraint did I set for Project Kestrel?"
```

Artifact commands do not require PostgreSQL for inspection or verification:

```powershell
uv run prometheist inspect --latest
uv run prometheist verify --latest
```

## Verification

Use a disposable PostgreSQL database whose name contains `test` or `benchmark`:

```powershell
$env:TEST_DATABASE_URL = "postgresql://USER:PASSWORD@localhost:5432/jit_agent_test"
uv sync --frozen
uv run ruff check .
uv run python scripts/audit_constraints.py --fail-unregistered
uv run pytest -q
```

The v0.7 closure gate must run on the intended native Windows host with PostgreSQL
and the configured Ollama model available. Pass the published 40-character
candidate SHA; the script rejects a different SHA, a detached branch, a dirty tree,
or skipped native dependencies:

```powershell
.\scripts\run_v07_acceptance.ps1 -ExpectedCommit <candidate-sha>
```

Deterministic Linux CI is necessary but does not substitute for this native gate.
The script prints every native answer plus its structural artifact receipt, then
ends with `HUMAN REVIEW REQUIRED`; a zero exit proves the structural gate, not the
quality of the prose. Do not declare v0.7 closed without exact revision identity,
retained native evidence, and a recorded human verdict on those responses.

## Documentation

Start with [`docs/README.md`](docs/README.md). The most important current documents
are:

- [`docs/architecture/PERCEPT_TO_RESPONSE_PIPELINE.md`](docs/architecture/PERCEPT_TO_RESPONSE_PIPELINE.md)
- [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)
- [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)
- [`docs/architecture/FINAL_RESPONDER.md`](docs/architecture/FINAL_RESPONDER.md)
- [`docs/milestones/v0.7/README.md`](docs/milestones/v0.7/README.md)
- [`docs/milestones/v0.8/README.md`](docs/milestones/v0.8/README.md)
- [Situation cognition and operator commands](docs/architecture/SITUATION_COGNITION.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)

Prometheist remains a cognitive-architecture research project. Accepted behavior is
the behavior supported by code, tests, frozen experiment records, and the required
native evidence—not by architectural aspiration alone.

### Non-user cognition

Typed observations now form durable situations with explicit expectations and
prediction errors. Source policies, narrow triage, deterministic reflexes, guarded
Attention Fabric tasks, observed action outcomes, and separately scheduled
consolidation support operation beyond chat. Run one bounded scheduler pass with
`uv run python -m jit_agent.percept_cli tick` after configuring sources. See the
[situation guide](docs/architecture/SITUATION_COGNITION.md) for complete commands,
contracts, supported operations, and current limits.
