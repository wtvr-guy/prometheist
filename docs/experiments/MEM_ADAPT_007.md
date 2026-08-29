# MEM-ADAPT-007: Model-Capacity Crossover

**Status:** experimental. Composer v2 and the production interaction path remain unchanged.

## Question

`MEM-ADAPT-006` showed a clean separation between memory composition and local-model cognition: relevance-constrained Composer v2 supplied complete evidence in every quick and stress case, while Qwen3:4b produced only four exact answers out of eight.

`MEM-ADAPT-007` asks:

> How much disposable local-model capacity is required before Prometheist's frozen memory architecture stops being the dominant bottleneck?

The experiment changes only the response model. Adaptive retrieval, Composer v2, the six-item final packet, scenario histories, concise retrieval cues, response prompt, structured output adapter, and stateless invocation contract remain frozen.

## Candidate model

The first larger candidate is:

```text
ministral-3:8b-instruct-2512-q4_K_M
```

This is the current Ollama Ministral 3 8B instruction model. It is used as a normal non-thinking instruction model; Prometheist does not request or consume a reasoning trace.

The existing control remains:

```text
qwen3:4b-instruct-2507-q4_K_M
```

The generic Ollama `qwen3:8b` target was not selected because it belongs to Qwen3's hybrid thinking/non-thinking family. This experiment specifically requires a dedicated instruction-style, non-thinking worker target.

The older `mistral:7b-instruct` remains available in Ollama, but Mistral has retired the original Mistral 7B line for new integrations in favor of Ministral 3. The newer 8B candidate is therefore the primary test target.

## Resource safety

The production native resource calibration is intentionally **not changed yet**. Its current cold-load estimate is empirically tied to the Qwen3:4b target and must not be silently generalized.

`MEM-ADAPT-007` therefore applies an experiment-only preflight estimate:

- Qwen3:4b control: 3072 MiB cold-load reservation;
- Ministral 3 8B candidate: 7168 MiB cold-load reservation;
- unknown model target: 8192 MiB conservative experimental fallback.

The same native CPU threshold, system RAM headroom, uncertainty headroom, and one-local-LLM concurrency limit are retained. If current host pressure cannot safely admit the candidate, the benchmark fails before model inference rather than forcing the launch.

The larger estimate is provisional. The artifact records Ollama residency information, reported resident bytes when available, host available RAM, safe post-headroom RAM, and the incremental memory requirement. After target-host measurements exist, `RES-NATIVE-001` can calibrate the production gate from evidence rather than from the model-file size alone.

For an explicit experiment-only override:

```powershell
$env:MEM_ADAPT_007_COLD_MEMORY_MIB = "7552"
```

Do not use the override to force a launch that the host cannot safely sustain.

## Evaluation

`MEM-ADAPT-006` used exact-answer correctness. That exposed two different Qwen3:4b failure classes:

1. genuine evidence-use/reasoning failures; and
2. answers containing the correct values but violating the requested output form.

`MEM-ADAPT-007` records both dimensions:

```text
evidence_complete
answer_value_complete
answer_exact
format_only_failure
failure_layer
```

`answer_value_complete` requires every expected answer atom to occur in the model response. It does not give credit for the Qwen numeric-template failure (`<v1> ... <v6>`), and it does not rescue an answer that selected a duplicate instead of the old target. It does classify a response that contains all six correct labels plus unwanted source wording as a format-only failure.

Exact instruction following remains the primary final-response criterion; value correctness exists to localize the failure.

## Stateless model contract

Each answer is a fresh `OllamaClient.respond()` invocation. No transcript, hidden model context, previous answer, or previous scenario state is passed to the next call. Only model weights/runtime residency may persist.

Only one model target is tested per benchmark process. This prevents the crossover experiment itself from defeating the one-local-LLM resource invariant by attempting to keep both Qwen and Ministral resident simultaneously.

## Local execution

Pull the candidate first:

```powershell
ollama pull ministral-3:8b-instruct-2512-q4_K_M
```

Use the dedicated test database:

```powershell
$env:TEST_DATABASE_URL = "postgresql://jit_agent_app@localhost:5432/jit_agent_test"
```

Run the contract tests and normal repository suite:

```powershell
uv run pytest tests/test_cognition_model_benchmark_contract.py -v
uv run pytest
```

Run Ministral quick and stress:

```powershell
uv run python benchmarks/compare_cognition_models.py
uv run python benchmarks/compare_cognition_models.py --stress
```

For an apples-to-apples fresh Qwen control run using the same evaluator:

```powershell
uv run python benchmarks/compare_cognition_models.py --model qwen3:4b-instruct-2507-q4_K_M
uv run python benchmarks/compare_cognition_models.py --model qwen3:4b-instruct-2507-q4_K_M --stress
```

Artifacts are written as:

```text
benchmarks/results/MEM-ADAPT-007_<model>_<timestamp>.json
```

## Interpretation

The desired crossover is not merely a higher benchmark number. A convincing larger-model result should show:

- Composer v2 remains evidence-complete;
- required-value correctness improves over the 4B control;
- exact instruction-following improves;
- unsupported-query abstention remains correct;
- no new model-runtime/schema failures;
- quick/stress behavior remains qualitatively stable;
- latency and host-resource cost remain acceptable on the target machine.

If the 8B model materially improves cognition while the six-item evidence budget remains fixed, that supports the architectural claim that Prometheist can trade **better external memory selection plus a modest competent worker** for much larger resident model/context requirements.

If it does not improve enough, the failure remains informative: the memory system has already isolated the bottleneck at the disposable cognition worker boundary, and the next model-capacity step can be tested without redesigning memory again.
