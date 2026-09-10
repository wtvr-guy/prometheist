# Percept-to-Response Pipeline

This document defines the current target for moving from a percept to either a user-facing response or another bounded system action. It is the architectural home for the distinction between user prompts and other percept classes.

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

For a non-user percept, response policy may differ according to the deterministic contract for that percept class. A background observation may require internal work and no conversational output; a scheduled task may require an acknowledgment only under specific policy; a sensor event may require no response at all.

This distinction avoids conflating two different questions:

1. **Does this input class require conversational output?** — deterministic intake policy.
2. **What work must Prometheist perform before completing the input?** — pre-cognitive semantic work selection within bounded contracts.

## 4. Pre-cognitive model responsibilities

The pre-cognitive LLM receives the current user prompt or other percept, bounded orientation memory, and a numbered catalog of authorized non-memory capabilities.

It decides only bounded work requirements from the available catalog. It does not decide whether a user prompt deserves a response, and it does not author capability IDs, execution order, dependencies, or policy.

## 5. The pre-cognitive LLM: work selection

The pre-cognitive LLM is a disposable semantic worker. It may select one or more bounded capability indices from the application-owned catalog when work is required.

Non-user percepts may support additional non-response outcomes, but those belong to their own intake policies rather than to the user-prompt LLM contract.

## 6. Memory sufficiency and final response

A separate memory-sufficiency loop decides whether the memory exposed for the current percept is enough for the final responder.

That loop may request bounded Adaptive Recall when evidence is insufficient. It does not own the response policy for the input class.

## 7. Final response worker

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

## 8. Architectural invariants captured here

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

## 9. Relationship to v0.8

v0.8 adds deterministic perception and salience, with normalized percept contracts and salience dispositions such as `IGNORE`, `DELIBERATE`, `ORIENT`, and `REFLEX`. The percept classes defined here are the response-policy side of that work: a percept may be user-facing, internal, or non-conversational, and only some percept classes require a response.

## 10. Implementation consequences

User-facing conversational interfaces should route explicit user prompts through the deterministic response-required path.

Other percept sources should define their own intake policy, response policy, and whether they emit an external response at all. Do not infer response requirement from the mere existence of a percept.
