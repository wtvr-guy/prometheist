# Local-First Portability and User Sovereignty

**Status:** constitutional architecture deep dive.  
**Constitutional authority:** implements Articles 21 and 22 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md).

Prometheist is intended to be persistent personal infrastructure controlled by the person running it. Local-first is therefore an architectural constraint, not merely a deployment preference.

## Core rule

> **Prometheist's durable identity, history, memory, control plane, replay, auditability, and recovery must remain user-controlled and must not constitutionally depend on one hosted vendor, model provider, database, orchestration stack, or machine.**

The current implementation may use specific components while the architecture matures. A reference implementation is not automatically a constitutional dependency.

## What local-first means

Local-first means that the authoritative copy of Prometheist's persistent cognitive state can be owned and operated by the user on hardware they control.

Core durable operation must not inherently require:

- a hosted AI API;
- a vendor account or subscription;
- an always-on remote server owned by a third party;
- Docker or Kubernetes;
- a managed vector/graph/object database;
- a particular LLM vendor or model family;
- one particular database engine;
- a heavyweight resident model merely to maintain or inspect authoritative state.

Optional remote services may later be used as explicitly selected capabilities or storage replicas, but they must not silently become the only owner of identity, memory, provenance, or control state.

## Reference implementations versus architectural dependencies

PostgreSQL and Ollama are current development/reference components. They are allowed and useful. The constitutional rule is that their APIs and data model must not become synonymous with Prometheist itself.

A healthy boundary is:

```text
Prometheist canonical contracts
          |
          +--> persistence adapter A
          +--> persistence adapter B
          +--> local model runtime A
          +--> model runtime B
          +--> no-LLM maintenance/audit mode
```

The architecture should define canonical logical identities, state transitions, provenance, and behavioral contracts independently of a backend's accidental details wherever practical.

Portability does not mean lowest-common-denominator design. A backend may expose richer optional performance features. It means the system can distinguish an optimization/integration from a foundational cognitive invariant.

## `LLM = null`

Prometheist's durable substrate must remain inspectable and administratively operable without a functioning LLM.

With model-dependent cognition unavailable, the system may be unable to perform semantic reasoning or generate natural-language responses. It should still be able, as applicable, to:

- start safely;
- validate/migrate durable state;
- inspect authoritative history and provenance;
- verify integrity;
- enumerate unfinished durable work;
- export/backup data;
- restore or move data;
- run deterministic audits/tests;
- disable or replace model/runtime components;
- fail model-dependent work explicitly rather than corrupting state.

A broken model runtime is a degraded capability, not loss of system identity.

## Model agnosticism

No LLM is Prometheist.

Model integration must therefore preserve:

- fresh stateless invocation semantics;
- bounded input contracts;
- mechanically validated structured control results where models participate in control;
- explicit model/runtime/version provenance when it materially affects a result;
- replacement without rewriting authoritative history;
- graceful unavailability/failure handling.

A more capable model may improve cognition. It may not become the sole store of what the system knows or has done.

## Persistence portability

Canonical durable information needs stable logical identity and export semantics independent of physical placement.

Portability should eventually cover at least:

- canonical event/history records;
- retained source evidence;
- tasks and intentions;
- active WorkingState;
- checkpoints and terminal results;
- policy/configuration versions needed for replay;
- provenance and causal relationships;
- integrity metadata;
- derived indexes when useful, while remaining rebuildable where possible.

Changing machines or storage backends must not silently change semantic identity.

A physical volume, database table, or cloud bucket does not semantically own a person, topic, memory, or situation.

## Modest-hardware requirement

Prometheist should remain architecturally usable on ordinary personal hardware rather than assuming data-center resources.

This has several consequences:

- bounded per-inference context is mandatory;
- ordinary memory navigation should rely heavily on inexpensive indexed/deterministic operations;
- local-model concurrency must be conservative and host-aware;
- heavyweight infrastructure requires measured justification;
- storage growth should be handled through tiering, indexing, caching, and progressive evidence navigation rather than destructive memory compression;
- stronger hardware may increase throughput and available capabilities without changing constitutional semantics.

“Usable” does not mean every advanced workload must be fast on every device. It means the architecture does not make unnecessary heavyweight infrastructure a prerequisite for core continuity and state ownership.

## Modular capabilities

External functionality should enter through explicit capabilities/adapters with contracts for:

- input/output schemas;
- permissions;
- resource requirements;
- provenance;
- idempotency/side effects;
- failure semantics;
- availability.

This applies to web retrieval, code execution, filesystems, databases, sensors, actuators, remote model providers, and future services.

Removing one optional capability should degrade the functionality that depends on it, not invalidate unrelated durable history.

## User sovereignty

The user is the authority over the locally held deployment and its data.

The architecture should support, as mechanisms mature:

- inspection of canonical history and system state;
- understandable provenance of consequential behavior;
- export in documented formats;
- backup and restore;
- migration between compatible deployments;
- disabling/replacing optional components;
- explicit user-directed deletion/erasure operations where implemented;
- clear distinction between unavailable data, automatically expired pre-admission raw input, and deliberately erased durable data.

Automatic retention policy is not user-directed erasure.

Prometheist's rule that admitted canonical memory is not automatically destroyed does not imply that the system may permanently deny its owner an explicit governance mechanism for erasure. If explicit erasure is implemented, it must be deliberate, auditable as policy permits, and designed separately from ordinary compaction/retention.

## Privacy and remote services

Local-first minimizes the need to expose private persistent context to third parties. If a remote capability is explicitly enabled, the architecture should make the boundary visible and minimize the data sent to what that capability requires.

Remote output must carry provenance showing that it came from an external capability rather than from Prometheist's internal memory.

The constitutional architecture does not assume that an external service is trustworthy merely because it is convenient.

## No infrastructure by fashion

Infrastructure must solve a measured problem.

The following are not valid reasons by themselves to make a component foundational:

- it is common in enterprise deployments;
- it is fashionable in agent/RAG stacks;
- it may be useful someday;
- it simplifies a single development machine setup;
- a framework expects it.

If a simpler local mechanism satisfies the frozen requirement, additional infrastructure must earn its complexity through evidence.

This rule is reinforced by [`../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](../engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md).

## Backup, restore, and migration

Portability is not established by source-code portability alone. A persistent cognitive system must be able to move its mind-state safely.

The mature architecture must test that backup/restore or export/import preserves, where applicable:

- canonical identifiers and evidence bytes;
- authoritative order;
- durable task/checkpoint state;
- WorkingState;
- policy provenance;
- associations/provenance or their rebuildability;
- integrity checks;
- unfinished work without duplicate irreversible effects.

A restored system should not need the previous model's hidden context because no such context is authoritative.

## Constitutional gaps are allowed to be visible

Current versions may not yet satisfy every portability target. That is a `GAP`, not a reason to weaken the constitutional rule to match the current implementation.

For example, a release may currently require PostgreSQL for authoritative operation while the long-lived architecture requires persistence abstraction and export/migration capability. The correct governance response is to record the gap and roadmap the work, not redefine PostgreSQL as Prometheist's identity.

## Testing requirements

Portability/user-sovereignty acceptance should eventually include:

- model-runtime replacement;
- model unavailable / `LLM = null` administrative operation;
- deterministic export/import round trips;
- backup/restore across fresh process state;
- migration to a compatible alternate host;
- reconstruction of derived indexes from canonical evidence;
- preservation of canonical IDs/provenance across physical storage changes;
- optional capability removal/degradation;
- remote-capability provenance boundaries;
- modest-hardware profiling;
- explicit user-directed erasure tests once that feature exists.

See [`../engineering/TESTING_AND_ACCEPTANCE.md`](../engineering/TESTING_AND_ACCEPTANCE.md).

## Invariant

> **Prometheist may use powerful components, but no replaceable component is allowed to become the owner of the user's persistent cognitive identity.**
