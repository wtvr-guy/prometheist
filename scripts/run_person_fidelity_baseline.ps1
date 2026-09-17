param(
    [string]$DatabaseUrl = $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL,
    [string]$VerifyResult,
    [switch]$ValidateOnly
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

    uv run --locked python benchmarks/run_person_fidelity_baseline.py --validate-only
    if ($LASTEXITCODE -ne 0) { throw "person-fidelity fixture validation failed" }
    if ($ValidateOnly) { return }

    if ($DatabaseUrl) {
        $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL = $DatabaseUrl
    }
    # Python loads the repository .env and checks the dedicated benchmark setting.
    # An explicit parameter or shell setting takes precedence over that file.

    Write-Host "The selected benchmark database will be reset before every isolated probe."
    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $output = "benchmarks/results/PERSON-FIDELITY-001_$stamp.json"
    uv run --locked python benchmarks/run_person_fidelity_baseline.py --output $output
    if ($LASTEXITCODE -ne 0) { throw "person-fidelity baseline failed" }

    Write-Host "Person-fidelity evidence written to $output"
    Write-Host "Raw event and interaction artifacts are retained under benchmarks/generated/person_fidelity/ and are visible to Git."
    Write-Host "The structural result is not a semantic verdict. Human review remains required."
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
