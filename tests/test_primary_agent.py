import re
import uuid

import pytest

from jit_agent import db, event_store, primary_agent
from jit_agent.models import (
    AgentAction,
    AgentDecision,
    EventType,
    MemoryPacket,
    SemanticRetrievalIntentV1,
    SemanticRetrievalTarget,
    SemanticTemporalFocus,
)


class FakeLLM:
    """Deterministic stateless stand-in for Primary and specialist roles."""

    def classify(self, prompt: str) -> AgentDecision:
        lowered = prompt.lower()
        if "use a specialist" in lowered:
            if "deployment" in lowered or "plan" in lowered or "propose" in lowered:
                return AgentDecision(
                    action=AgentAction.REQUEST_CAPABILITY,
                    capability_query="planning and recommendation functionality",
                )
            if "atlas" in lowered or "compare" in lowered or "changed" in lowered:
                return AgentDecision(
                    action=AgentAction.REQUEST_CAPABILITY,
                    capability_query="comparison and analysis functionality",
                )
        if "what" in lowered and (
            "remember" in lowered or "number" in lowered or "codename" in lowered
        ):
            if "codename" in lowered:
                recall_input = "Project Oriole codename"
            else:
                recall_input = "remember"
            return AgentDecision(
                action=AgentAction.REQUEST_CAPABILITY,
                capability_query="persisted internal history access",
                capability_input=recall_input,
            )
        return AgentDecision(action=AgentAction.RESPOND_DIRECTLY)

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        if memory_packet and memory_packet.items:
            match = re.search(r"[0-9a-fA-F]{6,}", memory_packet.items[0].content)
            if match:
                return f"You asked me to remember {match.group(0)}."
            return memory_packet.items[0].content
        if "hello" in prompt.lower():
            return "Hello! How can I help?"
        return "Got it."

    def decide_specialist_action(
        self,
        specialist_instruction: str,
        task: str,
    ) -> AgentDecision:
        lowered = task.lower()
        if "deployment" in lowered:
            subject = "deployment requirement"
        elif "atlas" in lowered:
            subject = "Project Atlas schedule change"
        else:
            subject = task
        return AgentDecision(
            action=AgentAction.REQUEST_CAPABILITY,
            capability_query="persisted internal history access",
            capability_input=subject,
        )

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket | None,
    ) -> str:
        if packet and packet.items:
            return packet.items[0].content
        return "Completed from supplied task context."


class LossyCapabilityCueLLM(FakeLLM):
    """Classifier whose discovery and invocation hints are intentionally useless."""

    def classify(self, prompt: str) -> AgentDecision:
        return AgentDecision(
            action=AgentAction.REQUEST_CAPABILITY,
            capability_query="unrelated additional functionality",
            capability_input="unrelated compressed information cue",
        )


class PlanningMisrouteLLM(FakeLLM):
    """Model decision that mistakes a continuity question for a planning task."""

    def classify(self, prompt: str) -> AgentDecision:
        return AgentDecision(
            action=AgentAction.REQUEST_CAPABILITY,
            capability_query="planning and recommendation functionality",
        )


class SemanticSpecialistLLM(FakeLLM):
    """Specialist produces a semantically correct but lexically weak memory cue."""

    def decide_specialist_action(
        self,
        specialist_instruction: str,
        task: str,
    ) -> AgentDecision:
        return AgentDecision(
            action=AgentAction.REQUEST_CAPABILITY,
            capability_query="persisted internal history access",
            capability_input="prior internal constraint for the current rollout",
            retrieval_intent=SemanticRetrievalIntentV1(
                target=SemanticRetrievalTarget.PROCEDURE,
                temporal_focus=SemanticTemporalFocus.UNSPECIFIED,
            ),
        )


class FakeEmbeddingProvider:
    provider_name = "fake"
    model = "fake-nested-semantic-v1"
    dimensions = 1536

    @staticmethod
    def _vector(bucket: int) -> list[float]:
        values = [0.0] * 1536
        values[bucket] = 1.0
        return values

    @classmethod
    def _bucket(cls, text: str) -> int:
        lowered = text.casefold()
        if "deployment" in lowered or "rollout" in lowered or "operational requirement" in lowered:
            return 0
        return 1

    def embed_documents(self, texts):
        return [self._vector(self._bucket(text)) for text in texts]

    def embed_query(self, query: str, instruction: str):
        return self._vector(self._bucket(query + " " + instruction))


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def test_acceptance_scenario_three_interactions(conn):
    conversation_id = uuid.uuid4()

    reply1 = primary_agent.handle_interaction(conn, FakeLLM(), "hello", conversation_id)
    assert reply1

    token = uuid.uuid4().hex[:10]
    reply2 = primary_agent.handle_interaction(
        conn, FakeLLM(), f"I want you to remember {token}.", conversation_id
    )
    assert reply2

    reply3 = primary_agent.handle_interaction(
        conn, FakeLLM(), "what was that number I just asked you to remember?", conversation_id
    )
    assert token in reply3


def test_memory_spans_conversations_by_default(conn):
    conv_a = uuid.uuid4()
    conv_b = uuid.uuid4()

    token = uuid.uuid4().hex[:10]
    primary_agent.handle_interaction(conn, FakeLLM(), f"remember {token}", conv_a)

    reply = primary_agent.handle_interaction(
        conn, FakeLLM(), "what number did I ask you to remember?", conv_b
    )
    assert token in reply


def test_primary_discovers_internal_memory_and_preserves_exact_user_cue(conn):
    fact_conversation = uuid.uuid4()
    recall_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()
    question = "What codename did I give Project Oriole?"

    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        f"The codename for Project Oriole is {token}.",
        fact_conversation,
    )

    reply = primary_agent.handle_interaction(
        conn,
        LossyCapabilityCueLLM(),
        question,
        recall_conversation,
    )
    assert token in reply

    events = event_store.get_events_by_conversation(conn, recall_conversation)
    decision_event = next(event for event in events if event.event_type == EventType.AGENT_DECISION)
    capability_packet = next(
        event for event in events if event.event_type == EventType.CAPABILITY_PACKET
    )
    request_event = next(event for event in events if event.event_type == EventType.MEMORY_REQUEST)
    packet_event = next(event for event in events if event.event_type == EventType.MEMORY_PACKET)

    assert decision_event.payload["capability_query"] == "unrelated additional functionality"
    assert decision_event.payload["capability_input"] == "unrelated compressed information cue"
    selected = capability_packet.payload["packet"]["matches"][0]["descriptor"]["capability_id"]
    assert selected == "internal_memory"
    assert capability_packet.payload["packet"]["selected_query_role"] == "canonical"
    assert request_event.payload["need"]["query_text"] == question
    assert request_event.payload["need"]["supplemental_query_texts"] == [
        "unrelated compressed information cue"
    ]
    assert packet_event.payload["packet"]["supported"] is True
    assert packet_event.payload["packet"]["retrieval_trace"]["selected_query_role"] == "canonical"


def test_direct_memory_use_does_not_create_agent_delegation(conn):
    source_conversation = uuid.uuid4()
    recall_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()

    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        f"The codename for Project Oriole is {token}.",
        source_conversation,
    )
    answer = primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        "What codename did I give Project Oriole?",
        recall_conversation,
    )

    assert token in answer
    events = event_store.get_events_by_conversation(conn, recall_conversation)
    assert EventType.CAPABILITY_REQUEST in {event.event_type for event in events}
    assert EventType.MEMORY_REQUEST in {event.event_type for event in events}
    assert EventType.AGENT_DELEGATION not in {event.event_type for event in events}
    assert EventType.AGENT_RESULT not in {event.event_type for event in events}


class RaisingLLM(FakeLLM):
    def classify(self, prompt: str) -> AgentDecision:
        raise RuntimeError("boom")


def test_classify_failure_is_persisted_as_error_event(conn):
    conversation_id = uuid.uuid4()

    with pytest.raises(RuntimeError):
        primary_agent.handle_interaction(conn, RaisingLLM(), "hello", conversation_id)

    events = event_store.get_events_by_conversation(conn, conversation_id)
    error_events = [e for e in events if e.event_type == EventType.ERROR]
    assert len(error_events) == 1
    assert error_events[0].payload["stage"] == "classify"
    assert error_events[0].payload["error_type"] == "RuntimeError"


def test_handle_interaction_needs_no_shared_python_state(conn):
    conversation_id = uuid.uuid4()

    reply1 = primary_agent.handle_interaction(conn, FakeLLM(), "hello", conversation_id)
    reply2 = primary_agent.handle_interaction(conn, FakeLLM(), "hello again", conversation_id)

    assert reply1 and reply2


@pytest.mark.parametrize(
    "prompt",
    [
        "Why did we rule that one out?",
        "Name that approach and explain why we ruled it out.",
        "Which of those approaches conflicts with the rule?",
        "What did you just decide?",
        "What nickname are we using?",
        "Between A and B, which of those options is cheaper, and what nickname are we using?",
        "Compare A and B; which of those plans did we previously choose?",
        "Compare that plan with A and B, and tell me which of those options is cheaper.",
    ],
)
def test_explicit_conversation_references_require_persisted_context(prompt):
    assert primary_agent._requires_persisted_context(prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "Please call this plan Blue Harbor.",
        "Compare Docker with native PostgreSQL.",
        "Explain why virtualization matters in general.",
        "Between Docker and native PostgreSQL, which of those options is simpler?",
        "Compare Docker and native PostgreSQL; which of those approaches is simpler?",
        "These options are Docker and native PostgreSQL; which of those options is simpler?",
    ],
)
def test_self_contained_messages_do_not_trigger_the_continuity_policy(prompt):
    assert not primary_agent._requires_persisted_context(prompt)


def test_continuity_policy_overrides_an_ungrounded_direct_response(conn):
    conversation_id = uuid.uuid4()
    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        "Docker was an option, but we ruled it out because virtualization is disabled.",
        conversation_id,
    )

    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        "Why did we rule that one out?",
        conversation_id,
    )

    events = event_store.get_events_by_conversation(conn, conversation_id)
    second_prompt = [event for event in events if event.event_type == EventType.USER_PROMPT][-1]
    correlated = [
        event for event in events if event.correlation_id == second_prompt.correlation_id
    ]
    decision = next(event for event in correlated if event.event_type == EventType.AGENT_DECISION)

    assert decision.payload["action"] == AgentAction.REQUEST_CAPABILITY.value
    assert decision.payload["policy_override"] == primary_agent.CONTINUITY_POLICY
    assert EventType.MEMORY_REQUEST in {event.event_type for event in correlated}


def test_continuity_policy_preserves_a_classifier_memory_cue():
    decision = AgentDecision(
        action=AgentAction.REQUEST_CAPABILITY,
        capability_query="persisted internal history access",
        capability_input="the prior deployment constraint and its reason",
    )

    routed, policy = primary_agent._apply_continuity_policy(
        "Why did we rule that one out?",
        decision,
    )

    assert policy == primary_agent.CONTINUITY_POLICY
    assert routed.capability_input == decision.capability_input


@pytest.mark.parametrize(
    "prompt",
    [
        "Use a specialist to expand that plan.",
        "Use the planning specialist to expand that plan using prior constraints.",
        "Ask the analysis agent to compare that plan with the baseline.",
    ],
)
def test_explicit_specialist_operation_is_not_replaced_by_memory_only_routing(prompt):
    decision = AgentDecision(
        action=AgentAction.REQUEST_CAPABILITY,
        capability_query="planning and recommendation functionality",
        capability_input="expand the plan using prior constraints",
    )

    routed, policy = primary_agent._apply_continuity_policy(
        prompt,
        decision,
    )

    assert routed == decision
    assert policy is None


@pytest.mark.parametrize(
    "prompt",
    [
        "What nickname are we using for this plan, and which approach did you just rule out?",
        "Name that approach and explain why we ruled it out, in one sentence.",
    ],
)
def test_continuity_policy_constrains_a_specialist_misroute_to_memory(conn, prompt):
    conversation_id = uuid.uuid4()

    primary_agent.handle_interaction(
        conn,
        PlanningMisrouteLLM(),
        prompt,
        conversation_id,
    )

    events = event_store.get_events_by_conversation(conn, conversation_id)
    capability_packet = next(
        event for event in events if event.event_type == EventType.CAPABILITY_PACKET
    )
    selected = capability_packet.payload["packet"]["matches"][0]["descriptor"]["capability_id"]

    assert selected == "internal_memory"
    assert EventType.MEMORY_REQUEST in {event.event_type for event in events}
    assert EventType.AGENT_DELEGATION not in {event.event_type for event in events}


@pytest.mark.parametrize(
    "fact,task,expected_specialist,expected_memory_input",
    [
        (
            "My deployment requirement is {token}.",
            "Use a specialist to propose a deployment plan that explicitly includes my deployment requirement.",
            "planning_specialist",
            "deployment requirement",
        ),
        (
            "The Project Atlas schedule changed from September to {token}.",
            "Use a specialist to compare the Project Atlas schedule change and state the new schedule.",
            "analysis_specialist",
            "Project Atlas schedule change",
        ),
    ],
)
def test_multiple_specialists_independently_discover_internal_memory(
    conn,
    fact,
    task,
    expected_specialist,
    expected_memory_input,
):
    fact_conversation = uuid.uuid4()
    task_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()

    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        fact.format(token=token),
        fact_conversation,
    )
    answer = primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        task,
        task_conversation,
    )

    assert token in answer
    events = event_store.get_events_by_conversation(conn, task_conversation)
    event_types = [event.event_type for event in events]
    assert EventType.AGENT_DELEGATION in event_types
    assert EventType.MEMORY_REQUEST in event_types
    assert EventType.MEMORY_PACKET in event_types
    assert EventType.AGENT_RESULT in event_types
    assert EventType.AGENT_RESPONSE in event_types

    correlations = {event.correlation_id for event in events}
    assert len(correlations) == 1

    capability_packets = [
        event for event in events if event.event_type == EventType.CAPABILITY_PACKET
    ]
    assert len(capability_packets) == 2
    first_selected = capability_packets[0].payload["packet"]["matches"][0]["descriptor"][
        "capability_id"
    ]
    second_selected = capability_packets[1].payload["packet"]["matches"][0]["descriptor"][
        "capability_id"
    ]
    assert first_selected == expected_specialist
    assert second_selected == "internal_memory"

    delegation_event = next(
        event for event in events if event.event_type == EventType.AGENT_DELEGATION
    )
    result_event = next(event for event in events if event.event_type == EventType.AGENT_RESULT)
    memory_request = next(event for event in events if event.event_type == EventType.MEMORY_REQUEST)

    assert delegation_event.payload["specialist"] == expected_specialist
    assert result_event.payload["specialist"] == expected_specialist
    assert memory_request.source == expected_specialist
    assert memory_request.payload["need"]["query_text"] == expected_memory_input
    assert token in result_event.payload["text"]


def test_nested_specialist_semantic_fallback_propagates_provider_and_intent(conn):
    fact_conversation = uuid.uuid4()
    task_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()

    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        f"My deployment requirement is {token}.",
        fact_conversation,
    )
    answer = primary_agent.handle_interaction(
        conn,
        SemanticSpecialistLLM(),
        "Use a specialist to propose one deployment step that respects my prior rollout constraint.",
        task_conversation,
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert token in answer
    events = event_store.get_events_by_conversation(conn, task_conversation)
    memory_request = next(event for event in events if event.event_type == EventType.MEMORY_REQUEST)
    memory_packet = next(event for event in events if event.event_type == EventType.MEMORY_PACKET)

    assert memory_request.source == "planning_specialist"
    assert memory_request.payload["need"]["semantic_intent"] == {
        "schema_version": 1,
        "target": "PROCEDURE",
        "temporal_focus": "UNSPECIFIED",
    }
    assert memory_packet.payload["packet"]["supported"] is False
    assert memory_packet.payload["packet"]["items"][0]["evidence_status"] == "SEMANTIC_CANDIDATE"
    assert memory_packet.payload["packet"]["retrieval_trace"]["semantic"]["candidate_limit"] == 10
