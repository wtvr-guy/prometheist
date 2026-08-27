from benchmarks import native_audit_remediation as remediation


def test_evidence_complete_requires_both_native_scenarios():
    complete, failures = remediation.evidence_complete(
        {
            "RES-CONTENTION-001": {"result": "NATIVE_ACCEPTANCE"},
            "OLLAMA-COLD-WARM-001": {"result": "NO_NATIVE_EVIDENCE"},
        }
    )
    assert complete is False
    assert failures == ["OLLAMA-COLD-WARM-001"]


def test_evidence_complete_accepts_both_native_scenarios():
    complete, failures = remediation.evidence_complete(
        {
            "RES-CONTENTION-001": {"result": "NATIVE_ACCEPTANCE"},
            "OLLAMA-COLD-WARM-001": {"result": "NATIVE_ACCEPTANCE"},
        }
    )
    assert complete is True
    assert failures == []
