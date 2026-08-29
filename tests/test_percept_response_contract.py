from __future__ import annotations

import pytest

from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.percept_response_runtime import (
    MemorySufficiencyDecision,
    PreCognitiveDisposition,
    _external_capability_catalog,
)


def test_pre_cognitive_disposition_allows_no_work_no_response() -> None:
    decision = PreCognitiveDisposition(response_required=False, capability_indices=[])
    assert decision.response_required is False
    assert decision.capability_indices == []


def test_pre_cognitive_disposition_rejects_duplicate_indices() -> None:
    with pytest.raises(ValueError):
        PreCognitiveDisposition(response_required=True, capability_indices=[0, 0])


def test_composer_sufficient_contract_has_no_deficit() -> None:
    decision = MemorySufficiencyDecision(sufficient=True, memory_deficit=None)
    assert decision.sufficient is True
    assert decision.memory_deficit is None


def test_composer_insufficient_contract_requires_semantic_deficit() -> None:
    with pytest.raises(ValueError):
        MemorySufficiencyDecision(sufficient=False, memory_deficit=None)


def test_legacy_memory_research_modes_are_not_pre_cognitive_capabilities() -> None:
    catalog = _external_capability_catalog(DEFAULT_REGISTRY)
    assert catalog == ()
