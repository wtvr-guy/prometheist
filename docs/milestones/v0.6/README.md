# Prometheist v0.6 — Shared JIT Memory and Stateless Multi-Agent Execution

**Status:** in progress on `memory-kernel-v0.6-mas`.

## Question

> Can multiple completely stateless agents behave as components of one continuous system by obtaining all persistent internal context through the same JIT Memory subsystem?

v0.6 is an integration milestone. Memory Kernel v0.5 remains the frozen retrieval baseline; this milestone does not add embeddings, a vector database, an orchestration framework, or another retrieval algorithm.

## First vertical slice

The initial v0.6 implementation introduces:

- a stable MAS-facing `MemoryNeed` / `MemoryPacket` contract that does not expose retrieval implementation choices;
- `jit_memory.request_memory()` as the shared internal-memory boundary;
- application-owned memory request IDs, correlation metadata, bounded packet size, source-event IDs, ordering metadata, and association provenance;
- explicit `INTERNAL_MEMORY` origin metadata so persisted-memory recall is distinct from future external web/API/tool acquisition;
- automatic persistence of `MEMORY_REQUEST` and `MEMORY_PACKET` events;
- default exclusion of control-plane memory/delegation/error events from evidence admission;
- an incremental projection-freshness bridge so newly appended authoritative events can enter the verified v0.5 PostgreSQL candidate/association paths without requiring callers to perform a manual full rebuild;
- migration of the live Primary Agent from the legacy Retrieval Service to the shared JIT Memory boundary;
- a stateless LLM-backed `memory_specialist` that independently plans a memory need, obtains its own MemoryPacket, and returns a persisted `AGENT_RESULT`;
- persisted `AGENT_DELEGATION`, `AGENT_RESULT`, memory request/packet, response, and failure events under one interaction correlation ID;
- a deterministic specialist-level abstention guard when JIT Memory returns no supporting evidence;
- a real-Ollama cross-process acceptance test for Primary -> specialist -> JIT Memory recall, skipped only when Ollama is unavailable.

## Projection freshness boundary

v0.5 benchmark runs explicitly rebuilt derived projections before recall. The live event store correctly appends only authoritative events, so directly swapping the Primary Agent onto the v0.5 PostgreSQL kernel would have left the derived routes stale.

v0.6 addresses that integration gap outside the frozen kernel algorithms. Before satisfying a live MemoryNeed, the adapter projects newly visible events into the existing lexical projection and idempotently adds deterministic associations derived from the visible append-only history. Canonical `events` rows are never rewritten.

This is deliberately an integration mechanism, not a new memory algorithm. Its runtime cost should be characterized separately if v0.6 workloads reveal that association synchronization is material at large histories.

## Acceptance chain

The v0.6 acceptance path is intended to prove this causal sequence:

1. Process A persists an arbitrary fact and exits.
2. Process B starts with a fresh Primary Agent invocation and no inherited transcript.
3. The Primary Agent persists an `AGENT_DELEGATION` to `memory_specialist`.
4. The specialist performs a fresh inference to describe its `MemoryNeed`.
5. JIT Memory persists the request, retrieves bounded canonical evidence through the v0.5 kernel, and persists the resulting `MemoryPacket`.
6. The specialist performs another fresh inference using only its task and MemoryPacket.
7. The specialist result and Primary user-facing response are persisted.
8. The entire chain shares durable correlation metadata and can be reconstructed from the event ledger.

## Verification required before v0.6 can close

The code in this first slice must still be run on the local Prometheist PostgreSQL/Ollama development environment. Closure requires, at minimum:

```powershell
uv run pytest tests/test_jit_memory.py tests/test_primary_agent.py -v
uv run pytest -v
```

When Ollama is running, the full suite should execute the v0.6 cross-process specialist acceptance test rather than skipping it.

The frozen v0.5 regression baseline must continue to pass unchanged. Any failure in the v0.5 memory tests is a regression, not an invitation to retune the old benchmark.
