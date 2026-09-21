param(
    [ValidateSet("composer", "source-policy", "all")]
    [string]$Experiment = "composer",
    [ValidateRange(1, 20)]
    [int]$Trials = 3,
    [ValidateSet("v1", "v2")]
    [string]$CandidateVersion = "v2",
    [string]$VerifyResult,
    [string]$ArtifactRoot,
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
        --validate-only --candidate-version $CandidateVersion
    if ($LASTEXITCODE -ne 0) { throw "mechanism fixture validation failed" }
    if ($ValidateOnly) { return }

    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $label = switch ($Experiment) {
        "composer" { "EXP2-COMPOSER-SUFFICIENCY" }
        "source-policy" { "EXP3-HISTORICAL-SOURCE-POLICY" }
        default { "EXP2-EXP3" }
    }
    $output = "benchmarks/results/PERSON-FIDELITY-${label}_$stamp.json"
    $artifactRootArgument = if ($ArtifactRoot) {
        $ArtifactRoot
    } else {
        "benchmarks/generated/person_fidelity_mechanisms/$stamp"
    }
    uv run --locked python benchmarks/run_person_fidelity_mechanism_experiments.py `
        --experiment $Experiment --candidate-version $CandidateVersion `
        --trials $Trials --output $output --artifact-root $artifactRootArgument
    if ($LASTEXITCODE -ne 0) { throw "mechanism experiment failed" }

    Write-Host "Native experiment result written to $output"
    Write-Host "Complete raw artifact journal written to $artifactRootArgument"
    Write-Host "Review and commit the result before promoting either candidate."
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
