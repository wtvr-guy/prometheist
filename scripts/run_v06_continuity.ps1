$ErrorActionPreference = "Stop"
$previousRequireOllama = [Environment]::GetEnvironmentVariable(
    "REQUIRE_OLLAMA_ACCEPTANCE",
    "Process"
)
$previousPythonUtf8 = [Environment]::GetEnvironmentVariable("PYTHONUTF8", "Process")
$testExitCode = 1
$locationPushed = $false

try {
    Push-Location (Split-Path -Parent $PSScriptRoot)
    $locationPushed = $true
    $env:REQUIRE_OLLAMA_ACCEPTANCE = "1"
    $env:PYTHONUTF8 = "1"

    uv run --locked pytest -vv -s -m ollama `
        tests/test_acceptance_conversation_continuity.py::test_stateless_multiturn_conversation_retains_local_context_and_relevant_history
    $testExitCode = $LASTEXITCODE
}
finally {
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

exit $testExitCode
