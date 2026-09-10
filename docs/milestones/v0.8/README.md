# v0.8 — Deterministic perception and salience

**Status:** baseline implementation landed on 2026-09-10.

This milestone adds a bounded perception/salience layer to the live user-percept path while preserving the post-v0.7 constitutional constraints:

- every LLM invocation remains stateless;
- canonical evidence remains lossless and append-only;
- normalized percepts, feature buffers, and salience assessments remain replaceable derived state;
- control-plane authority remains deterministic; and
- insufficient authority/evidence still fails closed.

## Frozen experimental scope

v0.8 remains a **one-mechanism** experiment. It does **not** silently combine perception/salience with a richer epistemic `WorkingState`, hidden recurrent inference, or policy-authoritative model control.

The baseline implemented here is:

1. immutable normalized `Percept` contracts for user interaction, scheduled events, anomaly alerts, and heterogeneous structured observations;
2. deterministic bounded intake buffers and structural feature extraction;
3. immutable `SalienceAssessment` records with closed `REFLEX` / `ORIENT` / `DELIBERATE` / `IGNORE` dispositions;
4. deterministic anomaly/threat/opportunity/goal/novelty/uncertainty/system-integrity signals;
5. advisory-only semantic classification fields with explicit `authoritative = false`;
6. live user-percept integration through the durable interaction/task boundary and artifact journal.

## Current implementation notes

The raw user prompt still enters canonical history exactly as a `USER_PROMPT` event. v0.8 then derives a normalized `Percept` and `SalienceAssessment` from that canonical input and persists those structures with the durable interaction record and the immutable artifact journal.

User prompts are therefore only **one** percept class, not the architectural center of Prometheist. The v0.8 contract space also treats scheduled internal triggers, anomaly detections, and other non-conversational observations as first-class percepts with their own deterministic response policies and salience outcomes, even though the current live worker pipeline is only fully wired for the explicit user-response path.

This keeps the evidence boundary explicit:

- **canonical evidence:** the exact user/system event in the append-only ledger;
- **replaceable derived state:** normalized percept text, bounded intake segments, extracted features, signal scores, dispositions, and advisory semantic labels.

The current user-percept path exposes deterministic salience to later workers as context only. Response requirements, task identity, scheduling, capability ordering, memory access, and persistence remain system-owned deterministic policy.

## Validation added for this baseline

- contract coverage for heterogeneous normalized percepts and bounded buffers;
- deterministic salience classification coverage, including advisory-only labels;
- reflex/orient/deliberate disposition coverage;
- persistence coverage for percept/salience state on the durable interaction path;
- regression coverage for artifact journaling and interactive evidence authority.

## Follow-on work intentionally left out

The following remain future work on top of the v0.8 contracts rather than part of this baseline:

- broader non-user sensor adapters and richer reflex catalogs;
- overlapping multi-percept situation assembly;
- general deterministic salience-driven task synthesis beyond the current user-interaction task boundary;
- v0.9 retention policy and raw-buffer expiration;
- any richer recurrent or epistemic `WorkingState` design.
