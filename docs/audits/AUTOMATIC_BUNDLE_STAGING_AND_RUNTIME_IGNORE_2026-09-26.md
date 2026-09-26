# Automatic benchmark staging and runtime artifact ignore — 2026-09-26

After a benchmark finishes, the packaging CLI verifies the source result and
its complete raw manifest, writes the portable ZIP, verifies the ZIP, atomically
replaces `.tmp/latest-benchmark.zip`, and stages that one file with `git add`.
The PowerShell wrappers call the packager after a successful run. The operator
still decides when to commit and push; no benchmark runner publishes a remote
commit. Other `.tmp` files are not ignored by policy, although the packager
normally leaves only the latest ZIP there.

The `.prometheist/` runtime journal is now Git-ignored, and its previously tracked
synthetic files are removed from the current index. They remain in earlier Git
history and in the operator's backup. Pulling this change can remove the tracked
files from an existing checkout; restore the backup to `.prometheist/` after
pulling. This does not change runtime persistence, only Git tracking.

The clean-source guard in each benchmark runner continues to allow changes to
`.tmp/latest-benchmark.zip`, whether staged or unstaged. It rejects other source
changes so the benchmark's revision still identifies the executed implementation.
