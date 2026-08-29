# MEM-ADAPT-006: Native Memory Composition to Cognition

**Status:** experimental. Not wired into the production interaction path.

## Question

`MEM-ADAPT-003` through `MEM-ADAPT-005` established that a bounded evidence composer can surface a more useful six-item evidence set than either raw top-k or novelty-first coverage under synthetic and PostgreSQL-backed composition tests.

`MEM-ADAPT-006` asks the next question:

> Does better bounded evidence composition cause a small, fresh, stateless local model to answer correctly more often without increasing the model context budget?

The benchmark separates four layers:

```text
retrieval availability
        ↓
composition completeness
        ↓
LLM reasoning
        ↓
final answer correctness
```

If required evidence never reaches the shared retrieval pool, the failure is retrieval. If it reaches the shared pool but not the six-item packet, the failure is composition. If the complete evidence packet reaches Qwen3:4b and the answer is still wrong, the failure is reasoning rather than memory.

## Controlled architecture

Each scenario creates one canonical PostgreSQL history and one current percept. Prometheist then runs exactly one adaptive memory-attention retrieval pass to produce a shared candidate population.

The same ordered pool is given to three composition policies:

1. retrieval-order top-k;
2. frozen coverage-aware Composer v1;
3. relevance-constrained Composer v2.

Every policy receives the same final packet limit of six evidence items.

Each resulting packet is passed to a separate `OllamaClient.respond()` call. These calls are sequential and stateless: no transcript, prior response, or LLM context is inherited from another policy or scenario. Ollama may keep model weights resident, but not conversational state.

The benchmark rotates policy call order across scenarios so one policy is not systematically penalized by always receiving the first cold invocation.

## Production response adapter

The benchmark deliberately uses `OllamaClient.respond()` rather than a benchmark-only inference wrapper. This preserves the production response-worker behavior already exercised by native acceptance:

- fresh disposable invocation;
- chronological evidence rendering;
- event-role exposure without retrieval scores or event IDs;
- opaque-literal placeholder protection;
- structured text-answer envelope;
- zero-temperature Qwen3 Instruct transport;
- bounded generation and existing retry behavior.

Composition metadata is not shown to the model. Qwen sees only the user question and the six-item evidence timeline.

## Scenario families

The corpus includes old facts under duplicate pressure, claim-plus-correction reasoning, distributed clues, numeric payloads, lexical novelty bait, stale retained evidence, zero-overlap association recovery, and unsupported-query abstention.

The association case exercises the complete path:

```text
PostgreSQL ledger
→ adaptive attention
→ association traversal
→ shared candidate pool
→ bounded composition
→ stateless Qwen3:4b
→ final answer
```

The abstention case asks for a synthetic marker that does not exist in the ledger. Every policy should return `INSUFFICIENT` rather than invent a value.

## Output

Each case records required canonical event IDs, required ranks in the shared pool, retained evidence IDs, the adaptive retrieval policy, policy call order, each six-item packet, evidence completeness, raw answer, answer correctness, LLM wall-clock latency, model/runtime errors, and the classified failure layer.

Aggregate output reports per-policy counts and pairwise answer head-to-heads.

## Local execution

Use the dedicated disposable PostgreSQL test database and the configured Qwen3:4b Ollama model:

```powershell
$env:TEST_DATABASE_URL = "postgresql://jit_agent_app@localhost:5432/jit_agent_test"
$env:OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
```

Run the non-Ollama contract first:

```powershell
uv run pytest tests/test_memory_composition_cognition_benchmark_contract.py tests/test_memory_composition_cognition_benchmark_integration.py -v
```

Then run the full repository suite:

```powershell
uv run pytest
```

Run native cognition comparison:

```powershell
uv run python benchmarks/compare_memory_composition_cognition.py
uv run python benchmarks/compare_memory_composition_cognition.py --stress
```

Artifacts are written to `benchmarks/results/MEM-ADAPT-006_*.json`.

The benchmark is destructive and refuses a database whose name does not contain `test` or `benchmark`.

## Interpretation discipline

Do not infer that Composer v2 improves cognition merely because its evidence packet is complete. The central result is answer correctness.

A strong result would combine higher v2 answer accuracy, no baseline-only answer regressions, correct abstention, stable quick/stress behavior, and explicit reasoning failures when v2 supplied complete evidence but the model still answered incorrectly.

Passing `MEM-ADAPT-006` is still not sufficient to replace the production architecture. Before promotion, the experimental path should also survive generated holdout histories, repeated native runs, latency/resource analysis, and end-to-end interaction acceptance. Top-k and Composer v1 remain regression baselines until the replacement decision is complete.
