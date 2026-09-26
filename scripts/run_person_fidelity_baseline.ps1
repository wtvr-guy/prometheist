param(
    [string]$DatabaseUrl = $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL,
    [string]$VerifyResult,
    [switch]$ValidateOnly,
    [switch]$Holdout
)

$ErrorActionPreference = "Stop"
$locationPushed = $false

try {
    Push-Location (Split-Path -Parent $PSScriptRoot)
    $locationPushed = $true
    $env:PYTHONUTF8 = "1"

    uv sync --frozen
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

    if ($VerifyResult) {
        uv run --locked python benchmarks/run_person_fidelity_baseline.py --verify-result $VerifyResult
        if ($LASTEXITCODE -ne 0) { throw "person-fidelity artifact verification failed" }
        return
    }

    $fixtureArgs = @()
    $benchmarkId = "PERSON-FIDELITY-001"
    $evidenceDir = "benchmarks/generated/person_fidelity/"
    if ($Holdout) {
        $fixtureArgs = @("--holdout")
        $benchmarkId = "PERSON-FIDELITY-002-HOLDOUT"
        $evidenceDir = "benchmarks/generated/person_fidelity_holdout/"
    }

    uv run --locked python benchmarks/run_person_fidelity_baseline.py @fixtureArgs --validate-only
    if ($LASTEXITCODE -ne 0) { throw "person-fidelity fixture validation failed" }
    if ($ValidateOnly) { return }

    if ($DatabaseUrl) {
        $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL = $DatabaseUrl
    }
    # Python loads the repository .env and checks the dedicated benchmark setting.
    # An explicit parameter or shell setting takes precedence over that file.

    Write-Host "The selected benchmark database will be reset before every isolated probe."
    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $output = "benchmarks/results/${benchmarkId}_$stamp.json"
    uv run --locked python benchmarks/run_person_fidelity_baseline.py @fixtureArgs --output $output
    if ($LASTEXITCODE -ne 0) { throw "person-fidelity run failed" }

    uv run --locked python benchmarks/package_benchmark_run.py --result $output
    if ($LASTEXITCODE -ne 0) { throw "benchmark sharing ZIP failed; raw run remains intact" }

    Write-Host "Person-fidelity evidence written to $output"
    Write-Host "Raw event and interaction artifacts are retained under $evidenceDir."
    Write-Host "Upload .tmp/latest-benchmark.zip when you want the run inspected."
    Write-Host "The structural result is not a semantic verdict. Human review remains required."
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
