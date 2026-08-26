"""Exclusive Prometheist-owned process-launch boundary for Increment F."""
from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from jit_agent.attention_observation import HostResourceProbe, ResourceSafetyPolicy
from jit_agent.attention_store import DEFAULT_SCHEDULER_KEY
from jit_agent.worker_protocol import (
    WorkerClaimAttempt,
    WorkerClaimEnvelope,
    WorkerClaimResourceObservation,
)
from jit_agent.worker_store import (
    DEFAULT_WORKER_LEASE_SECONDS,
    WorkerProtocolError,
    guarded_claim_worker_step,
    release_worker_claim,
)


class WorkerLaunchDenied(WorkerProtocolError):
    """Raised when the durable claim-time gate refuses process launch."""

    def __init__(self, observation: WorkerClaimResourceObservation) -> None:
        super().__init__(observation.reason)
        self.observation = observation.model_copy(deep=True)


@dataclass(frozen=True)
class LaunchedWorker:
    """A process handle paired with the durable lease that authorized it."""

    envelope: WorkerClaimEnvelope
    process: Any


ProcessFactory = Callable[..., Any]


class GuardedWorkerLauncher:
    """Claim, commit, and only then start a disposable worker process.

    Production code that starts a Prometheist worker belongs behind this class.
    The launcher does not select queue work: callers must register a step from
    an assignment already chosen by the deterministic Attention Fabric.
    """

    def __init__(
        self,
        connection_factory: Callable[[], psycopg.Connection],
        *,
        probe: HostResourceProbe | None = None,
        policy: ResourceSafetyPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        process_factory: ProcessFactory | None = None,
        scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    ) -> None:
        self.connection_factory = connection_factory
        self.probe = probe
        self.policy = policy
        self.clock = clock
        self.process_factory = process_factory or subprocess.Popen
        self.scheduler_key = scheduler_key

    def claim(
        self,
        *,
        step_id: UUID,
        worker_id: str,
        lease_seconds: int = DEFAULT_WORKER_LEASE_SECONDS,
    ) -> WorkerClaimEnvelope:
        """Return an executable lease or raise without starting a process."""

        conn = self.connection_factory()
        try:
            attempt: WorkerClaimAttempt = guarded_claim_worker_step(
                conn,
                step_id=step_id,
                worker_id=worker_id,
                probe=self.probe,
                policy=self.policy,
                clock=self.clock,
                lease_seconds=lease_seconds,
                scheduler_key=self.scheduler_key,
            )
        finally:
            conn.close()
        if attempt.envelope is None:
            raise WorkerLaunchDenied(attempt.observation)
        return attempt.envelope.model_copy(deep=True)

    def launch(
        self,
        *,
        step_id: UUID,
        worker_id: str,
        command: Sequence[str],
        lease_seconds: int = DEFAULT_WORKER_LEASE_SECONDS,
        env: Mapping[str, str] | None = None,
        cwd: str | Path | None = None,
    ) -> LaunchedWorker:
        """Create the durable guarded claim before invoking ``Popen``.

        Shell execution is deliberately unavailable.  A failed process spawn
        releases the just-created lease because no worker began executing it.
        """

        if isinstance(command, (str, bytes)):
            raise TypeError("worker command must be a sequence of arguments")
        normalized_command = [str(value) for value in command]
        if not normalized_command or any(not value for value in normalized_command):
            raise ValueError("worker command must contain nonempty arguments")
        envelope = self.claim(
            step_id=step_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        child_env = dict(os.environ if env is None else env)
        child_env.update(
            {
                "PROMETHEIST_WORKER_CLAIM_ID": str(envelope.claim.claim_id),
                "PROMETHEIST_WORKER_STEP_ID": str(envelope.step.step_id),
                "PROMETHEIST_WORKER_ID": envelope.claim.worker_id,
                "PROMETHEIST_WORKER_TASK_ID": str(envelope.step.task_id),
                "PROMETHEIST_WORKER_ASSIGNMENT_ID": str(
                    envelope.step.assignment_id
                ),
                "PROMETHEIST_WORKER_SCHEDULER_KEY": self.scheduler_key,
                "PROMETHEIST_WORKER_IDEMPOTENCY_KEY": (
                    envelope.step.idempotency_key
                ),
                "PROMETHEIST_WORKER_CHECKPOINT_REVISION": str(
                    envelope.claim.checkpoint_revision
                ),
            }
        )
        try:
            process = self.process_factory(
                normalized_command,
                env=child_env,
                cwd=(str(cwd) if cwd is not None else None),
                shell=False,
            )
        except Exception:
            conn = self.connection_factory()
            try:
                release_worker_claim(
                    conn,
                    claim_id=envelope.claim.claim_id,
                    worker_id=worker_id,
                    clock=self.clock,
                    scheduler_key=self.scheduler_key,
                )
            except Exception as release_error:
                raise WorkerProtocolError(
                    "worker process failed to start and its claim could not be released"
                ) from release_error
            finally:
                conn.close()
            raise
        return LaunchedWorker(envelope=envelope, process=process)
