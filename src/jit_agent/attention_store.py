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
from jit_agent.attention_resources import ExecutionResource, ExecutionResourceClass


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
    """Persist resource, task, lifecycle, and scheduler focus state atomically."""

    snapshot = scheduler.snapshot()
    with conn.cursor() as cur:
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

        cur.execute(
            """
            INSERT INTO attention_scheduler_state (
                scheduler_key, cycle, active_task_id, pending_preemption_task_id
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (scheduler_key) DO UPDATE SET
                cycle = EXCLUDED.cycle,
                active_task_id = EXCLUDED.active_task_id,
                pending_preemption_task_id = EXCLUDED.pending_preemption_task_id,
                updated_at = now()
            """,
            (
                scheduler_key,
                snapshot.cycle,
                snapshot.active_task_id,
                snapshot.pending_preemption_task_id,
            ),
        )
    conn.commit()


def load_scheduler(
    conn: psycopg.Connection,
    *,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> JITAttentionScheduler:
    """Reconstruct resource, focus, and resumable task state without LLM context."""

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT cycle, active_task_id, pending_preemption_task_id
            FROM attention_scheduler_state
            WHERE scheduler_key = %s
            """,
            (scheduler_key,),
        )
        state = cur.fetchone()

        cur.execute(
            """
            SELECT resource_id, resource_class, capacity, enabled, metadata
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
                required_capabilities, required_resource_classes, dependency_ids,
                status, enqueued_cycle, revision, resumable_state
            FROM attention_tasks
            ORDER BY created_seq ASC, task_id ASC
            """
        )
        rows = cur.fetchall()

    tasks = [_row_to_task(row) for row in rows]
    return JITAttentionScheduler.from_snapshot(
        SchedulerSnapshot(
            cycle=int(state["cycle"]),
            active_task_id=state["active_task_id"],
            pending_preemption_task_id=state["pending_preemption_task_id"],
            tasks=tasks,
            execution_resources=resources,
        )
    )


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


def _upsert_execution_resource(
    cur: psycopg.Cursor[Any],
    resource: ExecutionResource,
) -> None:
    cur.execute(
        """
        INSERT INTO attention_execution_resources (
            resource_id, resource_class, capacity, enabled, metadata
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (resource_id) DO UPDATE SET
            resource_class = EXCLUDED.resource_class,
            capacity = EXCLUDED.capacity,
            enabled = EXCLUDED.enabled,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        (
            resource.resource_id,
            resource.resource_class.value,
            resource.capacity,
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
            required_capabilities, required_resource_classes, dependency_ids,
            status, enqueued_cycle, revision, resumable_state
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
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
            Json([str(value) for value in metadata.dependency_ids]),
            task.status.value,
            task.enqueued_cycle,
            task.revision,
            Json(task.resumable_state),
        ),
    )


def _row_to_execution_resource(row: dict[str, Any]) -> ExecutionResource:
    return ExecutionResource(
        resource_id=row["resource_id"],
        resource_class=ExecutionResourceClass(row["resource_class"]),
        capacity=int(row["capacity"]),
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
            dependency_ids=list(row["dependency_ids"] or []),
        ),
        status=TaskStatus(row["status"]),
        enqueued_cycle=int(row["enqueued_cycle"]),
        revision=int(row["revision"]),
        resumable_state=dict(row["resumable_state"] or {}),
    )
