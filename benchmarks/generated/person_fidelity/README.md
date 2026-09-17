# Person-fidelity native artifact journals

This directory is intentionally visible to Git.

Each `PERSON-FIDELITY-001` native run creates one timestamped directory here.
Every probe has an isolated artifact root containing the exact canonical-event
mirrors and hash-linked interaction artifacts produced by the production
percept-to-response pipeline. A completed run also writes `run_manifest.json`
with a SHA-256 inventory and per-probe chain receipts.

Git attributes preserve these files byte-for-byte, including historical Windows
CRLF endings. Do not run line-ending normalization or JSON reformatting over a
captured bundle: the manifest receipts cover its original bytes. New native
manifests and results use explicit UTF-8/LF output on every platform. See the
[fresh-run review](../../../docs/audits/PERSON_FIDELITY_FRESH_REVIEW_2026-09-17.md)
for the hash-proven restoration of the first schema-v2 manifest after transport.

These records are permanent, append-only benchmark evidence. Do not delete or
rewrite a prior run because it failed or because a later implementation performs
better. Raw outputs may eventually support LoRA, preference, or evaluator
training, but a model-generated response is not training-ready merely because it
was preserved. Human-review labels and provenance must remain attached so failed
baseline behavior cannot be mistaken for a positive example.

Only fictional benchmark subjects belong here. Ordinary Prometheist runtime
artifacts remain under `.prometheist/`; that is a separate live personal store,
not benchmark evidence.
