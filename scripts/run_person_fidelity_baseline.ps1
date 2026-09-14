param(
    [string]$DatabaseUrl = $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL,
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

    uv run --locked python benchmarks/run_person_fidelity_baseline.py --validate-only
    if ($LASTEXITCODE -ne 0) { throw "person-fidelity fixture validation failed" }
    if ($ValidateOnly) { return }

    if (-not $DatabaseUrl) {
        throw "Provide -DatabaseUrl or PROMETHEIST_PERSON_FIDELITY_DATABASE_URL. The database must be dedicated to this benchmark and its name must contain 'benchmark'."
    }
    $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL = $DatabaseUrl

    Write-Host "The selected benchmark database will be reset before every isolated probe."
    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $output = "benchmarks/results/PERSON-FIDELITY-001_$stamp.json"
    uv run --locked python benchmarks/run_person_fidelity_baseline.py --output $output
    if ($LASTEXITCODE -ne 0) { throw "person-fidelity baseline failed" }

    Write-Host "Person-fidelity evidence written to $output"
    Write-Host "The structural result is not a semantic verdict. Human review remains required."
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
