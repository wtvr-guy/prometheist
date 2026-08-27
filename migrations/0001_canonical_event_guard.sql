-- Constitutional hardening: database-level DML boundary for canonical events.
--
-- This supersedes the older schema.sql comment that described append-only
-- storage as application-enforced only. New application connections install
-- the same versioned guard automatically; this migration exists for explicit
-- operator/audit application to an existing database.

CREATE OR REPLACE FUNCTION prometheist_guard_canonical_events_v1()
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
$$;

DROP TRIGGER IF EXISTS trg_prometheist_canonical_events_v1 ON events;
CREATE TRIGGER trg_prometheist_canonical_events_v1
BEFORE UPDATE OR DELETE OR TRUNCATE ON events
FOR EACH STATEMENT
EXECUTE FUNCTION prometheist_guard_canonical_events_v1();
