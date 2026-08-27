# Attention Focus Concentration Clarification — 2026-08-26

## Decision

Prometheist's Attention Fabric must not treat maximum safe concurrency as the goal in itself.

Safe concurrency is the normal baseline when several compatible tasks can make useful progress. However, attention may legitimately narrow around one focal task and concentrate most safely allocatable resources on it when priority, urgency, uncertainty, or measured resource elasticity makes that concentration preferable.

The governing principle is:

> **Attention controls not only which work is active, but how strongly limited computational capacity is concentrated on active work.**

This decision refines, rather than reverses, the 2026-08-24 resource-admission clarification.

## Attention as a cross-cutting control principle

Several Prometheist mechanisms share the same abstract pattern:

```text
many possible targets
        |
        v
relevance / importance evaluation
        |
        v
limited processing capacity
        |
        v
selective activation
        |
        v
suppression of competitors
        |
        v
deeper processing of selected targets
```

This appears at several layers:

- perceptual attention: which observations warrant orientation;
- mnemonic/associative attention: which areas of durable memory become activated;
- working-memory attention: which exact evidence is admitted into bounded model context;
- executive attention: which durable tasks deserve execution now;
- resource attention: how much safely allocatable CPU/RAM/inference/I/O capacity active tasks receive.

These layers remain separate mechanisms in software. The shared attention principle does not justify one monolithic `attention` module.

## Activation is not focus

Prometheist should distinguish activation from resource-consuming focus.

**Activation** means an entity, memory region, situation, task, or percept has become a candidate for attention.

**Focus** means scarce computational capacity is actually being allocated to it.

Several tasks may remain runnable/activated while one receives the majority of safely allocatable resources.

Likewise, many memories may become associated with the present cue while only a small exact evidence set is dereferenced into working context.

## Dynamic attention aperture

A useful conceptual model is a dynamic attention aperture.

A broad aperture permits useful concurrent work:

```text
Task A    Task B    Task C    Task D
  |         |         |         |
  +---------+---------+---------+
      distributed safe capacity
```

A narrow aperture concentrates capacity:

```text
                 FOCAL TASK A
              /      |       \
           CPU      RAM      LLM
          most safely allocatable capacity

Task B/C/D -> checkpointed, slowed, or left queued when policy permits
```

The aperture may widen again after the focal condition ends, allowing previously runnable work to resume from durable state.

## Protected capacity during deep focus

No focal task may consume resources reserved for:

1. **system viability** — operating system, database, scheduler/runtime, required services, and configured safety headroom;
2. **perception** — enough capacity to notice meaningful new input;
3. **reflex/orientation** — enough capacity to react to a newly arrived condition that may deserve even higher priority.

Therefore the target is not literal 100% resource ownership. It is ownership of most or all **safely allocatable** capacity that can usefully accelerate the focal task.

## Priority does not imply useful elasticity

Importance alone is insufficient to decide how much hardware a task should receive.

A high-priority operation may be single-threaded, I/O-bound, latency-bound, or otherwise unable to use additional CPU/RAM productively. Resource concentration should therefore eventually depend on explicit or measured resource profiles rather than arbitrary percentages.

A future task/capability resource profile may distinguish concepts such as:

```text
minimum resources
preferred resources
maximum useful resources
resource elasticity by class
```

For example, a task may require one CPU unit to run, benefit substantially from four, and gain almost nothing beyond six. The Attention Fabric should not starve other work merely to allocate useless excess capacity.

Initial profiles may be conservative estimates. Over time Prometheist should be able to update estimates from persisted empirical measurements while retaining versioned, explainable policy inputs.

## Relationship to current v0.7 implementation

The current v0.7 implementation correctly separates:

- attention ordering;
- resource safety/admission;
- durable reservations;
- atomic assignments;
- contention-driven preemption;
- host CPU/RAM observations;
- safety headroom;
- the default one-local-LLM limit.

Those mechanisms remain valid.

This clarification adds a future allocation question beyond binary admission:

> **Given the tasks that deserve execution and the current safe resource envelope, what allocation best reflects present attention while avoiding pointless oversubscription?**

The immediate implementation priority remains the generic durable worker/claim protocol and claim-time revalidation. Dynamic focus concentration should not be bolted on before workers can safely execute committed assignments and before resource usage can be measured in the real development environment.

## v0.7 closure implication

Before v0.7 is considered architecturally closed, the milestone should at minimum preserve an extension path for resource concentration. The current fixed quantitative requirements must not be interpreted as a permanent claim that every admitted task should receive only a single fixed allocation or that maximizing concurrent task count is always correct.

An implementation experiment may follow the worker protocol once actual resource profiles can be observed. The baseline should remain simple and deterministic until measurements justify greater sophistication.

## Relationship to lossless progressive memory

The same selective-attention principle applies to memory without changing stored memory.

A cue activates associations. A bounded subset receives deeper navigation. A still smaller set of exact source memories is dereferenced into working context. Additional evidence is activated only if the requested recall depth requires it.

This keeps the durable corpus large and lossless while the active cognitive working set remains small.

See `../../architecture/LOSSLESS_PROGRESSIVE_MEMORY.md`.

## Acceptance direction

Future attention/resource benchmarks should measure not merely throughput and safe admission, but whether resource concentration improves completion latency for elastic high-priority work without violating:

- system headroom;
- perception/reflex responsiveness;
- deterministic policy;
- checkpoint/interruption guarantees;
- lower-priority service guarantees;
- resource safety.

The desired behavior is not permanent single-task execution and not indiscriminate parallelism. It is dynamically concentrated attention over safely bounded hardware.
