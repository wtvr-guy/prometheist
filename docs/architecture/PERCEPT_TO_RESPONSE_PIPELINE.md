# Percept-to-Response Pipeline

**Status:** current target architecture decision, 2026-08-29.  
**Scope:** the path from an admitted input through pre-cognitive work selection, capability execution, memory sufficiency, and final response generation.

This document records the current architectural decisions for Prometheist's percept-to-response path. It narrows responsibilities among deterministic intake policy, the pre-cognitive LLM, deterministic execution machinery, Adaptive Recall, the v2 Composer, and the final response worker.

It should be read consistently with `CONSTITUTION.md`, `COGNITIVE_ARCHITECTURE.md`, `INTERACTION_CONTINUITY.md`, and the system determinism/execution-governance documents. Where older architecture text refers to separate focused-recall, cross-reference, or deeper-research memory capabilities, the target described here supersedes that decomposition in favor of Adaptive Recall.

## 1. Core principle

Prometheist distinguishes **explicit user prompts** from other percepts.

An explicit user prompt always requires a user-facing response. That requirement is established deterministically by the interaction boundary itself; no LLM decides whether the user deserves an answer.

Other percept classes may legitimately require no response. Examples include sensor observations, background state changes, scheduled internal work, or other non-conversational inputs. Their response policy belongs to their deterministic intake contract, not to the final responder.

The final responder never decides whether to respond.

## 2. Explicit user-prompt path

```text
USER PROMPT
   |
   v
Deterministic ingestion / persistence
   |
   +--> immutable normalized Percept
   +--> bounded intake buffer + structural features
   +--> deterministic SalienceAssessment
   +--> response_required = TRUE
   |
   v
Default bounded memory activation / orientation
   |
   v
PRE-COGNITIVE LLM
   |
   +--> determine required non-memory system work
   +--> select bounded semantic capabilities/requirements
   |
   v
Persisted work directives
   |
   +------------------------------+
   |                              |
   v                              v
Capability / tool work        V2 COMPOSER
   |                           (memory only)
   v                              |
Authoritative results         sufficient?
   |                           /        \
   |                         yes        no
   |                          |          |
   |                          |          v
   |                          |    ADAPTIVE RECALL
   |                          |          |
   |                          |          +----> V2 COMPOSER
   |                          |                (repeat boundedly)
   |                          v
   |                     MEMORY PACKAGE
   |                          |
   +--------------------------+
                              |
                              v
                        FINAL RESPONDER
                        + personality prompt
                        + original user prompt
                        + memory package
                        + direct work/tool results
                              |
                              v
                        persist / emit response
```

The diagram is conceptual. Independent work may be scheduled according to the Attention Fabric and resource-admission rules rather than being forced into unnecessary serial execution.

## 3. Deterministic ingestion and response policy

Every admitted input is persisted before downstream cognition.

For an explicit user prompt, the intake boundary sets `response_required=true`. This is application-owned control state. The pre-cognitive LLM does not receive a semantic choice about whether to answer.

The live v0.8 baseline also derives an immutable normalized `Percept` plus an immutable `SalienceAssessment` before model routing. This step remains deterministic and bounded: raw canonical evidence stays lossless in the event ledger, while normalized buffers/features/salience are persisted as replaceable derived state and mirrored into the artifact journal for restart/replay.

For a non-user percept, response policy may differ according to the deterministic contract for that percept class. A background observation may require internal work and no conversational output; a scheduled task may require an acknowledgment only under specific policy; a sensor event may require no response at all.

This distinction avoids conflating two different questions:

1. **Does this input class require conversational output?** — deterministic intake policy.
2. **What work must Prometheist perform before completing the input?** — pre-cognitive semantic work selection within bounded contracts.

## 4. Default memory orientation

Every admitted input receives the bounded system-owned memory activation required by the Constitution before model routing. This is an attention aperture, not a complete answer and not a claim of evidentiary sufficiency.

The system remains the owner of ordering, identity, provenance, WorkingState, resource policy, and durable control state.

Deterministic salience and model reasoning are intentionally separate. The salience layer may provide bounded advisory context to later model workers, but models do not gain policy authority over response requirements, reflex authorization, task identity, scheduling, or memory ordering by virtue of seeing the salience result.

## 5. The pre-cognitive LLM: work selection

There is one LLM-powered role in the pre-cognitive pipeline.

For an explicit user prompt, its responsibility is:

> **Given this user prompt, bounded orientation memory, and the available non-memory capability catalog, what work must Prometheist perform before responding?**

The model may determine, through bounded application-owned outputs:

- that no external/non-memory work is required;
- that one or more system capabilities or external actions are required;
- which bounded capability indices express those requirements.

The model does **not** decide whether to respond to an explicit user prompt. It also does not own scheduling, capability identity, resource admission, permissions, durable identifiers, retry semantics, or side effects. It expresses semantic work requirements within application-owned contracts; Prometheist deterministically translates committed directives into executable work.

Conceptually, an explicit user prompt therefore has two possible work shapes:

```text
NO EXTERNAL WORK + RESPONSE -> memory sufficiency path -> responder
WORK + RESPONSE             -> execute work; responder receives work results directly
```

Non-user percepts may support additional non-response outcomes, but those belong to their own intake policies rather than to the user-prompt LLM contract.

## 6. Capability and tool execution

When the pre-cognitive work selection requires work, Prometheist dispatches that work through its deterministic control plane and transient-worker protocol.

Examples include scheduling a task, calling an external tool, performing filesystem/database work, invoking a bounded capability, or carrying out another authorized action.

The pre-cognitive LLM does not perform these effects itself.

Capability/tool workers return authoritative structured results whenever possible. Those results are persisted with provenance and remain distinct from persistent-memory evidence.

A completed tool or capability result does **not** pass through the v2 Composer merely so the Composer can restate or reinterpret it.

## 7. The v2 Composer: memory-context sufficiency specialist

The v2 Composer has a deliberately narrow domain.

Its responsibility is to determine whether the memory context available for a required user-facing response is sufficient for the final responder.

It is **not** a general evidence synthesizer, a second pre-cognitive executive, a tool-result interpreter, or the final response generator.

The Composer receives the current user prompt plus the current memory evidence. It determines whether the activated/retrieved persistent memory is sufficient for a separate responder to answer accurately.

### 7.1 If memory is sufficient

The Composer produces/approves a bounded response-ready **memory package** for the final responder.

### 7.2 If memory is insufficient

The Composer identifies the semantic memory deficit: what additional remembered information is needed to make the memory context sufficient.

It may direct another Adaptive Recall request for that deficit. The Composer does not choose database implementation details, author arbitrary search-control policy, or directly search storage.

The loop is therefore:

```text
V2 COMPOSER
    |
    +-- sufficient --> MEMORY PACKAGE
    |
    +-- insufficient --> semantic memory deficit
                              |
                              v
                        ADAPTIVE RECALL
                              |
                              v
                         new memories
                              |
                              +----> V2 COMPOSER
```

This loop is bounded by deterministic stopping/resource policies. Repeated Composer invocations are fresh/stateless LLM calls supplied only with the bounded state needed for that invocation.

### 7.3 Exhaustion and legitimate unknowns

Adaptive Recall can exhaust its permitted search without establishing the requested memory fact. That is a valid result, not permission to hallucinate.

Once deterministic stopping criteria establish that no further useful memory expansion is available within policy, the Composer can produce a memory package that explicitly represents the unresolved/unknown state and the relevant evidence that was found. The final responder can then accurately tell the user that Prometheist cannot establish the requested fact from available memory.

## 8. Adaptive Recall

Adaptive Recall is the target unified memory-expansion capability.

It replaces the architectural need for separate overlapping **focused recall**, **cross-reference**, and **deeper-research** memory capabilities.

Adaptive Recall is deterministic retrieval machinery. Given a bounded semantic memory requirement and authoritative current retrieval state/policy, it performs the permitted search/expansion/ranking/filtering steps and returns provenance-bearing memory evidence.

The division of responsibility is:

> **Composer: what remembered information is still needed?**
>
> **Adaptive Recall: how does Prometheist deterministically search its persistent memory for it?**

Adaptive Recall does not decide what Prometheist should say and does not perform the final semantic sufficiency judgment.

## 9. Two independent information channels into the final responder

Memory evidence and action/tool results remain separate until the final response worker.

```text
PERSISTENT MEMORY -> V2 Composer -> memory package ----+
                                                     |
TOOL RESULTS ----------------------------------------+--> FINAL RESPONDER
                                                     |
CAPABILITY / ACTION RESULTS -------------------------+
                                                     |
ORIGINAL USER PROMPT --------------------------------+
```

This separation is intentional.

The Composer is allowed to transform/select memory context because memory sufficiency is its job. It must not become a semantic laundering layer through which authoritative tool/action results are unnecessarily rewritten.

The final responder receives authoritative structured work results directly, together with their provenance/status where relevant.

## 10. Final response worker

For an explicit user prompt, the final response worker is mandatory once the required work and memory-sufficiency path have completed or exhausted according to policy.

It receives, as applicable:

1. the original/current user prompt;
2. the response-ready memory package from the v2 Composer;
3. authoritative final tool/capability/action results directly from their execution paths;
4. other bounded system-owned response metadata required by policy; and
5. the Prometheist personality prompt.

The personality prompt is always supplied to the final response worker.

The final responder's job is expression: generate the appropriate user-facing natural-language response from the completed inputs.

It does not decide whether to respond. It does not own memory retrieval. It does not execute requested side effects. It does not become the owner of durable continuity.

## 11. Non-user percepts

A non-user percept need not generate conversational language.

Examples include internal state maintenance, sensor observations, scheduled/background tasks, or authorized actions whose contract does not require an acknowledgment.

The key rule is that silence is determined by the **input class and deterministic policy**, not by asking a small LLM whether a direct user deserves an answer.

Future non-user percept pipelines may share portions of the same pre-cognitive, capability, memory, and Attention infrastructure while carrying a different deterministic response policy.

## 12. LLM-worker accounting

On the ordinary user-response path there are three distinct LLM-powered worker **roles**:

1. **Pre-cognitive LLM** — bounded semantic work selection only.
2. **v2 Composer** — memory-context sufficiency and semantic memory-deficit identification.
3. **Final response worker** — personality-conditioned user-facing expression.

There is only **one LLM-powered role in the pre-cognitive pipeline**.

The number of LLM **invocations** is not necessarily three. The v2 Composer may be invoked more than once when Adaptive Recall requires iterative memory expansion. Each invocation remains stateless.

Current resource policy remains independent of this logical count: multiple logical LLM roles do not imply simultaneous resident inference. Local execution remains subject to the one-LLM-at-a-time default and resource-admission policy unless empirical evidence and configured capacity justify otherwise.

## 13. Architectural invariants captured here

The following are deliberate boundaries:

- every explicit user prompt requires a response;
- response requirement for an explicit user prompt is deterministic application-owned control state, not an LLM choice;
- non-user percepts may have different deterministic response policies;
- the pre-cognitive LLM determines semantic work requirements, not whether to answer the user;
- system execution/control remains deterministic wherever deterministic control is possible;
- Adaptive Recall is deterministic and supersedes separate focused-recall/cross-reference/deeper-research memory modes;
- the v2 Composer is a memory-context sufficiency specialist, not a general-purpose executive;
- the Composer may identify missing memory semantics but does not own low-level retrieval policy;
- authoritative tool/action results bypass the Composer and reach the final responder directly;
- memory and external/tool evidence retain distinct provenance domains;
- the final responder always receives the personality prompt;
- the final responder never decides whether it should respond;
- every LLM invocation remains fresh and stateless.

## 14. Implementation consequence

The interactive CLI and other direct conversational interfaces must use a user-prompt intake contract that fixes `response_required=true` before the pre-cognitive LLM runs. The pre-cognitive model schema for that path should expose only the bounded work-selection fields it is actually authorized to choose.

Existing code and documentation should be audited against this target before implementation is considered complete. In particular, older references to `MEMORY_ANALYSIS`, focused recall, cross-reference, deeper research, a second pre-cognitive synthesis LLM, or model-selected silence for direct user prompts should not be treated as current target architecture where they conflict with this document.

The intended target is a narrow set of semantic LLM responsibilities surrounded by durable, deterministic system machinery: deterministic user-response policy; one pre-cognitive work-selection worker; deterministic action/capability execution; a Composer-driven, Adaptive-Recall-backed memory-sufficiency loop; and a personality-conditioned final responder that receives memory context and authoritative work results through separate channels.
