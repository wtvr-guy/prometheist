# Deterministic Capability Registry

## Purpose

Prometheist should not preload every installed agent, tool, schema, and capability description into every LLM context. That would recreate the same resource problem the JIT Memory architecture is designed to avoid.

The Capability Registry applies the same just-in-time principle to executable system functionality:

```text
potentially useful system capability
        |
        v
CapabilityNeed
        |
        v
deterministic Capability Registry
        |
        v
bounded CapabilityPacket
        |
        v
selected capability only
        |
        v
fresh stateless agent/tool invocation
```

The registry is application-owned current system configuration. It is not an LLM specialist and it is not autobiographical memory.

## Core invariant

> **No LLM should need to remember or receive the complete MAS/tool catalog merely in case one capability becomes useful.**

An agent expresses the functionality it needs. Deterministic system code resolves that request against capabilities that are actually registered in the running Prometheist installation.

## Separation from JIT Memory

The two boundaries answer different questions:

```text
MemoryNeed -> JIT Memory -> MemoryPacket
    "What persisted internal evidence is relevant?"

CapabilityNeed -> Capability Registry -> CapabilityPacket
    "What can this Prometheist installation do right now?"
```

Historical capability changes may themselves be persisted as system events, but historical evidence that a capability once existed must not make that capability currently executable.

## Contracts

`CapabilityNeed` currently contains:

- `query_text`: a bounded natural-language description of functionality needed;
- optional capability `kinds` such as `AGENT` or `TOOL`;
- a bounded result `limit`.

`CapabilityPacket` contains:

- an application-owned request ID;
- the original need;
- bounded deterministic matches;
- only the public descriptor for each matched capability.

Internal routing terms, role instructions, executor details, and the rest of the capability catalog are not dumped into the calling LLM's prompt.

Capability discovery requests and packets are persisted as `CAPABILITY_REQUEST` and `CAPABILITY_PACKET` events so delegation remains auditable.

## Discovery policy

The v0.6 implementation uses deterministic token/phrase matching over application-owned routing terms. Matching is bounded and tie-breaking is deterministic.

The registry must return no match rather than inventing a capability.

If the capability inventory eventually becomes large enough that deterministic discovery produces a measured routing failure, a semantic selector may be evaluated later. Even then, the deterministic registry remains the authoritative source of what is actually installed and executable.

## Current specialist capabilities

The v0.6 completion experiment registers three heterogeneous stateless agent roles:

- `memory_specialist` — recall and synthesis of persisted internal history;
- `planning_specialist` — plans and recommendations constrained by persisted requirements/preferences;
- `analysis_specialist` — comparison and evaluation across persisted evidence.

The Primary Agent's permanent system prompt does not enumerate these names. It only knows that `DELEGATE` is available when specialist work would help. Application code performs capability discovery and passes only the selected specialist's short role instruction into that specialist's fresh invocation.

## Extension model

`CapabilityRegistry.register()` and `unregister()` are explicit extension points. Adding a new capability does not require another `if/elif` branch in the Primary Agent.

A future installed capability can provide:

- a stable capability ID;
- a kind (`AGENT`, `TOOL`, or another future class);
- a concise public description;
- deterministic routing terms;
- capability-specific execution metadata/instructions.

This permits future plugins or local modules to register capabilities without expanding every agent's permanent prompt.

## Prompt-budget rule

The intended context policy is progressive disclosure:

1. Permanent agent prompts contain only stable behavioral invariants and interfaces.
2. Capability catalogs are not preloaded.
3. An agent requests capability discovery when needed.
4. Only relevant matched descriptors are surfaced.
5. Only the selected capability's execution instructions/schema are bound into the fresh invocation that uses it.

This generalizes Prometheist's resource rule:

> **Nothing should occupy an LLM context merely because it might become useful later.**

Memory, capabilities, tools, artifacts, and other system state should be introduced just in time when the current inference actually needs them.

## v0.6 acceptance target

v0.6 should not be considered finally closed merely because the Primary Agent can call one hard-coded specialist.

The strengthened acceptance target is:

1. Evidence is persisted in one process and that process exits.
2. A fresh Primary invocation chooses only generic `DELEGATE` without receiving a capability catalog.
3. Deterministic capability discovery selects the relevant registered specialist.
4. The selected specialist receives no hidden transcript and independently requests JIT Memory.
5. The specialist completes its task using only its task, short role instruction, and returned MemoryPacket.
6. Capability discovery, delegation, memory request/packet, specialist result, and Primary response are durably correlated.
7. The same architecture succeeds with multiple heterogeneous specialists.

Only after that acceptance path is verified with the real local LLM/process boundary should v0.6 be frozen again and v0.7 durable execution begin.
