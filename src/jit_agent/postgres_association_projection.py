"""PostgreSQL persistence for the disposable v0.4 association projection."""
from __future__ import annotations

from typing import Iterable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from jit_agent.association_projection import (
    ASSOCIATION_PROJECTION_VERSION,
    derive_associations,
)
from jit_agent.associative_memory import Association
from jit_agent.memory_kernel import MemoryEvent


def rebuild_associations(
    conn: psycopg.Connection,
    events: Iterable[MemoryEvent],
) -> tuple[Association, ...]:
    """Replace disposable association rows with a deterministic rebuild."""
    associations = derive_associations(events)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM memory_association_entries")
        if associations:
            cur.executemany(
                """
                INSERT INTO memory_association_entries (
                    association_id, projection_version, source_kind, source,
                    target_kind, target, relationship, strength,
                    provenance_event_ids, required_cue_terms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        association.association_id,
                        ASSOCIATION_PROJECTION_VERSION,
                        association.source_kind,
                        association.source,
                        association.target_kind,
                        association.target,
                        association.relationship,
                        association.strength,
                        Json(list(association.provenance_event_ids)),
                        Json(list(association.required_cue_terms)),
                    )
                    for association in associations
                ],
            )
    return associations


def load_associations(conn: psycopg.Connection) -> tuple[Association, ...]:
    """Load the current derived association projection in stable ID order."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT association_id, source_kind, source, target_kind, target,
                   relationship, strength, provenance_event_ids,
                   required_cue_terms
            FROM memory_association_entries
            WHERE projection_version = %s
            ORDER BY association_id ASC
            """,
            (ASSOCIATION_PROJECTION_VERSION,),
        )
        return tuple(
            Association(
                association_id=row["association_id"],
                source_kind=row["source_kind"],
                source=row["source"],
                target_kind=row["target_kind"],
                target=row["target"],
                relationship=row["relationship"],
                strength=float(row["strength"]),
                provenance_event_ids=tuple(row["provenance_event_ids"] or ()),
                required_cue_terms=tuple(row["required_cue_terms"] or ()),
            )
            for row in cur.fetchall()
        )
