"""Postgres connection helper and durable-store safety bootstrap."""
from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv

from jit_agent.canonical_event_guard import ensure_canonical_event_guard

load_dotenv()


def get_connection() -> psycopg.Connection:
    database_url = os.environ["DATABASE_URL"]
    conn = psycopg.connect(database_url)
    ensure_canonical_event_guard(conn)
    return conn
