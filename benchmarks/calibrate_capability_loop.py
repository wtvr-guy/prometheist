"""CAP-LOOP-001 deterministic calibration for recurrent stateless routing.

This benchmark mirrors the production round-budget semantics without invoking a
model or capability runtime. It answers two bounded questions only:

1. Is the current finite round guard non-binding for the frozen scripted
   workflows we currently require?
2. Does every finite candidate fail closed when a router never converges to an
   explicit RESPOND decision?

The scenario depths are hand-authored test obligations, not observations of a
natural workload distribution. Therefore even the smallest candidate that passes
all frozen scripts is not declared empirically optimal. Native Ollama evidence is
still required before changing or verifying the production convergence guard.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from jit_agent.interaction_policy import (
    MAX_CAPABILITY_ROUNDS,
    InteractionAction,
    InteractionDecision,
)


@dataclass(frozen=True, slots=True)
class ScriptedRound:
    decision: InteractionDecision
    catalog_size: int


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    rounds: tuple[ScriptedRound, ...]
    must_converge: bool


def _respond() -> ScriptedRound:
    return ScriptedRound(
        decision=InteractionDecision(next_action=InteractionAction.RESPOND),
        catalog_size=1,
    )


def _use(*indices: int, catalog_size: int = 2) -> ScriptedRound:
    return ScriptedRound(
        decision=InteractionDecision(
            next_action=InteractionAction.USE_CAPABILITIES,
            capability_indices=list(indices),
        ),
        catalog_size=catalog_size,
    )


def _frozen_scenarios() -> tuple[Scenario, ...]:
    return (
        Scenario("respond_without_capability", (_respond(),), True),
        Scenario("one_capability_then_respond", (_use(0), _respond()), True),
        Scenario(
            "multiple_independent_capabilities_then_respond",
            (_use(0, 1), _respond()),
            True,
        ),
        Scenario(
            "two_stage_progressive_research",
            (_use(0), _use(1), _respond()),
            True,
        ),
        Scenario(
            "three_stage_progressive_research",
            (_use(0), _use(1), _use(0), _respond()),
            True,
        ),
        Scenario(
            "nonconvergent_router",
            tuple(_use(0) for _ in range(12)),
            False,
        ),
    )


def _validate_catalog_domain(round_spec: ScriptedRound) -> None:
    if round_spec.catalog_size < 1:
        raise RuntimeError("scripted catalog size must be positive")
    if any(
        index < 0 or index >= round_spec.catalog_size
        for index in round_spec.decision.capability_indices
    ):
        raise RuntimeError("scripted capability index is outside its supplied catalog")


def execute_script(round_budget: int, scenario: Scenario) -> dict[str, object]:
    """Mirror the production EXECUTE_CAPABILITY round-budget semantics."""

    if round_budget < 1:
        raise ValueError("round_budget must be positive")

    evaluated_rounds = 0
    capability_rounds = 0
    for round_index in range(round_budget):
        if round_index >= len(scenario.rounds):
            return {
                "outcome": "SCRIPT_EXHAUSTED_WITHOUT_RESPOND",
                "evaluated_rounds": evaluated_rounds,
                "capability_rounds": capability_rounds,
            }
        round_spec = scenario.rounds[round_index]
        _validate_catalog_domain(round_spec)
        evaluated_rounds += 1
        decision = round_spec.decision
        if decision.next_action is InteractionAction.RESPOND:
            return {
                "outcome": "RESPOND",
                "evaluated_rounds": evaluated_rounds,
                "capability_rounds": capability_rounds,
            }

        capability_rounds += 1
        # Production raises here after executing the final allowed capability
        # round rather than constructing another routing round.
        if round_index + 1 >= round_budget:
            return {
                "outcome": "ROUND_LIMIT_FAIL_CLOSED",
                "evaluated_rounds": evaluated_rounds,
                "capability_rounds": capability_rounds,
            }

    raise RuntimeError("unreachable scripted capability-loop state")


def _scenario_passes(result: dict[str, object], scenario: Scenario) -> bool:
    if scenario.must_converge:
        return result["outcome"] == "RESPOND"
    return result["outcome"] == "ROUND_LIMIT_FAIL_CLOSED"


def evaluate_budget(round_budget: int, scenarios: Iterable[Scenario]) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for scenario in scenarios:
        execution = execute_script(round_budget, scenario)
        passed = _scenario_passes(execution, scenario)
        results.append(
            {
                "scenario_id": scenario.scenario_id,
                "must_converge": scenario.must_converge,
                "passed": passed,
                **execution,
            }
        )
    return {
        "round_budget": round_budget,
        "passed": all(bool(item["passed"]) for item in results),
        "scenarios": results,
    }


def run_calibration() -> dict[str, object]:
    scenarios = _frozen_scenarios()
    candidate_budgets = tuple(range(1, 9))
    evaluations = [evaluate_budget(value, scenarios) for value in candidate_budgets]
    passing_budgets = [
        int(item["round_budget"])
        for item in evaluations
        if bool(item["passed"])
    ]
    if not passing_budgets:
        raise RuntimeError("CAP-LOOP-001 has no passing finite budget")

    current = next(
        item for item in evaluations
        if item["round_budget"] == MAX_CAPABILITY_ROUNDS
    )
    if not bool(current["passed"]):
        raise RuntimeError(
            "production MAX_CAPABILITY_ROUNDS truncates a frozen scripted workflow"
        )

    nonconvergent = next(
        scenario for scenario in scenarios if scenario.scenario_id == "nonconvergent_router"
    )
    nonconvergent_fail_closed = all(
        execute_script(value, nonconvergent)["outcome"] == "ROUND_LIMIT_FAIL_CLOSED"
        for value in candidate_budgets
    )
    if not nonconvergent_fail_closed:
        raise RuntimeError("a finite candidate failed to stop a nonconvergent router")

    return {
        "schema_version": 1,
        "benchmark_id": "CAP-LOOP-001",
        "result": "NATIVE_REQUIRED",
        "production_round_budget": MAX_CAPABILITY_ROUNDS,
        "candidate_budgets": list(candidate_budgets),
        "passing_budgets": passing_budgets,
        "minimum_passing_scripted_budget": min(passing_budgets),
        "production_budget_passes_frozen_scripts": True,
        "all_finite_candidates_fail_closed_on_nonconvergence": True,
        "evaluations": evaluations,
        "decision": (
            "The current round guard is non-binding for the frozen scripted workloads and "
            "fails closed for a nonconvergent router. The three-stage scripted workload makes "
            "four the smallest passing budget in this fixture, but that fixture depth is a test "
            "obligation rather than an empirical workload distribution. The exact production "
            "bound therefore remains NATIVE_REQUIRED pending real local-model evidence."
        ),
    }


def main() -> None:
    print(json.dumps(run_calibration(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
