# v0.7 — Closure Candidate

**Milestone:** durable JIT Attention Fabric, minimal WorkingState, and authoritative
v2 percept-to-response pipeline

**Status:** implementation consolidated; the 2026-09-03 native run failed 6 of 14
model-backed tests. Evidence-bound remediation has passed hosted PostgreSQL CI but
remains blocked on native acceptance for one exact replacement SHA.

**Rebaselined:** 2026-09-03

## Question

Can Prometheist deterministically allocate durable work across bounded concurrent
resources, survive destruction of every worker, preserve bounded current activation,
surface relevant persistent memory before fresh model reasoning, and complete user
interaction without a privileged persistent agent or inherited LLM transcript?

## Accepted architecture

v0.7 has one live interaction path:

```text
explicit user prompt
  -> deterministic response requirement + persistence
  -> bounded WorkingState and attention aperture
  -> fresh pre-cognitive selection of non-memory work only
  -> deterministic dependency/resource execution
  -> fresh v2 Composer judges memory sufficiency only
       -> Adaptive Recall + fresh Composer, boundedly, when deficient
  -> current-only response policy selects admissible historical source roles
  -> application filters memory; evidence is quarantined before current authority
  -> exact-source extraction or personality-conditioned final response
  -> response event + final artifact disposition
```

The following designs are explicitly superseded and are not v0.7 architecture:

- a persistent Primary Agent or specialist hierarchy;
- a parallel `interaction_runtime`/`interaction_worker` execution path;
- a recurrent general router choosing response versus capability use;
- separate model-selectable deeper-research, cross-reference, or focused-recall
  memory capabilities;
- phrase-specific application policy for deciding whether prior context matters.

Adaptive Recall retains progressively broader/deeper deterministic retrieval profiles
under the neutral internal stage names `BROAD`, `ASSOCIATIVE`, `RELATIONAL`, and
`FOCUSED`. Those stages are not capabilities.

## Implemented mechanisms

### Attention and safe execution

- structured priority, deadlines, dependencies, service guarantees, and stable total
  ordering;
- explicit CPU, RAM, and local-LLM resources with configured/observed capacity and
  protected headroom;
- deterministic admission, reservations, epoch-wide atomic assignments, and
  contention-only preemption;
- `PREEMPTIBLE`, `CHECKPOINT_ONLY`, and `ATOMIC` interruption semantics;
- guarded claim-time re-observation, durable leases, checkpoints, recovery, and
  idempotent terminal/effect handling;
- default one-local-LLM slot until native evidence supports another value.

### Continuity and memory

- append-only canonical event history and independent immutable artifact chains;
- bounded canonical-reference `InteractionWorkingState`;
- current prompt/new recall precedence when WorkingState is saturated;
- automatic bounded memory orientation before model work selection;
- deterministic Adaptive Recall and Composer exhaustion/unknown behavior;
- initial aperture evidence retained ahead of later Adaptive Recall expansions;
- deep-history anchor reservation under recent same-topic crowding;
- incremental association projection updates from durable high-water marks;
- per-item and aggregate model-evidence byte validation without truncating canonical
  evidence.

### Response and evidence authority

- explicit user prompts deterministically require response;
- non-user percepts may have deterministic no-response intake policies;
- work/tool results bypass memory composition and retain direct authority/provenance;
- a fresh policy worker sees only the current prompt and selects the narrow historical
  source role and response surface contract;
- application code physically removes inadmissible event roles before synthesis;
- historical memory and work results travel in a quarantined evidence channel before
  the later current user instruction, including escaped Qwen control sequences;
- exact output uses model-selected, application-validated source substrings and
  application-owned composition rather than free-form regeneration;
- natural responses still receive the mandatory core plus optional additive
  personality prompt;
- exact stateless invocation inputs, separate evidence/current channels, settings,
  and results are durably inspectable.

## Selective hardening incorporated during closure

The closure candidate ports current-architecture invariants from the v0.7 red-team
branch without reviving its obsolete recurrent runtime. After the first consolidated
native run demonstrated that prompt-only authority guidance was insufficient, the
source-admissibility and evidence-isolation mechanism was also ported into v2:

- memory prompt-injection and evidence-authority native scenarios;
- assistant-only historical-claim isolation;
- saturated WorkingState admission of newly relevant evidence;
- deep temporal history under candidate-window crowding;
- bounded model evidence by bytes as well as item count;
- incremental projection freshness without lifetime-ledger scans;
- response-event persistence failure releasing the claim without publishing false
  completion.

The Adaptive Memory Attention experiment branch contributes its decision record and
benchmark evidence only. Its production implementation is not merged because the
accepted result is already represented by the v2 Composer plus Adaptive Recall.

See [`../../audits/V07_BRANCH_SALVAGE_2026-09-03.md`](../../audits/V07_BRANCH_SALVAGE_2026-09-03.md)
and [`../../experiments/README.md`](../../experiments/README.md).

## Runtime artifact policy

The independent artifact journal remains constitutionally required and defaults to
`.prometheist/artifacts` locally. Runtime output is now fully ignored by Git. Evidence
intended for review must be deliberately copied, sanitized where appropriate, and
stored under `docs/audits/evidence/` or `benchmarks/results/` with provenance and a
tested revision. Normal chat/test runs must not dirty the repository or publish user
content accidentally.

## Deterministic closure evidence

The candidate must pass:

```powershell
uv sync --frozen
uv run ruff check .
uv run python scripts/audit_constraints.py --fail-unregistered
uv run python benchmarks/run_deterministic_constraints.py
uv run pytest -q
```

GitHub Actions supplies disposable PostgreSQL and runs the complete suite. Local
collection without PostgreSQL is useful for import/schema coverage but is not a full
test pass.

The constraint registry is fail-fast: changed values, uncovered production numbers,
stale entries, missing benchmark links, or missing required evidence fail the audit.
Current native-sensitive families include the v2 response pipeline, host resource
policy, worker behavior, and local-model behavior.

## Native closure gate

From a clean named branch at the exact candidate SHA on the intended Windows host:

```powershell
git switch closure/v0.7-v2-consolidation
git pull --ff-only
.\scripts\run_v07_acceptance.ps1 -ExpectedCommit <candidate-sha>
.\scripts\run_native_constraint_calibration.ps1
```

The acceptance script itself verifies and prints the branch, full SHA, and clean-tree
state. A mismatch fails before dependency setup or tests begin.

Required conditions:

1. PostgreSQL uses a disposable test database;
2. the configured Ollama model is installed and reachable;
3. `REQUIRE_V07_LOCAL_ACCEPTANCE=1` and `REQUIRE_OLLAMA_ACCEPTANCE=1` make missing
   dependencies/skips fatal;
4. all non-Ollama tests pass;
5. every `ollama`-marked acceptance and red-team test actually runs and passes;
6. restart, cross-process, cross-conversation, artifact-path, memory-authority, and
   prompt-injection cases pass;
7. the native constraint result records the same commit, model/runtime, and host
   context needed to interpret the result.

No Linux CI simulation or collected-but-skipped test substitutes for this gate.

## Closure record

This section is deliberately incomplete until the hard gates pass.

- preceding code candidate SHA: `10c2c942395267f95888f8922dc75cd843c934b7`
- preceding hosted CI run: **#714 passed; not evidence for the remediation**
- failed native run: **2026-09-03; 8 passed / 6 failed / zero skipped among 14 selected**
- failed native revision identity: **not established by the old script**
- remediation code commit SHA: `f1756cc9d694198dad4952a7f2529794d3a4fceb`
- remediation hosted CI run: **#716 passed; 280 passed / 14 native-only skipped**
- exact native candidate SHA: **current PR #24 head, recorded in its conversation**
- replacement native acceptance result: **pending**
- final constitutional/codebase audit: **pending**
- merge SHA: **pending**
- new closure tag: **pending; existing `v0.7` remains immutable**
- v0.8 branch: **blocked until all preceding fields are complete**

The milestone must not be described as closed while any field above remains pending.

## Historical records

The other files in this directory are dated implementation/decision records. Several
describe intermediate architectures that were valid at their recorded commit but are
now superseded. Their historical claims remain useful evidence; the Constitution,
current architecture documents, and this rebaseline govern the live system.

## Closure invariant

> Kill every model and worker, restart from durable state, and the same bounded,
> provenance-bearing interaction can continue safely—without a hidden transcript,
> parallel runtime, model-owned control plane, or unsafe resource guess.
