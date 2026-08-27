"""Database-level DML guard for canonical Prometheist events.

The application still owns the normal append path, but the database itself
rejects accidental/ad-hoc mutation of admitted canonical history. Explicit
owner-directed erasure is a separate transaction-local authority and never
permits UPDATE.
"""
from __future__ import annotations

import psycopg


CANONICAL_EVENT_GUARD_TRIGGER = "trg_prometheist_canonical_events_v1"
CANONICAL_EVENT_GUARD_FUNCTION = "prometheist_guard_canonical_events_v1"

_GUARD_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION {CANONICAL_EVENT_GUARD_FUNCTION}()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'canonical events are immutable; UPDATE is forbidden'
            USING ERRCODE = '55000';
    END IF;

    IF TG_OP IN ('DELETE', 'TRUNCATE')
       AND current_setting('prometheist.user_erasure', true) IS DISTINCT FROM 'on'
    THEN
        RAISE EXCEPTION 'canonical event erasure requires explicit owner authorization'
            USING ERRCODE = '55000';
    END IF;

    RETURN NULL;
END
$$
"""

_CREATE_TRIGGER_SQL = f"""
CREATE TRIGGER {CANONICAL_EVENT_GUARD_TRIGGER}
BEFORE UPDATE OR DELETE OR TRUNCATE ON events
FOR EACH STATEMENT
EXECUTE FUNCTION {CANONICAL_EVENT_GUARD_FUNCTION}()
"""


def ensure_canonical_event_guard(conn: psycopg.Connection) -> bool:
    """Install the canonical-event DML boundary once the events table exists.

    Returns ``True`` only when this call installed the guard. New/empty
    databases may call this before ``schema.sql`` exists; that is intentionally
    a no-op, and the next normal connection installs the guard after schema
    creation.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.events')")
            if cur.fetchone()[0] is None:
                conn.commit()
                return False
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgrelid = 'events'::regclass
                      AND tgname = %s
                      AND NOT tgisinternal
                )
                """,
                (CANONICAL_EVENT_GUARD_TRIGGER,),
            )
            if bool(cur.fetchone()[0]):
                conn.commit()
                return False
            cur.execute(_GUARD_FUNCTION_SQL)
            cur.execute(_CREATE_TRIGGER_SQL)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True
