# Development artifact journal

Prometheist's default local artifact root is `.prometheist/artifacts/`. It is
intentionally visible to Git in this development repository so exact test and
debugging evidence can be reviewed across machines.

Checked-in journals must contain only synthetic or deliberately non-sensitive
test interactions. A deployment containing real personal memory, credentials,
private tool results, or identifying sensor data should set
`PROMETHEIST_ARTIFACT_ROOT` to storage outside a public checkout or use a private
repository.

Artifact histories are permanent evidence. Do not delete or rewrite a prior
interaction because it failed. Failed calls and incorrect outputs can support
debugging and later negative/preference examples, while reviewed successful
outputs may eventually contribute to training datasets.

Corrupt content-addressed media remains in place with a corresponding record
under `artifacts/quarantine/`. The mismatched bytes and their expected and
observed digests are retained as integrity-failure evidence; quarantined media
must never be treated as a valid object or training example.
