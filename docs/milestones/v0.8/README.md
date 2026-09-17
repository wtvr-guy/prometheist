# v0.8 — Predictive situations and non-user cognition

**Status:** active development milestone on the closed v0.7 baseline; calibration
and native acceptance remain separately gated.

The scope follows the supplied final response from “Map Precognitive Pipeline
Workers.” `main` is the integration baseline; subsequent changes use focused
branches. [PR #28](https://github.com/wtvr-guy/prometheist/pull/28) consolidates
`constitutional-amendment-v2` and `person-fidelity-baseline`, including
Constitution 2.0, the frozen person-fidelity fixture, retained negative evidence,
and the reviewed situation-completion fixes.

Implemented mechanisms include typed multimodal percepts, expectations and
prediction errors, overlapping situation snapshots, contextual salience, source
policies, narrow non-user triage, deterministic reflexes, situation attention,
guarded task workers, observed action feedback, and scheduled consolidation.
The user path retains all seven v0.7 baseline specialist/deterministic stages,
mandatory user responses, source-scoped memory, exact/natural realization, and
artifact-backed recovery.

Read the [situation architecture and operator guide](../../architecture/SITUATION_COGNITION.md)
for contracts, process boundaries, supported operations, commands, and limits.
The [implementation record](../../audits/V08_CLOSURE_INTEGRATION_2026-09-12.md)
explains each change, its reason, research grounding, and validation.

## Evaluation

This user-authorized integration contains several independent mechanisms. It is
not a single controlled experiment. [HYPOTHESIS.md](HYPOTHESIS.md) specifies
separate ablations before making quality or efficiency claims. Numeric budgets
and salience bins remain provisional. Deterministic CI does not establish native
Windows/Ollama acceptance or neurobiological fidelity.

The [Copilot audit follow-up](../../audits/COPILOT_AUDIT_REVIEW_2026-09-16.md#completion-evidence--2026-09-17)
records **378 passed, 13 skipped** on revision `23ef8d8`, with the required
static and deterministic checks passing. Mike also reported a passing local
run; its native counts and environment were not supplied. Neither result closes
the independent performance, model-quality, or person-fidelity review gates.

The historical basic perception/lexical-salience implementation remains preserved
at parent `a2636c25ea8b8e4192371063d72f73522f8154da`. The unfrozen Epistemic WorkingState
proposal is archived rather than silently represented as completed.
