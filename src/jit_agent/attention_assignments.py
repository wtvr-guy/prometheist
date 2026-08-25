"""Durable scheduling-epoch and assignment primitives for JIT Attention."""
from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, model_validator

from jit_agent.attention_resources import (
    ResourceReservation,
    resource_reservation_sort_key,
)


ASSIGNMENT_POLICY_VERSION = "v0.7-d-epoch-v1"
_EPOCH_NAMESPACE = UUID("d82c9bb5-1c09-4cc6-a28d-ff46aa1ca7cd")


class AssignmentStatus(str, Enum):
    """Increment D exposes only ready, committed assignments to workers."""

    READY = "READY"


class SchedulingEpochStatus(str, Enum):
    PLANNED = "PLANNED"
    COMMITTED = "COMMITTED"


class DurableAssignment(BaseModel):
    """Worker-visible entitlement to advance one durable task.

    Increment D deliberately stops before worker claims, leases, heartbeats, or
    effects. Those lifecycle fields belong to the durable worker protocol.
    """

    assignment_id: UUID
    task_id: UUID
    task_revision: int = Field(ge=0)
    created_epoch_sequence: int = Field(ge=1)
    reservation_ids: list[UUID] = Field(default_factory=list)
    status: AssignmentStatus = AssignmentStatus.READY

    @model_validator(mode="after")
    def validate_reservation_ids(self) -> "DurableAssignment":
        if len(self.reservation_ids) != len(set(self.reservation_ids)):
            raise ValueError("reservation_ids must not contain duplicates")
        return self


class SchedulingEpoch(BaseModel):
    """Complete immutable assignment/reservation decision for one epoch."""

    epoch_id: UUID
    sequence: int = Field(ge=1)
    previous_epoch_id: UUID | None = None
    scheduler_cycle: int = Field(ge=0)
    admission_policy_version: str = Field(min_length=1)
    assignment_policy_version: str = Field(
        default=ASSIGNMENT_POLICY_VERSION,
        min_length=1,
    )
    status: SchedulingEpochStatus
    assignment_ids: list[UUID] = Field(default_factory=list)
    reservations: list[ResourceReservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_complete_set(self) -> "SchedulingEpoch":
        if len(self.assignment_ids) != len(set(self.assignment_ids)):
            raise ValueError("assignment_ids must not contain duplicates")
        reservation_ids = [item.reservation_id for item in self.reservations]
        if len(reservation_ids) != len(set(reservation_ids)):
            raise ValueError("epoch reservations must not contain duplicate ids")
        self.reservations = sorted(
            self.reservations,
            key=resource_reservation_sort_key,
        )
        return self


class SchedulingEpochPlan(BaseModel):
    """Provisional epoch that is not worker-visible until durability commits."""

    epoch: SchedulingEpoch
    admitted_task_ids: list[UUID] = Field(default_factory=list)
    unadmitted_task_ids: list[UUID] = Field(default_factory=list)
    assignments: list[DurableAssignment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_complete_plan(self) -> "SchedulingEpochPlan":
        if self.epoch.status is not SchedulingEpochStatus.PLANNED:
            raise ValueError("A scheduling epoch plan must be PLANNED")

        admitted = set(self.admitted_task_ids)
        unadmitted = set(self.unadmitted_task_ids)
        if len(admitted) != len(self.admitted_task_ids):
            raise ValueError("admitted_task_ids must not contain duplicates")
        if len(unadmitted) != len(self.unadmitted_task_ids):
            raise ValueError("unadmitted_task_ids must not contain duplicates")
        if admitted.intersection(unadmitted):
            raise ValueError("admitted and unadmitted task ids must be disjoint")
        if any(
            reservation.task_id not in admitted
            for reservation in self.epoch.reservations
        ):
            raise ValueError("every epoch reservation must belong to an admitted task")

        assignment_ids = [item.assignment_id for item in self.assignments]
        assignment_task_ids = [item.task_id for item in self.assignments]
        if assignment_ids != self.epoch.assignment_ids:
            raise ValueError("epoch assignment_ids must match assignments in order")
        if assignment_task_ids != self.admitted_task_ids:
            raise ValueError("one assignment must exist for every admitted task in order")

        reservations_by_task: dict[UUID, set[UUID]] = {}
        for reservation in self.epoch.reservations:
            reservations_by_task.setdefault(reservation.task_id, set()).add(
                reservation.reservation_id
            )
        for assignment in self.assignments:
            if set(assignment.reservation_ids) != reservations_by_task.get(
                assignment.task_id,
                set(),
            ):
                raise ValueError(
                    "assignment reservation_ids must match its complete reservation set"
                )
        return self


def deterministic_assignment_id(
    task_id: UUID,
    *,
    task_revision: int,
    reservations: list[ResourceReservation],
) -> UUID:
    """Return a stable id while task revision and reservations remain unchanged."""

    if task_revision < 0:
        raise ValueError("task_revision must be >= 0")
    canonical_reservations = sorted(reservations, key=resource_reservation_sort_key)
    reservation_key = ",".join(
        f"{item.reservation_id}:{item.units}"
        for item in canonical_reservations
    )
    return uuid5(
        task_id,
        f"prometheist-assignment:{task_revision}:{reservation_key}",
    )


def deterministic_epoch_id(
    *,
    sequence: int,
    previous_epoch_id: UUID | None,
    scheduler_cycle: int,
    admission_policy_version: str,
    assignment_policy_version: str,
    assignment_ids: list[UUID],
    reservations: list[ResourceReservation],
) -> UUID:
    """Return the stable identity of one complete scheduling decision."""

    if sequence < 1:
        raise ValueError("sequence must be >= 1")
    if scheduler_cycle < 0:
        raise ValueError("scheduler_cycle must be >= 0")
    previous = "root" if previous_epoch_id is None else str(previous_epoch_id)
    assignment_key = ",".join(str(value) for value in assignment_ids)
    reservation_key = ",".join(
        f"{item.reservation_id}:{item.units}"
        for item in sorted(reservations, key=resource_reservation_sort_key)
    )
    canonical = "|".join(
        [
            str(sequence),
            previous,
            str(scheduler_cycle),
            admission_policy_version,
            assignment_policy_version,
            assignment_key,
            reservation_key,
        ]
    )
    return uuid5(_EPOCH_NAMESPACE, canonical)
