"""Exercise the new stage through real claims, artifacts, and database handoff."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from prometheist import artifact_journal, db
from prometheist.attention_observation import HostResourceMetrics
from prometheist.composer_coverage import MemoryRequirements
from prometheist.percept_response_runtime import PerceptStage, begin_percept
from prometheist.percept_response_worker import UserPromptLLM, _execute_claimed_user_prompt_step
from prometheist.worker_protocol import deterministic_worker_step_id
from prometheist.worker_runtime import guarded_claim_worker_step
from prometheist.worker_store import load_worker_result


class FixedProbe:
    def capture(self):
        return HostResourceMetrics(
            platform="test", logical_cpu_count=8, cpu_utilization_percent=10,
            load_1m=0, memory_total_mib=16384, memory_available_mib=12000,
        )


@pytest.mark.parametrize("model", ["test:model", "qwen3:4b-instruct"])
def test_requirement_stage_is_guarded_and_published_before_the_composer_runs(model):
    now = datetime.now(timezone.utc)
    expected = MemoryRequirements.model_validate({"requirements": [
        {"need": "communication style"}, {"need": "comparable past messages"},
    ]})
    calls = []
    with db.get_connection() as conn:
        interaction = begin_percept(conn, "Draft the update I would send.", uuid4(),
                                    probe=FixedProbe(), clock=lambda: now)
        for stage in (PerceptStage.RESOLVE_REFERENCES, PerceptStage.EVIDENCE_POLICY,
                      PerceptStage.MEMORY_REQUIREMENTS):
            step_id = deterministic_worker_step_id(interaction.assignment_id, stage.value)
            attempt = guarded_claim_worker_step(conn, step_id=step_id, worker_id=stage.value,
                                                probe=FixedProbe(), clock=lambda: now)
            assert attempt.envelope is not None
            llm = UserPromptLLM(model=model, interaction=interaction, stage=stage,
                                claim_id=attempt.envelope.claim.claim_id)
            def post(path, *, json):
                calls.append((stage, json))
                content = (
                    '{"evidence_scope":"SELF_MODEL","surface_mode":"NATURAL_LANGUAGE",'
                    '"insufficient_literal":null}'
                    if stage is PerceptStage.EVIDENCE_POLICY else expected.model_dump_json()
                )
                return SimpleNamespace(raise_for_status=lambda: None,
                                       json=lambda: {"message": {"content": content}, "response": content})
            llm._client = SimpleNamespace(post=post)
            _execute_claimed_user_prompt_step(
                conn, llm, claim_id=attempt.envelope.claim.claim_id,
                worker_id=stage.value, scheduler_key="default",
            )
            stored = load_worker_result(conn, step_id)
            journaled = artifact_journal.load_stage_result_artifact(interaction.interaction_id, stage.value)
            assert journaled["output"] == stored.output
        assert stored.output["requirements"] == expected.model_dump(mode="json")
        assert [stage for stage, _ in calls] == [PerceptStage.EVIDENCE_POLICY, PerceptStage.MEMORY_REQUIREMENTS]
        sent = calls[-1][1]
        if "messages" in sent:
            assert sent["messages"][-1]["content"] == interaction.user_text
        else:
            assert interaction.user_text in sent["prompt"]
        compose_id = deterministic_worker_step_id(interaction.assignment_id, PerceptStage.COMPOSE_MEMORY.value)
        assert load_worker_result(conn, compose_id) is None
