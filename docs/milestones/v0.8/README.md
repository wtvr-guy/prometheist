# v0.8 — Predictive situations and non-user cognition

**Status:** implementation integrated with the v0.7 closure candidate; calibration
and native acceptance remain separately gated.

The scope follows the supplied final response from “Map Precognitive Pipeline
Workers.” The active branch is `copilot/implement-v08-milestone`.

Implemented mechanisms include typed multimodal percepts, expectations and
prediction errors, overlapping situation snapshots, contextual salience, source
policies, narrow non-user triage, deterministic reflexes, situation attention,
guarded task workers, observed action feedback, and scheduled consolidation.
The user path retains all seven v0.7 closure specialist/deterministic stages,
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

The historical basic perception/lexical-salience implementation remains preserved
at parent `a2636c25ea8b8e4192371063d72f73522f8154da`. The unfrozen Epistemic WorkingState
proposal is archived rather than silently represented as completed.
