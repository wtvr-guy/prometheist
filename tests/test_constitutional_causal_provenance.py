from __future__ import annotations

import uuid
from datetime import datetime, timezone

from jit_agent import db
from jit_agent.attention_observation import HostResourceMetrics
from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.interaction_policy import INTERACTION_STAGES, InteractionAction, InteractionDecision
from jit_agent.interaction_runtime import handle_interaction
from jit_agent.models import MemoryPacket


NOW = datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc)


class FixedProbe:
    def capture(self) -> HostResourceMetrics:
        return HostResourceMetrics(
            platform="test",
            logical_cpu_count=8,
            cpu_utilization_percent=10,
            load_1m=0,
            memory_total_mib=16_384,
            memory_available_mib=12_000,
        )


class ProvenanceLLM:
    def classify(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        completed_results=(),
        capability_results=(),
    ) -> InteractionDecision:
        del prompt, memory_packet, capability_catalog, completed_results, capability_results
        return InteractionDecision(next_action=InteractionAction.RESPOND, capability_indices=[])

    def respond(self, prompt, memory_packet, capability_results=()):
        del prompt, memory_packet, capability_results
        return "provenance-ok"

    def select_research_candidates(self, task, packet):
        raise AssertionError("research selection is not expected in this provenance path")

    def select_focused_candidate(self, task, packet):
        raise AssertionError("focused selection is not expected in this provenance path")


def test_material_interaction_influence_has_one_reconstructable_durable_causal_path():
    conn = db.get_connection()
    try:
        conversation_id = uuid.uuid4()
        response = handle_interaction(
            conn,
            ProvenanceLLM(),
            "trace this percept",
            conversation_id,
            probe=FixedProbe(),
            clock=lambda: NOW,
        )
        assert response == "provenance-ok"

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.interaction_id, i.user_prompt_event_id, i.task_id,
                       i.assignment_id, e.event_type, e.payload_text,
                       t.status, a.task_id
                FROM attention_interactions i
                JOIN events e ON e.event_id = i.user_prompt_event_id
                JOIN attention_tasks t ON t.task_id = i.task_id
                JOIN attention_assignments a
                  ON a.scheduler_key = i.scheduler_key
                 AND a.assignment_id = i.assignment_id
                WHERE i.conversation_id = %s
                """,
                (conversation_id,),
            )
            interaction = cur.fetchone()
            assert interaction is not None
            interaction_id, prompt_event_id, task_id, assignment_id = interaction[:4]
            assert interaction[4] == "USER_PROMPT"
            assert interaction[5] == "trace this percept"
            assert interaction[6] == "COMPLETED"
            assert interaction[7] == task_id

            cur.execute(
                """
                SELECT s.step_key, s.task_id, s.assignment_id, r.result_id
                FROM attention_worker_steps s
                LEFT JOIN attention_worker_results r
                  ON r.scheduler_key = s.scheduler_key AND r.step_id = s.step_id
                WHERE s.assignment_id = %s
                ORDER BY s.created_epoch_sequence, s.step_key
                """,
                (assignment_id,),
            )
            stage_rows = cur.fetchall()
            assert len(stage_rows) == len(INTERACTION_STAGES)
            assert all(row[1] == task_id for row in stage_rows)
            assert all(row[2] == assignment_id for row in stage_rows)
            assert all(row[3] is not None for row in stage_rows)

            cur.execute(
                """
                SELECT e.assignment_ids, e.resource_observation_id,
                       e.admission_policy_version, e.assignment_policy_version,
                       o.healthy
                FROM attention_scheduling_epochs e
                JOIN attention_resource_observations o
                  ON o.scheduler_key = e.scheduler_key
                 AND o.observation_id = e.resource_observation_id
                WHERE e.assignment_ids ? %s
                ORDER BY e.epoch_sequence DESC
                LIMIT 1
                """,
                (str(assignment_id),),
            )
            epoch = cur.fetchone()
            assert epoch is not None
            assert str(assignment_id) in epoch[0]
            assert epoch[1] is not None
            assert epoch[2]
            assert epoch[3]
            assert epoch[4] is True

            cur.execute(
                """
                SELECT event_type, source, payload
                FROM events
                WHERE conversation_id = %s
                ORDER BY conversation_seq ASC
                """,
                (conversation_id,),
            )
            events = cur.fetchall()

        assert prompt_event_id is not None
        assert interaction_id is not None
        assert any(
            event_type == "SYSTEM_EVENT" and payload.get("kind") == "CAPABILITY_DECISION_ROUND"
            for event_type, _, payload in events
        )
        assert any(
            event_type == "INTERACTION_RESPONSE" and source == "attention_interaction"
            for event_type, source, _ in events
        )
    finally:
        conn.close()
