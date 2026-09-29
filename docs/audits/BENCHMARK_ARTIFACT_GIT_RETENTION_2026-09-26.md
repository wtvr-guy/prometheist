# Benchmark artifact Git retention change — 2026-09-26

The earlier decision recorded in
[`ARTIFACT_VISIBILITY_AND_RETENTION_2026-09-14.md`](ARTIFACT_VISIBILITY_AND_RETENTION_2026-09-14.md)
made every new synthetic artifact visible to Git so reviewers could inspect the
full causal record. It worked, but the branch accumulated thousands of raw files.
This change keeps the complete append-only evidence on the development machine
while moving review transport to a verified, single-run ZIP.

- `benchmarks/generated/` and new `benchmarks/results/*.json` are Git-ignored.
- Previously tracked raw files are removed from the current Git index, not from
  the author's backed-up local archive or earlier Git commits. Existing result
  summaries remain tracked; future runs require the ZIP for complete review.
- The PowerShell baseline, mechanism, and self-memory wrappers package completed
  runs into ignored `.tmp/latest-benchmark.zip`. The ZIP includes the exact result,
  manifest, and raw files and is published locally only after verification.
- Fresh CI checkouts no longer contain historical raw files, so CI tests fixture
  validation, the ZIP packaging contract, and the application suite instead of
  attempting to verify a historical run whose raw files are absent.

**For existing developer checkouts:** keep the external backup of
`benchmarks/generated/`. Pulling the deletion may remove the tracked files from
the working tree. Restore that backup to `benchmarks/generated/` after pulling and
check `git status --short` to confirm the restored files are ignored. Do not use
`git clean -x` against the local archive. The old bytes can also be recovered from
earlier Git commits; no Git history was rewritten by this change.

The remote repository's earlier commits still contain their original blobs. This
change prevents future accumulation and reduces the current branch checkout; it
does not shrink historical Git storage without rewriting history. The ZIP remains
a transport copy, not the sole retained record. Backups of local evidence remain
the operator's responsibility.
