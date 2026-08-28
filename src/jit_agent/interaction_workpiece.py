"""Typed cumulative workpiece for demand-driven Prometheist execution.

An interaction workpiece is the application-owned aggregate that moves through
conditional execution stations. Each station contributes one small validated
component. The complete terminal workpiece is a materialized audit/replay view;
append-only events and durable worker results remain the authoritative incremental
history underneath it.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from jit_agent.capability_registry import CapabilityDescriptor, CapabilityExecutionPlan
from jit_agent.capability_runtime import CapabilityExecution
from jit_agent.final_response_directive import FinalResponseDirective
from jit_agent.models import MemoryPacket
from jit_agent.pre_cognitive_specialists import (
    CapabilitySelectionStationComponent,
    EvidenceSufficiencyStationComponent,
)
from jit_agent.pre_cognitive_workers import CognitivePhase, PreCognitiveAssessment


INTERACTION_WORKPIECE_VERSION = "interaction-workpiece-v1"


class WorkpieceState(str, Enum):
    ASSEMBLING = "ASSEMBLING"
    TERMINAL = "TERMINAL"


class TerminalOutcomeKind(str, Enum):
    """General terminal outcomes; user-facing response is only one possibility."""

    RESPONSE_EMITTED = "RESPONSE_EMITTED"
    ABSTAINED = "ABSTAINED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    ACTION_FAILED = "ACTION_FAILED"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    DEFERRED = "DEFERRED"


class PerceptComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_type: Literal["PERCEPT"] = "PERCEPT"
    producer_profile_id: Literal["interaction_intake"] = "interaction_intake"
    user_text: str
    user_prompt_event_id: UUID


class ReferenceResolutionComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_type: Literal["REFERENCE_RESOLUTION"] = "REFERENCE_RESOLUTION"
    producer_profile_id: Literal["reference_resolver"] = "reference_resolver"
    working_state_available: bool


class AttentionApertureComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_type: Literal["ATTENTION_APERTURE"] = "ATTENTION_APERTURE"
    producer_profile_id: Literal["attention_aperture"] = "attention_aperture"
    aperture_version: str = Field(min_length=1)
    memory_packet: MemoryPacket


class PreCognitiveControlComponent(BaseModel):
    """Application-composed control checkpoint for one pre-cognitive phase."""

    model_config = ConfigDict(extra="forbid")
    component_type: Literal["PRE_COGNITIVE_CONTROL"] = "PRE_COGNITIVE_CONTROL"
    producer_profile_id: Literal["pre_cognitive_assessment"] = "pre_cognitive_assessment"
    phase: CognitivePhase
    assessment: PreCognitiveAssessment
    capability_catalog: list[CapabilityDescriptor]
    execution_plan: CapabilityExecutionPlan

    @model_validator(mode="after")
    def phase_matches_assessment(self) -> "PreCognitiveControlComponent":
        if self.assessment.phase is not self.phase:
            raise ValueError("pre-cognitive workpiece component phase mismatch")
        self.assessment.validate_catalog(tuple(self.capability_catalog))
        return self


class CapabilityWorkComponent(BaseModel):
    """One executed capability tranche in chronological workpiece order."""

    model_config = ConfigDict(extra="forbid")
    component_type: Literal["CAPABILITY_WORK"] = "CAPABILITY_WORK"
    producer_profile_id: Literal["capability_execution"] = "capability_execution"
    tranche_index: int = Field(ge=0)
    executions: list[CapabilityExecution] = Field(min_length=1)

    @model_validator(mode="after")
    def tranche_matches_executions(self) -> "CapabilityWorkComponent":
        if any(item.round_index != self.tranche_index for item in self.executions):
            raise ValueError("capability workpiece tranche does not match execution round")
        return self


class FinalEvidenceComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_type: Literal["FINAL_EVIDENCE"] = "FINAL_EVIDENCE"
    producer_profile_id: Literal["evidence_composer"] = "evidence_composer"
    memory_packet: MemoryPacket


class FinalResponseDirectiveComponent(BaseModel):
    """Current interactive terminal authority; future action paths need not use it."""

    model_config = ConfigDict(extra="forbid")
    component_type: Literal["FINAL_RESPONSE_DIRECTIVE"] = "FINAL_RESPONSE_DIRECTIVE"
    producer_profile_id: Literal["pre_cognitive_finalizer"] = "pre_cognitive_finalizer"
    directive: FinalResponseDirective


class UserOutputComponent(BaseModel):
    """Optional user-visible product of a terminal path."""

    model_config = ConfigDict(extra="forbid")
    component_type: Literal["USER_OUTPUT"] = "USER_OUTPUT"
    producer_profile_id: str = Field(min_length=1)
    text: str


class TerminalOutcomeComponent(BaseModel):
    """Application-owned terminalization result independent of chat semantics."""

    model_config = ConfigDict(extra="forbid")
    component_type: Literal["TERMINAL_OUTCOME"] = "TERMINAL_OUTCOME"
    producer_profile_id: Literal["terminalizer"] = "terminalizer"
    outcome: TerminalOutcomeKind
    user_output_required: bool = False


InteractionComponent = Annotated[
    PerceptComponent
    | ReferenceResolutionComponent
    | AttentionApertureComponent
    | EvidenceSufficiencyStationComponent
    | CapabilitySelectionStationComponent
    | PreCognitiveControlComponent
    | CapabilityWorkComponent
    | FinalEvidenceComponent
    | FinalResponseDirectiveComponent
    | UserOutputComponent
    | TerminalOutcomeComponent,
    Field(discriminator="component_type"),
]
_COMPONENT_ADAPTER = TypeAdapter(InteractionComponent)


class InteractionWorkpiece(BaseModel):
    """Cumulative typed product assembled by deterministic application logic."""

    model_config = ConfigDict(extra="forbid")

    version: str = INTERACTION_WORKPIECE_VERSION
    interaction_id: UUID
    task_id: UUID
    conversation_id: UUID
    correlation_id: UUID
    state: WorkpieceState = WorkpieceState.ASSEMBLING
    components: list[InteractionComponent] = Field(default_factory=list)

    @field_validator("components")
    @classmethod
    def percept_is_unique(cls, components: list[InteractionComponent]) -> list[InteractionComponent]:
        percept_count = sum(isinstance(item, PerceptComponent) for item in components)
        if percept_count != 1:
            raise ValueError("interaction workpiece requires exactly one percept component")
        return components

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "InteractionWorkpiece":
        if self.version != INTERACTION_WORKPIECE_VERSION:
            raise ValueError("unsupported interaction workpiece version")

        terminal_indices = [
            index
            for index, item in enumerate(self.components)
            if isinstance(item, TerminalOutcomeComponent)
        ]
        if self.state is WorkpieceState.ASSEMBLING:
            if terminal_indices:
                raise ValueError("assembling workpiece cannot contain terminal outcome")
            return self

        if terminal_indices != [len(self.components) - 1]:
            raise ValueError("terminal workpiece requires exactly one final terminal outcome")
        terminal = self.components[-1]
        assert isinstance(terminal, TerminalOutcomeComponent)
        outputs = [item for item in self.components if isinstance(item, UserOutputComponent)]
        if len(outputs) > 1:
            raise ValueError("terminal workpiece may contain at most one user output")
        if terminal.user_output_required != bool(outputs):
            raise ValueError("terminal user-output requirement does not match attached output")
        if terminal.outcome is TerminalOutcomeKind.RESPONSE_EMITTED and not outputs:
            raise ValueError("RESPONSE_EMITTED requires a user-output component")
        return self

    def attach(self, component: InteractionComponent | dict) -> "InteractionWorkpiece":
        """Validate one station component and return a newly assembled workpiece."""

        if self.state is WorkpieceState.TERMINAL:
            raise RuntimeError("cannot attach a component after workpiece terminalization")
        parsed = _COMPONENT_ADAPTER.validate_python(component)
        next_state = (
            WorkpieceState.TERMINAL
            if isinstance(parsed, TerminalOutcomeComponent)
            else WorkpieceState.ASSEMBLING
        )
        payload = self.model_dump(mode="python")
        payload["components"] = [*self.components, parsed]
        payload["state"] = next_state
        return InteractionWorkpiece.model_validate(payload)

    def user_output(self) -> UserOutputComponent | None:
        outputs = [item for item in self.components if isinstance(item, UserOutputComponent)]
        if not outputs:
            return None
        if len(outputs) != 1:
            raise RuntimeError("interaction workpiece contains multiple user outputs")
        return outputs[0]


def begin_interaction_workpiece(
    *,
    interaction_id: UUID,
    task_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    user_text: str,
    user_prompt_event_id: UUID,
) -> InteractionWorkpiece:
    """Create the frame and attach the originating percept as its first component."""

    return InteractionWorkpiece(
        interaction_id=interaction_id,
        task_id=task_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        components=[
            PerceptComponent(
                user_text=user_text,
                user_prompt_event_id=user_prompt_event_id,
            )
        ],
    )
