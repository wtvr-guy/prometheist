# Prometheist naming migration — 2026-09-26

## Scope and rationale

The application now uses `prometheist` as its distribution name, Python package,
console command, worker module prefix, and uv environment prompt. The previous
package directory had already been renamed, but installed commands and some worker
launches still referred to the former namespace and could fail at runtime.

Live scripts, test configuration, CI PostgreSQL service credentials, and the
constraint registry now use the current name. CI and project metadata target Python
3.14, matching `.python-version`. The VS Code workspace points at the uv-created
`.venv` interpreter on Windows; uv sets its activation prompt to `prometheist` from
the project name. The directory remains `.venv` by uv convention.

Historical benchmark results, generated artifacts, and dated audit and milestone
records are deliberately unchanged. Their original names and paths are evidence of
the conditions under which they were produced, and rewriting them could invalidate
their integrity receipts. Git history likewise retains its original contents.

## Local Windows checkout

From the repository root, run `uv sync --python 3.14` and select
`.venv\Scripts\python.exe` as the interpreter in VS Code if it has not updated
automatically. The terminal activation prompt should show `(prometheist)`, and
`uv run prometheist --help` should start the application.

If a previous installation left an obsolete command in an environment, `uv sync`
will reconcile the installed project scripts. The directory name `.venv` does not
set the prompt or package name.

New benchmark runs use `PROMETHEIST_BENCHMARK_DATABASE_URL`. New tests default to
the `prometheist_app` role and `prometheist_test` database; the CI service creates
these automatically. Existing local PostgreSQL databases and roles are not renamed
by updating the repository. If using an existing test database, set
`TEST_DATABASE_URL` to its actual connection URL. Likewise, keep `DATABASE_URL`
pointed at the existing application database until you intentionally migrate it;
renaming a database without migrating data does not preserve its records. Update
any local `.env` file separately because it is not tracked by Git.

## Validation

Verified with Python 3.14: installed console command help, Ruff, constraint
registry audit, benchmark fixture validation, and retained artifact verification.
The full test suite requires a running PostgreSQL service; this checkout had none.
