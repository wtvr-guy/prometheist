# v0.6 → v0.7 Integration Inventory — 2026-08-25

## Purpose

This record compares the remote `v0.6-capability-registry` branch, including commit `be1344aa858dc62c323756dafafb42230ba57c75` (`test: extend v0.6 conversation continuity validation`), against the active `v0.7-jit-attention` branch after the attention-centric architectural pivot.

The goal is **not** to merge the old branch wholesale. The goal is to preserve verified behavior and reusable mechanisms while refusing to carry forward architectural assumptions that Prometheist has deliberately superseded.

At the time of this review the branches share merge base `11b1e05e8517d3d0cad867d045fb50209ea5a390` and have diverged substantially. The v0.6 branch contains capability-registry, semantic-memory experiment, CLI, model-adapter, and conversation-continuity work that is not automatically present in v0.7. Conversely, v0.7 contains the new durable Attention Fabric/resource work and post-pivot documentation that is not present in v0.6.

## Decision

Do **not** merge `v0.6-capability-registry` wholesale into `v0.7-jit-attention`.

A full merge would combine useful regression evidence with superseded Primary-Agent orchestration, conversation-scoped mechanics, conflicting roadmap/README state, and semantic-memory experiments that have not yet earned a place in the post-pivot roadmap.

Instead, migrate behavior and mechanisms in bounded slices when the corresponding v0.7+ subsystem exists.

## 1. v0.6 conversation-continuity result: preserve as a behavioral baseline

The dated v0.6 experiment established a strong black-box contract that remains directly relevant after the architectural pivot.

The accepted scenario proved that:

- each external turn can execute in a completely fresh Python/CLI process;
- useful conversational continuity does not require inherited model context;
- one turn can require both recent interaction history and older relevant history from another conversation;
- unrelated persistent events can compete with the target evidence;
- context-dependent turns can be required to create persisted memory requests/packets;
- exact source-event IDs can prove that a correct-looking answer was actually grounded in the required historical evidence;
- answer validation must preserve relation and negation polarity rather than accepting token overlap;
- causal questions can require the original user-authored causal event rather than a later assistant paraphrase.

Those are forward architectural requirements. They are stronger than “the answer looked plausible,” and they should remain part of Prometheist's regression philosophy.

### Preserve/generalize these acceptance properties

1. **Fresh-process turn execution.** No model or worker may inherit hidden conversational state.
2. **Mixed-timescale recall.** One task may need immediate prior interaction state and much older history simultaneously.
3. **Cross-session evidence.** Physical chat/session boundaries must not block relevant recall.
4. **Distractor resistance.** Retrieval must select relevant evidence from competing persistent history.
5. **Exact provenance.** Correct text without required source provenance is insufficient.
6. **Polarity-sensitive assertions.** Negation and relation direction must be checked explicitly in benchmark oracles.
7. **Causal-source fidelity.** For “why” questions, a later restatement of a rule must not silently replace the underlying causal source.
8. **Opaque-token fidelity.** User-supplied names, codes, profile IDs, and similar exact identifiers must survive retrieval/synthesis unchanged when requested.
9. **Model nondeterminism is bounded, not denied.** Structured output and temperature controls can reduce variance, but deterministic policy tests remain separate from model-backed acceptance.

## 2. What must be generalized rather than copied

### 2.1 Referential continuity policy

The v0.6 implementation places `REFERENTIAL_CONTINUITY_REQUIRES_MEMORY_V1` inside `primary_agent.py`. It uses deterministic regexes to identify unresolved deictic/reference phrases such as “those approaches,” “what you just ruled out,” and “that approach,” then overrides the Primary Agent's model decision toward persisted-memory access.

The **behavior** is valuable. The **ownership location** is obsolete.

Post-pivot replacement:

```text
user utterance / external percept
        |
        v
perception + referential/context analysis
        |
        v
situation/task formation
        |
        v
explicit information need
        |
        v
JIT Memory capability
```

Reference detection may still begin with deterministic lexical/deictic rules. It should become a reusable interaction/perception policy, not a Primary-Agent override.

The system should eventually support substantially richer resolution than the bounded v0.6 reference vocabulary, while preserving deterministic handling wherever ordinary code can resolve the case.

### 2.2 User-authored authority and causal highlighting

The v0.6 continuity work discovered two useful synthesis policies:

- a user-authored constraint must not be silently overridden by an earlier assistant recommendation;
- causal questions benefit from deterministic highlighting of asserted user-authored `because` / `due to` clauses before model synthesis.

These policies should move into explicit evidence/authority and context-construction policy. They should not remain hard-coded behavior of a Primary Agent.

The exact bounded causal extractor is a useful tested baseline, not a claim of general causal parsing.

### 2.3 Structured model output

The v0.6 model adapter replaced unconstrained free-form synthesis with a validated structured answer envelope, retrying invalid output and failing closed after bounded attempts.

That pattern is reusable for future disposable workers:

> **When a model result participates in system mechanics or a tested contract, prefer a narrow validated schema over unconstrained text.**

The schema belongs to the worker/capability contract, not to an agent identity.

## 3. Capability Registry: concept strongly survives the pivot

The `v0.6-capability-registry` branch contains a deterministic JIT Capability Registry that answers a question distinct from JIT Memory:

```text
MemoryNeed -> JIT Memory
"What retained internal evidence is relevant?"

CapabilityNeed -> Capability Registry
"What can this Prometheist installation do right now?"
```

This distinction fits the new architecture extremely well.

The following properties should be preserved:

- currently installed/executable capabilities are application-owned runtime configuration, not autobiographical memory;
- capability discovery is bounded;
- deterministic discovery returns no match rather than inventing a capability;
- canonical task text is attempted before bounded supplemental cues;
- only relevant public descriptors are exposed just in time;
- the full capability catalog and internal routing metadata are not dumped into every model prompt;
- registrations can be added/removed without modifying a central cognitive worker;
- capability request/selection can remain auditable and provenance-bearing.

### Required terminology/contract changes before porting

The v0.6 implementation still encodes the old MAS worldview:

- `CapabilityKind.AGENT`;
- `requesting_agent`;
- `planning_specialist` / `analysis_specialist` as registered agents;
- `executor="stateless_specialist"`;
- a Primary Agent as the discovery caller.

The post-pivot version should generalize those concepts. Likely replacements include capability/service/tool/worker-profile categories, durable task/requester identity, and disposable execution profiles rather than agent identities.

Therefore the Capability Registry should be **ported by adaptation**, not copied verbatim and not lost.

## 4. Tests and infrastructure worth preserving

### High-value forward regression assets

- the four-turn conversation-continuity scenario itself;
- exact source-event provenance assertions;
- polarity-sensitive answer-oracle helpers;
- fresh-process CLI execution helpers;
- UTF-8 subprocess-boundary tests on Windows;
- mandatory local Ollama preflight when a real-model acceptance run is explicitly requested;
- explicit collection checks so model-backed acceptance tests cannot silently disappear from CI;
- serial execution for tests that share a globally truncated disposable database;
- bounded structured-output validation and malformed-output retry tests.

### How they should migrate

Do not require these tests to keep the same filenames, event names, or Primary-Agent call path.

Future post-pivot tests should assert **behavioral invariants** such as:

- a user utterance forms/advances a durable interaction task;
- referential context causes an explicit information need;
- JIT Memory returns the correct provenance-bearing evidence;
- a fresh disposable worker synthesizes the result;
- the physical session/conversation identifier is not required as a semantic scope;
- process destruction between turns/steps does not break continuity.

## 5. Historical-only mechanics: do not constrain v0.7+

The following are useful historical evidence but are not forward architectural requirements:

- `PrimaryAgent.handle_interaction()` owning an entire external turn;
- Primary-Agent classification deciding whether the system can respond or delegate;
- a Primary Agent applying the referential-continuity override;
- agent/specialist identity as the owner of a durable cognitive role;
- `CapabilityKind.AGENT` as a required first-class capability category;
- `requesting_agent` as the universal provenance identity;
- `AGENT_DECISION`, `AGENT_DELEGATION`, and `AGENT_RESPONSE` as permanent event ontology names;
- `ALL_CONVERSATIONS` as the normal semantic-retrieval scope;
- conversation IDs as memory partitions;
- capability discovery whose terminal purpose is “choose a specialist agent.”

Equivalent information may still exist under generalized task/worker/capability/result event types.

## 6. Semantic/pgvector work on the v0.6 branch

The v0.6 branch also contains pgvector schema support, semantic-memory code, a semantic benchmark fixture, and multiple embedding/hybrid/reranker benchmark scripts.

Do not import those into the active v0.7 architecture merely because they exist on the newer v0.6 branch.

The current roadmap deliberately places memory-generalization failure discovery in v0.10. Those experiments remain valuable research artifacts and should be revisited there against a frozen failure baseline. Their existence is not evidence that vector retrieval should become an architectural dependency today.

This separation also prevents the v0.7 Attention Fabric work from becoming entangled with an unrelated memory-mechanism decision.

## 7. CI differences

The v0.6 branch's latest workflow adds several generally useful hardening ideas:

- read-only repository permissions;
- cancellation of superseded branch runs;
- a pinned `uv` version;
- explicit collection of local-model acceptance modules;
- deterministic-vs-Ollama test separation;
- a Windows CLI encoding contract.

However, it also changes the PostgreSQL service to a pgvector image because that branch contains semantic-memory experiments.

Do not wholesale-copy the workflow into v0.7. Port generic hardening independently when needed, without making pgvector a v0.7 dependency.

## 8. Recommended integration sequence

No code from `v0.6-capability-registry` needs to be merged into v0.7 immediately merely to keep the work safe. The remote branch and commit history preserve it.

Recommended sequence:

1. **v0.7 Attention Fabric:** finish deterministic resource admission, assignments, interruption, and durable worker protocol without importing Primary-Agent orchestration.
2. **Capability discovery adaptation:** port the deterministic Capability Registry behind task/worker-neutral terminology once the worker protocol needs dynamic capability selection.
3. **Interaction execution replacement:** decompose user interactions into durable task steps; place referential/context analysis before capability selection rather than inside a Primary Agent.
4. **Continuity regression port:** rewrite the v0.6 four-turn scenario against the new execution path while preserving fresh-process execution, distractors, provenance, polarity, and causal-source assertions.
5. **Side-by-side behavioral comparison:** run the frozen v0.6 compatibility path and the new attention-centric path against equivalent scenarios until the new path reproduces or improves the accepted behavior.
6. **Retire compatibility code only after replacement acceptance:** remove Primary-Agent/specialist implementation code after its useful behaviors are covered by the new path.
7. **v0.10 semantic experiments:** revisit the v0.6 pgvector/semantic artifacts only when the memory-generalization milestone supplies a measured failure that justifies them.

## 9. Branch/history policy

Preserve both branches for now.

- `v0.6-capability-registry` is an experimental/historical line containing accepted conversation-continuity evidence and capability/semantic experiments.
- `v0.7-jit-attention` is the active architectural-development line.

Do not rebase or force-push either branch merely to make their graphs look linear. The divergence is meaningful historical evidence of the architectural pivot.

If a reusable implementation is ported, use a focused migration commit whose message identifies the source behavior/commit and adapts it to the current architecture. This makes it possible to audit what was intentionally carried forward and what was deliberately left behind.

## Bottom line

The v0.6 branch did not become irrelevant when Prometheist stopped being agent-centric.

It contains three different categories of work:

1. **Behavioral evidence that must survive** — especially stateless interaction continuity with provenance.
2. **Mechanisms that should be generalized** — especially deterministic JIT capability discovery, structured model contracts, and reference/context detection.
3. **Architecture-specific or premature mechanisms that should remain historical/experimental** — Primary-Agent orchestration, agent-first terminology, conversation-scoped cognition, and currently unearned semantic/vector dependencies.

The post-pivot project should preserve category 1, adapt category 2 when its subsystem becomes active, and resist accidentally importing category 3.
