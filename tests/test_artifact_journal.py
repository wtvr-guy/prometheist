from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jit_agent import artifact_journal, event_artifact_store, llm_artifact_store


def test_interaction_artifacts_are_hash_linked_idempotent_and_complete(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    interaction_id = uuid4()
    conversation_id = uuid4()
    correlation_id = uuid4()
    task_id = uuid4()
    assignment_id = uuid4()
    prompt_event_id = uuid4()

    percept = artifact_journal.write_percept_artifact(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        user_text="remember the phrase",
        user_prompt_event_id=prompt_event_id,
    )
    first_stage = artifact_journal.write_stage_result_artifact(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        stage="V2_PRECOGNITIVE",
        output={"disposition": {"response_required": True}},
        output_refs=["memory-request:example"],
    )
    retry = artifact_journal.write_stage_result_artifact(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        stage="V2_PRECOGNITIVE",
        output={"disposition": {"response_required": True}},
        output_refs=["memory-request:example"],
    )
    assert retry["artifact_id"] == first_stage["artifact_id"]
    assert len(artifact_journal.interaction_artifacts(interaction_id)) == 2

    loaded = artifact_journal.load_stage_result_artifact(
        interaction_id,
        "V2_PRECOGNITIVE",
    )
    assert loaded == {
        "output": {"disposition": {"response_required": True}},
        "output_refs": ["memory-request:example"],
    }

    artifact_journal.write_final_disposition_artifact(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        response_required=True,
        response_text="done",
    )
    verification = artifact_journal.verify_interaction_chain(interaction_id)
    assert verification["valid"] is True
    assert verification["complete"] is True
    assert verification["artifact_count"] == 3
    assert percept["previous_artifact_id"] is None
    assert percept["payload"]["percept_kind"] == "USER_PROMPT"
    assert percept["payload"]["response_required"] is True


def test_llm_invocation_artifact_preserves_exact_stateless_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    interaction_id = uuid4()
    conversation_id = uuid4()
    correlation_id = uuid4()
    task_id = uuid4()
    assignment_id = uuid4()
    claim_id = uuid4()
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }

    artifact = llm_artifact_store.write_llm_invocation(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        stage="V2_RESPOND",
        claim_id=claim_id,
        invocation_index=0,
        kind="FINAL_RESPONSE",
        model="qwen3:4b",
        base_url="http://localhost:11434",
        system_prompt="exact system prompt",
        user_prompt="exact response context",
        schema=schema,
        max_tokens=256,
        output='{"answer":"hello"}',
        error_type=None,
        error_message=None,
    )

    assert artifact["artifact_type"] == "LLM_INVOCATION"
    assert artifact["payload"] == {
        "claim_id": str(claim_id),
        "invocation_index": 0,
        "kind": "FINAL_RESPONSE",
        "model": "qwen3:4b",
        "base_url": "http://localhost:11434",
        "system_prompt": "exact system prompt",
        "user_prompt": "exact response context",
        "schema": schema,
        "max_tokens": 256,
        "output": '{"answer":"hello"}',
        "error_type": None,
        "error_message": None,
    }
    assert artifact_journal.verify_interaction_chain(interaction_id)["valid"] is True


def test_event_artifacts_are_semantically_idempotent_and_verifiable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    event_id = uuid4()
    conversation_id = uuid4()
    correlation_id = uuid4()

    first = event_artifact_store.write_event_record(
        event_id=event_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        conversation_seq=7,
        event_type="USER_PROMPT",
        source="user",
        payload={"text": "hello"},
        payload_text="hello",
    )
    second = event_artifact_store.write_event_record(
        event_id=event_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        conversation_seq=7,
        event_type="USER_PROMPT",
        source="user",
        payload={"text": "hello"},
        payload_text="hello",
    )
    assert first["record_hash"] == second["record_hash"]
    assert event_artifact_store.verify_event_record(first)

    committed_at = datetime.now(timezone.utc)
    commit = event_artifact_store.write_event_commit(
        event_id=event_id,
        global_seq=42,
        conversation_seq=7,
        created_at=committed_at,
        schema_version=1,
    )
    retry = event_artifact_store.write_event_commit(
        event_id=event_id,
        global_seq=42,
        conversation_seq=7,
        created_at=committed_at,
        schema_version=1,
    )
    assert commit == retry
    assert event_artifact_store.verify_event_commit(commit)
    pairs = event_artifact_store.iter_event_artifacts()
    assert len(pairs) == 1
    assert pairs[0]["record"]["event_id"] == str(event_id)
    assert pairs[0]["commit"]["global_seq"] == 42
