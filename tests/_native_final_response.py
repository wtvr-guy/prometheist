"""Shared native-acceptance inspection of the persisted final responder view.

The v0.7 continuity gate verifies the architectural handoff into the disposable
final response worker rather than requiring one canned surface string.  The
terminal InteractionWorkpiece already records the final evidence, durable
response directive, capability work, and visible output.  This helper rebuilds
the same policy-admitted evidence projection used by production response
realization and exposes a compact diagnostic view for pytest failures.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
import uuid

from jit_agent import db, event_store
from jit_agent.evidence_bound_llm import _admitted_capability_results
from jit_agent.final_response_directive import FinalResponseAction, FinalResponseDirective
from jit_agent.interaction_workpiece import (
    CapabilityWorkComponent,
    FinalEvidenceComponent,
    FinalResponseDirectiveComponent,
    InteractionWorkpiece,
    PerceptComponent,
    UserOutputComponent,
)
from jit_agent.models import Event, EventType, MemoryPacket
from jit_agent.pre_cognitive_workers import structured_capability_result
from jit_agent.response_policy import ResponseSurfaceMode, filter_memory_packet_for_scope


@dataclass(frozen=True, slots=True)
class FinalResponderView:
    """Application-reconstructable inputs and visible product for one final response."""

    prompt_event: Event
    workpiece_event: Event
    directive: FinalResponseDirective
    final_memory_packet: MemoryPacket
    admitted_memory_packet: MemoryPacket | None
    admitted_capability_results: tuple[dict[str, Any], ...]
    response_text: str

    @property
    def admitted_source_event_ids(self) -> set[uuid.UUID]:
        if self.admitted_memory_packet is None:
            return set()
        return {item.source_event_id for item in self.admitted_memory_packet.items}

    @property
    def admitted_texts(self) -> tuple[str, ...]:
        texts: list[str] = []
        if self.admitted_memory_packet is not None:
            texts.extend(item.content for item in self.admitted_memory_packet.items)
        texts.extend(
            json.dumps(item, sort_keys=True, default=str, separators=(",", ":"))
            for item in self.admitted_capability_results
        )
        return tuple(texts)


def events(conversation_id: uuid.UUID) -> list[Event]:
    with db.get_connection() as conn:
        return event_store.get_events_by_conversation(conn, conversation_id)


def event_for_text(conversation_id: uuid.UUID, event_type: EventType, text: str) -> Event:
    matches = [
        event
        for event in events(conversation_id)
        if event.event_type is event_type and event.payload.get("text") == text
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one {event_type.value} event with exact text {text!r}; "
            f"found {len(matches)}."
        )
    return matches[0]


def _single_component(workpiece: InteractionWorkpiece, component_type: type[Any]) -> Any:
    matches = [item for item in workpiece.components if isinstance(item, component_type)]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one {component_type.__name__} in terminal workpiece; found {len(matches)}."
        )
    return matches[0]


def final_responder_view(conversation_id: uuid.UUID, prompt: str) -> FinalResponderView:
    """Rebuild exactly the policy-admitted evidence/authority presented at response time."""

    prompt_event = event_for_text(conversation_id, EventType.USER_PROMPT, prompt)
    correlated = [
        event for event in events(conversation_id) if event.correlation_id == prompt_event.correlation_id
    ]
    snapshots = [
        event
        for event in correlated
        if event.event_type is EventType.SYSTEM_EVENT
        and event.payload.get("kind") == "INTERACTION_WORKPIECE_SNAPSHOT"
    ]
    if len(snapshots) != 1:
        raise AssertionError(
            f"Expected one terminal workpiece snapshot for {prompt_event.correlation_id}; "
            f"found {len(snapshots)}."
        )

    workpiece_event = snapshots[0]
    workpiece = InteractionWorkpiece.model_validate(workpiece_event.payload["workpiece"])
    percept = _single_component(workpiece, PerceptComponent)
    if percept.user_text != prompt or percept.user_prompt_event_id != prompt_event.event_id:
        raise AssertionError("terminal workpiece percept does not match the current user prompt")

    final_evidence = _single_component(workpiece, FinalEvidenceComponent)
    directive_component = _single_component(workpiece, FinalResponseDirectiveComponent)
    output = _single_component(workpiece, UserOutputComponent)
    directive = directive_component.directive
    final_packet = final_evidence.memory_packet

    if directive.final_memory_request_id != final_packet.memory_request_id:
        raise AssertionError("final response directive references a different final evidence packet")

    executions = [
        execution
        for component in workpiece.components
        if isinstance(component, CapabilityWorkComponent)
        for execution in component.executions
    ]
    capability_results = tuple(structured_capability_result(item) for item in executions)
    if [str(item.get("capability_id", "")) for item in capability_results] != directive.capability_ids:
        raise AssertionError("terminal workpiece capability results do not match final directive")

    admitted_packet = filter_memory_packet_for_scope(
        final_packet,
        directive.response_policy.evidence_scope,
    )
    admitted_capability_results = _admitted_capability_results(
        directive.response_policy.evidence_scope,
        capability_results,
    )

    return FinalResponderView(
        prompt_event=prompt_event,
        workpiece_event=workpiece_event,
        directive=directive,
        final_memory_packet=final_packet,
        admitted_memory_packet=admitted_packet,
        admitted_capability_results=admitted_capability_results,
        response_text=output.text,
    )


def assert_final_responder_has(
    view: FinalResponderView,
    *,
    required_source_event_ids: tuple[uuid.UUID, ...] = (),
    required_literals: tuple[str, ...] = (),
    expected_surface_mode: ResponseSurfaceMode | None = None,
) -> None:
    """Score the responder handoff, not the wording it eventually realizes."""

    failures: list[str] = []
    if view.directive.action is not FinalResponseAction.RESPOND:
        failures.append(f"directive action was {view.directive.action.value}, expected RESPOND")

    missing_sources = [
        event_id
        for event_id in required_source_event_ids
        if event_id not in view.admitted_source_event_ids
    ]
    if missing_sources:
        failures.append("missing admitted source events: " + ", ".join(map(str, missing_sources)))

    texts = view.admitted_texts
    missing_literals = [
        literal for literal in required_literals if not any(literal in text for text in texts)
    ]
    if missing_literals:
        failures.append("missing admitted evidence literals: " + repr(missing_literals))

    if (
        expected_surface_mode is not None
        and view.directive.response_policy.surface_mode is not expected_surface_mode
    ):
        failures.append(
            "surface mode was "
            f"{view.directive.response_policy.surface_mode.value}, "
            f"expected {expected_surface_mode.value}"
        )

    if failures:
        raise AssertionError("; ".join(failures) + "\n" + compact_final_responder_trace(view))


def compact_final_responder_trace(view: FinalResponderView) -> str:
    """Return the smallest useful causal slice for a failed native handoff assertion."""

    policy = view.directive.response_policy
    lines = [
        f"correlation={view.prompt_event.correlation_id}",
        f"current_prompt={view.prompt_event.payload.get('text')!r}",
        (
            "directive="
            f"action:{view.directive.action.value} "
            f"scope:{policy.evidence_scope.value} "
            f"surface:{policy.surface_mode.value} "
            f"memory_request:{view.directive.final_memory_request_id}"
        ),
        "admitted_memory:",
    ]
    if view.admitted_memory_packet is None or not view.admitted_memory_packet.items:
        lines.append("  none")
    else:
        for item in view.admitted_memory_packet.items:
            lines.append(
                "  "
                f"event={item.source_event_id} type={item.event_type.value} "
                f"source={item.source} score={item.score} content={item.content!r}"
            )

    lines.append("admitted_capability_results:")
    if not view.admitted_capability_results:
        lines.append("  none")
    else:
        for item in view.admitted_capability_results:
            lines.append("  " + json.dumps(item, sort_keys=True, default=str))

    lines.append(f"visible_response={view.response_text!r}")
    return "\n".join(lines)
