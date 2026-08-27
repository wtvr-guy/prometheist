# First Constitutional Audit remediation — 2026-08-27

**Source audit:** [`CONSTITUTIONAL_AUDIT_2026-08-27.md`](CONSTITUTIONAL_AUDIT_2026-08-27.md)  
**Remediation branch:** `constitutional-audit-remediation`  
**Scope:** every remediation item R1–R6 plus the Article 18 audit-depth note.

This work does not amend the Constitution. It changes implementation/evidence so the implementation better satisfies the existing rules.

| Item | Disposition | Evidence |
|---|---|---|
| R1 / Article 21 — `LLM = null` administration | IMPLEMENTED | `jit_agent.admin` / `prometheist-admin` inspect history, integrity, rebuild, unfinished work, export/restore, and erasure without importing an LLM runtime. |
| R2 / Article 21 — PostgreSQL FTS coupling | IMPLEMENTED | PostgreSQL FTS moved behind `RetrievalBackend`; `retrieval.py` contains no PostgreSQL FTS operators. |
| R3 / Article 22 — export/user erasure | IMPLEMENTED | Versioned digest-checked logical export/restore plus exact-confirmation whole-deployment erasure. |
| R4 / Article 3 — database-level append-only hardening | IMPLEMENTED EARLY | Automatic PostgreSQL trigger rejects ordinary UPDATE/DELETE/TRUNCATE against `events`; owner erasure is a separate transaction-local authority. |
| R5 — stale Copilot repository memory | REPOSITORY SIDE ADDRESSED | `.github/copilot-instructions.md` explicitly marks the obsolete “Increment C not implemented” state as stale and makes current code/tests authoritative. The external Copilot memory object named in the audit is not a versioned repository file and cannot itself be edited by a repository commit. |
| R6 / Article 25 — native breadth | HARNESS IMPLEMENTED; NATIVE EVIDENCE REQUIRED | `RES-CONTENTION-001` and `OLLAMA-COLD-WARM-001` are included in the native wrapper and required for its successful completion. They still require execution on the intended native host. |
| Article 18 audit-depth note | IMPLEMENTED | `test_constitutional_causal_provenance.py` independently traces a complete materially influential interaction across canonical events, task/assignment authority, scheduler epoch/resource provenance, disposable worker results, routing decision, and final response. |

## Deliberate limits

The canonical-event trigger is a database DML boundary against ordinary application/operator mutation. It is not presented as protection from a PostgreSQL superuser who intentionally alters or disables database objects.

The logical export format establishes a stable state-transfer boundary and the legacy retrieval path now has a replaceable backend protocol. PostgreSQL remains the current authoritative reference implementation; this remediation does not add an alternate production database merely to claim portability without a measured need.

Native evidence is not fabricated in CI. The new native scenarios are implementation-complete only after the intended development machine runs `scripts/run_native_constraint_calibration.ps1` successfully and preserves the resulting artifact.
