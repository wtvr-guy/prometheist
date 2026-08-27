# Architectural Pivot — 2026-08-24

## Decision

Prometheist will no longer treat a privileged Primary Agent, a fixed collection of long-lived agents, or a chat/session boundary as a core cognitive abstraction.

Beginning with v0.7, the target architecture is an **attention-centric persistent cognitive system** in which:

- persistent identity belongs to the system;
- internal history belongs to the system;
- durable intentions/tasks belong to the system;
- interaction continuity belongs to the system rather than a chat session;
- executive attention belongs to deterministic system policy;
- execution resources are represented explicitly;
- capabilities are modular system functions;
- LLM invocations and worker processes are disposable;
- named agents, where useful, are temporary worker roles rather than owners of continuity.

The current target architecture is documented in [`COGNITIVE_ARCHITECTURE.md`](COGNITIVE_ARCHITECTURE.md).

## What changed

The original prototype architecture centered a stateless Primary Agent that could retrieve JIT Memory, respond directly, or delegate to specialists. v0.6 successfully demonstrated that multiple fresh stateless LLM calls can participate in one continuous system without inheriting hidden transcripts.

That experiment exposed a more general possibility: if memory, task state, provenance, interaction history, and execution state already live outside the model, there is no architectural requirement for a permanent Primary Agent at all.

The v0.7 JIT Attention work then made focus itself durable and deterministic. From that point, the more coherent design became to let persistent attention allocate work directly to disposable workers and capabilities.

## New first-class primitives

The target system is organized around:

- **Percepts** — normalized observations from users, devices, software, and external sources.
- **Interaction events/streams** — provenance-bearing records of communication without treating a UI session as a memory boundary.
- **Situations / associations** — overlapping semantic, temporal, causal, entity, and task relationships among events.
- **Retention decisions** — deterministic policy decisions controlling how external observations age, aggregate, promote, or expire.
- **Tasks / intentions** — durable units of work carrying priority, dependencies, resource needs, interruption semantics, and resumable state.
- **Attention** — deterministic allocation of tasks to bounded system resources.
- **Execution resources / lanes** — explicit available compute or I/O capacity.
- **Capabilities** — memory, models, code, files, web, device interfaces, actuators, and other bounded functions.
- **Checkpoints** — durable safe-resume boundaries.
- **Actions / results** — persisted outcomes with provenance.
- **Internal events** — durable causal history of what Prometheist knew, decided, attempted, and did.
- **Memory** — demand-driven access to retained historical internal information.
- **Policy** — deterministic authority over scheduling, retention, permissions, reflex actions, and other system mechanics.

## Attention becomes plural

The first v0.7 scheduler supports one active focus. The target is a deterministic **Attention Fabric** with multiple bounded execution lanes. The number of lanes is not synonymous with logical CPU thread count; lanes represent safe resource capacity.

The system must deterministically assign compatible runnable tasks to available resources in explicit scheduling epochs rather than allowing workers to race for queue items.

## Perception and salience

Continuous external input introduces a second problem: not every observation deserves cognition.

Prometheist will develop a deterministic perceptual/salience pipeline that can classify observations as routine, attention-worthy, urgent, or eligible for a bounded reflex response.

The system must distinguish `REFLEX`, `ORIENT`, `DELIBERATE`, and `IGNORE`. Threat is not the only source of salience. Opportunity, novelty, uncertainty, active-goal relevance, social relevance, and system-integrity relevance may also influence whether an event deserves attention.

LLMs may assist semantic classification when warranted, but they provide structured evidence/proposals rather than owning scheduling or action authority.

## Persistence rule revised

The earlier design language sometimes implied that every piece of input should be persisted indefinitely. That rule is too inflexible for continuous sensors and high-volume external telemetry.

The revised distinction is:

1. **Ephemeral raw experience** — may exist only in bounded rolling buffers.
2. **Observational memory** — external data retained according to explicit deterministic policy.
3. **Internal history** — durable by default when required to explain Prometheist's cognition, attention, decisions, commitments, actions, or system state.

The new persistence invariant is:

> **Experience broadly, preserve consequentially, and never lose the internal history required to explain what Prometheist knew, what it was doing, why it focused, why it acted, and what evidence supported that behavior.**

Retention policy should support explicit classes from ephemeral data through protected evidence. An LLM may assist classification but must not possess unilateral deletion authority.

## Conversation/session boundaries revised

The v0.6 implementation uses conversation identifiers and scopes because they were useful coordinates for proving stateless cross-turn and cross-conversation recall. Those identifiers remain useful provenance metadata, but they are not the target cognitive model.

Prometheist should behave as though its experience is continuous. A user should be able to resume a prior subject naturally—for example, "remember that thing we were talking about yesterday, about the attention layers?"—without selecting, naming, or switching to a stored conversation.

The system should resolve such references from semantic, temporal, causal, entity, task, and situation cues. Topics/situations must not merely replace conversations as rigid containers: associations may overlap, one event may participate in several situations, and one situation may span many sessions or devices.

`conversation_id`, `conversation_seq`, session IDs, device IDs, and similar fields may continue to support ordering, provenance, debugging, UI grouping, explicit source-scoped questions, and retrieval optimization. They must not normally constrain semantic recall.

If a reference is genuinely ambiguous, Prometheist should ask a natural semantic clarification rather than requiring the user to manipulate an internal memory namespace.

The interaction invariant is:

> **Conversations, sessions, devices, and interfaces are provenance metadata—not cognitive boundaries. Context is reconstructed just in time from current intent and available retrieval cues.**

## Historical status of the Primary Agent and v0.6 conversation mechanics

The Primary Agent implementation and specification are not erased. They remain historically important because v0.6 established stateless LLM execution, shared JIT Memory access, cross-worker memory retrieval, persisted delegation/results, and process-level continuity without hidden transcripts.

Likewise, v0.6 conversation tests remain valuable behavioral baselines where they test cross-turn/cross-session recall, corrections, temporal reference, topic resumption, ambiguity handling, or use of prior information without inherited transcripts. Tests whose essential requirement is that a Primary Agent owns the turn or that a conversation ID forms the semantic recall boundary are historical architecture tests and should not constrain the replacement design.

Future implementation should preserve or improve the useful conversational behavior while making the mechanism session-independent.

## Roadmap consequence

The roadmap from v0.7 onward is revised around these experiments:

- **v0.7** — durable multi-lane Attention Fabric;
- **v0.8** — deterministic perception and salience;
- **v0.9** — deterministic retention and memory admission;
- **v0.10** — harder memory-generalization failure discovery, including natural topic resumption across interaction boundaries;
- **v0.11** — integrated persistent cognitive loop and session-independent conversational continuity;
- **v0.12** — operational hardening and portability;
- **v1.0** — first complete attention-centric Prometheist architecture.

v0.5 and v0.6 remain accepted and frozen as historical experimental baselines.

## Experimental discipline

The pivot does not relax the project's evidence-driven engineering rule:

> **Freeze a measurable baseline, add exactly one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it.**

The new architecture is therefore a target hypothesis, not permission to implement every subsystem simultaneously. Each milestone must earn the next layer through deterministic tests and explicit acceptance demonstrations.
