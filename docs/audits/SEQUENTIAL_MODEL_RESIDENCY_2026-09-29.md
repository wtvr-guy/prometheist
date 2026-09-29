# Sequential local model residency

## Problem and scope

The local app scheduled one LLM worker at a time but added the cold memory costs
of every distinct routed model. A coding model could therefore pass its own
capacity check and still be excluded when added to the general model. A saved
`keep_alive` override could also undo the intended unload-after-request profile.

This change makes admission and execution agree for the app's local Ollama
pipeline. It does not remove OS headroom, CPU pressure checks, per-model metadata
validation, the scheduler's claim-time gates, or context-size requirements.

## Changes and rationale

- `model_admission.py`: reserve the maximum sequential stage estimate, which
  already includes worker overhead; enforce one LLM worker and `keep_alive=0`.
  Increment the admission policy version to preserve interpretation of receipts.
- `model_residency.py`: serialize local invocation boundaries, inspect running
  models, explicitly unload them, and verify an empty inventory before another
  inference. Repeat cleanup after success, HTTP failure or timeout. A failed
  inventory/unload blocks progress rather than guessing that memory was freed.
- `llm.py`: apply that lifecycle to both existing Ollama inference transports in
  app jobs; record the effective request and unload receipts in existing
  invocation diagnostics. No extra per-worker artifact family is introduced.
- `gui_worker.py`: unload cached models before planning on real available RAM.
- Route preview/UI: preserve measured observations separately from a labeled
  reclamation forecast. `needs_unload` permits only starting cleanup; the actual
  worker requires a new, measured, eligible plan before cognition starts.
- Resource and parameter help: explain peak sequential accounting and the
  enforced local unload policy. Surface specialist exclusion reasons in Preview.
- Constraint registry and LOCAL-APP-001: classify the unload deadline/poll interval
  as provisional tunables and record single-worker/deadline invariants.

The existing cleanup was published first on `fix/sequential-model-residency` as
`534f35b`: grouped resource display, resource filter, explicit Android permission
gap, and common model-weight exclusions. `main` was not modified.

## Validation and limits

Deterministic tests cover coding selection when the combined estimate would fail,
oversized single models, forced unload despite retention overrides, general-to-
coder request ordering, timeout/HTTP-failure cleanup, malformed inventories,
unload acknowledgement without actual release, lock contention, remote-service
exclusion, read-only forecasting and physical re-admission before worker launch.

Native Windows/Ollama acceptance remains necessary: register the installed coding
specialist, select Coding, preview the route, send a request, and confirm the
general model is absent before the coding request. Verify worker receipts and
actual memory usage. A forced process kill cannot execute Python cleanup; the
next job repeats cleanup and verifies residency before admitting work.

The lock coordinates one private runtime. Use a dedicated daemon and Ollama's
server-side `OLLAMA_MAX_LOADED_MODELS=1` / `OLLAMA_NUM_PARALLEL=1` controls for a
limit across unrelated clients. The app cannot reconfigure an already-running
external server. Cold boundaries incur reload latency; model weights on disk
are untouched.

An existing process-cancellation test encountered a container PID-visibility
failure before it could inspect its child. That is not a passing native
cancellation test. PostgreSQL-dependent gates are not claimed without a test
database, and no live model-inference result is claimed from HTTP fixtures.

Local results: 41 focused policy/lifecycle/GUI API tests passed. Another 24
existing LLM transport/residency tests passed with their original consent and
isolated-artifact fixtures, without the unrelated PostgreSQL setup fixtures.
Ruff, JavaScript syntax, diff whitespace, and the constraint registry audit passed.
The new browser regression covers explicit Coding → unload forecast → Send;
browser execution was unavailable because Chromium's download was not a valid
archive. Run it in the existing browser CI job or on a configured native host.
