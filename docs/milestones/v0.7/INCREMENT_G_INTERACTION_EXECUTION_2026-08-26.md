# Increment G — Attention-Centric Interaction Execution

**Implementation date:** 2026-08-26

**Status:** implemented; PostgreSQL CI and real local-model acceptance remain
separate evidence gates.

## Decision

A user interaction is now one durable Attention task rather than a synchronous
call owned by `PrimaryAgent.handle_interaction()`. The task publishes five
bounded agent-neutral worker steps:

1. `RESOLVE_REFERENCES`;
2. `CLASSIFY`;
3. `RETRIEVE`;
4. `RESPOND`;
5. `PERSIST_RESULT`.

The fixed sequence is workflow policy, not worker authority. Each stage obtains
a fresh Increment F guarded claim, reconstructs its bounded input from
PostgreSQL, commits an immutable terminal worker result, and may disappear.
The next worker discovers the first incomplete stage solely from durable state.

## Preserved behavior without Primary-Agent ownership

The bounded v0.6 `REFERENTIAL_CONTINUITY_REQUIRES_MEMORY_V1` regex policy now
lives in reusable interaction policy before capability selection. It detects
known unresolved deictic references and deterministically requires persisted
context. Inline antecedents remain excluded, and the implementation does not
claim general coreference resolution.

The compatibility Primary Agent and CLI remain temporarily for side-by-side
regression evidence, but the new interaction entry point neither imports nor
calls the Primary Agent.

Direct response, ordinary JIT Memory retrieval, and the existing memory-
specialist behavior execute on the new path. Every LLM method call remains
stateless. The user prompt, memory request/packet, worker lifecycle, worker
outputs, error evidence, and final response are persisted.

## Crash/idempotency boundary

Memory request IDs and append-only memory request/packet event IDs are derived
from the durable interaction. The final response event ID is also derived from
the interaction. Retrying either idempotent stage therefore returns the exact
existing event instead of adding duplicate history. Deterministic event retries
fail on conflicting payloads.

After `PERSIST_RESULT`, the concurrent Attention task transitions to
`COMPLETED` and a new resource-observed epoch releases its reservation. No
legacy single-active-task focus state is required.

## Regression coverage

The Increment G suite establishes:

- bounded reference-policy behavior, including inline-antecedent exclusion;
- an end-to-end response while the legacy Primary Agent entry point is forced
  to fail if called;
- one immutable result for every durable interaction stage;
- fresh worker identities reconstructing and completing an interrupted
  cross-interaction memory workflow from PostgreSQL;
- continuity-policy evidence attached to the classification result;
- deterministic final-response retry without duplicate append-only events;
- completion of a concurrently assigned task without legacy active focus.

Static compilation, whitespace validation, and collection of all 180 tests are
performed in the implementation workspace. Database execution requires the
repository's PostgreSQL 16 CI because this workspace has no PostgreSQL server.

## Deliberate boundary

Increment G does not remove compatibility code, port the complete v0.6
Capability Registry, claim general reference resolution, implement dynamic
focus concentration, or complete Increment H's forced concurrent restart
scenario. Real Ollama-backed interaction execution and actual child-process
stage execution remain development-machine acceptance gates.
