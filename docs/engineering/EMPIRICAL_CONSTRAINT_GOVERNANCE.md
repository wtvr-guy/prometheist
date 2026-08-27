# Empirical Constraint Governance

## Rule

Prometheist must not treat an arbitrary numeric bound as correct merely because it passes the tests that happened to exist when it was introduced.

Any numeric value that changes runtime behavior must be one of the following:

1. **Structural invariant** — follows from the representation or algorithm itself (for example, a sequence number is non-negative, a percentage is bounded by 0 and 100, or a cross-reference operation requires at least two references).
2. **External contract** — imposed by a protocol, dependency, operating system, model API, or other authority outside Prometheist.
3. **Identifier collision bound** — chosen from an explicit collision-risk calculation rather than a performance benchmark.
4. **Empirical tunable** — quality/cost trade-off whose value must be selected by a reproducible benchmark.
5. **Safety tunable** — operational trade-off whose value must be derived from failure-injection/load evidence under an explicit safety objective.
6. **Environment-calibrated value** — depends materially on the host/model/runtime and therefore must be calibrated on the intended deployment environment rather than inferred from CI.

The machine-readable source of record is `benchmarks/constraint_registry.json`. A static audit prevents newly introduced behavioral magic numbers from bypassing classification.

## What “optimal” means

There is rarely one scalar objective that can honestly combine correctness, abstention, latency, memory use, throughput, and safety. Inventing arbitrary utility weights would merely move the arbitrary number one level upward.

Prometheist therefore uses a **constraint + Pareto + lexicographic** decision procedure:

1. Reject candidates that violate a hard correctness, provenance, determinism, safety, or recovery invariant.
2. Compare the remaining candidates on every scenario family independently, not only on a pooled average.
3. Maximize the worst-performing scenario family first.
4. Then maximize aggregate correctness/recall/abstention metrics in a declared order appropriate to the subsystem.
5. Only when quality is indistinguishable under the benchmark evidence, prefer the candidate with lower resource cost, latency, context size, or complexity.
6. If the selected candidate lies on the edge of the explored search space, expand that edge and rerun. A boundary winner is not accepted as evidence of an optimum.
7. Preserve all negative results and the complete sweep output so a later change can be compared against the same evidence.

This avoids both “vibes” and arbitrary weighted scoring.

## Benchmark design requirements

Every empirical benchmark specification must identify:

- the exact constraint family being calibrated;
- the current value(s) and the search procedure;
- the null hypothesis/baseline;
- scenario families and relevant interactions;
- oracle truth that is kept separate from system inputs;
- hard invariants that no candidate may violate;
- primary and secondary metrics;
- a deterministic decision rule;
- exploratory versus holdout cases;
- scale/adversarial cases;
- required environment and hardware, when applicable;
- confounds and known coverage limits;
- the revision, model/runtime versions, and raw result artifact used for the decision.

A benchmark must include all materially distinct scenarios we currently know how to construct. When a new failure mode is discovered, it becomes a permanent scenario family before the parameter is recalibrated.

## Search-space rule

The initial search grid is not treated as authoritative. Search is iterative:

- finite integer constraints begin with values that span below and above the current setting and expand geometrically until quality has saturated or a hard feasibility boundary is reached;
- continuous thresholds/decays begin with a coarse sweep over their mathematical domain, then refine the non-dominated region;
- interacting parameters are swept jointly when changing one can reverse the ranking of another;
- any optimum at a tested boundary forces expansion/refinement before acceptance.

Thus the benchmark does not silently encode the answer through a narrow hand-picked range.

## Generalization controls

For deterministic benchmarks, scenario generators use fixed published seeds and separate exploratory and holdout partitions. The optimizer may inspect exploratory results; the final decision must also survive the holdout set.

For stochastic local-model or host measurements, sample size is determined from observed variance and the effect size needed to distinguish competing candidates rather than from a fixed arbitrary repetition count. Raw samples are retained. Repeated runs across cold/warm model state and representative host pressure are required.

## Constraint families

### Memory scoring and evidence admission

Must cover exact facts, paraphrases, sparse cues, distractors, confusables, polarity, causal-source questions, temporal/deictic references, cross-conversation recall, previous-state/supersession, contradictory facts, unknown-fact abstention, long histories, and high-overlap irrelevant evidence.

### Associative traversal and retrieval breadth

Must vary graph fan-out, graph depth, cycles, guarded relationships, disconnected distractors, multiple plausible anchors, candidate starvation, and scale. Quality is evaluated together with candidate/association work performed and latency.

### Working-state/context bounds

Must cover short and long conversations, interleaved topics, multiple simultaneously active facts, corrections, resumed tasks, accumulated capability results, and distraction pressure. Truncation must never silently remove required evidence in a passing scenario.

### Capability selection/round bounds

Must include tasks needing zero, one, several independent, several dependent, repeated, and progressively narrowing capabilities. The benchmark measures completion correctness, unnecessary executions, number of stateless model calls, convergence, and failure to issue an explicit `RESPOND`.

### Scheduler service guarantees

Must exercise bursty and steady arrivals across every service class, dependencies, preemptible/checkpoint-only/atomic tasks, overload, long-running work, and recovery. Measure per-class queue-delay distributions, starvation, interactive latency, background progress, throughput, and preemption cost.

### Resource admission and process estimates

Must be calibrated on deployment-class hosts. Measure real CPU/RAM peaks and system responsiveness for cold/warm local-model inference, PostgreSQL, worker startup, concurrent non-LLM work, and background OS pressure. Headroom must be derived from observed demand/error distributions plus an explicit safety objective. CI may verify formulas but cannot substitute for native calibration.

### Worker leases/retries/timeouts

Must include normal, slow, hung, killed, restarted, DB-delayed, and temporarily resource-starved workers. Optimize false abandonment and needless delay subject to no duplicate irreversible effects and bounded recovery.

### Local-model retry/token/timeout bounds

Must use the actual supported local model(s), prompt/schema sizes, cold/warm state, malformed first outputs, and host contention. Measure schema success, truncation, retry recovery, latency distribution, and wasted inference.

## Release rule

A release is not considered empirically calibrated merely because all functional tests pass. Before release, every runtime constraint discovered by the audit must be classified, every empirical/safety/environment tunable must have a benchmark specification, and every release-required calibration must have a result artifact tied to the release revision.

When current evidence cannot establish an optimum, the registry must say so explicitly. The accepted value is then a documented provisional bound, not falsely presented as optimal.
