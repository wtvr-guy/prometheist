# v0.8 closure integration and predictive situation implementation

## Scope and provenance

Mike requested implementation of the recommendations from “Map Precognitive
Pipeline Workers,” integration of the v0.7 closure branch into v0.8, documentation
of each change and its reason, and remote publication. The actual conversation was
not available through retrieval. Initial local merge work began too early; Mike
asked for work to stop until the missing response was supplied. Work paused and
resumed only after reading both supplied copies of the final response, which match.
That supplied response is the implementation specification.

Integration parents are v0.8 `a2636c25ea8b8e4192371063d72f73522f8154da` and closure
`39a3223c38f1b1f8fae7f9e667c6cd7460774ffe`. Both histories are retained. The target
is `copilot/implement-v08-milestone`; this does not merge into `main`, tag a release,
or claim the remaining v0.7 native acceptance requirements are satisfied.

## What changed and why

| Change | Implementation and reason | Validation |
| --- | --- | --- |
| Merge v0.7 closure | Preserve separate evidence-policy, capability selection, memory-only Composer, final response, and deterministic stages; retain artifact recovery, evidence budgets, incremental projections, native diagnostics, acceptance scripts, and audit remediation. Resolve incompatible v0.8 imports/contracts rather than restoring retired recurrent workers. | Existing closure regression suite and new perception integration tests |
| Interaction protocol | Use `v0.8-interaction-v11` for the merged seven-stage user graph. Earlier incompatible protocols fail closed instead of silently resuming with changed responsibilities. Historical artifacts remain readable. | `test_specialist_worker_contract.py` |
| Preserve user authority | Force response necessity in normalization and the application disposition boundary. Preserve exact raw prompt bytes before derived normalization; quarantine salience with historical evidence. | Perception/specialist and policy tests |
| Typed context | Add bounded entity, goal, task, causal, expectation, and property references in `percept_context.py`. These are assertions with provenance, never execution permissions. | Context/type, finite-number, cross-correlation tests |
| Expectations and prediction errors | Add value/range expectations, units, validity, confidence, scale, and explicit comparison outcomes in `expectations.py`. Unexpected observations now have a reproducible meaning. | Range, boolean/type, units, expiry, and late-observation tests |
| Situation formation | Add bounded immutable snapshots in `situations.py`. Related percepts become one operational situation; multiple references permit overlap. Late arrivals do not overwrite newer observations. | Four-observation grouping, replay, head recovery, provenance tests |
| Salience | Replace lexical escalation with typed signals, goal relevance, and normalized prediction error. Retain advisory classification without authority. Record retention hints without deleting source records. | Multilingual, quoted-threat, instruction-shaped, and discrepancy tests |
| Durable cognitive store | Add `cognitive_store.py` and the transactional `cognitive_heads` trigger/index. Canonical events and independent artifacts remain authoritative; indexed heads are rebuildable. | Rebuild equivalence, crash receipt replay, immutable-source checks |
| Input adapters | Add strict source policies, stable delivery IDs, content-addressed media, and bounded event streams. Preserve exact admitted JSON/text or bytes. Add `ACTION_OUTCOME` and richer modalities without interface-specific kind inflation. | Replay conflict, media corruption, modality and event-stream tests |
| Evidence roles | Add `PERCEPT_OBSERVATION` and `DERIVED_REPRESENTATION` event types with explicit external/derived source-scope mappings. Sensor data and derived hypotheses must not become direct user evidence. | Existing source-policy/authority suites plus new scope assertions |
| Non-user triage | Add a closed specialist with exactly four fields. Deterministic policy bypasses inference when operational meaning is already explicit; source policy validates all proposals. | Closed schema, unauthorized task rejection, stage role guards |
| Situation attention and workers | Add cursor-based candidate ranking/coalescing, immutable task snapshots, six fresh guarded stages, and durable completion. Use the existing Attention Fabric; salience cannot override resource admission. | PostgreSQL process-path and low-memory admission tests |
| Work and response separation | Add registered observation, reconciliation, and scheduled consolidation operations. No-work and no-response paths skip unnecessary model calls. Optional natural responses reuse separate Composer and final-responder roles; work bypasses Composer. | LLM=null process test and stage role tests |
| Action feedback | Persist intentions and expectations separately from matching executor receipts. Reingest observed outcomes as percepts. Matching outcomes cannot reopen an unchanged earlier discrepancy. | Receipt forgery rejection, one-action feedback convergence |
| Reflexes | Journal admission denials; mark actual stale claims suspect; rehash before quarantine; terminate only an owned process after its declared timeout. Keep canonical bytes and ordinary execution permissions intact. | Resource gate regressions, media quarantine checks, worker lifecycle tests |
| Consolidation | Schedule bounded historical snapshot pages separately from interactive cognition. Derive supported property/value projections, preserve variation and provenance, and never assert universal facts or rewrite canonical history. | Scheduled execution, support references, immutable-source checks |
| Operator commands | Add `python -m jit_agent.percept_cli` for explicit policy installation, intake, expectations, schedules, bounded ticks, inspection, and offline index rebuilding. | Module import/CLI collection and runtime API integration tests |
| Constraint governance | Register new structural domains, provisional budgets, safety lifetimes, and manually audited salience bins. Preserve the prior lexical baseline in the parent commit. | Numeric constraint audit; no unregistered or mislabeled tuning claim |
| Documentation | Update the active milestone, roadmap, architecture, pipeline, testing guidance, and index. Archive the superseded unfrozen Epistemic WorkingState proposal. Add this per-change record and the operational situation guide. | Link and stale-scope checks |

## Research and philosophical grounding

The Constitution and project philosophy were read before implementation. The
design keeps system-owned state, stateless inference, lossless canonical evidence,
bounded JIT context, deterministic authority/resources, restart-safe effects,
independent artifacts, and one semantic responsibility per model worker. Scope
authorization does not substitute for calibration or native acceptance.

The project’s two lessons documents and the referenced projects informed distinct
mechanisms; none is incorporated as a new runtime dependency:

- [AIOS](https://arxiv.org/abs/2403.16971) separates agent services and scheduling;
  Prometheist retains its own deterministic host/resource admission.
- [M3-Agent](https://arxiv.org/abs/2508.09736) motivates an ongoing multimodal
  perception–memory–action loop; this implementation supplies typed transport and
  feedback, without claiming equivalent perceptual encoders or measured ability.
- [Soar architecture](https://soar.eecs.umich.edu/soar_manual/02_TheSoarArchitecture/)
  distinguishes current working state, proposals, and decisions. Situation
  representation is separated from deterministic task/resource selection here.
- The referenced [LIDA cognitive-cycle paper](https://ccrg.cs.memphis.edu/assets/papers/2011/ijmc-2011.pdf)
  motivates situational representation before attention and action. Its direct
  publisher/university PDF endpoints were unavailable during this session; the
  supplied discussion and project lessons document identify the intended analogy.
- [Letta context repositories](https://www.letta.com/blog/context-repositories/)
  motivate separating active context from background memory work. Prometheist
  keeps canonical evidence immutable and derives new projections instead.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
  provides a useful comparison for durable checkpoints. Prometheist’s conversation
  provenance remains distinct from semantic situation membership.
- [Furutachi et al., 2024](https://www.nature.com/articles/s41586-024-07851-w)
  report selective circuit responses to unexpected sensory input. The software
  analogy is explicit prediction comparison and selective attention, not a model
  of the biological circuit.
- [MICrONS, 2025](https://www.nature.com/articles/s41586-025-08840-3)
  supports structured wiring as a useful architectural consideration. It does not
  validate these software modules or establish cognitive gains.
- The supplied discussion also cites the 2025 review
  [“How prediction error drives memory updating”](https://www.sciencedirect.com/science/article/abs/pii/S0166223625001894).
  Full text was unavailable here. Its stated topic motivates separating matching
  evidence, discrepancies, and subsequent updating; no specific neurobiological
  thresholds or causal mechanism is asserted from inaccessible text.

These are engineering inferences from the sources and discussion. They do not
establish consciousness, neurobiological fidelity, or superiority over the named
systems. Frozen ablations and target-host evidence are still required.

## Verification and practical limits

Local pure-policy tests and static checks run without PostgreSQL or Ollama.
The hosted PostgreSQL suite is the integration gate; its final result is recorded
after publication. Native Windows/Ollama acceptance remains a separate gate and
cannot be inferred from deterministic CI.

Media intake preserves and verifies bytes; modality-specific interpretation models
are not provided. The non-user action catalog is intentionally bounded to the
registered local operations described above. General external tools require their
own authorized capability adapters and observed outcome receipts. Consolidation
provides supported derived projections, not autonomous canonical editing or learned
procedural skills. Retention hints do not implement source deletion. These limits
keep the implemented suggestions consistent with the Constitution.
