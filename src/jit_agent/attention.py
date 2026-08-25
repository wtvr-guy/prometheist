"""Deterministic JIT Attention scheduling primitives.

JIT Attention owns execution focus, not semantic interpretation.  Agents may
propose work, but this module derives scheduling priority from structured
metadata and applies deterministic queue, service-guarantee, dependency, and
interruption rules without an LLM in the scheduling loop.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, model_validator

from jit_agent.attention_resources import (
    ExecutionResource,
    ExecutionResourceClass,
    RESOURCE_ADMISSION_POLICY_VERSION,
    ResourceAdmissionPlan,
    ResourceRequirement,
    ResourceReservation,
    deterministic_reservation_id,
    execution_resource_class_sort_key,
    execution_resource_sort_key,
    resource_requirement_sort_key,
    resource_reservation_sort_key,
)


class PriorityClass(IntEnum):
    """Lower numeric values have higher scheduling priority."""

    P0 = 0  # emergency / integrity / safety
    P1 = 1  # user-blocking interactive work
    P2 = 2  # active user-requested work
    P3 = 3  # supporting work
    P4 = 4  # maintenance
    P5 = 5  # opportunistic background work


class TaskCriticality(str, Enum):
    EMERGENCY = "EMERGENCY"
    USER_BLOCKING = "USER_BLOCKING"
    USER_REQUESTED = "USER_REQUESTED"
    SUPPORTING = "SUPPORTING"
    MAINTENANCE = "MAINTENANCE"
    OPPORTUNISTIC = "OPPORTUNISTIC"


CRITICALITY_PRIORITY: dict[TaskCriticality, PriorityClass] = {
    TaskCriticality.EMERGENCY: PriorityClass.P0,
    TaskCriticality.USER_BLOCKING: PriorityClass.P1,
    TaskCriticality.USER_REQUESTED: PriorityClass.P2,
    TaskCriticality.SUPPORTING: PriorityClass.P3,
    TaskCriticality.MAINTENANCE: PriorityClass.P4,
    TaskCriticality.OPPORTUNISTIC: PriorityClass.P5,
}


class ServiceClass(str, Enum):
    INTERACTIVE = "INTERACTIVE"
    USER_WORK = "USER_WORK"
    SUPPORT = "SUPPORT"
    MAINTENANCE = "MAINTENANCE"
    BACKGROUND = "BACKGROUND"


class InterruptionPolicy(str, Enum):
    """How a running task may yield to higher-priority work."""

    PREEMPTIBLE = "PREEMPTIBLE"
    CHECKPOINT_ONLY = "CHECKPOINT_ONLY"
    ATOMIC = "ATOMIC"


class TaskStatus(str, Enum):
    NEW = "NEW"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FocusAction(str, Enum):
    IDLE = "IDLE"
    START = "START"
    CONTINUE = "CONTINUE"
    PREEMPT = "PREEMPT"
    WAIT_FOR_CHECKPOINT = "WAIT_FOR_CHECKPOINT"


class ServiceGuarantee(BaseModel):
    """Queue-cycle guarantee used to prevent deterministic starvation.

    Once ``max_wait_cycles`` is reached, a queued task is promoted to at least
    ``guaranteed_priority``.  Guarantees never override a running task's
    interruption policy; an ATOMIC task still runs to completion.
    """

    max_wait_cycles: int | None = Field(default=None, ge=0)
    guaranteed_priority: PriorityClass


DEFAULT_SERVICE_GUARANTEES: dict[ServiceClass, ServiceGuarantee] = {
    ServiceClass.INTERACTIVE: ServiceGuarantee(
        max_wait_cycles=1,
        guaranteed_priority=PriorityClass.P1,
    ),
    ServiceClass.USER_WORK: ServiceGuarantee(
        max_wait_cycles=4,
        guaranteed_priority=PriorityClass.P2,
    ),
    ServiceClass.SUPPORT: ServiceGuarantee(
        max_wait_cycles=8,
        guaranteed_priority=PriorityClass.P2,
    ),
    ServiceClass.MAINTENANCE: ServiceGuarantee(
        max_wait_cycles=32,
        guaranteed_priority=PriorityClass.P2,
    ),
    ServiceClass.BACKGROUND: ServiceGuarantee(
        max_wait_cycles=128,
        guaranteed_priority=PriorityClass.P3,
    ),
}


class SchedulingMetadata(BaseModel):
    """Structured inputs from which scheduling behavior is derived."""

    criticality: TaskCriticality
    service_class: ServiceClass
    interruption_policy: InterruptionPolicy = InterruptionPolicy.PREEMPTIBLE
    deadline: datetime | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    required_resource_classes: list[ExecutionResourceClass] = Field(default_factory=list)
    resource_requirements: list[ResourceRequirement] = Field(default_factory=list)
    dependency_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_resource_contract(self) -> "SchedulingMetadata":
        requirements_by_class: dict[ExecutionResourceClass, ResourceRequirement] = {}
        for requirement in self.resource_requirements:
            if requirement.resource_class in requirements_by_class:
                raise ValueError("resource_requirements must contain each class at most once")
            requirements_by_class[requirement.resource_class] = requirement

        required_classes = set(self.required_resource_classes)
        required_classes.update(requirements_by_class)
        self.required_resource_classes = sorted(
            required_classes,
            key=execution_resource_class_sort_key,
        )
        self.resource_requirements = sorted(
            requirements_by_class.values(),
            key=resource_requirement_sort_key,
        )
        return self

    def quantitative_resource_requirements(self) -> list[ResourceRequirement]:
        """Return the canonical quantitative contract, including v0.7-B inputs."""

        explicit = {
            requirement.resource_class: requirement
            for requirement in self.resource_requirements
        }
        return [
            explicit.get(
                resource_class,
                ResourceRequirement(resource_class=resource_class, units=1),
            ).model_copy(deep=True)
            for resource_class in self.required_resource_classes
        ]


class AttentionTask(BaseModel):
    """Durable task representation; no LLM context is required to resume it."""

    task_id: UUID
    task_key: str = Field(min_length=1)
    created_seq: int = Field(ge=1)
    metadata: SchedulingMetadata
    parent_task_id: UUID | None = None
    status: TaskStatus = TaskStatus.NEW
    enqueued_cycle: int = Field(default=0, ge=0)
    revision: int = Field(default=0, ge=0)
    resumable_state: dict[str, Any] = Field(default_factory=dict)


class TaskTransition(BaseModel):
    transition_id: UUID
    task_id: UUID
    revision: int = Field(ge=1)
    scheduler_cycle: int = Field(ge=0)
    from_status: TaskStatus
    to_status: TaskStatus
    reason: str


class FocusDecision(BaseModel):
    action: FocusAction
    active_task_id: UUID | None = None
    candidate_task_id: UUID | None = None
    reason: str


class SchedulerSnapshot(BaseModel):
    cycle: int = Field(ge=0)
    active_task_id: UUID | None = None
    pending_preemption_task_id: UUID | None = None
    tasks: list[AttentionTask]
    execution_resources: list[ExecutionResource] = Field(default_factory=list)
    admission_policy_version: str = Field(
        default=RESOURCE_ADMISSION_POLICY_VERSION,
        min_length=1,
    )
    admitted_task_ids: list[UUID] = Field(default_factory=list)
    resource_reservations: list[ResourceReservation] = Field(default_factory=list)


def deterministic_task_id(namespace: UUID, task_key: str) -> UUID:
    """Return a stable task id for a stable namespace + task key."""

    normalized = task_key.strip()
    if not normalized:
        raise ValueError("task_key must not be empty")
    return uuid5(namespace, f"prometheist-task:{normalized}")


def derive_priority(metadata: SchedulingMetadata) -> PriorityClass:
    """Derive base priority solely from explicit structured metadata."""

    return CRITICALITY_PRIORITY[metadata.criticality]


def _normalize_deadline(deadline: datetime | None) -> datetime:
    if deadline is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    if deadline.tzinfo is None:
        return deadline.replace(tzinfo=timezone.utc)
    return deadline.astimezone(timezone.utc)


class JITAttentionScheduler:
    """Deterministic executive scheduler for Prometheist task focus.

    The scheduler has no wall-clock dependency.  Service guarantees use the
    monotonic ``cycle`` counter so identical input/state produces identical
    decisions across machines and restarts.
    """

    def __init__(
        self,
        *,
        service_guarantees: dict[ServiceClass, ServiceGuarantee] | None = None,
    ) -> None:
        configured = DEFAULT_SERVICE_GUARANTEES if service_guarantees is None else service_guarantees
        self.service_guarantees = {
            service_class: guarantee.model_copy(deep=True)
            for service_class, guarantee in configured.items()
        }
        missing = set(ServiceClass) - set(self.service_guarantees)
        if missing:
            missing_names = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"Missing service guarantees for: {missing_names}")
        self.tasks: dict[UUID, AttentionTask] = {}
        self.resources: dict[str, ExecutionResource] = {}
        self.admission_policy_version = RESOURCE_ADMISSION_POLICY_VERSION
        self.admitted_task_ids: list[UUID] = []
        self._resource_reservations: dict[UUID, ResourceReservation] = {}
        self.active_task_id: UUID | None = None
        self.pending_preemption_task_id: UUID | None = None
        self.cycle = 0
        self.transitions: list[TaskTransition] = []

    @classmethod
    def from_snapshot(
        cls,
        snapshot: SchedulerSnapshot,
        *,
        service_guarantees: dict[ServiceClass, ServiceGuarantee] | None = None,
    ) -> "JITAttentionScheduler":
        scheduler = cls(service_guarantees=service_guarantees)
        scheduler.tasks = {task.task_id: task.model_copy(deep=True) for task in snapshot.tasks}
        resource_ids = [resource.resource_id for resource in snapshot.execution_resources]
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("Snapshot contains duplicate execution resource ids")
        scheduler.resources = {
            resource.resource_id: resource.model_copy(deep=True)
            for resource in snapshot.execution_resources
        }
        scheduler.admission_policy_version = snapshot.admission_policy_version
        admitted_task_ids = list(snapshot.admitted_task_ids)
        if len(admitted_task_ids) != len(set(admitted_task_ids)):
            raise ValueError("Snapshot contains duplicate admitted task ids")
        scheduler.admitted_task_ids = admitted_task_ids
        reservation_ids = [
            reservation.reservation_id
            for reservation in snapshot.resource_reservations
        ]
        if len(reservation_ids) != len(set(reservation_ids)):
            raise ValueError("Snapshot contains duplicate resource reservation ids")
        scheduler._resource_reservations = {
            reservation.reservation_id: reservation.model_copy(deep=True)
            for reservation in snapshot.resource_reservations
        }
        scheduler.active_task_id = snapshot.active_task_id
        scheduler.pending_preemption_task_id = snapshot.pending_preemption_task_id
        scheduler.cycle = snapshot.cycle
        scheduler._validate_snapshot()
        return scheduler

    def snapshot(self) -> SchedulerSnapshot:
        return SchedulerSnapshot(
            cycle=self.cycle,
            active_task_id=self.active_task_id,
            pending_preemption_task_id=self.pending_preemption_task_id,
            tasks=[
                task.model_copy(deep=True)
                for task in sorted(self.tasks.values(), key=lambda item: (item.created_seq, item.task_id.hex))
            ],
            execution_resources=self.execution_resources(),
            admission_policy_version=self.admission_policy_version,
            admitted_task_ids=list(self.admitted_task_ids),
            resource_reservations=self.resource_reservations(),
        )

    def configure_execution_resource(self, resource: ExecutionResource) -> ExecutionResource:
        """Create or update one durable resource definition deterministically.

        A resource id may change capacity, enabled state, or metadata, but it may
        not silently change resource class. Stable identity now becomes the
        basis for deterministic lane identity in the next v0.7 increment.
        """

        existing = self.resources.get(resource.resource_id)
        if existing is not None and existing.resource_class is not resource.resource_class:
            raise ValueError(
                f"Execution resource {resource.resource_id!r} cannot change class "
                f"from {existing.resource_class.value} to {resource.resource_class.value}"
            )
        self._invalidate_resource_admission()
        stored = resource.model_copy(deep=True)
        self.resources[stored.resource_id] = stored
        return stored.model_copy(deep=True)

    def execution_resources(self, *, enabled_only: bool = False) -> list[ExecutionResource]:
        resources = [
            resource
            for resource in self.resources.values()
            if not enabled_only or resource.enabled
        ]
        resources.sort(key=execution_resource_sort_key)
        return [resource.model_copy(deep=True) for resource in resources]

    def resource_reservations(self) -> list[ResourceReservation]:
        reservations = list(self._resource_reservations.values())
        reservations.sort(key=resource_reservation_sort_key)
        return [reservation.model_copy(deep=True) for reservation in reservations]

    def reconcile_resource_admission(self) -> ResourceAdmissionPlan:
        """Reserve a deterministic attention-ordered set that fits safely.

        The current single-focus task is preserved first because contention-
        driven interruption is deliberately deferred to a later v0.7 increment.
        Dependency-satisfied queued work is then considered in normal attention
        order. Each task's multi-resource contract is all-or-nothing.

        This records admission and reservations only. Durable worker assignments
        and scheduling epochs remain separate follow-up work.
        """

        remaining = {
            resource.resource_id: resource.admissible_capacity
            for resource in self.execution_resources(enabled_only=True)
        }
        resources_by_class: dict[ExecutionResourceClass, list[ExecutionResource]] = {
            resource_class: [] for resource_class in ExecutionResourceClass
        }
        for resource in self.execution_resources(enabled_only=True):
            resources_by_class[resource.resource_class].append(resource)

        candidate_ids: list[UUID] = []
        if self.active_task_id is not None:
            candidate_ids.append(self.active_task_id)
        candidate_ids.extend(
            task_id
            for task_id in self._ranked_dependency_satisfied_queued_task_ids()
            if task_id != self.active_task_id
        )

        admitted: list[UUID] = []
        unadmitted: list[UUID] = []
        reservations: list[ResourceReservation] = []
        for task_id in candidate_ids:
            allocation = self._allocate_task_resources(
                self.tasks[task_id],
                remaining=remaining,
                resources_by_class=resources_by_class,
            )
            if allocation is None:
                if task_id == self.active_task_id:
                    raise RuntimeError(
                        "Active task resource requirements exceed the safe capacity envelope"
                    )
                unadmitted.append(task_id)
                continue

            task_reservations, updated_remaining = allocation
            remaining = updated_remaining
            admitted.append(task_id)
            reservations.extend(task_reservations)

        reservations.sort(key=resource_reservation_sort_key)
        plan = ResourceAdmissionPlan(
            policy_version=RESOURCE_ADMISSION_POLICY_VERSION,
            admitted_task_ids=admitted,
            unadmitted_task_ids=unadmitted,
            reservations=reservations,
        )
        self.admission_policy_version = plan.policy_version
        self.admitted_task_ids = list(plan.admitted_task_ids)
        self._resource_reservations = {
            reservation.reservation_id: reservation.model_copy(deep=True)
            for reservation in plan.reservations
        }
        return plan.model_copy(deep=True)

    def submit(self, task: AttentionTask) -> AttentionTask:
        if task.task_id in self.tasks:
            raise ValueError(f"Duplicate task_id: {task.task_id}")
        if any(existing.created_seq == task.created_seq for existing in self.tasks.values()):
            raise ValueError(f"Duplicate created_seq: {task.created_seq}")
        if task.status not in {TaskStatus.NEW, TaskStatus.QUEUED}:
            raise ValueError("Newly submitted tasks must be NEW or QUEUED")

        stored = task.model_copy(deep=True)
        self.tasks[stored.task_id] = stored
        self._transition(stored.task_id, TaskStatus.QUEUED, "task submitted")
        self._replace_task(stored.task_id, enqueued_cycle=self.cycle)
        return self.tasks[stored.task_id].model_copy(deep=True)

    def advance_cycle(self, count: int = 1) -> int:
        if count < 0:
            raise ValueError("count must be >= 0")
        if count:
            self._invalidate_resource_admission()
        self.cycle += count
        return self.cycle

    def queued_tasks(self) -> list[AttentionTask]:
        return [
            self.tasks[task_id].model_copy(deep=True)
            for task_id in self._ranked_queued_task_ids()
        ]

    def reconcile_focus(self) -> FocusDecision:
        """Choose what should own focus at the current deterministic cycle."""

        self.advance_cycle()
        candidate_id = self._best_queued_task_id()

        if self.active_task_id is None:
            if candidate_id is None:
                return FocusDecision(action=FocusAction.IDLE, reason="no runnable queued tasks")
            self._start(candidate_id, "highest-ranked runnable task")
            return FocusDecision(
                action=FocusAction.START,
                active_task_id=candidate_id,
                candidate_task_id=candidate_id,
                reason="started highest-ranked runnable task",
            )

        active = self.tasks[self.active_task_id]
        if candidate_id is None:
            return FocusDecision(
                action=FocusAction.CONTINUE,
                active_task_id=active.task_id,
                reason="no higher-priority runnable task",
            )

        candidate = self.tasks[candidate_id]
        if not self._strictly_outprioritizes(candidate, active):
            return FocusDecision(
                action=FocusAction.CONTINUE,
                active_task_id=active.task_id,
                candidate_task_id=candidate.task_id,
                reason="queued task does not strictly outrank active task",
            )

        policy = active.metadata.interruption_policy
        if policy is InterruptionPolicy.ATOMIC:
            return FocusDecision(
                action=FocusAction.CONTINUE,
                active_task_id=active.task_id,
                candidate_task_id=candidate.task_id,
                reason="active task is atomic",
            )

        if policy is InterruptionPolicy.CHECKPOINT_ONLY:
            self.pending_preemption_task_id = candidate.task_id
            return FocusDecision(
                action=FocusAction.WAIT_FOR_CHECKPOINT,
                active_task_id=active.task_id,
                candidate_task_id=candidate.task_id,
                reason="higher-priority task waiting for safe checkpoint",
            )

        previous_id = active.task_id
        self._requeue_active("preempted by higher-priority task")
        self._start(candidate.task_id, f"preempted {previous_id}")
        return FocusDecision(
            action=FocusAction.PREEMPT,
            active_task_id=candidate.task_id,
            candidate_task_id=candidate.task_id,
            reason=f"preempted {previous_id}",
        )

    def checkpoint_active(self) -> FocusDecision:
        """Yield at a safe boundary if a pending/higher-priority task exists."""

        if self.active_task_id is None:
            return self.reconcile_focus()

        self.advance_cycle()
        active = self.tasks[self.active_task_id]
        if active.metadata.interruption_policy is InterruptionPolicy.ATOMIC:
            return FocusDecision(
                action=FocusAction.CONTINUE,
                active_task_id=active.task_id,
                reason="atomic task ignores checkpoints for preemption",
            )

        candidate_id = self._best_queued_task_id()
        if candidate_id is None:
            self.pending_preemption_task_id = None
            return FocusDecision(
                action=FocusAction.CONTINUE,
                active_task_id=active.task_id,
                reason="checkpoint reached with no runnable queued task",
            )

        candidate = self.tasks[candidate_id]
        if not self._strictly_outprioritizes(candidate, active):
            self.pending_preemption_task_id = None
            return FocusDecision(
                action=FocusAction.CONTINUE,
                active_task_id=active.task_id,
                candidate_task_id=candidate.task_id,
                reason="checkpoint reached but queued task no longer outranks active task",
            )

        previous_id = active.task_id
        self._requeue_active("yielded at checkpoint to higher-priority task")
        self._start(candidate.task_id, f"checkpoint preemption of {previous_id}")
        return FocusDecision(
            action=FocusAction.PREEMPT,
            active_task_id=candidate.task_id,
            candidate_task_id=candidate.task_id,
            reason=f"checkpoint preemption of {previous_id}",
        )

    def complete_active(self, resumable_state: dict[str, Any] | None = None) -> AttentionTask:
        if self.active_task_id is None:
            raise RuntimeError("No active task")
        task_id = self.active_task_id
        if resumable_state is not None:
            self._replace_task(task_id, resumable_state=dict(resumable_state))
        self._transition(task_id, TaskStatus.COMPLETED, "task completed")
        self.active_task_id = None
        self.pending_preemption_task_id = None
        return self.tasks[task_id].model_copy(deep=True)

    def fail_active(self, resumable_state: dict[str, Any] | None = None) -> AttentionTask:
        if self.active_task_id is None:
            raise RuntimeError("No active task")
        task_id = self.active_task_id
        if resumable_state is not None:
            self._replace_task(task_id, resumable_state=dict(resumable_state))
        self._transition(task_id, TaskStatus.FAILED, "task failed")
        self.active_task_id = None
        self.pending_preemption_task_id = None
        return self.tasks[task_id].model_copy(deep=True)

    def set_resumable_state(self, task_id: UUID, state: dict[str, Any]) -> AttentionTask:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        self._replace_task(task_id, resumable_state=dict(state))
        return self.tasks[task_id].model_copy(deep=True)

    def _ranked_queued_task_ids(self) -> list[UUID]:
        runnable = [
            self.tasks[task_id]
            for task_id in self._ranked_dependency_satisfied_queued_task_ids()
            if self._resources_satisfied(self.tasks[task_id])
        ]
        return [task.task_id for task in runnable]

    def _ranked_dependency_satisfied_queued_task_ids(self) -> list[UUID]:
        runnable = [
            task
            for task in self.tasks.values()
            if task.status is TaskStatus.QUEUED
            and self._dependencies_satisfied(task)
        ]
        runnable.sort(key=self._queue_key)
        return [task.task_id for task in runnable]

    def _best_queued_task_id(self) -> UUID | None:
        ranked = self._ranked_queued_task_ids()
        return ranked[0] if ranked else None

    def _dependencies_satisfied(self, task: AttentionTask) -> bool:
        for dependency_id in task.metadata.dependency_ids:
            dependency = self.tasks.get(dependency_id)
            if dependency is None or dependency.status is not TaskStatus.COMPLETED:
                return False
        return True

    def _resources_satisfied(self, task: AttentionTask) -> bool:
        available_by_class = {
            resource_class: 0 for resource_class in ExecutionResourceClass
        }
        for resource in self.resources.values():
            available_by_class[resource.resource_class] += resource.admissible_capacity
        return all(
            available_by_class[requirement.resource_class] >= requirement.units
            for requirement in task.metadata.quantitative_resource_requirements()
        )

    def _allocate_task_resources(
        self,
        task: AttentionTask,
        *,
        remaining: dict[str, int],
        resources_by_class: dict[ExecutionResourceClass, list[ExecutionResource]],
    ) -> tuple[list[ResourceReservation], dict[str, int]] | None:
        tentative_remaining = dict(remaining)
        reservations: list[ResourceReservation] = []
        for requirement in task.metadata.quantitative_resource_requirements():
            needed = requirement.units
            for resource in resources_by_class[requirement.resource_class]:
                available = tentative_remaining[resource.resource_id]
                reserved = min(needed, available)
                if reserved <= 0:
                    continue
                reservations.append(
                    ResourceReservation(
                        reservation_id=deterministic_reservation_id(
                            task.task_id,
                            resource.resource_id,
                        ),
                        task_id=task.task_id,
                        resource_id=resource.resource_id,
                        resource_class=resource.resource_class,
                        units=reserved,
                    )
                )
                tentative_remaining[resource.resource_id] -= reserved
                needed -= reserved
                if needed == 0:
                    break
            if needed:
                return None
        return reservations, tentative_remaining

    def _service_due(self, task: AttentionTask) -> bool:
        guarantee = self.service_guarantees[task.metadata.service_class]
        if guarantee.max_wait_cycles is None:
            return False
        waited = max(0, self.cycle - task.enqueued_cycle)
        return waited >= guarantee.max_wait_cycles

    def _effective_priority(self, task: AttentionTask) -> PriorityClass:
        base = derive_priority(task.metadata)
        if task.status is not TaskStatus.QUEUED:
            return base
        guarantee = self.service_guarantees[task.metadata.service_class]
        if not self._service_due(task):
            return base
        return PriorityClass(min(int(base), int(guarantee.guaranteed_priority)))

    def _queue_key(self, task: AttentionTask) -> tuple[int, int, datetime, int, str]:
        # A due guarantee wins tie-breaking within its promoted priority class.
        return (
            int(self._effective_priority(task)),
            0 if self._service_due(task) else 1,
            _normalize_deadline(task.metadata.deadline),
            task.created_seq,
            task.task_id.hex,
        )

    def _strictly_outprioritizes(self, candidate: AttentionTask, active: AttentionTask) -> bool:
        # Same-priority arrivals do not preempt.  This prevents deterministic
        # thrashing; FIFO/deadline tie-breakers apply when focus next becomes free.
        return int(self._effective_priority(candidate)) < int(derive_priority(active.metadata))

    def _start(self, task_id: UUID, reason: str) -> None:
        if self.active_task_id is not None:
            raise RuntimeError("Cannot start a second active task")
        task = self.tasks[task_id]
        if task.status is not TaskStatus.QUEUED:
            raise RuntimeError(f"Task {task_id} is not queued")
        self._transition(task_id, TaskStatus.RUNNING, reason)
        self.active_task_id = task_id
        self.pending_preemption_task_id = None

    def _requeue_active(self, reason: str) -> None:
        if self.active_task_id is None:
            raise RuntimeError("No active task")
        task_id = self.active_task_id
        self._transition(task_id, TaskStatus.SUSPENDED, reason)
        self._transition(task_id, TaskStatus.QUEUED, "suspended task returned to queue")
        self._replace_task(task_id, enqueued_cycle=self.cycle)
        self.active_task_id = None
        self.pending_preemption_task_id = None

    def _transition(self, task_id: UUID, to_status: TaskStatus, reason: str) -> None:
        self._invalidate_resource_admission()
        task = self.tasks[task_id]
        from_status = task.status
        revision = task.revision + 1
        transition = TaskTransition(
            transition_id=uuid5(task.task_id, f"transition:{revision}:{from_status.value}:{to_status.value}"),
            task_id=task.task_id,
            revision=revision,
            scheduler_cycle=self.cycle,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
        )
        self.transitions.append(transition)
        self.tasks[task_id] = task.model_copy(
            update={"status": to_status, "revision": revision},
            deep=True,
        )

    def _replace_task(self, task_id: UUID, **updates: Any) -> None:
        self.tasks[task_id] = self.tasks[task_id].model_copy(update=updates, deep=True)

    def _invalidate_resource_admission(self) -> None:
        self.admitted_task_ids = []
        self._resource_reservations = {}

    def _validate_snapshot(self) -> None:
        running = [task.task_id for task in self.tasks.values() if task.status is TaskStatus.RUNNING]
        if self.active_task_id is None:
            if running:
                raise ValueError("Snapshot has RUNNING task but no active_task_id")
        elif running != [self.active_task_id]:
            raise ValueError("Snapshot active_task_id does not match exactly one RUNNING task")

        if self.pending_preemption_task_id is not None:
            pending = self.tasks.get(self.pending_preemption_task_id)
            if pending is None or pending.status is not TaskStatus.QUEUED:
                raise ValueError("pending_preemption_task_id must reference a queued task")

        created = [task.created_seq for task in self.tasks.values()]
        if len(created) != len(set(created)):
            raise ValueError("Snapshot contains duplicate created_seq values")

        admitted = set(self.admitted_task_ids)
        if len(admitted) != len(self.admitted_task_ids):
            raise ValueError("Snapshot contains duplicate admitted task ids")
        for task_id in self.admitted_task_ids:
            task = self.tasks.get(task_id)
            if task is None:
                raise ValueError("admitted_task_ids must reference existing tasks")
            if task.status not in {TaskStatus.QUEUED, TaskStatus.RUNNING}:
                raise ValueError("Only queued or running tasks may be admitted")
            if not self._dependencies_satisfied(task):
                raise ValueError("Admitted task dependencies must be satisfied")
        if admitted and self.active_task_id is not None and self.active_task_id not in admitted:
            raise ValueError("An authoritative admission set must include the active task")

        resource_usage: dict[str, int] = {}
        task_class_usage: dict[UUID, dict[ExecutionResourceClass, int]] = {}
        task_resource_pairs: set[tuple[UUID, str]] = set()
        for reservation in self._resource_reservations.values():
            if reservation.task_id not in admitted:
                raise ValueError("Resource reservation must belong to an admitted task")
            resource = self.resources.get(reservation.resource_id)
            if resource is None:
                raise ValueError("Resource reservation references an unknown resource")
            if resource.resource_class is not reservation.resource_class:
                raise ValueError("Resource reservation class does not match its resource")
            if reservation.reservation_id != deterministic_reservation_id(
                reservation.task_id,
                reservation.resource_id,
            ):
                raise ValueError("Resource reservation id is not deterministic")
            pair = (reservation.task_id, reservation.resource_id)
            if pair in task_resource_pairs:
                raise ValueError("Task has duplicate reservations for one resource")
            task_resource_pairs.add(pair)

            resource_usage[reservation.resource_id] = (
                resource_usage.get(reservation.resource_id, 0) + reservation.units
            )
            if resource_usage[reservation.resource_id] > resource.admissible_capacity:
                raise ValueError("Resource reservations exceed admissible capacity")

            class_usage = task_class_usage.setdefault(reservation.task_id, {})
            class_usage[reservation.resource_class] = (
                class_usage.get(reservation.resource_class, 0) + reservation.units
            )

        for task_id in self.admitted_task_ids:
            expected = {
                requirement.resource_class: requirement.units
                for requirement in self.tasks[
                    task_id
                ].metadata.quantitative_resource_requirements()
            }
            if task_class_usage.get(task_id, {}) != expected:
                raise ValueError(
                    "Admitted task reservations do not exactly satisfy its requirements"
                )
