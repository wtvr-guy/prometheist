"""Pytest session setup: point the test suite at a dedicated, disposable
PostgreSQL database (jit_agent_test) instead of the long-lived dev database
(jit_agent). Keeps the application's append-only design intact -- tests only
truncate their own disposable database, never the dev one -- while keeping
the test corpus controlled and reproducible instead of accumulating
unrelated history across runs.

Set TEST_DATABASE_URL to override; defaults to a local jit_agent_test db
using the same role as the dev database.
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


@pytest.fixture(scope="session", autouse=True)
def _reset_test_database():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text())
            cur.execute("TRUNCATE TABLE events, conversations RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()
    yield
