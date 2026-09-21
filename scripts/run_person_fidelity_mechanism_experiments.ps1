param(
    [ValidateSet("composer", "source-policy", "all")]
    [string]$Experiment = "composer",
    [ValidateRange(1, 20)]
    [int]$Trials = 3,
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
        uv run --locked python benchmarks/run_person_fidelity_mechanism_experiments.py `
            --verify-result $VerifyResult
        if ($LASTEXITCODE -ne 0) { throw "mechanism experiment verification failed" }
        return
    }

    uv run --locked python benchmarks/run_person_fidelity_mechanism_experiments.py `
        --validate-only
    if ($LASTEXITCODE -ne 0) { throw "mechanism fixture validation failed" }
    if ($ValidateOnly) { return }

    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $label = switch ($Experiment) {
        "composer" { "EXP2-COMPOSER-SUFFICIENCY" }
        "source-policy" { "EXP3-HISTORICAL-SOURCE-POLICY" }
        default { "EXP2-EXP3" }
    }
    $output = "benchmarks/results/PERSON-FIDELITY-${label}_$stamp.json"
    uv run --locked python benchmarks/run_person_fidelity_mechanism_experiments.py `
        --experiment $Experiment --trials $Trials --output $output
    if ($LASTEXITCODE -ne 0) { throw "mechanism experiment failed" }

    Write-Host "Raw native experiment evidence written to $output"
    Write-Host "Review and commit the result before promoting either candidate."
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
