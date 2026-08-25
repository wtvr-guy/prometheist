# v0.6 Conversation Continuity Validation — 2026-08-24

## Decision

Accepted for the measured v0.6 scenario.

On 2026-08-24, the frozen four-turn acceptance path passed with every external
turn executed by a fresh CLI process. The final run demonstrated both immediate
same-conversation continuity and recall of an older user-authored fact from a
different conversation. Plausible answers without the required source-event
provenance cannot pass.

This result is evidence for the tested configuration, not a claim of general
coreference resolution or semantic-memory completeness.

## Question

Can a sequence of stateless Primary Agent invocations behave as one continuous
conversation while also using JIT Memory to recover an older relevant fact from
persistent history?

The acceptance contract requires more than correct-looking text:

1. every `run_once` call launches a new Python/CLI process;
2. the active conversation contains four independent user turns;
3. an older rule is seeded through a fifth process in a separate conversation;
4. twelve unrelated persistent events compete with that rule;
5. context-dependent turns must persist a `MEMORY_REQUEST` and `MEMORY_PACKET`;
6. exact source event IDs must prove where each answer came from; and
7. answer assertions preserve relation and negation polarity.

## Frozen scenario

The test generates fresh opaque labels on every run:

- constraint profile: `VX-<random>`;
- plan nickname: `BlueHarbor-<random>`.

The historical conversation records that Project Kestrel must never use Docker,
must deploy PostgreSQL directly on Windows, and has that constraint because
virtualization is disabled. The active conversation then proceeds as follows:

1. choose between Docker Compose and native Windows PostgreSQL and assign the
   random plan nickname;
2. ask which of “those approaches” conflicts and request the older random
   profile;
3. ask for the plan nickname and the approach “you just ruled out”; and
4. ask to name “that approach” and give the underlying technical reason in one
   sentence.

The source proof is deliberately strict:

| Turn | Required source events |
| --- | --- |
| 2 | the Turn 1 `USER_PROMPT` and the historical rule `USER_PROMPT` |
| 3 | the Turn 1 `USER_PROMPT` and the exact Turn 2 `AGENT_RESPONSE` |
| 4 | the exact Turn 3 `AGENT_RESPONSE` and the historical rule `USER_PROMPT` |

Turn 4 requires the original causal user event unconditionally. A prior answer
that merely says Docker was prohibited cannot stand in for the source that says
virtualization was disabled.

## Environment

| Component | Observed configuration |
| --- | --- |
| OS | Windows NT 10.0.26200.0 |
| Shell | PowerShell 7.6.4 |
| Python | 3.12.13 |
| pytest | 9.1.1 |
| PostgreSQL | 16.15 |
| pgvector | 0.8.6 |
| Ollama chat model | `qwen3:4b` |
| Ollama embedding model | `qwen3-embedding:4b-q4_K_M` |
| Test database | dedicated `jit_agent_test` database |

The existing local workspace virtual-environment launcher referred to a removed
interpreter, so this workstation used Codex's bundled Python with the locked
environment's site packages. The repository's supported local entry point remains
`scripts/run_v06_continuity.ps1`, which uses `uv run --locked` and makes Ollama
availability mandatory rather than silently skipping the test.

## Diagnostic sequence

The investigation kept the scenario fixed and changed one causal mechanism at a
time. Durations below are pytest wall times where available.

| Observation | Diagnosis | Correction |
| --- | --- | --- |
| Failure after 365.41 s: child output could not decode on Windows | `subprocess.run(text=True)` inherited the parent cp1252 codec even though the CLI emitted UTF-8 | Set the child boundary explicitly to UTF-8 and kept decoding strict |
| Failure after 89.32 s while printing a valid model glyph | pytest's parent transcript was still rendered through a cp1252 stream | Sanitize display only for the current stream; preserve the real captured answer |
| Failure after 561.11 s: the final reference responded directly with no memory request | Referential messages were trusted to the stochastic classifier; an acceptance-specific Docker example in the system prompt also made a guess look informed | Remove scenario leakage and add a persisted-context continuity policy |
| Focused regression pass, then a 692.06 s live provenance pass whose Turn 2 opened with “none conflict” before contradicting itself | Token-presence assertions accepted contradictory relation polarity | Add positive/negative relation contracts and exact-case opaque-ID assertions |
| Failure after 247.21 s under the stronger oracle | Synthesis gave an earlier agent recommendation precedence over the user's prohibition | Make user-authored constraints authoritative and require reconciliation before the opening conclusion |
| Isolated packet replays first produced verbose/truncated analysis, then omitted an exact identifier | Free-form generation spent its answer budget on analysis and paraphrased opaque labels | Require requested identifiers in the first sentence and later replace free-form output with a validated structured answer envelope |
| Failure after 471.35 s: the final answer repeated the Docker rule but omitted its cause | “Why” guidance did not distinguish a decision from its underlying causal fact | Require the explicit underlying cause rather than merely restating the rule |
| Failure after 404.18 s: “that approach” selected the planning specialist | The deterministic reference vocabulary covered “that one” but not the equivalent noun phrase | Cover singular deictic noun phrases and constrain unresolved recall to the internal-memory service |
| Production-adapter replay returned only visible packet analysis and exhausted 256 tokens | `think: false` did not prevent the model from placing analysis in ordinary content | Use a Pydantic-validated `{answer: string}` response schema, retry malformed output once, reject blank answers, and set temperature to zero |
| Failure after 428.43 s: the original causal event was present but ranked behind recent dialogue, and the answer again stopped at the prohibition | The correct canonical evidence was available, but its `because` clause was not salient enough during synthesis | For why/reason requests, deterministically highlight up to three exact `because`/`due to` clauses from `USER_PROMPT` packet items; the underlying event remains the authority |
| Final exact-packet replay | The structured response named Docker Compose and stated that virtualization was disabled | Proceed to the full frozen run |

One early failure caused by running database tests concurrently against the same
globally truncated test database was excluded from causal evidence. It was a test
orchestration artifact: one process deleted another process's conversation while
the latter was still using it. All authoritative database runs were serialized
after that observation.

Before the final certification run, a read-only adversarial review added
deterministic guards for quantified negation, negated/question/hypothetical
causal mentions, mixed inline and unresolved references, and explicitly named
specialist requests. Those cases do not change the frozen live scenario or its
retrieved events; they harden adjacent behavior and are covered by the final
deterministic suite reported below.

## Changes accepted under test

### Continuity routing

- Explicit unresolved references trigger
  `REFERENTIAL_CONTINUITY_REQUIRES_MEMORY_V1`.
- The override constrains discovery to the registered internal-memory service,
  preventing words such as “plan” and “approach” from selecting a planning agent
  before recall.
- Self-contained inline antecedents are removed before evaluating any remaining
  historical references, so a mixed message can still require memory.
- Explicit non-memory specialist operations remain specialist operations; their
  stateless specialist may request persistent context through the same boundary.
- A classifier's useful memory `capability_input` is preserved.

### Grounded response synthesis

- User-authored constraints take precedence over earlier agent recommendations
  unless a later user event changes them.
- Opaque names, profiles, codes, and IDs must be copied exactly.
- User-facing generation uses a validated structured envelope, strips surrounding
  whitespace before accepting the value, retries invalid output once, and fails
  closed after two invalid responses.
- Why/reason requests receive a deterministic highlight of exact causal clauses
  from user-authored packet items only. Negated, interrogative, and explicitly
  uncertain mentions are conservatively excluded, and agent-generated
  rationales are not promoted into this block.
- Acceptance-scenario facts do not appear in production prompts.

### Acceptance and platform contract

- The child CLI boundary decodes UTF-8 explicitly.
- The actual module entry point is exercised in a subprocess to prove UTF-8
  configuration occurs before argument parsing.
- The answer oracle includes negation, quantified negation, contraction,
  contrast, split phrasal-verb, and enabled/disabled polarity cases.
- The real-model preflight validates both configured Ollama models.
- Mandatory local runs fail rather than skip when Ollama is unavailable.
- The preflight runs before any database fixture can mutate state.

## Final result

Command-equivalent target:

```powershell
$env:REQUIRE_OLLAMA_ACCEPTANCE = "1"
uv run --locked pytest -vv -s -m ollama `
  tests/test_acceptance_conversation_continuity.py::test_stateless_multiturn_conversation_retains_local_context_and_relevant_history
```

Observed result:

```text
PASS: immediate context + older relevant history survived fresh-process turns.
1 passed in 416.19s (0:06:56)
```

The final Turn 4 answer named Docker Compose, said virtualization was disabled,
and remained one sentence. The correlated memory packet contained the exact Turn
3 agent response and the original historical user prompt.

Additional local verification:

```text
pytest -q -m "not ollama"
171 passed, 6 deselected in 16.98s

pytest --collect-only -q -m ollama <three explicit acceptance modules>
6 tests collected in 0.15s

pytest --noconftest -q tests/test_cli.py tests/test_cli_helpers.py
10 passed in 0.85s

offline Ollama + unreachable database preflight-order probe
1 skipped in 2.19s
```

## CI and continuous-learning contract

The hosted workflow now:

- installs a pinned `uv` version and synchronizes with `--locked`;
- explicitly collects all three real-model acceptance modules, so a missing file
  or marker fails collection;
- runs the deterministic suite with `-m "not ollama"` against PostgreSQL/pgvector;
- runs a separate Windows CLI-encoding contract without database fixtures;
- uses read-only repository permissions and cancels superseded branch runs.

Hosted CI deliberately does not claim to execute local Ollama. The real-model
test is a mandatory serialized local gate through the checked-in PowerShell
runner. Repository branch protection must make both hosted jobs required outside
this code change if that policy is desired.

For continuous learning, the dated record preserves failed observations rather
than reporting only the final green run. Each correction was tied to a frozen
failure, verified with the smallest useful replay or contract test, and then
rechecked end to end.

## Limitations and next risks

- The accepted result is one final observation on one chat model, embedding
  model, OS, and local hardware configuration. Temperature zero and structured
  output reduce variability but do not make LLM behavior mathematically
  deterministic.
- The continuity policy covers explicit reference classes, not unrestricted
  linguistic coreference.
- Causal highlighting recognizes bounded asserted `because` and `due to` clauses
  from user-authored packet events; it is not a general causal parser and
  conservatively abstains on negated, interrogative, or uncertain mentions.
- Vector recovery remains candidate-only. `SEMANTIC_CANDIDATE` similarity does
  not admit a fact or set `supported=true`; the source content itself must support
  the answer.
- The disposable test database uses global truncation and must not be shared by
  parallel pytest processes.
- The live-model subprocess helper has a 300-second end-to-end timeout for each
  fresh child process, but timeout failures expose less diagnostic context than
  ordinary nonzero exits. A future hardening change should preserve partial
  stdout/stderr and identify the conversation and turn on timeout.
- Hosted CI verifies collection, deterministic behavior, and Windows encoding;
  it does not provide a hosted Ollama service.
