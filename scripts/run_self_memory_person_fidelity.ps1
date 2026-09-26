param(
    [string]$DatabaseUrl = $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL,
    [switch]$ValidateOnly,
    [switch]$PreflightOnly,
    [switch]$Holdout,
    [string[]]$ProbeId
)

$ErrorActionPreference = "Stop"
$locationPushed = $false

try {
    Push-Location (Split-Path -Parent $PSScriptRoot)
    $locationPushed = $true
    $env:PYTHONUTF8 = "1"
    if (-not $env:PROMETHEIST_OLLAMA_KEEP_ALIVE) {
        $env:PROMETHEIST_OLLAMA_KEEP_ALIVE = "30m"
    }

    uv sync --frozen
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

    if ($DatabaseUrl) {
        $env:PROMETHEIST_PERSON_FIDELITY_DATABASE_URL = $DatabaseUrl
    }

    $argsList = @()
    if ($Holdout) {
        $argsList += "--holdout"
    }
    if ($ValidateOnly) {
        $argsList += "--validate-only"
    }
    if ($PreflightOnly) {
        $argsList += "--preflight-only"
    }
    foreach ($id in $ProbeId) {
        $argsList += "--probe-id"
        $argsList += $id
    }

    uv run --locked python benchmarks/run_self_memory_person_fidelity.py @argsList
    if ($LASTEXITCODE -ne 0) { throw "self-memory person-fidelity run failed" }
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
