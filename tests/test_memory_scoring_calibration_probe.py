from pathlib import Path
import json
import runpy


def test_emit_mem_score_calibration_probe():
    root = Path(__file__).resolve().parents[1]
    module = runpy.run_path(str(root / "benchmarks" / "tune_memory_scoring.py"))
    result = module["run_staged_sweep"]()
    raise AssertionError("MEM-SCORE-001 RESULT\n" + json.dumps(result, sort_keys=True))
