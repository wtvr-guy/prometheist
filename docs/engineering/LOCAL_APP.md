# Local control app

Prometheist now includes a chat-first local web application. It uses the existing
Python environment, guarded cognitive workers, canonical event store, and artifact
journal. It requires no Electron runtime, frontend build server, CDN, or analytics.
The browser is presentation; closing a tab does not stop the local app or its job.

## Start on Windows

From the checkout, run `uv sync --frozen`, then:

```powershell
uv run prometheist gui --profile C:\Prometheist\subject_001\profile.json
```

Use an existing private imprint profile outside Git and synchronized folders. With
no `--profile`, the app prepares a new `subject_001` profile under
`%LOCALAPPDATA%\Prometheist\subject_001` (or `~/.local/share/Prometheist/subject_001`
on other systems). It does not silently create a PostgreSQL database or activate a
different identity. A dedicated, migrated private database is still required for
chat and canonical host-map persistence; see [imprinting setup](IMPRINTING_SETUP.md).
Set the database environment variable named in `profile.json` before launching.

The app opens a one-use loopback link in your browser. `--no-browser` prints the
link without opening it; `--port 8766` selects another unprivileged port. Reuse the
same browser session for additional tabs. If the launch link has already been
consumed in a different browser, restart the app for a new one. Only one app may
own a profile at a time.

Models, settings, Files, grants, and host observations remain available when the
database is unavailable. Chat stays disabled with setup guidance. Host observations
are saved locally even when they cannot be admitted to the canonical database;
the interface distinguishes this state. Inventory monitoring continues while the
app process runs, and its configured interval can be changed in Settings.

## Everyday use

- **Chat** opens first. Conversations retain their own display grouping; memory
  retrieval still follows the system's cross-conversation evidence rules.
- **Controls** chooses a provider/model and exposes registered generation options.
  An unchecked override inherits the registered execution profile or model default. Ollama metadata narrows
  thinking support and maximum context where reported. Sampling overrides affect
  final responses; hardware overrides affect all local model calls. Control workers
  keep their deterministic temperature. Model output itself is not guaranteed
  reproducible across runtimes or hardware.
- **Models** lists installed Ollama weights, inspects metadata, downloads exact
  names/tags, searches Ollama's public library, and deletes weights after exact-name
  confirmation. Catalog search parses the public library page; an upstream markup
  change can make it unavailable. Direct model-name downloads remain available.
  Stop cancels Prometheist's transfer request; the separate Ollama daemon may finish
  an in-flight download and retain reusable partial layers.
- **Activity** shows the latest 200 app jobs, their captured settings, progress,
  results, and bounded worker-log tails. Older receipts remain available in Files. A bounded recent-job index prevents
  polling from scanning lifetime history; restart performs one recovery scan.
  Cancellation stops only the owned orchestrator and its descendants. It retains
  already-admitted input and partial artifacts; it does not silently retry.
- **Settings** separates workspace preferences, stage routing, resource admission,
  evidence budgets, devices/sensors, native security, destination consent, and
  registries. Advanced mode adds the validated complete settings editor.

Each chat snapshots settings into a private file inherited by its fresh worker
processes. Later UI edits do not change an active task. Workers use the existing
schema validation, stage specialization, admission policy, and artifact journal.

## Deterministic model choice and capacity

The fallback order is **installed local specialist → capability-based catalog
search → optional OpenAI review → local default**. Nothing is downloaded or sent
to a cloud model automatically. An explicit stage route takes precedence; disabling
automatic specialist routing deliberately pins the selected model. The default
fallback can also be disabled in advanced settings.

Register installed models using **Models → Use as specialist**. Declare general,
coding or future vision expertise and a priority. Ollama reports modalities, but
not a trustworthy coding-quality score; operator expertise labels are distinct from
reported capabilities. Automatic task classification uses only a `/code` prefix or
fenced code to identify coding; otherwise it chooses general. The task selector
is an explicit override. Eligible specialists are ordered by priority, estimated
memory, then canonical model ID. Only the final response stage changes; control
stages retain their configured models. The combined stage budget must fit.

When no specialist qualifies, the chat presents deterministic choice dialogs before
starting cognition. Catalog search uses registered public queries (`coder` for
coding, the `vision` capability filter for vision), sorts the results, rejects
incompatible advertised modalities and cloud-only listings, and records the
response digest and matches locally. The personal prompt is never a catalog query.
Results are advertisements, not verified suitability: review an exact tag and
choose its download, then register and assess the installed model. If no local
option suits the task, review OpenAI; declining it leads to the final local-default
choice. These questions, disclosures and status messages are code/template output,
with no LLM call. Model inference still requires a fresh eligibility check.

**Check capacity** and **Preview route** show measured CPU/RAM, the estimate and
reasons. Every job records its original settings, complete admission inputs and
effective settings in private `operator/app-jobs/` receipts. The pure policy returns
the same result from identical inputs. It distinguishes eligible, temporarily
blocked, unsupported, unverified and explicitly remote selections. An inventory
outage produces a reviewable fallback. Remote service capacity remains unknown;
only local worker overhead is assessed for explicit remote routes.

The first registered estimator is deliberately limited to dense architectures in
`model_admission.py` and CPU inference. It counts full installed weights, a full
context K/V cache envelope, runtime buffers and worker memory, then applies the
existing OS and uncertainty headroom policy. Context is explicitly set to the
configured default (initially 4096) capped by reported model support, unless the
operator overrides it. It never silently shrinks an explicit context. The initial
profile uses one CPU thread, a batch of 128, no GPU offload, and unload-after-request;
valid explicit overrides remain visible. Larger batches, speculative decoding,
GPU offload and unknown/hybrid architectures require a registered estimator and
native calibration. Shared integrated graphics memory is never counted as extra
RAM. Resident models receive no optimistic reuse credit in the GUI profile.

The estimate is provisional, not a physical RAM reservation or an OOM/performance
guarantee. Worker claims remeasure capacity before launch. External workloads can
still change resource pressure; the target laptop needs acceptance calibration.
The full context envelope uses four bytes per K/V element and counts all layers,
without taking savings for quantized caches or sliding-window attention. Formula
inputs correspond to [Ollama metadata](https://docs.ollama.com/api-reference/show-model-details)
and [llama.cpp cache dimensions](https://github.com/ggml-org/llama.cpp/blob/master/src/llama-kv-cache.cpp).
Explicit context prevents drift with [Ollama's hardware-dependent defaults](https://docs.ollama.com/context-length).

Vision capabilities and catalog discovery are registered, but image input is not
connected to the guarded chat pipeline yet; vision execution stays unsupported.
This interface does not pretend that a text prompt can supply missing image data.

## OpenAI

Connect a key in **Models → OpenAI**, or set `OPENAI_API_KEY` before launch. The GUI
key remains in server memory and the environment of its owned active workers. It is
never written to settings, browser storage, URLs, or request artifacts. Disconnect
removes it from future jobs; cancel an active job to stop its future requests.
API billing is separate from a ChatGPT subscription.

A reviewed purpose/destination grant is required before requests to
`https://api.openai.com`. The disclosure includes current prompts and retrieved
personal evidence. Grants can be revoked in Privacy; workers check them again before
sending. The endpoint is fixed, ambient proxies are disabled, and redirects are not
followed. Requests use the stateless Responses API, strict structured outputs and
`store: false`, without previous-response IDs, background tasks, or hosted tools.
OpenAI's own retention policies still apply; `store: false` is not a promise of
zero retention. Reasoning content is not retained in Prometheist diagnostics.

The model listing supplies IDs, not a complete parameter schema or a guarantee
that every listed model can run this pipeline. Choose a Responses-compatible text
model with structured outputs. Controls use conservative family profiles: reasoning
models omit temperature/top-p, and exact effort/verbosity support is checked by the
provider. Unknown or unsupported combinations fail visibly; there is no silent
provider or model fallback. Reasoning budgets include reasoning tokens.

Use **Model routing** to send only selected worker stages to OpenAI, or leave routes
inherited to use the chat model throughout. Small stages may still fail on an
underpowered model; the interface does not claim every downloadable model is an
adequate cognitive specialist.

## Persistent Files

**My files** is the writable `files/` folder alongside the private profile.
**Runtime records** exposes the whole private deployment for inspection and download.
Add another existing local folder with a reviewed, revocable read-only or read/write
scope. Network/UNC/mapped-network roots and linked root paths are rejected before
resolution; a network filesystem needs its own explicit integration and consent.
The app retains its resolved path and filesystem identity. OS permissions
still apply. Viewing or uploading a file does **not** automatically index it into
memory, execute it, or send it to a model.

Files provides breadcrumbs, filename search, paged listings, text/image/audio/video
previews, original downloads, new folders/text files, text editing, uploads, copies,
renames/moves, and Trash restoration. Search is filename-based; it does not silently
scan document contents. Text previews/editing are bounded to 512 KiB; larger files
can be downloaded or uploaded in 1 MiB chunks. HTML/SVG and unknown types are
attachment downloads, never executable app-origin previews. Symlinks, junctions,
special files and ambiguous Windows names cannot be followed through Files.

Edits require the file revision observed when opened. A concurrent change rejects
the save. Replacements preserve POSIX ownership/mode/access ACLs where exposed, or
use Windows ReplaceFileW to preserve the existing DACL without ignoring ACL errors. Replaced text is retained in **File activity → Previous version**. Files
never overwrites an existing copy/upload/move destination. Trash stays on the source
volume and is never automatically emptied. File activity restores to the original
path only if it is still free. Cross-volume moves require copy, verification, then
Trash of the original. Large copies run as cancellable jobs; interruption can leave
a partial destination, which is explicitly reported and retained for inspection.

Canonical evidence and operator/system records are read-only through this general
file interface, including when another granted folder encloses the deployment.
Their dedicated controls enforce their contracts. File mutations have independently
persisted intent/completion receipts. An intent without completion is not evidence
of success. These safeguards address app-origin mistakes; they are not an OS sandbox
against another process running as the same user with permission to race file I/O.

## Security and extensibility

The server binds only `127.0.0.1`. Authentication exchanges a single-use launch
fragment for an HttpOnly SameSite=Strict session cookie. Exact Host/Origin checks,
JSON-only bounded mutations, no CORS, no-store responses, and a restrictive content
security policy protect the local control surface. The app does not elevate itself.
Native Firewall actions show the exact plan and still require OS administrator
rights plus the existing enrollment contract. Local-only Firewall rules also block
consented OpenAI/model-catalog calls; review removal when that is your intention.

Typed settings, model selection, task plans, deterministic control templates, filesystem scopes and generation parameters are in
the contract registry. `model_parameters.py` owns metadata and validation;
`gui_models.py` owns model lifecycle operations; the existing artifact-aware transport
owns inference. UI view modules are registered in `web/app.js`; add views as local
ES modules and CSS, without external scripts. New providers need an explicit consent
boundary, stateless transport, bounded inputs, typed outputs and tests. Register
new capabilities and schemas rather than allowing arbitrary model-authored commands.

## Validation and limits

Run:

```text
uv run pytest -q tests/unit --confcutdir=tests/unit
uv run ruff check .
uv run python scripts/audit_registries.py
uv run python scripts/audit_constraints.py --fail-unregistered
```

Browser acceptance runs a real local API and filesystem with fixture model metadata.
Set `PROMETHEIST_BROWSER_TESTS=1` and provide Chrome through
`PROMETHEIST_BROWSER_BINARY`, or install Chromium with `uv run playwright install chromium`.
Then run `uv run pytest -q tests/browser --confcutdir=tests/browser`.
CI retains desktop/mobile screenshots. Full database regression runs independently.

Live Ollama inference/downloads, OpenAI account/model compatibility, latency, target
laptop resource tuning, native device coverage and elevated Firewall behavior still
need their respective native acceptance checks. No paid cloud request is needed
for deterministic transport tests. The app is a control and observation surface;
it does not establish identity maturity or promise autonomous 24/7 protection when
the machine or app is stopped.
