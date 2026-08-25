# Prometheist v0.6 — Shared JIT Memory and Stateless Multi-Agent Execution

**Status:** accepted and closed on 2026-08-21.

## Question

> Can multiple completely stateless agents behave as components of one continuous system by obtaining all persistent internal context through the same JIT Memory subsystem?

**Observed answer:** yes, within the verified v0.6 acceptance scope.

v0.6 is an integration milestone. Memory Kernel v0.5 remains the frozen retrieval baseline. At the original 2026-08-21 closure, this milestone had not added embeddings, a vector database, an orchestration framework, or another retrieval algorithm. The dated post-closure extension below distinguishes later candidate-recovery work from that original result.

## Accepted result

v0.6 established:

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
- a real-Ollama cross-process acceptance path for Primary -> specialist -> JIT Memory recall;
- canonical-first query handling in which the exact user message is the Primary Agent's canonical memory cue and the classifier's shorter semantic formulation is retained only as a bounded supplemental fallback after canonical abstention;
- retrieval-trace metadata recording which query formulation was attempted and which formulation produced evidence.

## Projection freshness boundary

v0.5 benchmark runs explicitly rebuilt derived projections before recall. The live event store correctly appends only authoritative events, so directly swapping the Primary Agent onto the v0.5 PostgreSQL kernel would have left the derived routes stale.

v0.6 addresses that integration gap outside the frozen kernel algorithms. Before satisfying a live MemoryNeed, the adapter projects newly visible events into the existing lexical projection and idempotently adds deterministic associations derived from the visible append-only history. Canonical `events` rows are never rewritten.

This remains an integration mechanism, not a new memory algorithm. Its runtime cost can be characterized separately if later workloads show that association synchronization is material at larger histories.

## Query-cue integration regression and fix

The first live Primary-Agent integration exposed an important boundary defect: allowing an LLM-generated `query_text` to replace the user's exact message made recall dependent on a lossy paraphrase preserving every distinguishing term. Switching exclusively to the exact user message repaired the real cross-process Project Oriole/Falcon/Harrier acceptance cases but exposed the opposite failure: a verbose user question could fail the frozen v0.5 direct-support gate even when the classifier had produced a useful compressed cue.

The accepted v0.6 policy therefore keeps both formulations without retuning v0.5:

1. evaluate the exact user message as the canonical cue;
2. if canonical recall returns admissible evidence, stop;
3. only after canonical abstention, try bounded supplemental query formulations;
4. preserve all attempts and the selected cue role in the MemoryPacket retrieval trace.

This repaired the integration regression without changing v0.5 scoring, evidence-admission thresholds, association behavior, or PostgreSQL candidate routing.

## Acceptance chain

The accepted v0.6 path demonstrates this causal sequence:

1. Process A persists an arbitrary fact and exits.
2. Process B starts with a fresh Primary Agent invocation and no inherited transcript.
3. The Primary Agent persists an `AGENT_DELEGATION` to `memory_specialist`.
4. The specialist performs a fresh inference to describe its `MemoryNeed`.
5. JIT Memory persists the request, retrieves bounded canonical evidence through the v0.5 kernel, and persists the resulting `MemoryPacket`.
6. The specialist performs another fresh inference using only its task and MemoryPacket.
7. The specialist result and Primary user-facing response are persisted.
8. The entire chain shares durable correlation metadata and can be reconstructed from the event ledger.

## Closure verification

On 2026-08-21 the local Prometheist PostgreSQL/Ollama development environment verified:

- the focused JIT Memory, Primary Agent, restart, and cross-conversation regression tests passed;
- the real-Ollama cross-process specialist acceptance test executed and passed;
- the complete pytest suite passed;
- the frozen v0.5 regression baseline remained green.

PR #14 (`Add canonical-first supplemental JIT cue fallback`) was then merged into `main`, completing the final v0.6 integration correction.

## Post-closure extensions and revalidation

The later v0.6 capability-registry branch added a bounded Ollama/pgvector
semantic recovery route for lexically weak cues. This does not replace or retune
the frozen v0.5 deterministic kernel: deterministic retrieval gets first refusal,
vector similarity returns bounded `SEMANTIC_CANDIDATE` source events only, and
similarity alone never changes a packet to `supported=true`. The CLI and test
environment therefore now require `schema_pgvector.sql` and the configured
embedding model even though the original closure did not.

On 2026-08-24 the milestone was revalidated against a stricter four-turn
conversation in which every turn ran in a new process. The accepted path combines
immediate same-conversation context with an older fact from a separate
conversation, rejects plausible answers without source provenance, and requires
the final pronoun-heavy turn to retrieve the preceding grounded response plus the
older causal rule. The run also exposed and corrected Windows UTF-8 harness
failures, ungrounded direct routing for referential messages, source-precedence
and exact-identifier synthesis errors, and non-enforcing local-model CI gates.

See the dated
[`conversation-continuity validation record`](experiments/V06_CONVERSATION_CONTINUITY_RESULT_2026-08-24.md)
for the frozen scenario, observed failures, isolated packet replays, changes, CI
contract, and limitations.

## Frozen conclusion

v0.6 provides evidence that multiple fresh, stateless LLM roles can operate as parts of one persistent system when durable history, memory requests, evidence packets, delegation/result state, and provenance are externalized from every LLM context window.

The next architectural question belongs to v0.7: whether unfinished multi-step work itself can survive process destruction and resume from durable execution state.
