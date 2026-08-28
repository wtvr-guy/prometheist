from uuid import uuid4

import pytest
from pydantic import ValidationError

from jit_agent.interaction_workpiece import (
    InteractionWorkpiece,
    ReferenceResolutionComponent,
    TerminalOutcomeComponent,
    TerminalOutcomeKind,
    UserOutputComponent,
    WorkpieceState,
    begin_interaction_workpiece,
)
from jit_agent.pre_cognitive_specialists import (
    EvidenceSufficiency,
    EvidenceSufficiencyDecision,
    EvidenceSufficiencyStationComponent,
)


def _workpiece():
    return begin_interaction_workpiece(
        interaction_id=uuid4(),
        task_id=uuid4(),
        conversation_id=uuid4(),
        correlation_id=uuid4(),
        user_text="Do the requested work.",
        user_prompt_event_id=uuid4(),
    )


def test_workpiece_contains_only_components_that_were_attached():
    workpiece = _workpiece().attach(
        ReferenceResolutionComponent(working_state_available=False)
    )
    workpiece = workpiece.attach(
        EvidenceSufficiencyStationComponent(
            phase="PRE_CAPABILITY",
            decision=EvidenceSufficiencyDecision(
                sufficiency=EvidenceSufficiency.SUFFICIENT
            ),
        )
    )

    assert [item.component_type for item in workpiece.components] == [
        "PERCEPT",
        "REFERENCE_RESOLUTION",
        "EVIDENCE_SUFFICIENCY",
    ]
    assert workpiece.state is WorkpieceState.ASSEMBLING


def test_action_can_terminalize_without_any_user_response_worker():
    workpiece = _workpiece().attach(
        TerminalOutcomeComponent(
            outcome=TerminalOutcomeKind.ACTION_COMPLETED,
            user_output_required=False,
        )
    )

    assert workpiece.state is WorkpieceState.TERMINAL
    assert workpiece.user_output() is None
    round_trip = InteractionWorkpiece.model_validate_json(workpiece.model_dump_json())
    assert round_trip == workpiece


def test_response_terminalization_requires_attached_user_output():
    with pytest.raises(ValidationError, match="user-output requirement"):
        _workpiece().attach(
            TerminalOutcomeComponent(
                outcome=TerminalOutcomeKind.RESPONSE_EMITTED,
                user_output_required=True,
            )
        )

    workpiece = _workpiece().attach(
        UserOutputComponent(
            producer_profile_id="final_response",
            text="Done.",
        )
    )
    workpiece = workpiece.attach(
        TerminalOutcomeComponent(
            outcome=TerminalOutcomeKind.RESPONSE_EMITTED,
            user_output_required=True,
        )
    )
    assert workpiece.user_output().text == "Done."


def test_no_station_can_attach_after_terminalization():
    workpiece = _workpiece().attach(
        TerminalOutcomeComponent(
            outcome=TerminalOutcomeKind.DEFERRED,
            user_output_required=False,
        )
    )
    with pytest.raises(RuntimeError, match="after workpiece terminalization"):
        workpiece.attach(
            ReferenceResolutionComponent(working_state_available=True)
        )


def test_master_schema_rejects_multiple_percepts():
    first = _workpiece()
    percept = first.components[0]
    with pytest.raises(ValidationError, match="exactly one percept"):
        InteractionWorkpiece(
            interaction_id=first.interaction_id,
            task_id=first.task_id,
            conversation_id=first.conversation_id,
            correlation_id=first.correlation_id,
            components=[percept, percept],
        )
