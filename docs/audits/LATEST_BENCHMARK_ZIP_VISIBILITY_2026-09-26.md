# Latest benchmark ZIP visibility — 2026-09-26

Following the local-retention change, the operator chose Git as the transport
for the latest review bundle. `.tmp/latest-benchmark.zip` is the one allowed
artifact in `.tmp/`; other temporary files remain ignored. The wrappers still
replace that ZIP only after the result and archive verify. The raw historical
archive remains under ignored `benchmarks/generated/` on the development machine.

The three native benchmark runners ignore the latest ZIP when checking that the
source revision is clean. They still reject any source-code change. This permits
another run while the previous ZIP is modified or has not yet been committed.
The operator commits and pushes the latest ZIP after a run; a reviewer fetches
the branch and verifies the bundle independently.

Git retains every committed version of that ZIP in its history even though the
branch tip contains only one. This policy reduces the number of current files
and review steps; it does not cap historical repository bytes. A later move to
expiring external artifacts would be needed to bound remote storage over time.
