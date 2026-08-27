from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from jit_agent.capability_registry import CapabilityDescriptor, CapabilityKind
from jit_agent.interaction_policy import InteractionAction
from jit_agent.llm import OllamaClient
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeHTTPClient:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = iter(payloads)
        self.calls: list[tuple[str, dict]] = []

    def post(self, path: str, *, json: dict) -> _FakeResponse:
        self.calls.append((path, json))
        return _FakeResponse(next(self._payloads))


def _packet() -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Which established constraint applies?"),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=uuid4(),
                event_type=EventType.USER_PROMPT,
                source="test",
                created_at=datetime.now(timezone.utc),
                conversation_id=uuid4(),
                conversation_seq=1,
                global_seq=1,
                content="Project Kestrel uses PostgreSQL directly on Windows.",
            )
        ],
    )


def _catalog() -> tuple[CapabilityDescriptor, ...]:
    return (
        CapabilityDescriptor(
            capability_id="memory.inspect",
            kind=CapabilityKind.WORKFLOW,
            description="Inspect additional memory only if required.",
        ),
    )


def _chat_respond_payload() -> dict:
    return {
        "message": {
            "content": '{"next_action":"RESPOND","capability_indices":[]}',
        },
        "done_reason": "stop",
        "eval_count": 12,
    }


def _generate_respond_payload() -> dict:
    return {
        "response": '{"next_action":"RESPOND","capability_indices":[]}',
        "done_reason": "stop",
        "eval_count": 12,
    }


def test_qwen3_structured_call_appends_latest_no_think_soft_switch():
    client = OllamaClient(base_url="http://ollama.test", model="qwen3:4b")
    fake = _FakeHTTPClient([_chat_respond_payload()])
    client._client = fake

    decision = client.classify("Answer from established memory.", _packet(), _catalog())

    assert decision.next_action is InteractionAction.RESPOND
    assert fake.calls[0][0] == "/api/chat"
    assert fake.calls[0][1]["think"] is False
    assert fake.calls[0][1]["messages"][1]["content"].endswith("/no_think")


def test_qwen3_instruct_call_uses_raw_structured_generate_transport():
    client = OllamaClient(
        base_url="http://ollama.test",
        model="qwen3:4b-instruct-2507-q4_K_M",
    )
    fake = _FakeHTTPClient([_generate_respond_payload()])
    client._client = fake

    decision = client.classify("Answer from established memory.", _packet(), _catalog())

    assert decision.next_action is InteractionAction.RESPOND
    path, request = fake.calls[0]
    assert path == "/api/generate"
    assert request["raw"] is True
    assert "think" not in request
    assert "messages" not in request
    assert request["format"]
    assert request["prompt"].startswith("<|im_start|>system\n")
    assert "<|im_end|>\n<|im_start|>user\n" in request["prompt"]
    assert "Answer from established memory." in request["prompt"]
    assert request["prompt"].endswith("<|im_end|>\n<|im_start|>assistant\n")
    assert "/no_think" not in request["prompt"]


def test_router_receives_evidence_without_application_owned_memory_metadata():
    packet = _packet()
    item = packet.items[0]
    client = OllamaClient(
        base_url="http://ollama.test",
        model="qwen3:4b-instruct-2507-q4_K_M",
    )
    fake = _FakeHTTPClient([_generate_respond_payload()])
    client._client = fake

    decision = client.classify("Answer from established memory.", packet, _catalog())

    assert decision.next_action is InteractionAction.RESPOND
    prompt = fake.calls[0][1]["prompt"]
    assert item.content in prompt
    assert f"event_type: {item.event_type.value}" in prompt
    assert str(packet.memory_request_id) not in prompt
    assert str(item.source_event_id) not in prompt
    assert str(item.conversation_id) not in prompt
    assert "conversation_seq:" not in prompt
    assert "global_seq:" not in prompt
    assert "created_at:" not in prompt
    assert "retrieval_reasons:" not in prompt
    assert "association_provenance_event_ids:" not in prompt


def test_qwen3_empty_or_thinking_only_output_retries_with_larger_budget():
    client = OllamaClient(base_url="http://ollama.test", model="qwen3:4b")
    fake = _FakeHTTPClient(
        [
            {
                "message": {"content": "", "thinking": "bounded hidden trace"},
                "done_reason": "length",
                "prompt_eval_count": 900,
                "eval_count": 48,
            },
            {
                "message": {
                    "content": '{"next_action":"RESPOND","capability_indices":[]}',
                    "thinking": "",
                },
                "done_reason": "stop",
                "prompt_eval_count": 900,
                "eval_count": 12,
            },
        ]
    )
    client._client = fake

    decision = client.classify("Answer from established memory.", _packet(), _catalog())

    assert decision.next_action is InteractionAction.RESPOND
    assert [call[1]["options"]["num_predict"] for call in fake.calls] == [48, 96]
    assert all(call[1]["messages"][1]["content"].endswith("/no_think") for call in fake.calls)


def test_qwen3_empty_output_failure_reports_metadata_without_reasoning_text():
    secret_reasoning = "THIS_REASONING_MUST_NOT_ESCAPE"
    client = OllamaClient(base_url="http://ollama.test", model="qwen3:4b")
    client._client = _FakeHTTPClient(
        [
            {
                "message": {"content": "", "thinking": secret_reasoning},
                "done_reason": "length",
                "prompt_eval_count": 900,
                "eval_count": 48,
            },
            {
                "message": {"content": "<think>still hidden</think>", "thinking": secret_reasoning},
                "done_reason": "length",
                "prompt_eval_count": 900,
                "eval_count": 96,
            },
        ]
    )

    with pytest.raises(ValueError, match="interaction capability selection failed") as exc_info:
        client.classify("Answer from established memory.", _packet(), _catalog())

    message = str(exc_info.value)
    assert secret_reasoning not in message
    assert '"thinking_length"' in message
    assert '"max_tokens":96' in message
    assert '"done_reason":"length"' in message
