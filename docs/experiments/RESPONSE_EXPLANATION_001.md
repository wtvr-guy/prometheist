# Requested explanations belong in the final response

Date: 2026-09-27. Status: wording candidate; native semantic acceptance pending.
Separate from the source-navigation change at `c70c231`.

The frozen `d971214` run's pf-q006 asks for a predicted offer choice and its main
tradeoff. The final worker returns `{"answer": "Offer B"}`. Ollama records
`done_reason=stop` and `eval_count=10` with a 256-token allowance. This is an
incomplete answer, not output truncation or a transport failure.

The response schema previously described `answer` as:

```text
Final user-facing answer only, with no analysis or preamble.
```

That language does not mechanically forbid explanations, and the trace cannot
prove it caused this particular omission. It is nevertheless ambiguous when
the requested product includes a reason or tradeoff. The revised description is:

```text
Complete user-facing response, including any requested explanation.
Exclude private deliberation and unrequested preamble.
```

The final responder prompt likewise asks it to satisfy every requested part and
distinguishes a requested explanation from private deliberation. The change adds
no answer rubric, required wording, minimum response length, new model stage,
retry loop, or token allowance. Exact-source response modes retain their existing
separate contracts. A short requested message can remain short.

The source-navigation commit is independently reviewable. This wording change
cannot affect canonical retrieval, Composer decisions, or the structural evidence
score; its intended effect is final response completeness. It is a hypothesis
about model behavior, not a deterministic semantic guarantee.

Validation: 29 existing transport, response-view, packet-merge and evidence-budget
tests pass, alongside the navigation change's 107 checks. Ruff and whitespace
checks pass. These validate unchanged protocol boundaries; they do not establish
that the native model will now supply a complete explanation.

Use the same frozen learning snapshot and targeted rerun documented in
[`SELF_ROOT_NAVIGATION_001.md`](SELF_ROOT_NAVIGATION_001.md). Human review of pf-q006
must inspect whether the answer explains the tradeoff with supported evidence and
appropriate uncertainty. Merely naming the expected offer is insufficient. Any
response-quality improvement in a combined run cannot be attributed solely to
wording because source coverage also changed; a causal wording comparison should
run pf-q006 at `c70c231` and at this commit with the same learning bundle.
