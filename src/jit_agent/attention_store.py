"""PostgreSQL durability adapter for the deterministic JIT Attention scheduler."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from jit_agent.attention import (
    AttentionTask,
    InterruptionPolicy,
    JITAttentionScheduler,
    SchedulerSnapshot,
    SchedulingMetadata,
    ServiceClass,
    TaskCriticality,
    TaskStatus,
)
from jit_agent.attention_resources import (
    ExecutionResource,
    ExecutionResourceClass,
    ResourceRequirement,
    ResourceReservation,
)
from jit_agent.attention_assignments import (
    AssignmentStatus,
    DurableAssignment,
    SchedulingEpoch,
    SchedulingEpochStatus,
)


DEFAULT_SCHEDULER_KEY = "default"


def allocate_created_seq(conn: psycopg.Connection) -> int:
    """Allocate the authoritative intake sequence used for deterministic tie-breaking."""

    with conn.cursor() as cur:
        cur.execute("SELECT nextval('attention_task_created_seq')")
        return int(cur.fetchone()[0])


def save_scheduler(
    conn: psycopg.Connection,
    scheduler: JITAttentionScheduler,
    *,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> None:
    """Persist scheduler state and publish a pending epoch atomically.

    A provisional epoch remains worker-invisible until its immutable epoch row,
    assignment rows, complete reservation set, and scheduler pointer all commit
    in this transaction. The in-memory scheduler is published only afterward.
    """

    snapshot = scheduler.snapshot()
    pending = scheduler.pending_scheduling_epoch()
    if pending is None:
        epoch = snapshot.current_epoch
        assignments = snapshot.assignments
        state_cycle = snapshot.cycle
        epoch_sequence = snapshot.epoch_sequence
        admitted_task_ids = snapshot.admitted_task_ids
        reservations = snapshot.resource_reservations
    else:
        epoch = pending.epoch.model_copy(
            update={"status": SchedulingEpochStatus.COMMITTED},
            deep=True,
        )
        assignments = pending.assignments
        state_cycle = epoch.scheduler_cycle
        epoch_sequence = epoch.sequence
        admitted_task_ids = pending.admitted_task_ids
        reservations = epoch.reservations
        publication_snapshot = SchedulerSnapshot(
            cycle=state_cycle,
            active_task_id=snapshot.active_task_id,
            pending_preemption_task_id=snapshot.pending_preemption_task_id,
            tasks=snapshot.tasks,
            execution_resources=snapshot.execution_resources,
            admission_policy_version=epoch.admission_policy_version,
            admitted_task_ids=admitted_task_ids,
            resource_reservations=reservations,
            epoch_sequence=epoch_sequence,
            assignment_policy_version=epoch.assignment_policy_version,
            current_epoch=epoch,
            assignments=assignments,
        )
        JITAttentionScheduler.from_snapshot(
            publication_snapshot,
            service_guarantees=scheduler.service_guarantees,
        )

    try:
        with conn.cursor() as cur:
            _lock_scheduler_generation(
                cur,
                scheduler_key=scheduler_key,
                snapshot_epoch_sequence=snapshot.epoch_sequence,
                snapshot_epoch_id=(
                    snapshot.current_epoch.epoch_id
                    if snapshot.current_epoch is not None
                    else None
                ),
                target_epoch=epoch if pending is not None else None,
            )
            for resource in snapshot.execution_resources:
                _upsert_execution_resource(cur, resource)

            for task in snapshot.tasks:
                _upsert_task(cur, task)

            for transition in scheduler.transitions:
                cur.execute(
                    """
                    INSERT INTO attention_task_transitions (
                        transition_id, task_id, revision, scheduler_cycle,
                        from_status, to_status, reason
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (transition_id) DO NOTHING
                    """,
                    (
                        transition.transition_id,
                        transition.task_id,
                        transition.revision,
                        transition.scheduler_cycle,
                        transition.from_status.value,
                        transition.to_status.value,
                        transition.reason,
                    ),
                )

            if epoch is not None:
                for assignment in assignments:
                    _insert_immutable_assignment(
                        cur,
                        scheduler_key=scheduler_key,
                        assignment=assignment,
                    )
                _insert_immutable_epoch(
                    cur,
                    scheduler_key=scheduler_key,
                    epoch=epoch,
                )

            cur.execute(
                """
                INSERT INTO attention_scheduler_state (
                    scheduler_key, cycle, active_task_id,
                    pending_preemption_task_id, admission_policy_version,
                    admitted_task_ids, epoch_sequence, current_epoch_id,
                    assignment_policy_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scheduler_key) DO UPDATE SET
                    cycle = EXCLUDED.cycle,
                    active_task_id = EXCLUDED.active_task_id,
                    pending_preemption_task_id = EXCLUDED.pending_preemption_task_id,
                    admission_policy_version = EXCLUDED.admission_policy_version,
                    admitted_task_ids = EXCLUDED.admitted_task_ids,
                    epoch_sequence = EXCLUDED.epoch_sequence,
                    current_epoch_id = EXCLUDED.current_epoch_id,
                    assignment_policy_version = EXCLUDED.assignment_policy_version,
                    updated_at = now()
                """,
                (
                    scheduler_key,
                    state_cycle,
                    snapshot.active_task_id,
                    snapshot.pending_preemption_task_id,
                    epoch.admission_policy_version
                    if epoch is not None
                    else snapshot.admission_policy_version,
                    Json([str(task_id) for task_id in admitted_task_ids]),
                    epoch_sequence,
                    epoch.epoch_id if epoch is not None else None,
                    epoch.assignment_policy_version
                    if epoch is not None
                    else snapshot.assignment_policy_version,
                ),
            )
            _replace_resource_reservations(
                cur,
                scheduler_key=scheduler_key,
                reservations=reservations,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if pending is not None:
        scheduler._commit_pending_epoch(pending.epoch.epoch_id)


def load_scheduler(
    conn: psycopg.Connection,
    *,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> JITAttentionScheduler:
    """Reconstruct resource, focus, and resumable task state without LLM context."""

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                cycle, active_task_id, pending_preemption_task_id,
                admission_policy_version, admitted_task_ids,
                epoch_sequence, current_epoch_id, assignment_policy_version
            FROM attention_scheduler_state
            WHERE scheduler_key = %s
            """,
            (scheduler_key,),
        )
        state = cur.fetchone()

        cur.execute(
            """
            SELECT
                resource_id, resource_class, capacity, system_headroom,
                enabled, metadata
            FROM attention_execution_resources
            ORDER BY resource_class ASC, resource_id ASC
            """
        )
        resource_rows = cur.fetchall()
        resources = [_row_to_execution_resource(row) for row in resource_rows]

        if state is None:
            return JITAttentionScheduler.from_snapshot(
                SchedulerSnapshot(cycle=0, tasks=[], execution_resources=resources)
            )

        cur.execute(
            """
            SELECT
                task_id, task_key, created_seq, parent_task_id,
                criticality, service_class, interruption_policy, deadline,
                required_capabilities, required_resource_classes,
                resource_requirements, dependency_ids,
                status, enqueued_cycle, revision, resumable_state
            FROM attention_tasks
            ORDER BY created_seq ASC, task_id ASC
            """
        )
        rows = cur.fetchall()

        cur.execute(
            """
            SELECT
                reservation_id, task_id, resource_id, resource_class, units
            FROM attention_resource_reservations
            WHERE scheduler_key = %s
            ORDER BY resource_class ASC, resource_id ASC, task_id ASC
            """,
            (scheduler_key,),
        )
        reservation_rows = cur.fetchall()

        epoch_row = None
        assignment_rows: list[dict[str, Any]] = []
        if state["current_epoch_id"] is not None:
            cur.execute(
                """
                SELECT
                    epoch_id, epoch_sequence, previous_epoch_id,
                    scheduler_cycle, admission_policy_version,
                    assignment_policy_version, status, assignment_ids,
                    reservations
                FROM attention_scheduling_epochs
                WHERE scheduler_key = %s AND epoch_id = %s
                """,
                (scheduler_key, state["current_epoch_id"]),
            )
            epoch_row = cur.fetchone()
            if epoch_row is None:
                raise ValueError(
                    "Scheduler state references a missing scheduling epoch"
                )
            cur.execute(
                """
                SELECT
                    assignment_id, task_id, task_revision,
                    created_epoch_sequence, reservation_ids, status
                FROM attention_assignments
                WHERE scheduler_key = %s
                """,
                (scheduler_key,),
            )
            assignment_rows = cur.fetchall()

    tasks = [_row_to_task(row) for row in rows]
    reservations = [
        _row_to_resource_reservation(row) for row in reservation_rows
    ]
    current_epoch = (
        _row_to_scheduling_epoch(epoch_row) if epoch_row is not None else None
    )
    assignment_by_id = {
        assignment.assignment_id: assignment
        for assignment in (
            _row_to_durable_assignment(row) for row in assignment_rows
        )
    }
    assignments: list[DurableAssignment] = []
    if current_epoch is not None:
        try:
            assignments = [
                assignment_by_id[assignment_id]
                for assignment_id in current_epoch.assignment_ids
            ]
        except KeyError as exc:
            raise ValueError(
                "Scheduling epoch references a missing durable assignment"
            ) from exc
    return JITAttentionScheduler.from_snapshot(
        SchedulerSnapshot(
            cycle=int(state["cycle"]),
            active_task_id=state["active_task_id"],
            pending_preemption_task_id=state["pending_preemption_task_id"],
            tasks=tasks,
            execution_resources=resources,
            admission_policy_version=state["admission_policy_version"],
            admitted_task_ids=list(state["admitted_task_ids"] or []),
            resource_reservations=reservations,
            epoch_sequence=int(state["epoch_sequence"]),
            assignment_policy_version=state["assignment_policy_version"],
            current_epoch=current_epoch,
            assignments=assignments,
        )
    )


def load_worker_visible_assignments(
    conn: psycopg.Connection,
    *,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> list[DurableAssignment]:
    """Load the complete committed assignment set exposed to workers."""

    return load_scheduler(
        conn,
        scheduler_key=scheduler_key,
    ).worker_visible_assignments()


def load_transition_count(conn: psycopg.Connection, task_id: UUID | None = None) -> int:
    """Small inspection helper used by deterministic persistence tests."""

    with conn.cursor() as cur:
        if task_id is None:
            cur.execute("SELECT count(*) FROM attention_task_transitions")
        else:
            cur.execute(
                "SELECT count(*) FROM attention_task_transitions WHERE task_id = %s",
                (task_id,),
            )
        return int(cur.fetchone()[0])


def _lock_scheduler_generation(
    cur: psycopg.Cursor[Any],
    *,
    scheduler_key: str,
    snapshot_epoch_sequence: int,
    snapshot_epoch_id: UUID | None,
    target_epoch: SchedulingEpoch | None,
) -> None:
    """Reject stale writers before they can move the current-epoch pointer."""

    cur.execute(
        """
        SELECT epoch_sequence, current_epoch_id
        FROM attention_scheduler_state
        WHERE scheduler_key = %s
        FOR UPDATE
        """,
        (scheduler_key,),
    )
    row = cur.fetchone()
    expected = (snapshot_epoch_sequence, snapshot_epoch_id)
    if row is None:
        if expected != (0, None):
            raise RuntimeError(
                "Cannot persist an existing epoch into missing scheduler state"
            )
        return

    state = _cursor_row_to_dict(cur, row)
    actual = (int(state["epoch_sequence"]), state["current_epoch_id"])
    allowed = {expected}
    if target_epoch is not None:
        allowed.add((target_epoch.sequence, target_epoch.epoch_id))
    if actual not in allowed:
        raise RuntimeError("Stale scheduler generation cannot overwrite current epoch")


def _insert_immutable_assignment(
    cur: psycopg.Cursor[Any],
    *,
    scheduler_key: str,
    assignment: DurableAssignment,
) -> None:
    cur.execute(
        """
        INSERT INTO attention_assignments (
            scheduler_key, assignment_id, task_id, task_revision,
            created_epoch_sequence, reservation_ids, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            scheduler_key,
            assignment.assignment_id,
            assignment.task_id,
            assignment.task_revision,
            assignment.created_epoch_sequence,
            Json([str(value) for value in assignment.reservation_ids]),
            assignment.status.value,
        ),
    )
    cur.execute(
        """
        SELECT
            assignment_id, task_id, task_revision,
            created_epoch_sequence, reservation_ids, status
        FROM attention_assignments
        WHERE scheduler_key = %s AND assignment_id = %s
        """,
        (scheduler_key, assignment.assignment_id),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Durable assignment insert did not produce a row")
    stored = _row_to_durable_assignment(_cursor_row_to_dict(cur, row))
    if stored.model_dump(mode="json") != assignment.model_dump(mode="json"):
        raise RuntimeError("Conflicting immutable durable assignment")


def _insert_immutable_epoch(
    cur: psycopg.Cursor[Any],
    *,
    scheduler_key: str,
    epoch: SchedulingEpoch,
) -> None:
    if epoch.status is not SchedulingEpochStatus.COMMITTED:
        raise ValueError("Only committed scheduling epochs may be persisted")
    cur.execute(
        """
        INSERT INTO attention_scheduling_epochs (
            scheduler_key, epoch_id, epoch_sequence, previous_epoch_id,
            scheduler_cycle, admission_policy_version,
            assignment_policy_version, status, assignment_ids, reservations
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            scheduler_key,
            epoch.epoch_id,
            epoch.sequence,
            epoch.previous_epoch_id,
            epoch.scheduler_cycle,
            epoch.admission_policy_version,
            epoch.assignment_policy_version,
            epoch.status.value,
            Json([str(value) for value in epoch.assignment_ids]),
            Json(
                [
                    reservation.model_dump(mode="json")
                    for reservation in epoch.reservations
                ]
            ),
        ),
    )
    cur.execute(
        """
        SELECT
            epoch_id, epoch_sequence, previous_epoch_id,
            scheduler_cycle, admission_policy_version,
            assignment_policy_version, status, assignment_ids, reservations
        FROM attention_scheduling_epochs
        WHERE scheduler_key = %s AND epoch_sequence = %s
        """,
        (scheduler_key, epoch.sequence),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Scheduling epoch insert did not produce a row")
    stored = _row_to_scheduling_epoch(_cursor_row_to_dict(cur, row))
    if stored.model_dump(mode="json") != epoch.model_dump(mode="json"):
        raise RuntimeError("Conflicting immutable scheduling epoch")


def _upsert_execution_resource(
    cur: psycopg.Cursor[Any],
    resource: ExecutionResource,
) -> None:
    cur.execute(
        """
        INSERT INTO attention_execution_resources (
            resource_id, resource_class, capacity, system_headroom, enabled, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (resource_id) DO UPDATE SET
            resource_class = EXCLUDED.resource_class,
            capacity = EXCLUDED.capacity,
            system_headroom = EXCLUDED.system_headroom,
            enabled = EXCLUDED.enabled,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        (
            resource.resource_id,
            resource.resource_class.value,
            resource.capacity,
            resource.system_headroom,
            resource.enabled,
            Json(resource.metadata),
        ),
    )


def _upsert_task(cur: psycopg.Cursor[Any], task: AttentionTask) -> None:
    metadata = task.metadata
    cur.execute(
        """
        INSERT INTO attention_tasks (
            task_id, task_key, created_seq, parent_task_id,
            criticality, service_class, interruption_policy, deadline,
            required_capabilities, required_resource_classes,
            resource_requirements, dependency_ids,
            status, enqueued_cycle, revision, resumable_state
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (task_id) DO UPDATE SET
            task_key = EXCLUDED.task_key,
            created_seq = EXCLUDED.created_seq,
            parent_task_id = EXCLUDED.parent_task_id,
            criticality = EXCLUDED.criticality,
            service_class = EXCLUDED.service_class,
            interruption_policy = EXCLUDED.interruption_policy,
            deadline = EXCLUDED.deadline,
            required_capabilities = EXCLUDED.required_capabilities,
            required_resource_classes = EXCLUDED.required_resource_classes,
            resource_requirements = EXCLUDED.resource_requirements,
            dependency_ids = EXCLUDED.dependency_ids,
            status = EXCLUDED.status,
            enqueued_cycle = EXCLUDED.enqueued_cycle,
            revision = EXCLUDED.revision,
            resumable_state = EXCLUDED.resumable_state,
            updated_at = now()
        """,
        (
            task.task_id,
            task.task_key,
            task.created_seq,
            task.parent_task_id,
            metadata.criticality.value,
            metadata.service_class.value,
            metadata.interruption_policy.value,
            metadata.deadline,
            Json(metadata.required_capabilities),
            Json([value.value for value in metadata.required_resource_classes]),
            Json(
                [
                    requirement.model_dump(mode="json")
                    for requirement in metadata.resource_requirements
                ]
            ),
            Json([str(value) for value in metadata.dependency_ids]),
            task.status.value,
            task.enqueued_cycle,
            task.revision,
            Json(task.resumable_state),
        ),
    )


def _replace_resource_reservations(
    cur: psycopg.Cursor[Any],
    *,
    scheduler_key: str,
    reservations: list[ResourceReservation],
) -> None:
    """Atomically replace one scheduler's complete authoritative reservation set."""

    cur.execute(
        "DELETE FROM attention_resource_reservations WHERE scheduler_key = %s",
        (scheduler_key,),
    )
    for reservation in reservations:
        cur.execute(
            """
            INSERT INTO attention_resource_reservations (
                scheduler_key, reservation_id, task_id,
                resource_id, resource_class, units
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                scheduler_key,
                reservation.reservation_id,
                reservation.task_id,
                reservation.resource_id,
                reservation.resource_class.value,
                reservation.units,
            ),
        )


def _row_to_execution_resource(row: dict[str, Any]) -> ExecutionResource:
    return ExecutionResource(
        resource_id=row["resource_id"],
        resource_class=ExecutionResourceClass(row["resource_class"]),
        capacity=int(row["capacity"]),
        system_headroom=int(row["system_headroom"]),
        enabled=bool(row["enabled"]),
        metadata=dict(row["metadata"] or {}),
    )


def _row_to_task(row: dict[str, Any]) -> AttentionTask:
    return AttentionTask(
        task_id=row["task_id"],
        task_key=row["task_key"],
        created_seq=int(row["created_seq"]),
        parent_task_id=row["parent_task_id"],
        metadata=SchedulingMetadata(
            criticality=TaskCriticality(row["criticality"]),
            service_class=ServiceClass(row["service_class"]),
            interruption_policy=InterruptionPolicy(row["interruption_policy"]),
            deadline=row["deadline"],
            required_capabilities=list(row["required_capabilities"] or []),
            required_resource_classes=[
                ExecutionResourceClass(value)
                for value in (row["required_resource_classes"] or [])
            ],
            resource_requirements=[
                ResourceRequirement.model_validate(value)
                for value in (row["resource_requirements"] or [])
            ],
            dependency_ids=list(row["dependency_ids"] or []),
        ),
        status=TaskStatus(row["status"]),
        enqueued_cycle=int(row["enqueued_cycle"]),
        revision=int(row["revision"]),
        resumable_state=dict(row["resumable_state"] or {}),
    )


def _row_to_resource_reservation(row: dict[str, Any]) -> ResourceReservation:
    return ResourceReservation(
        reservation_id=row["reservation_id"],
        task_id=row["task_id"],
        resource_id=row["resource_id"],
        resource_class=ExecutionResourceClass(row["resource_class"]),
        units=int(row["units"]),
    )


def _row_to_durable_assignment(row: dict[str, Any]) -> DurableAssignment:
    return DurableAssignment(
        assignment_id=row["assignment_id"],
        task_id=row["task_id"],
        task_revision=int(row["task_revision"]),
        created_epoch_sequence=int(row["created_epoch_sequence"]),
        reservation_ids=list(row["reservation_ids"] or []),
        status=AssignmentStatus(row["status"]),
    )


def _row_to_scheduling_epoch(row: dict[str, Any]) -> SchedulingEpoch:
    return SchedulingEpoch(
        epoch_id=row["epoch_id"],
        sequence=int(row["epoch_sequence"]),
        previous_epoch_id=row["previous_epoch_id"],
        scheduler_cycle=int(row["scheduler_cycle"]),
        admission_policy_version=row["admission_policy_version"],
        assignment_policy_version=row["assignment_policy_version"],
        status=SchedulingEpochStatus(row["status"]),
        assignment_ids=list(row["assignment_ids"] or []),
        reservations=[
            ResourceReservation.model_validate(value)
            for value in (row["reservations"] or [])
        ],
    )


def _cursor_row_to_dict(
    cur: psycopg.Cursor[Any],
    row: Any,
) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if cur.description is None:
        raise RuntimeError("Cursor has no result description")
    column_names = [description.name for description in cur.description]
    return dict(zip(column_names, row, strict=True))
