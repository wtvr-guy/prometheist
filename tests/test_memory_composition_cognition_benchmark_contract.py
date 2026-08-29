from pathlib import Path
import runpy
from uuid import uuid4

from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "compare_memory_composition_cognition.py"


def _namespace():
    return runpy.run_path(str(BENCHMARK), run_name="mem_adapt_006_contract")


def _evidence(index: int, content: str) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid4(),
        event_type=EventType.USER_PROMPT,
        source="contract",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=index + 1,
        global_seq=index + 1,
        content=content,
        score=1.0 - index * 0.01,
        retrieval_reasons=["LEXICAL"],
    )


def test_benchmark_import_does_not_run_native_comparison():
    namespace = _namespace()

    assert callable(namespace["run_comparison"])
    assert namespace["PACKET_LIMIT"] == 6


def test_packet_variants_share_one_pool_and_one_final_budget():
    namespace = _namespace()
    candidates = [
        _evidence(index, "shared repeated evidence" if index < 6 else "unique buried target")
        for index in range(7)
    ]
    pool = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="shared evidence", limit=32),
        supported=True,
        items=candidates,
    )

    packets = namespace["_packet_variants"](pool)

    assert set(packets) == {"top_k", "coverage_v1", "relevance_coverage_v2"}
    pool_ids = {item.source_event_id for item in pool.items}
    for packet in packets.values():
        assert len(packet.items) == 6
        assert packet.need.limit == 6
        assert {item.source_event_id for item in packet.items}.issubset(pool_ids)


def test_failure_layer_keeps_memory_and_reasoning_failures_separate():
    classify = _namespace()["_failure_layer"]

    assert classify(
        available=False,
        evidence_complete=False,
        answer_correct=False,
        model_error=None,
    ) == "retrieval_or_retention"
    assert classify(
        available=True,
        evidence_complete=False,
        answer_correct=False,
        model_error=None,
    ) == "composition"
    assert classify(
        available=True,
        evidence_complete=True,
        answer_correct=False,
        model_error=None,
    ) == "reasoning"
    assert classify(
        available=True,
        evidence_complete=True,
        answer_correct=False,
        model_error="boom",
    ) == "model_runtime"
    assert classify(
        available=True,
        evidence_complete=True,
        answer_correct=True,
        model_error=None,
    ) == "success"


def test_policy_order_rotates_deterministically():
    order = _namespace()["_policy_order"]

    assert order(0) == ("top_k", "coverage_v1", "relevance_coverage_v2")
    assert order(1) == ("coverage_v1", "relevance_coverage_v2", "top_k")
    assert order(2) == ("relevance_coverage_v2", "top_k", "coverage_v1")
    assert order(3) == order(0)
