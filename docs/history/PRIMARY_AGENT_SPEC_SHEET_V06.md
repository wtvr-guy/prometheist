# Historical Primary Agent Specification — v0.6

> **ARCHIVED / SUPERSEDED:** This document records the Primary-Agent architecture used to establish the v0.6 stateless-worker/JIT-Memory baseline. It is not a current Prometheist architecture specification. Beginning with v0.7, Prometheist is attention-centric: system-owned attention, tasks, memory, policy, interaction continuity, and execution state replace permanent agents as first-class primitives. See [`../architecture/COGNITIVE_ARCHITECTURE.md`](../architecture/COGNITIVE_ARCHITECTURE.md), [`../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md`](../architecture/ARCHITECTURAL_PIVOT_2026-08-24.md), and [`../architecture/INTERACTION_CONTINUITY.md`](../architecture/INTERACTION_CONTINUITY.md).

The original v0.6 specification is preserved in Git history and in the v0.6 milestone record. Its enduring conclusions are retained in the current architecture: all LLM calls are stateless, continuity belongs to the system, JIT Memory is demand-driven, authoritative internal history and provenance live outside model context, and model workers are disposable.

The superseded parts are the architectural claims that a Primary Agent is the top-level coordinator, that permanent named agents are first-class system components, and that conversation/session boundaries should define ordinary memory scope.

For the complete original text, inspect the repository history prior to the v0.7 architectural pivot or the v0.6 milestone commit. This archive intentionally summarizes rather than republishes the obsolete specification as if it were current design guidance.
