# Constitutional Governance and Auditing

**Status:** constitutional engineering deep dive.  
**Constitutional authority:** implements Article 26 of [`../../CONSTITUTION.md`](../../CONSTITUTION.md) and defines the repository-wide constitutional audit process.

`CONSTITUTION.md` is intended to prevent architectural drift. This document defines how constitutional rules are interpreted, changed, and audited against real code.

## Normative hierarchy

The repository uses the following authority order when current documents conflict:

1. [`../../CONSTITUTION.md`](../../CONSTITUTION.md)
2. constitutional deep-dive documents explicitly linked by the Constitution;
3. other current architecture documents;
4. the current roadmap and active milestone specifications;
5. dated implementation/experiment records;
6. historical/archived documentation.

Measured historical evidence remains evidence even when the implementation architecture that produced it is superseded. Lower-level documents may explain or specialize a higher-level rule; they may not silently weaken it.

## What belongs in the Constitution

A rule is constitutional when violating it would materially change what Prometheist is or how its persistent cognitive architecture is governed across versions.

Good constitutional subjects include:

- ownership of continuity and authoritative state;
- statelessness/disposability of model and worker compute;
- canonical-memory fidelity;
- bounded cognition;
- determinism and executive authority;
- resource safety;
- provenance/epistemic boundaries;
- local-first ownership and portability;
- scientific/verification discipline.

The Constitution should **not** normally freeze:

- a packet size;
- retry count;
- timeout;
- context-token cap;
- association hop count;
- scheduler wait-cycle value;
- one model name;
- one database version;
- one benchmark fixture;
- one internal class/table/function name.

Those are contracts, tunables, or implementation details governed under the constitutional rules.

## Explicit amendment rule

A code change, passing test, milestone note, or architectural convenience cannot silently amend the Constitution.

A constitutional change requires all of the following:

1. identify the article being amended, added, split, or removed;
2. state the old rule and proposed new rule clearly;
3. explain why the old invariant is no longer correct or sufficient;
4. identify affected constitutional deep dives and implementation surfaces;
5. define a falsifiable experiment/acceptance gate appropriate to the change;
6. preserve the prior wording in Git history and, where useful, a dated decision record;
7. update `CONSTITUTION.md` and every affected deep dive in the same coherent change set;
8. run the required deterministic/native evidence before treating the amended architecture as verified.

If the change merely clarifies wording without changing behavior, say so explicitly and show that the represented invariant is unchanged.

## Deep-dive status

Every article must point to at least one current deep-dive document.

A constitutional deep dive should state near its title:

- that it is a constitutional architecture/engineering authority;
- which articles it implements;
- that it is subordinate to the Constitution;
- where milestone-specific implementation evidence lives when relevant.

Deep dives should describe long-lived rules rather than freeze accidental current class names or numeric parameters unless those details are themselves structural invariants.

## Constitutional audit scope

A full audit is repository-wide. Documentation alone is not enough.

The audit should inspect, as applicable:

- production source code;
- database schema/migrations;
- configuration/defaults;
- model prompts and output schemas;
- worker/process launch paths;
- persistence/recovery code;
- capability registry/runtime;
- memory and retrieval code;
- attention/resource-admission code;
- CLI/API entry points;
- tests and benchmark fixtures;
- CI workflows;
- current architecture/engineering documentation;
- dependency choices when they affect a constitutional claim.

Generated benchmark result artifacts are evidence, not source code, and should be inspected when an article depends on empirical calibration.

## Per-article audit procedure

For every constitutional article:

1. **Restate the invariant.** Translate the article into concrete observable behaviors without weakening it.
2. **Identify implementation surfaces.** Find every code/config/schema path capable of satisfying or violating the rule.
3. **Trace authority.** Determine which component actually owns the relevant state/decision at runtime rather than trusting names/comments.
4. **Inspect persistence and failure behavior.** Ask what survives process death, restart, model replacement, stale state, and rollback.
5. **Inspect tests.** Determine whether the invariant is positively tested and whether important negative/failure paths are covered.
6. **Run applicable evidence.** Use deterministic CI/tests and native acceptance where the rule requires actual environment behavior.
7. **Assign status.** `PASS`, `FAIL`, `GAP`, or `NOT APPLICABLE`.
8. **Record evidence.** Cite exact files/functions/schema objects/tests/result artifacts and the audited revision.
9. **Create remediation.** Every `FAIL` and material `GAP` gets a concrete corrective action or tracked issue.

## Audit statuses

### PASS

The current audited implementation is consistent with the article and has evidence appropriate to the claim.

Documentation agreement alone is insufficient.

### FAIL

Current code/configuration/schema/runtime behavior contradicts the constitutional rule.

A failure should normally block a release that claims constitutional conformance unless the Constitution itself is explicitly amended through the required process.

### GAP

The article is part of the target/foundational architecture, but the current milestone has not implemented or adequately verified it yet.

A `GAP` is not necessarily a defect in an early milestone. It becomes a defect when a release claims the capability or when the gap allows current behavior to violate another implemented constitutional guarantee.

### NOT APPLICABLE

The audited scope genuinely cannot exercise the article. Use sparingly. “Not implemented yet” is usually `GAP`, not `NOT APPLICABLE`.

## Evidence grading

An audit should distinguish confidence levels rather than flattening all passes.

Useful evidence classes are:

- **Static structural evidence** — schemas, types, call graph, forbidden-path absence, constraints.
- **Deterministic runtime evidence** — reproducible tests from controlled inputs.
- **Failure/recovery evidence** — kill/restart/rollback/stale-state testing.
- **Native environment evidence** — actual deployment-class resources/models/processes.
- **Empirical calibration evidence** — frozen benchmark/result artifacts for a tunable.

An article may require more than one class.

For example, resource safety needs deterministic formula/admission tests plus native calibration for environment-sensitive bounds. Statelessness needs interface/code inspection plus cross-process acceptance showing no hidden transcript is required.

## No documentation-only passes

A constitutional audit must not mark an article `PASS` merely because:

- README says the rule is true;
- a class/function has the right name;
- a comment says a value is authoritative;
- the happy-path integration test passed;
- a model happened to answer correctly;
- a database row exists without proving runtime authority uses it.

Trace actual authority.

## No fixture-specific repairs

When an audit or acceptance case finds a constitutional violation, repair the general mechanism.

Do not resolve an interaction-continuity failure by adding a regex for that fixture, a resource failure by lowering headroom until the test starts, or an unsupported answer by teaching the oracle to accept the output.

The failing scenario should become permanent regression evidence before the fix is accepted.

## Audit report format

A repository constitutional audit should include:

```text
Audited revision:
Date/environment:
Constitution version:

Article N — <title>
Status: PASS | FAIL | GAP | NOT APPLICABLE
Implementation surfaces:
Evidence:
Tests/commands/artifacts:
Findings:
Remediation (if needed):
```

A summary table may precede the detailed findings, but it must not replace evidence per article.

## Automated constitutional auditing

Where practical, constitutional rules should gain executable guards.

Candidate static/dynamic checks include:

- enumerate all model invocation sites and verify fresh bounded input construction;
- detect forbidden transcript carry-forward fields;
- identify model-authored unconstrained control strings;
- inspect canonical-memory mutation/deletion paths;
- verify derived-memory foreign-key/provenance relationships;
- verify guarded worker launch is the only Prometheist-owned launch surface;
- verify scheduler authority is committed before worker execution;
- detect behavioral numeric literals not represented in the constraint registry;
- verify resource observations/policy versions are referenced by decisions;
- enforce documentation links from Constitution to deep dives;
- run restart/replay and process-destruction acceptance suites.

Automation should make drift harder, not create a false sense that unmechanized articles no longer matter.

## Pull-request review rule

Any change touching a constitutional implementation surface should answer three questions:

1. Which constitutional article(s) could this affect?
2. Does the change preserve the invariant, create a known `GAP`, or require an amendment?
3. What evidence demonstrates the answer?

A PR does not need to edit the Constitution simply because it touches an article. It does need to avoid silently changing the invariant.

## Relationship to empirical governance

A constitutional rule may require numeric policy without making the number itself constitutional.

For example:

- “resource admission preserves safety headroom” is constitutional;
- the exact RAM reserve is a safety/environment tunable;
- “ordinary LLM context remains bounded” is constitutional;
- the exact context-token maximum is an empirical/external-contract value;
- “service guarantees prevent starvation” is constitutional execution policy;
- exact wait-cycle thresholds are empirical tunables.

Those values are governed by [`EMPIRICAL_CONSTRAINT_GOVERNANCE.md`](EMPIRICAL_CONSTRAINT_GOVERNANCE.md).

## Relationship to the roadmap

Milestones are experiments toward constitutional completeness, not temporary constitutions.

The roadmap may deliberately schedule an article for later implementation. The audit should then record a `GAP` until the mechanism is built and verified.

A milestone must not implement a shortcut that contradicts an article merely because the complete target is scheduled later. Temporary implementation choices are acceptable only when they are compatible with the invariant or explicitly identified as a constitutional violation requiring amendment/remediation.

## Historical preservation

When architecture changes, preserve:

- accepted historical measurements;
- negative results that motivated the change;
- dated decision records when they clarify why a constitutional rule exists;
- superseded implementation docs under an appropriate historical/milestone status.

Do not rewrite history to make the present architecture appear inevitable.

## First audit after adoption

Adoption of the Constitution does not assert that the current v0.7 branch already passes every article. In particular, forward-looking rules such as full backend portability, export/restore maturity, and explicit user erasure may legitimately begin as `GAP`s.

The first full constitutional audit should establish the baseline honestly. Its purpose is to expose drift and unfinished constitutional work, not to manufacture a perfect score.

## Invariant

> **Prometheist's architecture may evolve, but foundational rules change only through explicit, evidence-backed amendments—not through implementation drift.**
