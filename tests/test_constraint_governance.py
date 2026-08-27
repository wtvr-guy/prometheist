from pathlib import Path
import runpy


def _load_auditor():
    root = Path(__file__).resolve().parents[1]
    return runpy.run_path(str(root / "scripts" / "audit_constraints.py"))


def test_every_policy_like_numeric_constraint_is_registered():
    auditor = _load_auditor()
    findings = auditor["discover_python_constraints"]()
    registry = auditor["load_registry"]()
    uncovered = auditor["uncovered_findings"](findings, registry)
    assert not uncovered, "Unregistered behavioral constraints:\n" + "\n".join(
        f"- {item.key} value={item.value!r} line={item.line} role={item.role} :: {item.source}"
        for item in uncovered
    )
