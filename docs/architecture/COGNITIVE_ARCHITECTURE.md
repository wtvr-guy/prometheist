# Prometheist Cognitive Architecture

Prometheist is a persistent cognitive system whose identity, memory, attention, and execution state belong to the system rather than to any particular model invocation or worker process.

## 1. System-owned continuity

Identity, memory, working state, tasks, attention, interaction continuity, policy, and causal provenance are all system-owned. They must survive worker death, model replacement, and process restarts.

## 2. Disposable LLM invocations

Every model invocation is stateless and disposable. No hidden transcript, private scratchpad, or durable worker context may be treated as authoritative system memory.

## 3. Deterministic control plane

Where deterministic control is possible, Prometheist should use ordinary software for identity, ordering, scheduling, resource policy, retention, and replay. Model output is advisory for bounded semantic choices, not a general control plane.

## 4. Memory and evidence

Canonical evidence is append-only. Derived structures such as indexes, projections, and summaries must remain replaceable and clearly non-authoritative.

## 5. Attention and execution

Attention determines what should be considered for execution. Resource admission determines what can safely run. The two concerns are distinct.

## 6. Working state

WorkingState is a bounded, system-owned activation structure for the current situation. It points back to canonical evidence; it is not a transcript or a hidden memory store.

## 7. Perception and salience

Continuous external input should not flow directly into an LLM or durable task queue. Sources first produce normalized percepts through cheap deterministic or conventional signal-processing logic where possible.

A percept may carry structured dimensions such as source/modality, magnitude, novelty, rate of change, anomaly class, confidence, threat relevance, opportunity relevance, goal relevance, uncertainty, and system-integrity relevance.

Prometheist should distinguish at least `IGNORE`, `DELIBERATE`, `ORIENT`, and `REFLEX` dispositions. Model interpretation may assist ambiguous cases, but deterministic policy retains authority over deletion, priority, permissions, and actuator use.

## 8. Situation assembly

Individual percepts often become meaningful only when correlated. Prometheist should assemble temporally, semantically, causally, and relationally connected percepts into overlapping situation representations where evidence justifies the mechanism.

Situations are associations, not rigid containers. One event may contribute to several situations; one situation may span sessions, devices, days, and tasks.

## 9. Interaction continuity

A current percept should receive a bounded default memory aperture before routing. A model should not have to guess whether unseen memory matters.

## 10. External knowledge and internal memory remain distinct

Internal memory and external knowledge are different evidence domains. Their provenance, freshness, and authority differ even when the same model language is used to describe them.

## 11. Percepts and responses

Not every percept requires a user-facing response. The required response policy belongs to the percept class and deterministic intake logic, not to the final responder.

## 12. Relevance versus truth

Activation, attention, salience, and retrieval do not make content true. The system should preserve clear distinctions among canonical evidence, derived signals, user statements, and model inferences.
