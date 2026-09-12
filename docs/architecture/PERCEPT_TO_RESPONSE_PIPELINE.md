# Percept-to-Response Pipeline

**Status:** authoritative implemented v2 path, adopted 2026-08-29 and revised
2026-09-12 to separate and durably bind evidence policy from work triage and
response realization.

**Scope:** the path from an admitted input through pre-cognitive work selection, capability execution, memory sufficiency, and final response generation.

This document records the live Prometheist percept-to-response path. It narrows
responsibilities among deterministic intake policy, the evidence-policy specialist,
the pre-cognitive work-triage LLM,
deterministic execution machinery, Adaptive Recall, the v2 Composer, current-only
response policy, application-owned evidence admission, exact-source selection, and
the final natural-language response worker.

It should be read consistently with `CONSTITUTION.md`, `COGNITIVE_ARCHITECTURE.md`, `INTERACTION_CONTINUITY.md`, and the system determinism/execution-governance documents. Older records that refer to separate focused-recall, cross-reference, or deeper-research memory capabilities, or to a recurrent general response router, are historical and superseded by this path.

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
EVIDENCE POLICY SPECIALIST
   |
   +--> persisted source/surface policy
   |
   v
Default bounded memory activation / orientation
   |
   v
WORK TRIAGE SPECIALIST
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
                        APPLICATION SOURCE FILTER
                              |
                              v
                        QUARANTINED EVIDENCE
                        before current instruction
                              |
                         exact? +------ yes --> validated source output
                              |
                              no
                              v
                        FINAL NATURAL RESPONDER
                        + personality prompt
                              |
                              v
                        persist / emit response
```

The diagram is conceptual. Independent work may be scheduled according to the Attention Fabric and resource-admission rules rather than being forced into unnecessary serial execution.

## 3. Deterministic ingestion and specialist evidence policy

Every admitted input is persisted before downstream cognition.

For an explicit user prompt, the intake boundary sets `response_required=true`. This is application-owned control state. The pre-cognitive LLM does not receive a semantic choice about whether to answer.

For a non-user percept, response policy may differ according to the deterministic contract for that percept class. A background observation may require internal work and no conversational output; a scheduled task may require an acknowledgment only under specific policy; a sensor event may require no response at all.

This distinction avoids conflating two different questions:

1. **Does this input class require conversational output?** — deterministic intake policy.
2. **What work must Prometheist perform before completing the input?** — pre-cognitive semantic work selection within bounded contracts.

Before historical retrieval, a separate evidence-policy specialist sees only the
current prompt and chooses a closed historical source scope plus response surface.
That exact typed decision is persisted as its own stage result. Every later stage
inherits it; no downstream worker reclassifies the policy.

## 4. Default memory orientation and retrieval scoping

Every admitted input receives the bounded system-owned memory activation required by
the Constitution before a model selects further capability work. The current-only
evidence-policy specialist runs first only to choose the closed provenance allowlist;
it does not decide capability work. The activation is an attention aperture, not a
complete answer and not a claim of evidentiary sufficiency.

The attention aperture and subsequent Adaptive Recall are scoped by the persisted
evidence-policy artifact to the event roles
relevant to the current request:

- **Default exclusion of model outputs:** Prior assistant/model responses
  (`INTERACTION_RESPONSE`, `AGENT_RESPONSE`, `AGENT_RESULT`) are excluded by default
  from standard memory retrieval. This prevents downstream workers from receiving
  fallible model assertions that could be mistaken for or reasoned over as user facts.
- **Explicit conversation history opt-in:** When the current prompt explicitly
  inquires about prior assistant statements, rulings, recommendations, or full
  dialogue exchanges (such as `MODEL_OUTPUT` or `MIXED_CONVERSATION` scopes), the
  system allows model-output event types in the retrieval scope.

The system remains the owner of ordering, identity, provenance, WorkingState, resource policy, and durable control state.

## 5. The pre-cognitive work-triage specialist

This worker has one LLM-powered responsibility: work selection.

For an explicit user prompt, its responsibility is:

> **Given this user prompt, bounded orientation memory, and the available non-memory capability catalog, what work must Prometheist perform before responding?**

Orientation memory is transported as quarantined evidence before a later current
message containing the user prompt and application-owned capability catalog. Text
inside memory cannot add a capability, request its own execution, or change the
current task.

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

The Composer receives the current user prompt plus the current memory evidence. The
memory is a separate quarantined evidence message followed by the current prompt; it
is not concatenated into the prompt's instruction channel. The Composer determines
whether activated/retrieved persistent memory is sufficient for a separate responder
to answer accurately.

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

Adaptive Recall is the implemented unified memory-expansion mechanism.

It replaces the architectural need for separate overlapping **focused recall**, **cross-reference**, and **deeper-research** memory capabilities.

Adaptive Recall is deterministic retrieval machinery. Given a bounded semantic memory requirement and authoritative current retrieval state/policy, it performs the permitted search/expansion/ranking/filtering steps and returns provenance-bearing memory evidence.

The division of responsibility is:

> **Composer: what remembered information is still needed?**
>
> **Adaptive Recall: how does Prometheist deterministically search its persistent memory for it?**

Adaptive Recall does not decide what Prometheist should say and does not perform the final semantic sufficiency judgment.

## 9. Evidence domains and current authority remain separate

Memory evidence and action/tool results remain distinct through response policy and
admission. Admitted data then travels in a quarantined channel that precedes the
later current user message.

```text
CURRENT USER PROMPT --> evidence-policy specialist --> durable source/surface policy
                                  |
PERSISTENT MEMORY --> role filter +-------------------+
                                                       |
TOOL / ACTION RESULTS --------------------------------+--> quarantined evidence
                                                       |
CURRENT USER PROMPT ----------------------------------+--> later current authority
```

This separation is intentional.

The Composer is allowed to request/select memory context because memory sufficiency
is its job. It must not become a semantic laundering layer through which
authoritative tool/action results are unnecessarily rewritten.

The current-only policy selects a closed historical event-role scope. Application
code—not the model—physically filters the packet. For chat backends, admitted data
uses a tool-role message; for raw Qwen transport, it uses an escaped tool-response
block. In both cases the current user message comes afterward.

## 10. Response policy, exact source output, and natural expression

For an explicit user prompt, the response stage is mandatory once required work and
the memory-sufficiency path have completed or exhausted.

Earlier in the interaction, a fresh evidence-policy worker sees only the current
prompt and selects:

1. which historical source role may establish the requested claim; and
2. whether output is natural language, one exact source substring, or a composition
   of exact source substrings.

When required historical support is absent, a separate current-only selector may
identify an explicit fallback literal. Application code accepts it only when it is a
verbatim current-prompt substring.

The selected policy is durably committed once. Retrieval, the Composer, and response
realization inherit it without another classification call.

For exact output, a deterministic-temperature model selects indexed source
substrings from admitted evidence. Application code validates every index and
substring and returns the canonical source bytes, joining multiple fields only with
formatting punctuation/whitespace copied from the current request. This path avoids
free-form respelling of opaque values.

For natural output, the final responder receives the current prompt, admitted
quarantined memory, admitted direct work results, bounded package status, and the
Prometheist personality prompt. Its job is expression.

Neither response-policy nor expression workers decide whether to respond, own memory
retrieval, execute side effects, or acquire durable continuity.

## 11. Non-user percepts

A non-user percept need not generate conversational language.

Examples include internal state maintenance, sensor observations, scheduled/background tasks, or authorized actions whose contract does not require an acknowledgment.

The key rule is that silence is determined by the **input class and deterministic policy**, not by asking a small LLM whether a direct user deserves an answer.

Future non-user percept pipelines may share portions of the same pre-cognitive, capability, memory, and Attention infrastructure while carrying a different deterministic response policy.

## 12. LLM-worker accounting

The user-response path has four semantic LLM worker **roles**, each isolated behind
its own guarded stage contract:

1. **Evidence-policy specialist** — historical source scope and output surface from current authority only.
2. **Work-triage specialist** — bounded semantic non-memory work selection only.
3. **v2 Composer** — memory-context sufficiency and semantic memory-deficit identification.
4. **Response realization** — exact-source selection or personality-conditioned
   natural-language expression; a current-only fallback selector runs only for an
   explicit unsupported-history fallback.

One guarded process may invoke only the LLM call kinds assigned to its stage. The
Composer may reassess the same sufficiency question after deterministic recall, and
realization modes are mutually exclusive ways to produce the same response-stage
outcome; neither exception combines independent semantic roles.

The number of LLM **invocations** is not fixed. The v2 Composer may recur during
Adaptive Recall, constrained outputs may retry, and exact/fallback selection is
conditional. Every invocation remains bounded and stateless.

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
- response policy is inferred without historical evidence;
- the exact response policy is persisted once and inherited without reclassification;
- every guarded LLM worker owns one coherent semantic responsibility;
- application code filters historical roles before synthesis;
- evidence precedes and remains separate from current instruction authority;
- exact outputs are mechanically validated against admitted source bytes;
- every natural final responder receives the personality prompt;
- the final responder never decides whether it should respond;
- every LLM invocation remains fresh and stateless.

## 14. Implementation consequence

The interactive CLI and other direct conversational interfaces must use a user-prompt intake contract that fixes `response_required=true` before the pre-cognitive LLM runs. The pre-cognitive model schema for that path should expose only the bounded work-selection fields it is actually authorized to choose.

The 2026-09-03 consolidation removed the parallel interaction runtime, old routing
schema, named memory capabilities, and active-document conflicts. Dated records retain
that terminology only when visibly marked historical. Any new live reference to those
interfaces is an architectural regression.

The implemented design is a narrow set of semantic LLM responsibilities surrounded
by durable, deterministic system machinery: deterministic user-response requirement;
one pre-cognitive work selector; deterministic action/capability execution; a
Composer-driven, Adaptive-Recall-backed memory-sufficiency loop; current-only
source/surface policy; application-owned evidence filtering; and validated exact
source output or personality-conditioned natural expression.
