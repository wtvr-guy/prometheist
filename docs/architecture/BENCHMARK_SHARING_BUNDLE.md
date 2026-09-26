# Shareable benchmark run ZIP

Person-fidelity benchmark runners retain their complete raw evidence under
`benchmarks/generated/` and write a result under `benchmarks/results/`. The
PowerShell wrappers now package a successful, verified run into the ignored
`.tmp/latest-benchmark.zip` for upload to a reviewer. Packaging copies bytes into
the ZIP; it does not modify or purge either original location. The next successful
run replaces only that ZIP. If packaging fails, the last good ZIP remains in place.

The ZIP contains the exact result JSON, `run_manifest.json`, all raw artifacts
listed by that manifest, and `bundle_index.json`. The index records the byte size
and SHA-256 of each included file. The packager first runs the appropriate native
benchmark verifier on the original result, including the artifact journal checks.
It then verifies the ZIP against its index, manifest, and result receipt before
atomically replacing the previous ZIP. A reviewer can validate the ZIP without
access to the original machine or its directory paths:

```powershell
uv run python benchmarks/package_benchmark_run.py --verify-bundle .tmp/latest-benchmark.zip
```

For a run launched directly with Python instead of a PowerShell wrapper, package
it after completion with:

```powershell
uv run python benchmarks/package_benchmark_run.py --result benchmarks/results/RESULT_FILENAME.json
```

Only result formats with complete raw-artifact receipts are supported. Older
compact reports without `artifact_evidence` cannot be made into complete verified
bundles merely by guessing which files belonged to them. ZIP verification checks
transport integrity and completeness; the original native verifier also checks
event and interaction chains before packaging.

`.tmp/` and new `benchmarks/generated/` evidence are ignored by Git. New result
JSON files are ignored as well; previously tracked summaries remain available as
historical reports. To share a run, upload `latest-benchmark.zip` itself; the
ignored local file is not accessible to a remote reviewer. Self-memory runs use
the same ZIP format. Their current runner does not yet implement the native
interaction-chain verifier, so their package check covers the result receipt,
manifest, exact raw file set, sizes, and SHA-256 hashes.

The historical raw files were removed from the current Git tree after the local
archive was backed up. They still exist in earlier commits. Pulling that deletion
can remove the old `generated` tree from a working checkout; restore the backed-up
tree to `benchmarks/generated/` after pulling. New runs append there locally, and
the latest ZIP is replaced only after a successfully verified package.
