from __future__ import annotations

import pytest

from jit_agent.budgeted_evidence_llm import BudgetedEvidenceBoundOllamaClient
from tests._cli_helpers import ollama_available


pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        (
            "Favorite color? USER_PROMPT only; otherwise INSUFFICIENT.",
            "INSUFFICIENT",
        ),
        (
            "Use SOURCE_ALPHA history only; if qualifying evidence is absent, return NO_DATA.",
            "NO_DATA",
        ),
        (
            "Consult MODEL_OUTPUT records; when no matching record exists, answer UNKNOWN.",
            "UNKNOWN",
        ),
        (
            "Use USER_PROMPT history only.",
            None,
        ),
    ],
)
def test_current_fallback_selector_distinguishes_source_labels_from_fallbacks(
    prompt: str,
    expected: str | None,
):
    client = BudgetedEvidenceBoundOllamaClient()
    try:
        selected = client._select_current_fallback_literal(prompt)
    finally:
        client._client.close()

    assert selected == expected, (
        "Current-percept fallback selection confused a source/constraint label with the "
        f"explicit no-evidence consequence: prompt={prompt!r}, selected={selected!r}, "
        f"expected={expected!r}."
    )
