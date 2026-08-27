# Prometheist repository instructions for GitHub Copilot

Treat the current repository tree, accepted tests, `CONSTITUTION.md`, and the most recent audit records as authoritative. Do not rely on stale external repository-memory notes when they conflict with current code.

As of the accepted `v0.7` implementation (`ad77be3`), the JIT Attention Fabric includes quantitative resource admission, deterministic scheduling epochs and assignments, contention-driven preemption, guarded durable worker claims/checkpoints/results, and interaction execution through disposable workers. In particular, any older note claiming that “Increment C is not yet implemented” is stale and must not be repeated as current repository state.

For architectural reviews, verify claims directly against code/schema/tests before assigning a constitutional status. When an exploratory finding conflicts with an authoritative audit script or recorded native evidence, run/read the authoritative evidence and record the correction explicitly rather than preserving the initial guess.

All future implementation work must be checked against `CONSTITUTION.md` and its linked deep-dive documents. A passing test or implementation shortcut does not silently amend a constitutional rule.
