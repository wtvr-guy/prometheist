# v0.7 Empirical Constraint Governance — 2026-08-27

## Purpose

Prometheist must not silently accumulate behavioral "magic numbers." Numeric policy choices are now treated as claims that require one of four things: a structural proof, an external-contract rationale, empirical calibration, or an explicit statement that current evidence is insufficient to identify a unique value.

The governing scientific rule is:

> Freeze a baseline, vary one bounded mechanism or interacting parameter family, rerun the same evidence, preserve hard invariants, and accept a new value only when the experiment actually discriminates it. If multiple values remain equivalent, record insufficient discrimination rather than inventing an optimum.

## Enforced inventory

`scripts/audit_constraints.py` scans production/operational Python for behavioral numeric constraints in constants, defaults, schema bounds, call arguments, comparisons, slices, regex quantifiers, scoring coefficients, retry/range bounds, structured-output token caps, and numeric instructions embedded in system prompts.

The current branch has **171 discovered constraints and 171 registered constraints**, with zero uncovered, stale, value-mismatched, or invalid entries. GitHub Actions run 331 verified this at head `f7cf27afb98621575d11751487640fcd5d91fcea`.

`benchmarks/constraint_registry.json` binds every discovered constraint to an exact key and expected value. Grouping shares classification metadata but does not wildcard future constraints. Any new numeric constraint, removed constraint, or changed registered value fails CI until it is deliberately classified.

The registry distinguishes:

- `STRUCTURAL_INVARIANT`: domain/protocol/representation facts that are not optimization knobs;
- `EXTERNAL_CONTRACT`: values dictated by an external data representation or interface;
- `EMPIRICAL_TUNABLE`: behavioral values whose exact setting must be justified by task-quality evidence;
- `ENVIRONMENT_CALIBRATED`: host/model/process values that require measurements on the deployment environment;
- other explicitly registered risk/safety classes where applicable.

CI runs the governance audit in the static-check stage so unclassified constraints fail before the PostgreSQL regression suite.

## Deterministic calibration evidence

`benchmarks/run_deterministic_constraints.py` is executed in GitHub CI. The first frozen result is committed at:

`benchmarks/results/DETERMINISTIC-CONSTRAINTS_2026-08-27_initial.json`

The current evidence does **not** support claiming that several working production values are optimal:

### Memory scoring

`MEM-SCORE-001` remains `INSUFFICIENT_DISCRIMINATION`. The frozen memory benchmark establishes correctness of the current scoring policy, but materially different threshold/weight policies also satisfy the measured corpus. Production values therefore remain working hypotheses rather than empirically identified constants.

### Memory breadth

`MEM-BREADTH-001` evaluated packet limits 1 through 24 over 31 frozen questions. The current limit of 5 achieved 31/31 question success, 28/28 required-evidence recall, and 4/4 unknown-fact abstention, but every tested packet limit from 3 through 24 was quality-equivalent. Candidate-generation breadth, attention-aperture breadth, active-working-state breadth, capability-result breadth, and final-context breadth remain unresolved by this corpus.

### Association graph

`MEM-GRAPH-001` explored hop depths 1 through 24 and decay values 0.25, 0.50, 0.75, 0.85, 0.90, and 1.0. The production baseline (`max_hops=2`, `decay=0.85`) passed all 31 questions, but **120 explored policies were quality-equivalent**. A one-hop/0.5-decay policy was among the lowest-work equivalent candidates. This means the current deeper graph budgets are not yet empirically identified by the frozen graph.

### Capability discovery

`CAP-DISCOVERY-001` tested five materially different routing coefficient vectors. All five preserved every current routing oracle. The production coefficients therefore remain provisional; the benchmark needs more adversarial/ambiguous routing cases before it can distinguish them.

### Scheduler service guarantees

`SCHED-SERVICE-001` compared quarter-, half-, current-, double-, and quadruple-scaled service wait vectors. All preserve the current deterministic service-order invariant. Without a measured arrival distribution and explicit queue-delay/service objective, exact wait-cycle values cannot honestly be labeled optimal.

## Constraint removal rather than post-hoc justification

Where a numeric bound was redundant with a stronger finite runtime domain, it was removed instead of being registered merely to satisfy the audit. Prompt-level numeric instructions that had no independent justification were likewise removed. The association identifier's truncated SHA-256 digest bound was eliminated rather than defended with an arbitrary collision-risk threshold; the full deterministic digest is now retained.

The audit was also expanded specifically to prevent policy numbers from hiding in LLM prompt strings, scoring arithmetic, comparisons, regexes, or slices.

## Native-only calibration

Three parameter families cannot be established by GitHub's Ubuntu runner:

- `RES-NATIVE-001`: CPU/RAM observation freshness, safety headroom, process estimates, and local-LLM concurrency;
- `WORKER-NATIVE-001`: leases, worker/process timeouts, claim retries/delays, and recovery timing;
- `LLM-NATIVE-001`: Ollama HTTP timeout, output-token caps, structured-output retries, and literal-preservation/output behavior.

`benchmarks/native_constraint_calibration.py` and `scripts/run_native_constraint_calibration.ps1` now collect target-host pilot evidence without rewriting production policy. The harness records raw host samples, controlled Ollama measurements across candidate token caps, and the frozen worker/runtime block duration. Its output is written to a timestamped `benchmarks/results/NATIVE-CONSTRAINTS_*.json` artifact.

Run on the intended Windows development/deployment machine:

```powershell
cd C:\Users\gy0d8\OneDrive\Documents\jit_agent_prototype
git switch v0.7-jit-attention
git pull
.\scripts\run_native_constraint_calibration.ps1
```

A single pilot is evidence collection, not verification. Resource margins require idle/CPU-pressure/memory-pressure/cold-model/warm-model samples. Worker timing requires normal, slow, killed, spawn-failure, and resource-denial trials. LLM bounds require cold/warm/contention and production-schema trials.

## Current verification

At head `f7cf27afb98621575d11751487640fcd5d91fcea`, GitHub Actions run 331 passed:

- Ruff;
- constraint audit: **171 discovered / 171 registered / 0 uncovered / 0 stale / 0 mismatched / 0 invalid**;
- deterministic constraint calibration;
- all 5 local-model/native acceptance tests collected;
- deterministic/PostgreSQL suite: **233 passed, 5 environment-dependent Ollama tests skipped**.

All four existing Copilot review threads on PR #18 remain resolved.

## Release-gate consequence

This governance work does **not** relax the v0.7 native acceptance requirement. PR #18 remains unmerged until the intended Windows machine passes `scripts/run_v07_acceptance.ps1` with real PostgreSQL, Ollama, resource observation, guarded subprocess execution, lease recovery, and the frozen stateless continuity experiment.

The constraint registry also intentionally preserves `NATIVE_REQUIRED`, `PROVISIONAL`, and `INSUFFICIENT_DISCRIMINATION` states where evidence is not yet sufficient. Green CI means the uncertainty is explicit and governed; it does not mean every tunable has magically become optimal.
