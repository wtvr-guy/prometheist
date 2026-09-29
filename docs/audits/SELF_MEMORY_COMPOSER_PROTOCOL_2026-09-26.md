# Self-Memory Composer output protocol, September 26, 2026

The `SELF-MEMORY-001` bundle at revision `b653623` shows `pf-q006` stopping in
`V2_COMPOSE_MEMORY`: Qwen emitted two unterminated JSON strings while expanding
`memory_deficit` across 96 and 192 output tokens. The activated self representations
included the relevant surveillance boundary and financial threshold. This was a
control-output failure, not evidence that those representations were absent.

The Composer now validates a 160-character maximum for `memory_deficit`, asks for
a short searchable phrase, and allocates 256 then 384 output tokens to leave room
for the closed JSON envelope. Both the generic and direct-user-prompt Composer
paths use the same contract. If both attempts remain invalid, the composition
loop records an explicit insufficient package and stops without admitting memory
or treating malformed text as an Adaptive Recall query. The invocation and
validation artifacts still retain the two failed attempts.

This addresses the output protocol only. It does not change whether the Composer
judges abstract self representations sufficient for novel decisions. A local
Ollama benchmark rerun is needed to measure the actual `pf-q006` outcome.
