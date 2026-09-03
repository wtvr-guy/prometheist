# Experiment Records

Experiment documents preserve questions, failures, measurements, and rejected
mechanisms. They are evidence, not current architecture authority.

## Adaptive Memory Attention / Composer branch (PR #22)

The records under [`history/pr22/`](history/pr22/) explain the sequence that replaced
separate named memory-research capabilities with one bounded Adaptive Recall mechanism
and narrowed the v2 Composer to memory sufficiency.

Accepted conclusions:

- basic bounded memory orientation precedes model work selection;
- the Composer identifies only whether memory is sufficient and, if not, the semantic
  deficit;
- Prometheist owns retrieval mechanics and stopping policy;
- external work/tool results bypass memory composition;
- final response generation is a separate fresh invocation;
- memory expansion can vary breadth, association, relation, and focus without exposing
  those internal profiles as capabilities.

Not accepted wholesale:

- the PR #22 production implementation;
- any branch-specific status claim or test count;
- earlier named capability/profile ontology;
- experimental tunable values as permanent constants.

Raw `MEM-ADAPT-*` JSON result artifacts remain under `benchmarks/results/`. Current
implementation and acceptance are governed by
[`../architecture/PERCEPT_TO_RESPONSE_PIPELINE.md`](../architecture/PERCEPT_TO_RESPONSE_PIPELINE.md),
the constraint registry, and the v0.7 closure gates.
