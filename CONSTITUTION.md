# Prometheist Constitution

**Version:** 1.2  
**Adopted:** 2026-08-27  
**Amended:** 2026-08-28 — Article 27 clarified demand-driven fresh semantic reassessment; Article 30 establishes typed workpiece assembly and general terminalization rather than mandatory chatbot response.  
**Status:** supreme repository-wide engineering policy for Prometheist.

Prometheist is developed under architectural and engineering rules intended to remain true across milestones, models, storage backends, devices, interfaces, and worker processes. This Constitution is the highest-level normative engineering authority in the repository.

Each article states a hard rule, why it matters, and the authoritative deep-dive material that operationalizes it. Implementation details and tunables belong in subordinate documents unless explicitly elevated here.

## Authority and interpretation

1. `CONSTITUTION.md` is the highest-level normative engineering document in the repository.
2. Constitutional deep dives may specialize these articles but may not weaken or contradict them.
3. Current architecture documents are subordinate to the Constitution and its deep dives; milestone notes, experiments, issue discussions, implementation comments, and historical records are subordinate to current architecture.
4. A current implementation value is not automatically constitutional. Numeric bounds, thresholds, model names, database choices, retry counts, packet sizes, and similar tunables remain governed implementation values unless explicitly elevated here.
5. When documents conflict, prefer: Constitution -> constitutional deep dive -> current architecture -> active milestone -> historical record.

## Constitutional rules

### Article 1 — Continuity belongs to the system

**Rule.** Identity, memory, active working state, tasks, attention, interaction continuity, policy, execution state, work-in-progress, and causal provenance belong to Prometheist itself. They must not depend on an LLM context window, chat transcript, worker process, or named agent remaining alive.

**Why it matters.** A persistent cognitive system is not persistent if its continuity disappears with disposable compute.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 2 — Every LLM invocation is stateless; workers are disposable

**Rule.** Every LLM call starts fresh. No invocation may inherit a hidden transcript or private model context from an earlier invocation. Workers receive bounded system-owned inputs, perform a bounded role, return/persist their result at the appropriate authority boundary, and may then disappear. Permanent agents are not owners of durable identity or executive authority.

**Why it matters.** Stateless inference makes continuity inspectable, restart-safe, model-replaceable, and independent of process lifetime.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md), [`docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md)

### Article 3 — Admitted durable memory is lossless, append-only canonical evidence

**Rule.** Once information is admitted as canonical durable memory or authoritative internal history, ordinary retention, indexing, summarization, aggregation, or storage-pressure policy must not replace, rewrite, or delete the exact canonical evidence. Corrections, contradictions, and supersession are represented by new provenance-bearing records referring to prior evidence rather than mutation of history.

**Why it matters.** Prometheist must be able to reconstruct what it actually knew rather than trust successively lossy or retrospectively rewritten representations.

**Deep dive:** [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)

### Article 4 — Derived memory is replaceable; canonical evidence is not

**Rule.** Indexes, embeddings, entity links, association edges, activation metadata, routing summaries, and other derived structures are non-authoritative and rebuildable wherever their derivation permits. Non-deterministically derived assertions retain provenance, method/version, and non-authoritative status.

**Why it matters.** Retrieval machinery must be improvable without rewriting system history.

**Deep dive:** [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)

### Article 5 — Ordinary cognition and recall are bounded

**Rule.** No ordinary mechanism may solve memory scale by growing a model context window, hidden transcript, workpiece projection, or ordinary-case inference count in proportion to total corpus size. Workers externalize bounded structured state and request additional exact evidence just in time.

**Why it matters.** External memory only solves context growth if each inference remains bounded as history grows.

**Deep dives:** [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md), [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 6 — Basic persistent-memory access precedes model routing

**Rule.** Every percept receives a small system-owned, bounded, provenance-bearing activation of potentially relevant persistent memory before a fresh model decides what additional evidence/capability work is needed. A model must not first be asked whether unseen memory matters.

**Why it matters.** Asking a stateless model whether unseen evidence is relevant is circular because the evidence required to decide may itself be unseen.

**Deep dive:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 7 — WorkingState is bounded canonical activation, not a hidden memory store

**Rule.** Active WorkingState consists of bounded system-owned state that points back to canonical evidence. It must not become an ever-growing transcript, free-form summary, profile blob, inferred truth store, interaction-workpiece dump, or substitute long-term memory.

**Why it matters.** Current focus must not recreate the context-window problem under another name.

**Deep dives:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 8 — Conversations, sessions, devices, and interfaces are provenance, not cognitive boundaries

**Rule.** Conversation/session/device/interface identifiers may constrain provenance, ordering, UI, debugging, or an explicitly scoped request, but they are not default semantic walls around memory, workpieces, or continuity.

**Why it matters.** Prometheist maintains one persistent system identity rather than fragmenting cognition into chat containers.

**Deep dive:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 9 — System control is deterministic wherever deterministic control is possible

**Rule.** Stable identity, total ordering, priority derivation, dependency handling, capability identity, execution order, resource policy, retention/deletion authority, permissions, validation, component attachment, retry semantics, and other deterministically representable control-plane decisions belong to ordinary software. Given the same authoritative state, observations, and policy versions, Prometheist must reconstruct the same authoritative decision.

**Why it matters.** Models may interpret semantics, but durable system authority must remain replayable and auditable.

**Deep dives:** [`docs/architecture/SYSTEM_DETERMINISM.md`](docs/architecture/SYSTEM_DETERMINISM.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 10 — Race conditions never decide durable authority

**Rule.** Independently racing workers must not determine which durable task, resource, capability, component, or side effect wins. Selection/attachment authority is committed by deterministic policy before effects are allowed.

**Why it matters.** Operating-system scheduling may be nondeterministic; durable executive authority may not be.

**Deep dive:** [`docs/architecture/SYSTEM_DETERMINISM.md`](docs/architecture/SYSTEM_DETERMINISM.md)

### Article 11 — Attention priority and resource admission are separate

**Rule.** Attention determines which durable work deserves execution and its deterministic order. Resource admission determines which compatible subset can safely run concurrently under authoritative capacity, reservations, and headroom. Prometheist should exploit safe parallelism rather than serialize work unnecessarily.

**Why it matters.** Priority is semantic/executive; physical concurrency is hardware-safety policy.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 12 — Resource safety is fail-closed and preserves headroom

**Rule.** Work may start only after authoritative resource policy says its reservation fits safely. Prometheist reserves headroom for the operating system and required/user-authorized processes. Local LLM inference defaults conservatively to one concurrent slot until evidence justifies another value. Transient pressure may delay/re-observe; it must not silently weaken committed thresholds.

**Why it matters.** A cognitive scheduler that can crash or severely degrade its host is not valid system infrastructure.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 13 — Preemption requires both priority and real contention

**Rule.** Higher-priority work does not preempt lower-priority work merely because it is higher priority. Preemption is considered only when occupied capacity prevents safe admission and the selected victim's interruption policy permits yielding. Disturb only the minimum deterministically selected work necessary to resolve contention.

**Why it matters.** Prometheist should focus resources when necessary without discarding useful safe concurrency.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 14 — Disposable-worker execution is durable, guarded, and recovery-safe

**Rule.** A committed assignment is entitlement, not process-start permission. Worker launch must pass guarded claim-time admission; work must have durable identity, leases/ownership where needed, append-only checkpoints/results, and side-effect/idempotency semantics that fail closed when an irreversible effect cannot be proven safe to retry.

**Why it matters.** Process destruction is expected behavior; recovery and duplicate-effect prevention must belong to the protocol, not worker memory.

**Deep dives:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 15 — Models select bounded semantics; Prometheist owns execution policy

**Rule.** Models may select among bounded application-owned semantic alternatives/capabilities. They do not author durable capability IDs, dependencies, execution order, resource policy, permissions, identifiers, station topology, component attachment authority, or scheduling authority. Capability/station results should be structured evidence/state whenever possible.

**Why it matters.** Semantic interpretation is useful; model-authored control planes are difficult to validate, replay, secure, and audit.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/WORKER_PROFILE_REGISTRY.md`](docs/architecture/WORKER_PROFILE_REGISTRY.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 16 — Model-generated natural language is control/state of last resort

**Rule.** Machine control and durable state prefer enums, booleans, bounded integers, application-owned IDs, discriminated typed components, and mechanically verified selections before free-form generated language. Natural language is appropriate when language is genuinely the product or no smaller mechanically verifiable representation can express required semantics.

**Why it matters.** Closed representations reduce ambiguity, hallucinated control data, brittle parsing, and protocol nondeterminism.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 17 — Relevance, activation, evidence sufficiency, and truth are distinct

**Rule.** Attention and retrieval do not promote content to truth. Prometheist must preserve distinctions among canonical evidence, user statements/beliefs, system interpretation, derived hypotheses, corrections/supersession, counterevidence, confidence, and unknown. Unsupported facts may remain unknown.

**Why it matters.** High-recall activation is useful only if it does not silently lower epistemic standards.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)

### Article 18 — Material influence must leave durable causal provenance

**Rule.** Anything that materially influences attention, reasoning, decisions, commitments, actions, terminal outcomes, or meaningful continuity must leave enough durable provenance to explain that behavior later. High-volume raw input may remain ephemeral before admission, but the causal record of what actually influenced the system must survive.

**Why it matters.** A persistent system must explain why it acted as it did even if source buffers and workers are gone.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 19 — Internal memory and external knowledge remain distinct evidence domains

**Rule.** Retrieval from Prometheist's own persistent memory is distinct from external knowledge/action systems such as web/API/tool calls. Their provenance, authority, freshness, and failure semantics remain explicit; one source must not silently masquerade as another.

**Why it matters.** Remembering internal history is epistemically different from learning or doing something in the outside world now.

**Deep dive:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)

### Article 20 — Natural-language continuity must not become vocabulary patchwork

**Rule.** Application policy must not accumulate phrase-specific English rules, regex vocabularies, or hand-written semantic parsers to decide whether persistent context exists, which prior conversation matters, or whether the system should remember. Lexical/entity/temporal/associative mechanisms remain legitimate inside memory retrieval.

**Why it matters.** Surface-form patches overfit fixtures and move semantic authority into brittle application code.

**Deep dive:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 21 — Local-first, user-controlled, model-agnostic, and replaceable by design

**Rule.** Core durable state, replay, audit, and control-plane mechanisms must not require a hosted AI service, vendor API, remote server, Docker/Kubernetes stack, heavyweight resident model, or one specific model/runtime/database. Current PostgreSQL/Ollama integrations are reference implementations. The administrative substrate must remain inspectable/operable with `LLM = null`, with model-dependent cognition degrading as capability rather than corrupting persistent state. Architecture must remain viable on modest local hardware.

**Why it matters.** Local ownership, portability, model replacement, and modest-hardware operation are project purposes, not deployment afterthoughts.

**Deep dive:** [`docs/architecture/LOCAL_FIRST_PORTABILITY.md`](docs/architecture/LOCAL_FIRST_PORTABILITY.md)

### Article 22 — User sovereignty governs stored data and replaceable components

**Rule.** The user is the authority over Prometheist's locally held data and deployment. Architecture should support inspection, export, backup/restore, component replacement/disablement, and explicit user-directed erasure when implemented. Automatic retention/compaction must not be confused with user-directed erasure.

**Why it matters.** A local persistent cognitive system the user cannot inspect, move, or ultimately control contradicts its ownership model.

**Deep dive:** [`docs/architecture/LOCAL_FIRST_PORTABILITY.md`](docs/architecture/LOCAL_FIRST_PORTABILITY.md)

### Article 23 — Development follows a falsifiable one-mechanism experimental discipline

**Rule.** Freeze a measurable baseline, change one mechanism, rerun the same experiment, and keep the mechanism only if evidence justifies it. Preserve negative results. Do not add models, infrastructure, workers, retrieval machinery, or architectural layers merely because they are fashionable or theoretically attractive.

**Why it matters.** Changing several mechanisms at once destroys causal evidence and lets complexity accumulate without proof.

**Deep dive:** [`docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md)

### Article 24 — Behavioral numbers must be classified and evidenced

**Rule.** Runtime-affecting numeric bounds must be classified as structural invariants, external contracts, explicit collision bounds, empirical tunables, safety tunables, or environment-calibrated values. Behavioral magic numbers may not bypass governance. Environment-sensitive values require representative native evidence where appropriate.

**Why it matters.** A number is not correct because it happened to make current tests pass.

**Deep dive:** [`docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md)

### Article 25 — Verification requires deterministic regression evidence and native acceptance where reality matters

**Rule.** Deterministic CI and native development/deployment-machine acceptance have different jobs and neither substitutes for the other. Core invariants require restart/replay, cross-process/session, provenance, bounded-context, hidden-transcript-absence, failure/recovery, and deterministic-order coverage. Resource- or local-model-sensitive claims also require representative real runtime/hardware evidence before acceptance.

**Why it matters.** CI catches deterministic regressions; native acceptance proves assumptions survive contact with actual processes, models, databases, and hardware.

**Deep dive:** [`docs/engineering/TESTING_AND_ACCEPTANCE.md`](docs/engineering/TESTING_AND_ACCEPTANCE.md)

### Article 26 — Constitutional changes must be explicit

**Rule.** Code, milestone implementation, or passing tests cannot silently repeal a constitutional rule. Changing an article requires an explicit Constitution amendment, corresponding updates to affected deep dives, and acceptance evidence appropriate to the changed invariant.

**Why it matters.** Constitutional audits are useful only if architectural drift cannot redefine the rules implicitly.

**Deep dive:** [`docs/engineering/CONSTITUTIONAL_GOVERNANCE.md`](docs/engineering/CONSTITUTIONAL_GOVERNANCE.md)

### Article 27 — Semantic reassessment is demand-driven, bounded, and always fresh

**Rule.** Completion of capability/station work never inherits or extends an earlier model context and never grants a model-authored open-ended control loop. When newly acquired material requires another semantic judgment, Prometheist persists/commits the preceding material at the appropriate authority boundary, rebuilds a bounded system-owned packet, and summons a fresh stateless worker. Application-owned topology determines which next stations/capabilities are legal. User-facing generation, when the terminal path requires it, occurs only after application-owned authority/evidence policy permits it.

**Why it matters.** Prometheist needs semantic depth without recurrent model context or a model-owned executive loop. Demand-driven fresh reassessment bounds latency/failure surfaces while preserving replayable authority.

**Deep dives:** [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md), [`docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md`](docs/architecture/PRE_COGNITIVE_TRANSIENT_WORKERS.md), [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 28 — Durable queued work must have an explicit anti-starvation policy

**Rule.** Lower-priority durable work may wait behind more important work, but the scheduler must provide structured deterministic service guarantees or an equivalent explicit anti-starvation mechanism. Exact thresholds are governed tunables and never override resource/dependency/interruption safety.

**Why it matters.** A durable intention that can remain runnable forever without a governed path to service is not meaningfully executable durable work.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 29 — Insufficient authority or evidence fails closed

**Rule.** Prometheist must not guess past invalid, stale, contradictory, missing, or ambiguous control authority. Invalid model/component output, unusable resource state, unresolved dependency/authorization authority, unsupported evidence, and ambiguous irreversible effects must produce an explicit failure, abstention, wait, defer, or reconciliation state rather than fabricated success or weakened policy.

**Why it matters.** Determinism, provenance, resource safety, and epistemic accuracy all fail if the system silently invents authority.

**Deep dives:** [`docs/architecture/SYSTEM_DETERMINISM.md`](docs/architecture/SYSTEM_DETERMINISM.md), [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md), [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md)

### Article 30 — Execution is typed workpiece assembly; terminal response is optional

**Rule.** Each bounded unit of work progresses through a system-owned typed workpiece. Stations/workers receive only the minimum projection required for their bounded role and may contribute only validated registered components; deterministic application logic attaches components and determines eligible next stations. Every completed path reaches an explicit application-owned terminal outcome. User-facing natural-language response is one optional product and must not be a mandatory execution stage for action, tool, device, background, maintenance, or other non-language work.

The materialized terminal workpiece may summarize the complete typed assembly in one JSON object, but it does not replace append-only causal events/checkpoints/results required for crash recovery, provenance, or effect safety.

**Why it matters.** Prometheist is a general persistent cognitive/execution system, not a chatbot-shaped pipeline. A common typed frame gives heterogeneous tasks a uniform audit/replay surface without giving every worker the whole context or forcing irrelevant stations to run.

**Deep dives:** [`docs/architecture/INTERACTION_WORKPIECE.md`](docs/architecture/INTERACTION_WORKPIECE.md), [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/WORKER_PROFILE_REGISTRY.md`](docs/architecture/WORKER_PROFILE_REGISTRY.md)

## Constitutional audit standard

A constitutional audit evaluates every article against the entire current code path, schemas, tests, configuration, and current architecture documentation. Record:

- **PASS** — implementation/tests are consistent with the rule;
- **FAIL** — current behavior contradicts the rule;
- **GAP** — the rule is intended but not yet implemented or adequately tested;
- **NOT APPLICABLE** — the audited scope genuinely does not exercise the rule.

Every failure/gap should cite the concrete code/config/schema path and missing or contradictory evidence. A passing audit must not rely only on documentation claims.

The detailed procedure is in [`docs/engineering/CONSTITUTIONAL_GOVERNANCE.md`](docs/engineering/CONSTITUTIONAL_GOVERNANCE.md).

## Constitutional test

A proposed change is constitutionally admissible only if all of the following are true:

1. it does not contradict an article, or the Constitution is explicitly amended first;
2. it preserves canonical evidence and causal provenance;
3. it does not give hidden continuity or durable authority to an LLM/worker context;
4. deterministic policy still owns deterministic control-plane decisions;
5. boundedness and resource-safety invariants still hold;
6. the change has required deterministic and/or native evidence;
7. any new behavioral tunable is classified and governed;
8. the change does not make a reference implementation an unjustified constitutional dependency;
9. insufficient authority/evidence still fails closed rather than being guessed past;
10. typed workpiece/component authority remains application-owned and user-facing response is not made a universal execution requirement.

That standard is the default review lens for future Prometheist development.
