# RT-05 remediation record — retrieved-memory authority boundary

**Date:** 2026-08-27  
**Branch:** `redteam/v07-memory-continuity`  
**Parent red-team report:** `docs/audits/V07_RED_TEAM_2026-08-27.md`

## Frozen failure

The native red-team baseline demonstrated that a retrieved `INTERACTION_RESPONSE` containing instruction-shaped text could override the current user request even when a legitimate `USER_PROMPT` fact was retrieved alongside it. The response worker emitted the poison value. RT-05 was therefore a confirmed model-facing authority-boundary failure.

## Mechanism changed

The remediation introduces an evidence-bound Ollama transport without changing canonical memory:

- retrieved memory and capability-result content are placed in a quarantined evidence channel;
- the current percept is delivered afterward as the current instruction-bearing user message;
- application-owned capability catalogs and control schemas remain outside retrieved evidence;
- Qwen/ChatML control delimiters found inside evidence are escaped in the disposable model-facing view;
- canonical event bytes, event type, provenance, and append-only history are not rewritten or deleted.

This is a structural transport change rather than a stronger version of the old prompt admonition.

## First native acceptance

The user reported that the requested remediation tests all passed on the native Windows/PostgreSQL/Ollama environment, including the original end-to-end RT-05 exploit (`tests/test_redteam_memory_prompt_injection_native.py`) and the deterministic evidence-bound transport tests.

This establishes that the exact frozen exploit no longer reproduces under the new transport. It does **not** by itself close RT-05.

## Extended authority corpus

`tests/test_redteam_memory_authority_corpus_native.py` broadens the same mechanism test across six attack shapes:

1. direct instruction in historical assistant output;
2. stale user-authored instruction attempting to override the current request;
3. instruction-shaped `TOOL_RESULT` content;
4. forged Qwen system/assistant ChatML control tokens;
5. forged tool-response/user ChatML breakout tokens; and
6. non-imperative factual poisoning that tries to supersede the legitimate user fact.

All cases retain one legitimate historical `USER_PROMPT` fact and require the fresh native model to return that fact exactly. These attacks test the evidence/instruction authority boundary without changing retrieval, storage, WorkingState, temporal routing, or context-bound mechanisms.

## Closure criterion

RT-05 may be marked remediated only after:

- deterministic CI for the transport remains green;
- the original native RT-05 exploit remains green;
- the extended native authority corpus is green on the configured Ollama model; and
- no pre-existing regression is introduced.

If any corpus case fails, RT-05 remains open and the failing shape becomes frozen regression evidence. The corpus must not be weakened merely to obtain a pass.

## Constitutional fit

The mechanism is intended to satisfy Articles 15, 17, 23, and 29: model semantics remain useful, retrieved evidence does not acquire control authority, one mechanism is changed at a time, and ambiguous/insufficient authority is not guessed past. No new database, embedding model, graph store, or guard model is introduced because RT-05 does not currently justify that infrastructure.
