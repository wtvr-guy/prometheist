# Prometheist Memory Kernel v0.5 — Scale Benchmark

This benchmark answers two separate questions:

1. **Accuracy under accumulated history:** does the same deterministic memory policy still retrieve oracle evidence when a persona has thousands or tens of thousands of events?
2. **Latency under accumulated history:** how quickly can the pure kernel and the indexed PostgreSQL path retrieve bounded evidence as authoritative history grows?

The benchmark deliberately measures both paths because they have different scaling behavior.

- `jit_agent.scale_benchmark` scores the **entire generated history in memory** for every question. This characterizes the raw deterministic algorithm without an index hiding its cost.
- `jit_agent.postgres_scale_benchmark` uses the **PostgreSQL lexical projection plus bounded association expansion**. This characterizes the path that is closer to the intended JIT architecture.

## Personas and oracle questions

The scale generator expands all three current synthetic personas:

- Jordan Vale — 18 base oracle questions;
- Avery Chen — 6 held-out base oracle questions;
- Morgan Reyes — 7 v0.5 adversarial base oracle questions.

The base events and questions remain semantically unchanged. All event and conversation IDs are deterministically remapped to UUIDv5 values so a generated corpus can be evaluated in memory and loaded into PostgreSQL without changing identity.

A scale corpus does **not** merely append thousands of junk rows and keep asking the same few old questions. By default, every 500 generated events it plants a deterministic exact-recall probe fact and adds a corresponding oracle question. Probe examples include a unique reference card stored in a unique locker, a parcel confirmation attached to a unique shelf, or an archive-bin code.

The probes are deliberately simple. They test whether a fact distributed through a long event history can still be found accurately and quickly. Semantic reasoning remains covered by the base persona questions rather than being mixed into the scale instrumentation.

At 50,000 events this produces roughly 100 additional probe questions per persona, distributed through the generated tail.

## Default scale profiles

The default profiles are:

| Profile | Events per persona | Total events across 3 personas |
|---|---:|---:|
| small | 1,000 | 3,000 |
| medium | 10,000 | 30,000 |
| large | 50,000 | 150,000 |

Running all three profiles for all three personas generates **183,000 total benchmark events** across nine independently materialized corpora.

Generated JSON is written under `benchmarks/generated/`, which is intentionally gitignored. The source benchmarks, generator seed, generation policy, and probe cadence are versioned instead of committing large derived files.

## Noise model

Most generated records are mundane synthetic background events: inventory notes, maintenance reminders, receipts, weather logs, office notes, and household checklists.

Every twelfth non-probe generated record is lexically confusable by default. Confusable records contain vocabulary from one benchmark domain without asserting the persona-specific answer:

- beverages;
- vehicles;
- deposits;
- employers/projects;
- people;
- locations;
- appointments;
- objects.

Default confusable records avoid repeatedly copying oracle-bearing proper nouns. Exact-name collision or poisoning should be tested as a separate adversarial profile rather than hidden inside the basic scale characterization.

This is intentional. A corpus containing 50,000 rows of random unrelated words would measure row-count overhead but would barely test retrieval interference.

The generator is deterministic and prefix-stable: given the same seed and cadence settings, the first 10,000 events of a 50,000-event corpus are identical to the standalone 10,000-event corpus. Probe facts/questions in that prefix are also identical. That makes scale comparisons controlled rather than anecdotal.

Defaults:

```text
seed = 20260820
confusable_every = 12
probe_every = 500
```

## 1. Pull the v0.5 branch

```powershell
git switch memory-kernel-v0.5-robustness
git pull
uv sync
```

Before interpreting benchmark results, run the ordinary regression suite:

```powershell
uv run pytest -v
```

Until this passes locally, v0.5 remains unverified.

## 2. Materialize the large corpora

To create all default JSON corpora:

```powershell
uv run python -m jit_agent.scale_corpus --events 1000 10000 50000
```

This writes nine files under `benchmarks/generated/`: three sizes for each of the three personas.

To generate only the 50,000-event histories:

```powershell
uv run python -m jit_agent.scale_corpus --events 50000
```

The probe cadence can be changed explicitly when a denser or lighter accuracy sample is useful:

```powershell
uv run python -m jit_agent.scale_corpus --events 50000 --probe-every 250
```

Keep the same `--probe-every` value when comparing in-memory and PostgreSQL results.

## 3. Run the full-history in-memory benchmark

```powershell
uv run python -m jit_agent.scale_benchmark `
  --events 1000 10000 50000 `
  --materialize-dir benchmarks/generated `
  --report benchmarks/generated/v05_in_memory_results.json
```

For every persona/size pair this reports:

- event count;
- base-question count;
- distributed probe-question count;
- question accuracy;
- evidence recall;
- mean reciprocal rank (MRR);
- unknown-fact abstention;
- association-derivation time;
- median (p50) recall latency;
- p95 recall latency;
- maximum recall latency.

The in-memory path intentionally examines the whole history on every query. It is a useful control, not the intended long-term storage strategy.

## 4. Run the indexed PostgreSQL benchmark

### Safety rule

The PostgreSQL scale runner is destructive to the database selected for the benchmark because it repeatedly replaces its event set. It has a hard guard: the current database name must contain either `test` or `benchmark`.

Do **not** point it at the long-lived development database.

The existing dedicated `jit_agent_test` database is an acceptable target when the ordinary test suite is not running.

Set a benchmark-specific environment variable rather than changing the normal development `DATABASE_URL`:

```powershell
$env:JIT_AGENT_BENCHMARK_DATABASE_URL = "postgresql://USER:PASSWORD@localhost:5432/jit_agent_test"
```

Then run:

```powershell
uv run python -m jit_agent.postgres_scale_benchmark `
  --events 1000 10000 50000 `
  --report benchmarks/generated/v05_postgres_results.json
```

The PostgreSQL benchmark separately reports:

- event count;
- base-question count;
- distributed probe-question count;
- corpus load time;
- complete derived-state rebuild time;
- question accuracy;
- evidence recall;
- MRR;
- unknown-fact abstention;
- p50/p95/max recall latency;
- lexical projection entry count;
- association entry count;
- candidate limit used for indexed retrieval.

The default candidate limit is 500 and the default bounded association limit is 250.

## 5. Candidate-window stress test

If the 50,000-event PostgreSQL profile loses accuracy, rerun the large profile at wider candidate windows before changing retrieval technology:

```powershell
uv run python -m jit_agent.postgres_scale_benchmark --events 50000 --candidate-limit 250
uv run python -m jit_agent.postgres_scale_benchmark --events 50000 --candidate-limit 500
uv run python -m jit_agent.postgres_scale_benchmark --events 50000 --candidate-limit 1000
uv run python -m jit_agent.postgres_scale_benchmark --events 50000 --candidate-limit 2000
```

Interpretation:

- If accuracy recovers as the candidate limit grows, the failure is primarily **candidate-index recall**, not evidence scoring or association derivation.
- If the correct event enters the candidate set but still ranks incorrectly, the failure is primarily **scoring/routing policy**.
- If accuracy remains strong but latency rises sharply, the next problem is **performance engineering** rather than retrieval semantics.
- If unknown-fact abstention degrades, the system is becoming too willing to surface merely related evidence and the activation policy needs tightening.
- If the distributed exact probes fail while the base questions remain strong, the candidate/index path is especially suspect because each probe has a unique high-specificity locator.

This distinction matters before considering embeddings or another retrieval subsystem.

## What counts as a v0.5 result

The scale benchmark is initially a characterization experiment, not a predeclared performance victory. The first local measurements should be recorded before setting device-specific latency thresholds.

Correctness requirements from the small corpora remain hard requirements:

- Morgan: 7/7, 1.000 evidence recall, 1.000 unknown abstention;
- Jordan: 18/18;
- Avery: 6/6;
- full regression suite green.

For scale profiles, record the exact corpus size, seed, confusable cadence, probe cadence, candidate limit, machine, PostgreSQL version, accuracy metrics, question counts, and latency metrics. Any large-corpus failure becomes evidence for the next mechanism change.
