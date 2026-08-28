import uuid

from jit_agent.final_response_directive import (
    FinalReadinessDecision,
    FinalResponseAction,
)
from jit_agent.models import MemoryNeed, MemoryPacket
from jit_agent.pre_cognitive_response_runtime import _terminal_assessment
from jit_agent.pre_cognitive_workers import (
    CognitiveDisposition,
    CognitivePhase,
    EvidenceState,
    IntentMode,
    PreCognitiveAssessment,
)


def _packet() -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="terminal readiness", limit=1),
        supported=False,
        items=[],
    )


def _assessment(disposition: CognitiveDisposition) -> PreCognitiveAssessment:
    if disposition is CognitiveDisposition.RESPOND:
        evidence_state = EvidenceState.ACTIVATED_MEMORY_SUFFICIENT
        capability_indices = []
    elif disposition is CognitiveDisposition.ACQUIRE_CAPABILITIES:
        evidence_state = EvidenceState.MORE_INTERNAL_EVIDENCE_REQUIRED
        capability_indices = [0]
    else:
        evidence_state = EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK
        capability_indices = []
    return PreCognitiveAssessment(
        phase=CognitivePhase.PRE_CAPABILITY,
        disposition=disposition,
        intent_mode=IntentMode.OTHER,
        evidence_state=evidence_state,
        claim_scopes=[],
        requirement_flags=[],
        capability_indices=capability_indices,
    )


def test_pre_cognitive_respond_remains_terminal_fast_path(monkeypatch):
    def unexpected_readiness(*args, **kwargs):
        del args, kwargs
        raise AssertionError("final readiness must not run after established sufficiency")

    monkeypatch.setattr(
        "jit_agent.pre_cognitive_response_runtime._load_or_create_final_readiness",
        unexpected_readiness,
    )
    pre = _assessment(CognitiveDisposition.RESPOND)
    effective, action, evidence_state = _terminal_assessment(
        object(),
        object(),
        interaction=object(),
        acquisition={"pre_assessment": pre.model_dump(mode="json"), "post_assessment": None},
        final_packet=_packet(),
        capability_results=(),
    )

    assert effective == pre
    assert action is FinalResponseAction.RESPOND
    assert evidence_state == EvidenceState.ACTIVATED_MEMORY_SUFFICIENT.value


def test_acquisition_abstain_must_receive_fresh_terminal_readiness(monkeypatch):
    calls = []

    def recovered_readiness(conn, llm, *, interaction, final_packet, capability_results):
        calls.append((conn, llm, interaction, final_packet, capability_results))
        return FinalReadinessDecision(
            action=FinalResponseAction.RESPOND,
            evidence_state=EvidenceState.ACTIVATED_MEMORY_SUFFICIENT.value,
        )

    monkeypatch.setattr(
        "jit_agent.pre_cognitive_response_runtime._load_or_create_final_readiness",
        recovered_readiness,
    )
    pre = _assessment(CognitiveDisposition.ABSTAIN)
    packet = _packet()
    conn = object()
    llm = object()
    interaction = object()

    effective, action, evidence_state = _terminal_assessment(
        conn,
        llm,
        interaction=interaction,
        acquisition={"pre_assessment": pre.model_dump(mode="json"), "post_assessment": None},
        final_packet=packet,
        capability_results=(),
    )

    assert effective == pre
    assert action is FinalResponseAction.RESPOND
    assert evidence_state == EvidenceState.ACTIVATED_MEMORY_SUFFICIENT.value
    assert calls == [(conn, llm, interaction, packet, ())]


def test_terminal_abstain_requires_fresh_readiness_to_agree(monkeypatch):
    def confirmed_readiness(*args, **kwargs):
        del args, kwargs
        return FinalReadinessDecision(
            action=FinalResponseAction.ABSTAIN,
            evidence_state=EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK.value,
        )

    monkeypatch.setattr(
        "jit_agent.pre_cognitive_response_runtime._load_or_create_final_readiness",
        confirmed_readiness,
    )
    pre = _assessment(CognitiveDisposition.ABSTAIN)

    effective, action, evidence_state = _terminal_assessment(
        object(),
        object(),
        interaction=object(),
        acquisition={"pre_assessment": pre.model_dump(mode="json"), "post_assessment": None},
        final_packet=_packet(),
        capability_results=(),
    )

    assert effective == pre
    assert action is FinalResponseAction.ABSTAIN
    assert evidence_state == EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK.value