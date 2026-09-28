# Fixed retrieval and empirical imprinting

Status: current production control path; retrieval quality remains experimental.
Policy: `fixed-retrieval/v1`. Introduced 2026-09-28.

The active path is:

1. Resolve references and classify the current prompt's source/surface policy.
2. Open the bounded attention aperture; activate derived self-context.
3. Select and execute any registered non-memory work. Empty catalogs need no model call.
4. Retrieve canonical self-model support/opposition roots where applicable and one bounded canonical neighborhood.
5. Run BROAD, ASSOCIATIVE, RELATIONAL, FOCUSED in that fixed order. A route without its required focus roots is explicitly recorded as skipped. An empty result from one route does not stop later routes.
6. Merge bounded route results deterministically, deduplicate event IDs, enforce source types and the exclusive history cutoff, alternate newer/older evidence within routes, and interleave routes and known evidence roles. Record budget exclusions without truncating or deleting canonical events.
7. Give the final responder admitted memory, separately labeled derived self-context, and authoritative capability results. Persist the response and final disposition.

The retrieval stage performs no LLM calls. It stops after exhausting the configured finite routes. It uses the original prompt and existing derived navigation hints, never a generated `memory_deficit`. Packet size and UTF-8 byte bounds remain the existing governed tunables. The initial implementation deliberately spends the bounded route budget even when an earlier route appears useful. Selective retrieval is a later experiment.

`ResponseMemoryPackage` records retrieval policy, route receipts, recall count, and stop reason. It has no sufficiency flag, requirements list, coverage decision, or Composer rounds. Retrieval completion establishes only that the configured searches ran. The responder must still acknowledge unknowns; a nonempty packet is not proof that an answer exists. Historical requests with no admissible evidence retain the explicit abstention path. Completed tool results bypass retrieval and remain available even when memory is empty.

`PerceptLLM` contains transport only. Semantic contracts live in `PerceptSpecialists`, and guarded worker processes remain restricted to one registered role. There is no new retrieval LLM.

## Registries

- `prompt_registry.py`: immutable prompt definitions and content hashes.
- `contract_registry.py`: active stage capabilities, allowed model roles, schema references, schema/prompt hashes, and links to the external capability registry.
- `capability_registry.py`: executable/discoverable capability contracts; internal memory stages are not selectable external work.
- `benchmarks/constraint_registry.json`: classified numeric bounds and calibration obligations.
- `schema.sql`: idempotent database bootstrap, including the one-subject deployment binding.

`uv run python scripts/audit_registries.py` resolves the entire live contract catalog without a DB or model. CI runs this and the numeric constraint audit. LLM artifacts retain actual prompts/schemas and registered contract identities. Dynamic personality text and actual schemas remain visible in the invocation envelope.

The legacy Composer schema/prompt is retained only in `benchmarks/legacy_composer_contract.py` for historical ablations. It is absent from active stage, capability, prompt, and output-schema registration. The old coverage/requirements module and its implementation-specific tests are removed. Their source and negative experimental evidence remain in Git history.

## Self-model epistemic policy

The proposal worker suggests evidence-linked interpretations. The review worker identifies possible opposition in a separately retrieved packet. Review output contains `opposition_indices` and `rationale`, never an establish/contest/reject verdict.

Ordinary code resolves source indices, rejects invalid links, deduplicates canonical roots, and applies the existing support, context breadth, and opposition policy. Known opposition prevents establishment. AVOWED, OBSERVED, INFERRED, ASPIRATIONAL, NORMATIVE, and SOCIAL_ATTRIBUTION remain distinct perspectives. An established derived representation is not canonical truth or identity maturity. The numeric support/breadth thresholds remain provisional and require longitudinal validation.

## Protocol transition

New interactions use `interaction-fixed-retrieval-v3`; new situation tasks use `v0.8-situation-v3`. Old incomplete workers cannot be replayed under the new contracts. Finish them on their original revision, or inspect their preserved artifacts and start a new interaction. Do not reinterpret or erase historical packages. Completed canonical evidence and independently durable artifacts are preserved.

## Research discipline

Subject IDs and individual values belong to private runtime state. No cognitive rule names subject_001 or assumes the founder's preferences. See [the setup and evaluation protocol](../engineering/IMPRINTING_SETUP.md).

The frozen previous-learning bundle can isolate retrieval changes from relearning. A run that also changes self-learning policy is an end-to-end comparison, not evidence that retrieval alone caused the difference. Preserve both successful and negative results, source-delivery metrics, model-call counts, latency, and independent human judgments. Sounding similar is only one fidelity dimension. Additional subjects and prospectively withheld cases remain necessary to test generalization.
