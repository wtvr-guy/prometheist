from pathlib import Path
import runpy

from jit_agent import db


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "compare_memory_composition_cognition.py"


def _namespace():
    return runpy.run_path(str(BENCHMARK), run_name="mem_adapt_006_integration")


def test_real_postgres_duplicate_pressure_reaches_v2_packet_not_top_k():
    ns = _namespace()
    conn = db.get_connection()
    try:
        scenario = ns["_duplicate_pressure_case"](conn, 12)
        pool = ns["_retrieve_shared_pool"](conn, scenario, pool_limit=32)
        packets = ns["_packet_variants"](pool)
    finally:
        conn.close()

    required = set(scenario.corpus.required_event_ids)
    assert required.issubset({item.source_event_id for item in pool.items})
    assert not required.issubset(
        {item.source_event_id for item in packets["top_k"].items}
    )
    assert required.issubset(
        {item.source_event_id for item in packets["relevance_coverage_v2"].items}
    )


def test_real_postgres_numeric_core_is_preserved_by_v2():
    ns = _namespace()
    conn = db.get_connection()
    try:
        scenario = ns["_numeric_core_case"](conn, 12)
        pool = ns["_retrieve_shared_pool"](conn, scenario, pool_limit=32)
        packets = ns["_packet_variants"](pool)
    finally:
        conn.close()

    required = set(scenario.corpus.required_event_ids)
    assert required.issubset({item.source_event_id for item in pool.items})
    assert required.issubset({item.source_event_id for item in packets["top_k"].items})
    assert required.issubset(
        {item.source_event_id for item in packets["relevance_coverage_v2"].items}
    )
    assert not required.issubset(
        {item.source_event_id for item in packets["coverage_v1"].items}
    )
