$ErrorActionPreference = "Stop"
$previousRequireV07 = [Environment]::GetEnvironmentVariable(
    "REQUIRE_V07_LOCAL_ACCEPTANCE",
    "Process"
)
$previousRequireOllama = [Environment]::GetEnvironmentVariable(
    "REQUIRE_OLLAMA_ACCEPTANCE",
    "Process"
)
$previousPythonUtf8 = [Environment]::GetEnvironmentVariable("PYTHONUTF8", "Process")
$exitCode = 1
$locationPushed = $false

try {
    Push-Location (Split-Path -Parent $PSScriptRoot)
    $locationPushed = $true
    $env:REQUIRE_V07_LOCAL_ACCEPTANCE = "1"
    $env:REQUIRE_OLLAMA_ACCEPTANCE = "1"
    $env:PYTHONUTF8 = "1"

    uv sync --frozen
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

    uv run --locked pytest -vv `
        tests/test_v07_increment_h.py `
        tests/test_worker_protocol.py::test_forced_process_loss_recovers_same_step_from_postgres `
        tests/test_cli.py `
        tests/test_interaction_runtime.py
    if ($LASTEXITCODE -ne 0) { throw "worker/runtime acceptance failed" }

    uv run --locked pytest -vv -s -m ollama `
        tests/test_acceptance_restart.py `
        tests/test_cross_conversation_memory.py `
        tests/test_acceptance_conversation_continuity.py
    if ($LASTEXITCODE -ne 0) { throw "Ollama continuity acceptance failed" }

    uv run --locked pytest -q -m "not ollama"
    $exitCode = $LASTEXITCODE
}
finally {
    [Environment]::SetEnvironmentVariable(
        "REQUIRE_V07_LOCAL_ACCEPTANCE",
        $previousRequireV07,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "REQUIRE_OLLAMA_ACCEPTANCE",
        $previousRequireOllama,
        "Process"
    )
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", $previousPythonUtf8, "Process")
    if ($locationPushed) {
        Pop-Location
    }
}

exit $exitCode
