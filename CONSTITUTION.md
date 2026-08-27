# Prometheist Constitution

**Version:** 1.0  
**Adopted:** 2026-08-27  
**Status:** supreme repository-wide engineering policy for Prometheist.

Prometheist is developed under a small set of architectural and engineering rules that are intended to remain true across milestones, implementations, models, storage backends, devices, and worker processes. This Constitution collects those rules in one place so that future design reviews and codebase audits can test the implementation against an explicit standard.

This file is intentionally concise. Each article states the hard rule, why it matters, and the authoritative deep-dive document that explains the rule in detail.

## Authority and interpretation

1. `CONSTITUTION.md` is the highest-level normative engineering document in the repository.
2. Constitutional deep dives explain and operationalize these articles. They may be more specific, but they may not weaken or contradict the Constitution.
3. Roadmaps, milestone notes, experiments, issue discussions, implementation comments, and historical documents do not silently override a constitutional rule.
4. A current implementation value is not automatically constitutional. Numeric bounds, thresholds, model names, database choices, retry counts, packet sizes, and similar tunables remain policy or implementation values unless this file explicitly elevates them.
5. When two documents conflict, prefer the Constitution, then the current constitutional deep dive, then current architecture documents, then active milestone documents, then historical records.

## Constitutional rules

### Article 1 — Continuity belongs to the system

**Rule.** Identity, memory, active working state, tasks, attention, interaction continuity, policy, execution state, and causal provenance belong to Prometheist itself. They must not depend on an LLM context window, chat transcript, worker process, or named agent remaining alive.

**Why it matters.** A persistent cognitive system cannot be persistent if its state disappears when disposable compute disappears.

**Deep dive:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)

### Article 2 — Every LLM invocation is stateless; workers are disposable

**Rule.** Every LLM call starts fresh. No model invocation may inherit a hidden transcript or private context from an earlier invocation. Workers receive only bounded system-owned durable/task-local inputs, persist their result or checkpoint, and may then disappear. Agent-like names may describe temporary roles, but permanent agents are not owners of durable identity or executive authority.

**Why it matters.** Stateless inference makes continuity inspectable, restart-safe, model-replaceable, and independent of process lifetime.

**Deep dive:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)

### Article 3 — Admitted durable memory is lossless canonical evidence

**Rule.** Once information is admitted as canonical durable memory or authoritative internal history, ordinary retention, indexing, summarization, aggregation, or storage-pressure policy must not replace or delete the exact canonical evidence. Derived structures are navigation aids, not substitute memories.

**Why it matters.** Prometheist's accuracy objective depends on being able to return to exact source evidence rather than trusting successively lossy reconstructions.

**Deep dive:** [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)

### Article 4 — Derived memory is replaceable; canonical evidence is not

**Rule.** Indexes, embeddings, entity links, association edges, salience/activation metadata, summaries used as aids, and other derived structures must be explicitly non-authoritative and rebuildable wherever their derivation permits it. Non-deterministically derived assertions must retain provenance, method/version, and non-authoritative status.

**Why it matters.** Prometheist must be able to improve its retrieval machinery without rewriting its history.

**Deep dive:** [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)

### Article 5 — Ordinary cognition and recall are bounded

**Rule.** No ordinary mechanism may solve memory scale by growing a model context window, hidden worker transcript, or ordinary-case inference count in proportion to total corpus size. Workers externalize bounded structured state and request additional exact evidence just in time.

**Why it matters.** External persistent memory only solves context growth if each inference remains bounded as history grows.

**Deep dives:** [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md), [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 6 — Basic persistent-memory access precedes model routing

**Rule.** Every percept receives a small system-owned, bounded, provenance-bearing activation of potentially relevant persistent memory before a fresh model decides what further capability work is needed. A model must not first be asked whether unseen memory matters.

**Why it matters.** Asking a stateless model whether unseen evidence is relevant is circular: the evidence needed to answer may itself be unseen.

**Deep dive:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 7 — WorkingState is bounded canonical activation, not a hidden memory store

**Rule.** Active working state consists of bounded system-owned state that points back to canonical evidence. It must not become an ever-growing transcript, free-form summary, profile blob, inferred truth store, or substitute long-term memory.

**Why it matters.** WorkingState should preserve current cognitive focus without reintroducing the context-window problem through another name.

**Deep dive:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 8 — Conversations, sessions, devices, and interfaces are provenance, not cognitive boundaries

**Rule.** Stored conversation IDs and interface/session/device identifiers may constrain provenance, ordering, UI, debugging, or an explicitly scoped request, but they are not default semantic walls around memory or continuity.

**Why it matters.** Prometheist is intended to maintain one persistent identity and history rather than fragment cognition into chat containers.

**Deep dive:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 9 — System control is deterministic wherever deterministic control is possible

**Rule.** Stable identity, total ordering, priority derivation, dependency handling, capability identity, execution order, resource policy, retention/deletion authority, permissions, validation, retry semantics, and other control-plane decisions belong to ordinary software whenever they can be represented deterministically. Given the same authoritative durable state, authoritative observations, and policy versions, Prometheist must reconstruct the same system decision.

**Why it matters.** Models may interpret semantics, but durable system authority must remain replayable, auditable, and independent of races or model preference.

**Deep dive:** [`docs/architecture/SYSTEM_DETERMINISM.md`](docs/architecture/SYSTEM_DETERMINISM.md)

### Article 10 — Race conditions never decide durable authority

**Rule.** Prometheist must not let independently racing workers determine which durable task, resource, capability, or side effect wins. Selection is committed by deterministic system policy before workers act.

**Why it matters.** Operating-system scheduling may be nondeterministic; Prometheist's durable executive decisions must not be.

**Deep dive:** [`docs/architecture/SYSTEM_DETERMINISM.md`](docs/architecture/SYSTEM_DETERMINISM.md)

### Article 11 — Attention priority and resource admission are separate

**Rule.** Attention determines which durable work deserves execution and its deterministic order. Resource admission determines which compatible subset can safely run concurrently under current authoritative capacity, reservations, and headroom. Prometheist should exploit safe parallelism rather than serialize work unnecessarily.

**Why it matters.** Priority is a semantic/executive property; physical concurrency is a hardware-safety property. Collapsing them wastes resources or creates unsafe oversubscription.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 12 — Resource safety is fail-closed and preserves headroom

**Rule.** Work may start only after the authoritative resource policy says its reservation fits safely. Prometheist reserves headroom for the operating system and required/user-authorized processes. Local LLM inference defaults conservatively to one concurrent slot until evidence justifies another value. Transient pressure may delay and trigger bounded re-observation; it must not silently weaken the committed safety thresholds.

**Why it matters.** A scheduler that can crash or severely degrade the host is not a valid attention mechanism.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 13 — Preemption requires both priority and real contention

**Rule.** Higher-priority work does not preempt lower-priority work merely because it is higher priority. Preemption is considered only when relevant occupied capacity prevents safe admission and the victim's declared interruption policy permits yielding. The minimum deterministically selected work necessary to resolve the contention should be disturbed.

**Why it matters.** Prometheist should focus resources when necessary without throwing away useful safe concurrency or violating execution safety.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 14 — Disposable-worker execution is durable, guarded, and recovery-safe

**Rule.** A committed assignment is entitlement, not process-start permission. Worker launch must pass guarded claim-time admission; work must have durable identity, leases/ownership where needed, append-only checkpoints, explicit terminal results, and side-effect/idempotency semantics that fail closed when an irreversible effect cannot be proven safe to retry.

**Why it matters.** Process destruction is expected behavior, so recovery and duplicate-effect prevention must be properties of the protocol rather than worker memory.

**Deep dive:** [`docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md`](docs/architecture/ATTENTION_AND_EXECUTION_GOVERNANCE.md)

### Article 15 — Models select semantic requirements; Prometheist owns execution policy

**Rule.** Models may select among bounded application-owned semantic alternatives or capabilities. They do not author capability IDs, dependencies, execution order, resource policy, permissions, durable identifiers, or scheduling authority. Capability results should be structured evidence/state whenever possible.

**Why it matters.** Semantic interpretation is useful; model-authored control planes are difficult to validate, replay, secure, and audit.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 16 — Model-generated natural language is control/state of last resort

**Rule.** Machine control and durable state prefer enums, booleans, bounded integers, application-owned IDs, and mechanically verified extractive selections before free-form generated language. Natural language is appropriate when language is genuinely the product or when no smaller mechanically verifiable representation can express the required semantics.

**Why it matters.** Closed representations reduce ambiguity, hallucinated control data, brittle parsers, and nondeterministic protocol behavior.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 17 — Relevance, activation, evidence sufficiency, and truth are distinct

**Rule.** Attention and retrieval do not promote content to truth. Prometheist must preserve distinctions among canonical evidence, user statements/beliefs, system interpretation, derived hypotheses, corrections/supersession, counterevidence, confidence, and unknown. Unsupported facts may remain unknown.

**Why it matters.** High-recall memory activation is useful only if it does not silently lower epistemic standards.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)

### Article 18 — Material influence must leave durable causal provenance

**Rule.** Anything that materially influences Prometheist's attention, reasoning, decisions, commitments, actions, or meaningful interaction continuity must leave enough durable provenance to explain that behavior later. High-volume external raw input may remain ephemeral before admission, but the causal record of what actually influenced the system must survive.

**Why it matters.** A persistent system must be able to explain why it acted as it did even if raw sensor/input buffers are later gone.

**Deep dives:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md), [`docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`](docs/architecture/LOSSLESS_PROGRESSIVE_MEMORY.md)

### Article 19 — Internal memory and external knowledge remain distinct evidence domains

**Rule.** Retrieval from Prometheist's own persistent memory is distinct from external knowledge retrieval such as web/API/tool calls. Their provenance, authority, freshness, and failure semantics must remain explicit; one source must not silently masquerade as the other.

**Why it matters.** Remembering what the system/user previously experienced is epistemically different from learning something from the outside world now.

**Deep dive:** [`docs/architecture/COGNITIVE_ARCHITECTURE.md`](docs/architecture/COGNITIVE_ARCHITECTURE.md)

### Article 20 — Natural-language continuity must not become vocabulary patchwork

**Rule.** Application policy must not accumulate phrase-specific English rules, regex vocabularies, or hand-written semantic parsers to decide whether persistent context exists, which prior conversation matters, or whether the model should remember. Lexical/entity/temporal/associative mechanisms remain legitimate inside the memory subsystem as evidence-retrieval machinery.

**Why it matters.** Surface-form patches overfit fixtures, regress each other, and shift semantic authority into brittle application code.

**Deep dive:** [`docs/architecture/INTERACTION_CONTINUITY.md`](docs/architecture/INTERACTION_CONTINUITY.md)

### Article 21 — Local-first, user-controlled, model-agnostic, and replaceable by design

**Rule.** Prometheist's architecture must not require a hosted AI service, vendor API, remote server, Docker/Kubernetes stack, heavyweight resident model, or one specific model/runtime/database in order for its core durable state, replay, audit, and control-plane mechanisms to exist. Current PostgreSQL and Ollama integrations are reference implementations, not constitutional owners of identity or continuity. Components should be modular and replaceable; the core must remain inspectable and operable without an LLM (`LLM = null`), with model-dependent cognition degrading as a capability rather than corrupting persistent state.

Prometheist is intended to remain usable on modest local hardware. Stronger hardware may increase throughput and capability, but architecture must not make heavyweight infrastructure a prerequisite merely for convenience.

**Why it matters.** Local ownership, portability, model replacement, and modest-hardware operation are part of the project's purpose, not afterthoughts.

**Deep dive:** [`docs/architecture/LOCAL_FIRST_PORTABILITY.md`](docs/architecture/LOCAL_FIRST_PORTABILITY.md)

### Article 22 — User sovereignty governs stored data and replaceable components

**Rule.** The user is the authority over Prometheist's locally held data and deployment. Architecture should support inspection, export, backup/restore, component replacement/disablement, and explicit user-directed erasure when implemented. Automatic retention/compaction must never be confused with user-directed erasure.

**Why it matters.** A local persistent cognitive system that the user cannot inspect, move, or ultimately control would contradict the ownership goal that motivates local-first design.

**Deep dive:** [`docs/architecture/LOCAL_FIRST_PORTABILITY.md`](docs/architecture/LOCAL_FIRST_PORTABILITY.md)

### Article 23 — Development follows a falsifiable one-mechanism experimental discipline

**Rule.** Freeze a measurable baseline, change one mechanism, rerun the same experiment, and keep the mechanism only if the evidence justifies it. Preserve negative results. Do not add infrastructure, retrieval machinery, optimization solvers, models, or architectural layers because they are fashionable or theoretically attractive; add them when a frozen failure or measured limitation justifies the complexity.

**Why it matters.** Prometheist is trying to discover which mechanisms are necessary. Changing several mechanisms at once destroys causal evidence and makes complexity accumulate without proof.

**Deep dive:** [`docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md)

### Article 24 — Behavioral numbers must be classified and evidenced

**Rule.** Runtime-affecting numeric bounds must be structural invariants, external contracts, explicit collision bounds, empirical tunables, safety tunables, or environment-calibrated values. Behavioral magic numbers may not bypass classification. Environment-sensitive values require evidence from the intended environment; CI simulation alone cannot establish native safety or model behavior.

**Why it matters.** A value is not correct because it happened to make the current tests pass.

**Deep dive:** [`docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](docs/engineering/EMPIRICAL_CONSTRAINT_GOVERNANCE.md)

### Article 25 — Verification requires deterministic regression evidence and native acceptance where reality matters

**Rule.** Deterministic CI and development/deployment-machine acceptance have different jobs and neither substitutes for the other. Core invariants require restart/replay, cross-process, cross-session, provenance, bounded-context, hidden-transcript-absence, failure/recovery, and deterministic-order coverage. Resource- or local-model-sensitive claims must also be exercised on representative real hardware/runtime before they are treated as verified.

**Why it matters.** Synthetic determinism catches regressions; real-machine acceptance proves that assumptions about processes, memory pressure, local models, databases, and recovery survive contact with the actual deployment environment.

**Deep dive:** [`docs/engineering/TESTING_AND_ACCEPTANCE.md`](docs/engineering/TESTING_AND_ACCEPTANCE.md)

### Article 26 — Constitutional changes must be explicit

**Rule.** Code, a milestone implementation, or a passing test cannot silently repeal a constitutional rule. Changing an article requires an explicit Constitution amendment, corresponding updates to affected constitutional deep dives, and acceptance evidence appropriate to the changed invariant. Superseded wording remains visible in history when it explains an earlier accepted result.

**Why it matters.** The Constitution is useful for audits only if architectural drift cannot redefine the rules implicitly.

**Deep dive:** [`docs/engineering/CONSTITUTIONAL_GOVERNANCE.md`](docs/engineering/CONSTITUTIONAL_GOVERNANCE.md)

## Constitutional audit standard

A constitutional audit should evaluate every article against the entire current code path, schema, tests, configuration, and current architecture documentation. For each article, record:

- **PASS** — implementation and tests are consistent with the rule;
- **FAIL** — at least one current behavior contradicts the rule;
- **GAP** — the rule is intended but not yet implemented or adequately tested;
- **NOT APPLICABLE** — the audited scope genuinely does not exercise the rule.

Every failure or gap should cite the concrete code/config/schema path and the missing or contradictory test evidence. A passing audit should not rely only on documentation claims.

The detailed audit procedure is defined in [`docs/engineering/CONSTITUTIONAL_GOVERNANCE.md`](docs/engineering/CONSTITUTIONAL_GOVERNANCE.md).

## Constitutional test

A proposed change is constitutionally admissible only if all of the following are true:

1. it does not contradict an article, or the Constitution is explicitly amended first;
2. it preserves canonical evidence and causal provenance;
3. it does not give hidden continuity or durable authority to an LLM/worker context;
4. deterministic policy still owns deterministic control-plane decisions;
5. boundedness and resource-safety invariants still hold;
6. the change has the required deterministic and/or native evidence;
7. any new behavioral tunable is classified and governed;
8. the change does not make a reference implementation into an unjustified constitutional dependency.

That standard is the default review lens for future Prometheist development.