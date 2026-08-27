from datetime import datetime, timezone
from uuid import uuid4

import pytest

from jit_agent import llm
from jit_agent.capability_registry import CapabilityDescriptor, CapabilityKind
from jit_agent.interaction_policy import InteractionAction
from jit_agent.llm import _strip_thinking
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket


class _FakeResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


class _FakeHTTPClient:
    def __init__(self, contents):
        self._contents = iter(contents)
        self.calls = []

    def post(self, path, *, json):
        self.calls.append((path, json))
        return _FakeResponse(next(self._contents))


def test_strip_thinking_preserves_plain_answer():
    assert _strip_thinking("final answer") == "final answer"


def test_strip_thinking_removes_complete_think_block():
    assert _strip_thinking("<think>hidden reasoning</think>final answer") == "final answer"


def test_strip_thinking_uses_content_after_unmatched_closing_tag():
    assert _strip_thinking("hidden reasoning</think>final answer") == "final answer"


def test_strip_thinking_rejects_truncated_response_with_no_post_tag_answer():
    with pytest.raises(ValueError, match="no answer content"):
        _strip_thinking("hidden reasoning</think>")


def test_strip_thinking_rejects_think_only_response():
    with pytest.raises(ValueError, match="no answer content"):
        _strip_thinking("<think>hidden reasoning</think>")


def test_strip_thinking_rejects_empty_response():
    with pytest.raises(ValueError, match="no answer content"):
        _strip_thinking("   ")


def test_response_prompt_does_not_leak_acceptance_scenario_facts():
    prompt = llm._RESPOND_SYSTEM_PROMPT.casefold()
    assert "project kestrel" not in prompt
    assert "virtualization is disabled" not in prompt
    assert "blueharbor" not in prompt
    assert "vx-" not in prompt


def test_user_facing_answers_use_a_deterministic_structured_envelope():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(['{"answer":"Final answer only."}'])
    client._client = fake_http

    assert client.respond("Question", None) == "Final answer only."

    path, payload = fake_http.calls[0]
    assert path == "/api/chat"
    assert payload["format"]["required"] == ["answer"]
    assert payload["think"] is False
    assert payload["stream"] is False
    assert payload["options"] == {"num_predict": 256, "temperature": 0}


def test_user_facing_answer_retries_invalid_structured_output():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(["not-json", '{"answer":"Recovered answer."}'])
    client._client = fake_http

    assert client.respond("Question", None) == "Recovered answer."
    assert len(fake_http.calls) == 2


def test_user_facing_answer_fails_closed_after_two_invalid_outputs():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    client._client = _FakeHTTPClient(["not-json", '{"answer":"   "}'])

    with pytest.raises(ValueError, match="model answer failed to validate"):
        client.respond("Question", None)


def _evidence(event_type: EventType, content: str, seq: int) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid4(),
        event_type=event_type,
        source="test",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=seq,
        global_seq=seq,
        content=content,
    )


def _packet(*contents: str) -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Question"),
        supported=bool(contents),
        items=[
            _evidence(EventType.USER_PROMPT, content, index + 1)
            for index, content in enumerate(contents)
        ],
    )


def test_capability_selection_returns_only_explicit_action_and_bounded_indices():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(
        ['{"next_action":"USE_CAPABILITIES","capability_indices":[1,0]}']
    )
    client._client = fake_http
    catalog = (
        CapabilityDescriptor(
            capability_id="alpha",
            kind=CapabilityKind.TOOL,
            description="First test capability.",
        ),
        CapabilityDescriptor(
            capability_id="beta",
            kind=CapabilityKind.WORKFLOW,
            description="Second test capability.",
        ),
    )

    decision = client.classify("Do the task", _packet(), catalog)

    assert decision.next_action is InteractionAction.USE_CAPABILITIES
    assert decision.capability_indices == [1, 0]
    payload = fake_http.calls[0][1]
    assert set(payload["format"]["properties"]) == {
        "next_action",
        "capability_indices",
    }
    assert "alpha" in payload["messages"][1]["content"]
    assert "beta" in payload["messages"][1]["content"]


def test_deeper_research_selects_packet_candidates_not_query_text():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(['{"candidate_indices":[1,0]}'])
    client._client = fake_http
    packet = _packet("candidate A", "candidate B")

    selection = client.select_research_candidates("Investigate", packet)

    assert selection.candidate_indices == [1, 0]
    payload = fake_http.calls[0][1]
    assert set(payload["format"]["properties"]) == {"candidate_indices"}
    model_input = payload["messages"][1]["content"]
    assert "candidate_index: 0" in model_input
    assert "candidate_index: 1" in model_input


def test_cross_reference_selects_two_or_more_packet_candidates_without_relation_text():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(['{"candidate_indices":[2,0]}'])
    client._client = fake_http
    packet = _packet("candidate A", "candidate B", "candidate C")

    selection = client.select_cross_reference_candidates("Compare evidence", packet)

    assert selection.candidate_indices == [2, 0]
    payload = fake_http.calls[0][1]
    assert set(payload["format"]["properties"]) == {"candidate_indices"}
    assert "candidate_index: 0" in payload["messages"][1]["content"]
    assert "candidate_index: 2" in payload["messages"][1]["content"]


def test_focused_recall_selects_exactly_one_packet_candidate():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(['{"candidate_index":1}'])
    client._client = fake_http
    packet = _packet("candidate A", "candidate B")

    selection = client.select_focused_candidate("Resolve ambiguity", packet)

    assert selection.candidate_index == 1
    payload = fake_http.calls[0][1]
    assert set(payload["format"]["properties"]) == {"candidate_index"}


def test_verbatim_placeholders_prevent_model_from_respelling_opaque_literals():
    exact_code = "A66673AD"
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="What codename did I give Project Oriole?"),
        supported=True,
        items=[
            _evidence(
                EventType.USER_PROMPT,
                f"The codename for Project Oriole is {exact_code}.",
                1,
            )
        ],
    )
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(['{"answer":"The codename is [[VERBATIM_0]]."}'])
    client._client = fake_http

    answer = client.respond("What codename did I give Project Oriole?", packet)

    assert answer == f"The codename is {exact_code}."
    model_input = fake_http.calls[0][1]["messages"][1]["content"]
    assert exact_code not in model_input
    assert "[[VERBATIM_0]]" in model_input


def test_verbatim_placeholders_cover_hyphenated_labels_and_current_input():
    exact_label = "BlueHarbor-4E0FF9"
    literal_to_placeholder, placeholder_to_literal = llm._build_verbatim_placeholder_maps(
        f"Call this plan {exact_label}."
    )

    assert literal_to_placeholder == {exact_label: "[[VERBATIM_0]]"}
    masked = llm._mask_verbatim_literals(
        f"Call this plan {exact_label}.",
        literal_to_placeholder,
    )
    assert masked == "Call this plan [[VERBATIM_0]]."
    assert llm._restore_verbatim_literals(masked, placeholder_to_literal) == (
        f"Call this plan {exact_label}."
    )
