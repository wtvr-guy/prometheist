"""Pytest database setup for an isolated, disposable PostgreSQL test store.

The test suite is redirected before application modules are imported so the
long-lived development database cannot be selected through the normal `.env`.
A database-name guard adds a second line of defense against destructive test
setup, and every test begins from an empty derived/authoritative store.

Set TEST_DATABASE_URL to override the default. The selected database name must
contain `test` or `benchmark`.
"""
from __future__ import annotations

import os
import pathlib

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://jit_agent_app:jit_agent_dev_pw@localhost:5432/jit_agent_test",
)

import pytest

from jit_agent import db

SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "schema.sql"


def _require_disposable_database(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        database_name = str(cur.fetchone()[0])
    lowered = database_name.casefold()
    if "test" not in lowered and "benchmark" not in lowered:
        raise RuntimeError(
            "Refusing destructive pytest setup against database "
            f"{database_name!r}; TEST_DATABASE_URL must select a dedicated "
            "database whose name contains 'test' or 'benchmark'."
        )
    return database_name


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database():
    """Apply the idempotent schema once after verifying the database target."""
    conn = db.get_connection()
    try:
        _require_disposable_database(conn)
        with conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text())
        conn.commit()
    finally:
        conn.close()
    yield


@pytest.fixture(autouse=True)
def _reset_test_database(_prepare_test_database):
    """Give every test a clean authoritative ledger and derived-memory state."""
    conn = db.get_connection()
    try:
        _require_disposable_database(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE TABLE
                    attention_resource_reservations,
                    attention_task_transitions,
                    attention_scheduler_state,
                    attention_tasks,
                    attention_execution_resources,
                    memory_association_entries,
                    memory_projection_entries,
                    memory_projection_runs,
                    event_integrity,
                    events,
                    conversations
                RESTART IDENTITY CASCADE
                """
            )
            cur.execute("ALTER SEQUENCE attention_task_created_seq RESTART WITH 1")
        conn.commit()
    finally:
        conn.close()
    yield
