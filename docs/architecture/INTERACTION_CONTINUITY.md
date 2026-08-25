# Interaction Continuity

**Status:** target architecture requirement introduced by the 2026-08-24 attention-centric pivot.

## Principle

Prometheist must not require a user to manage conversations as memory namespaces.

A user should be able to resume an earlier subject naturally:

> "Remember that thing we were talking about yesterday, about the attention layers?"

The system should infer the relevant prior context from available retrieval cues. It should not require the user to select, name, or switch to a stored conversation.

The governing invariant is:

> **Conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Context is reconstructed just in time from current intent and available retrieval cues.**

## Interaction stream, situation, and task are different things

Prometheist must distinguish three concepts that v0.6 partially conflated:

1. **Interaction stream** — where and when communication occurred. This includes UI/chat session, device, source, timestamps, and sequence coordinates.
2. **Situation/topic associations** — what an event appears to concern. These are overlapping associations, not exclusive containers.
3. **Task/intention** — durable work Prometheist is trying to advance.

The relationships are many-to-many. A single utterance may relate to several situations and tasks. A situation may span multiple sessions or devices. A task may outlive the interaction that created it.

## Conversation IDs remain provenance

Existing fields such as `conversation_id` and `conversation_seq` remain useful for:

- exact event ordering;
- provenance;
- debugging and audit;
- UI grouping;
- explicit questions such as "what did I say earlier in this chat?";
- retrieval optimization where it does not create a semantic wall.

They must not normally constrain semantic recall.

`CURRENT_CONVERSATION` versus `ALL_CONVERSATIONS` is therefore a historical v0.6 retrieval mechanism, not the target cognitive model.

## Retrieval cues

Natural topic resumption should be resolved from combinations of:

- semantic/referential cues;
- temporal expressions such as "yesterday" or "a few days ago";
- entities;
- causal relationships;
- active/recent durable tasks;
- situation/topic associations;
- prior corrections and supersession;
- source/provenance constraints when explicitly requested;
- confidence and authority.

The memory consumer asks for the information needed by the current task. JIT Memory determines which historical evidence satisfies that need without assuming that the physically current chat is the correct semantic scope.

## Topics are not replacement conversation containers

Prometheist must not simply replace `conversation_id` with a rigid `topic_id`.

An event may simultaneously concern attention scheduling, resource admission, v0.7 implementation, hardware constraints, and memory architecture. Topic/situation representations should therefore support overlapping associations and evolving relationships.

A topic change does not require a formal state transition visible to the user. The current utterance and system state determine which associations deserve cognitive attention.

## Natural ambiguity handling

When retrieval evidence strongly identifies a prior subject, Prometheist should resume it without fanfare.

When genuine semantic ambiguity remains, Prometheist should clarify meaning naturally. For example:

> "Do you mean the discussion about deterministic lane assignment, or the one about perceptual salience?"

It should not ask the user for a conversation ID or require them to navigate an internal memory namespace.

## Relationship to JIT Attention

Conversation is an interface, not the execution engine.

A user utterance enters the system as a percept. It may create or modify durable tasks, change the priority of existing work, retrieve context associated with an earlier situation, or simply request a response. Other tasks may continue concurrently.

Therefore:

```text
conversation != agent execution
conversation != task
conversation != attention lane
conversation != memory scope
```

A conversational response is one form of system work scheduled by the Attention Fabric.

## Accepted v0.6 behavioral baseline

The `v0.6-capability-registry` branch now contains a dated conversation-continuity experiment at commit `be1344aa858dc62c323756dafafb42230ba57c75`. That experiment is historical implementation evidence but a forward behavioral baseline.

Its strongest acceptance properties are:

- every external turn executes in a fresh Python/CLI process;
- one response can require both recent dialogue and older history from a different conversation;
- unrelated historical distractors compete with the target evidence;
- context-dependent turns must actually invoke persisted-memory access rather than succeed through plausible guessing;
- exact source-event IDs prove the required provenance;
- answer oracles reject polarity/negation inversions;
- causal questions require the underlying user-authored causal source when that source is part of the required evidence;
- opaque user-supplied identifiers must survive exactly when requested.

These properties should be preserved when the scenario is rewritten against the attention-centric execution path. The future test must not require the old Primary Agent, but it should remain at least as strict about statelessness and provenance.

See [`../milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md`](../milestones/v0.7/V06_INTEGRATION_INVENTORY_2026-08-25.md) for the complete migration inventory.

## What does not survive from the v0.6 mechanism

The v0.6 implementation detects a bounded set of unresolved references inside `primary_agent.py` and applies `REFERENTIAL_CONTINUITY_REQUIRES_MEMORY_V1` to override the Primary Agent toward persisted-memory access.

That is a useful tested mechanism, but the ownership is obsolete.

The replacement should move deterministic referential/context detection into reusable interaction/perception policy before capability selection:

```text
user utterance
    -> perception / referential analysis
    -> situation + task formation
    -> explicit information need
    -> JIT Memory capability
    -> disposable worker synthesis
```

The old regex vocabulary can serve as a first regression fixture, but the system should not pretend it solves general coreference resolution.

## v0.6 compatibility

v0.6 remains an important behavioral baseline. Preserve or generalize tests that establish:

- coherent stateless cross-turn recall;
- cross-conversation recall;
- corrections and supersession;
- temporal reference;
- prior-information use without inherited transcripts;
- ambiguous-reference handling;
- topic resumption.

Tests whose essential assertion is that a Primary Agent owns the turn or that a conversation boundary defines the semantic retrieval scope remain historical tests rather than forward architectural requirements.

The new architecture must reproduce or improve the useful v0.6 conversational behavior without requiring session-aware behavior from the user.

## Natural topic-resumption benchmark

A future memory-generalization benchmark should deliberately cross interaction boundaries.

Example sequence:

```text
Day/session 1:
  discuss A
  discuss B
  discuss C

Day/session 2:
  discuss D
  implicitly refer to B
  continue B
  drift into C
  return to D

Day/session 3:
  "What was that problem we found with B?"
```

No test input should provide the stored conversation identifier.

Harder cases should include progressive disambiguation:

```text
"Remember that thing from a couple days ago?"
"Not that one—the other thing about attention."
"Yeah. What problem did we identify if workers independently grabbed tasks?"
```

Measurements should include:

- correct historical referent resolution;
- precision of retrieved evidence;
- temporal correctness;
- correction/supersession correctness;
- unnecessary clarification rate;
- correct clarification when ambiguity is real;
- context size/boundedness;
- provenance correctness;
- abstention when the historical referent cannot be supported.

The v0.6 four-turn scenario should be migrated first as the fixed compatibility benchmark. The broader natural-topic benchmark should then extend beyond its bounded deictic vocabulary and deliberate conversation IDs.

## v1.0 interaction requirement

A defensible v1.0 must demonstrate continuous interaction across sessions, devices, worker destruction, and model replacement.

The user should experience one persistent Prometheist, not a collection of isolated chats. The physical boundaries of the interface remain available for provenance, but continuity belongs to the system itself.
