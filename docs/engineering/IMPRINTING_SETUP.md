# Private imprint setup and Subject 001 protocol

The architectural term remains **self-model**. Subject 001 is the first research participant, not the definition of a person. The general core boots with no knowledge of any participant. One private database and artifact root belong to one identity. A second subject requires another database and root.

## Windows setup

After pulling main and syncing dependencies:

```powershell
git switch main
git pull --ff-only origin main
uv sync --frozen
uv run python scripts/audit_registries.py
uv run python -m prometheist.imprinting --root C:\Prometheist\subject_001 --subject subject_001
```

The initializer refuses paths within Git checkouts and existing directories. It creates `profile.json`, the active contract manifest, and empty artifacts/objects/imports/evaluation directories. This is local private state, not a private Git repository. It does not enable encryption; use an encrypted local volume and encrypted backups. It does not contact accounts, collect sensors, or populate a personality profile.

Create a **new, empty** local PostgreSQL database, for example `prometheist_subject_001`, owned by your existing application role. Apply the repository schema to that new database:

```powershell
psql -U prometheist_app -d prometheist_subject_001 -f schema.sql
$env:PROMETHEIST_PRIVATE_DATABASE_URL = 'postgresql://prometheist_app:YOUR_PASSWORD@localhost:5432/prometheist_subject_001'
uv run prometheist chat --profile C:\Prometheist\subject_001\profile.json
```

Use the actual local PostgreSQL role/password if yours differs. The profile references the environment variable; credentials do not go in the profile or Git. `--profile` binds the database to the subject, rejects a populated unbound database, test/benchmark database names, or a conflicting subject binding, and sends artifacts to the private root. Subsequent chat commands must include `--profile`. The private database must have the schema before activation.

Run existing synthetic benchmarks against their dedicated benchmark database, without the private profile. Never point a benchmark reset at the private database. Do not replace `.tmp/latest-benchmark.zip` with private subject data: that file is tracked for deliberately shareable synthetic evidence only.

## First learning sessions

Start with direct conversation, specific remembered decisions, actual work samples you choose to share, and corrections. Keep each source identifiable. Assistant-generated assessments are hypotheses, not biographical facts. Avoid importing this assistant's memory summary as verified life history. Review proposed representations and supporting evidence before treating them as a useful description.

After a small conversation batch, run one bounded consolidation tick:

```powershell
uv run python -m prometheist.percept_cli --profile C:\Prometheist\subject_001\profile.json consolidate
```

This uses the existing guarded proposal and evidence-review workers; it requires
Ollama and resource admission. Inspect results with `prometheist audit --latest
--profile ...`. If work is queued, use `percept_cli --profile ... tick` later to
resume it. The command processes bounded pages; larger imports require cursor-driven
continuation using `consolidate --after-key <next_cursor>` from the retained
consolidation projection. It is not an always-running background service. Chat
itself records events and situations without silently scheduling model work.

The synthetic benchmark runner is not a personal-data importer. The initial
private workflow is conversation → explicit consolidation → inspection → held-out
prediction and feedback. Chat now includes passive host/device discovery and security posture monitoring; see [HOST_ENVIRONMENT.md](HOST_ENVIRONMENT.md). Hardware telemetry is not personality evidence.

## Evaluation

For each trial, store a scenario ID, subject ID, knowledge cutoff, model/runtime and registry manifest, frozen prediction, independent subject answer, and subsequent review in the private evaluation directory. Use the existing self-prediction records when evaluating derived representations. Keep evaluation answers outside cognition until the prediction is frozen; feedback enters later as new evidence. Preserve disagreement and uncertainty rather than rewriting the original prediction.

Judge choices, considerations, tradeoffs, noticed details, relationship interpretation, temporal change, communication, and calibrated unknowns separately. Your self-report and observed behavior are both evidence; neither automatically wins. Prefer held-out real decisions to leading hypothetical questions. Add a contrasting second subject before making cross-person claims.

Every proposed architectural change must identify a general failure class, its evidence, the general mechanism proposed, an unchanged holdout, and how it would behave for someone with opposite preferences. Person-specific knowledge remains data.

## Device and account integration plan

An initial native Java Android node for the Galaxy A16 and a narrow laptop ingestion gateway are implemented. See [Android setup, installers and recovery](../android-node.md). The phone maintains an encrypted immutable journal with a SQLite index and sends authenticated, deduplicated batches with device/source identity, observation time, protocol, delivery ID and sequence. Events enter canonical observation intake before interpretation or self-model consolidation. Synchronization is store-and-forward; real-time delivery is best effort. No PostgreSQL credentials or model runtime are placed on the phone. Native Samsung field validation remains pending.

This slice includes device pairing, notes, deliberate photos/voice memos, selected motion/environmental sensors, location and device-state observations with separate controls. Collectors discover available sensors and request Android permissions on the exact phone; they do not assume a particular A16 variant. Account adapters and iPad capture remain later work. No wearable-dependent measurements are assumed.

The private profile keeps manual chat as its original human-content source; explicit mobile pairing authorizes the separate phone observation sources. Local host/device inventories, supported physical sensor readings, continuous polling, destination consent, security enrollment and reviewed Windows Firewall controls are implemented; see [HOST_ENVIRONMENT.md](HOST_ENVIRONMENT.md). The Android slice adds gateway authentication, a personally signed APK, Keystore-backed storage, encrypted backup export and best-effort background sync. OAuth adapters, automatic media interpretation and phone-side backup restore are not implemented. Phone Link presence does not establish phone sensor access.
