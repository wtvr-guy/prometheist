param(
    [string]$Profile = "$env:LOCALAPPDATA\Prometheist\subject_001\profile.json",
    [ValidateRange(1024,65535)][int]$Port = 8766,
    [switch]$InboxOnly
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $RepoRoot
if (-not (Test-Path $Profile)) { throw 'Start prometheist gui once, or supply -Profile for your existing private imprint.' }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' }
$Tail = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
if (-not $Tail) { $Tail = "$env:ProgramFiles\Tailscale\tailscale.exe" }
if (-not (Test-Path $Tail)) { throw 'Install Tailscale on Windows and Android, sign in to your private tailnet, then rerun. Windows: winget install --id Tailscale.Tailscale --exact' }
$Network = (& $Tail status --json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or $Network.BackendState -ne 'Running') { throw 'Open Tailscale and connect this laptop, then rerun.' }
$DnsName = $Network.Self.DNSName.TrimEnd('.')
if (-not $DnsName.EndsWith('.ts.net')) { throw 'Enable MagicDNS and HTTPS in your Tailscale settings.' }
$ExistingServe = (& $Tail serve status --json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect existing Tailscale Serve configuration.' }
$ExpectedTarget = "http://127.0.0.1:$Port"
$HasServe = $ExistingServe -and @($ExistingServe.PSObject.Properties).Count -gt 0
if ($HasServe) {
    # A rerun is safe only if this is already the sole configured endpoint.
    $Web = @($ExistingServe.Web.PSObject.Properties)
    $Handlers = if ($Web.Count -eq 1) { @($Web[0].Value.Handlers.PSObject.Properties) } else { @() }
    $Tcp = @($ExistingServe.TCP.PSObject.Properties)
    $OurEndpoint = $Web.Count -eq 1 -and $Web[0].Name -eq "${DnsName}:443" -and
        $Handlers.Count -eq 1 -and $Handlers[0].Name -eq '/' -and
        $Handlers[0].Value.Proxy -eq $ExpectedTarget -and $Tcp.Count -eq 1 -and
        $Tcp[0].Name -eq '443' -and -not $ExistingServe.AllowFunnel
    if (-not $OurEndpoint) {
        throw 'Existing Tailscale Serve/Funnel configuration detected. It was left unchanged. Use the manual setup in docs/android-node.md with a dedicated endpoint.'
    }
}
& uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed' }
Write-Host 'This shares only the phone gateway within your tailnet. It does not use Funnel.'
& $Tail serve --bg --https=443 $ExpectedTarget
if ($LASTEXITCODE -ne 0) { throw 'Tailscale Serve failed. Follow its HTTPS enablement link and rerun.' }
$Url = "https://$DnsName"
& uv run prometheist node pair --profile $Profile --url $Url
if ($LASTEXITCODE -ne 0) { throw 'Pairing preparation failed' }
Write-Host 'Paste the JSON above into Prometheist > Connect on the phone. Keep this window running.'
$Arguments = @('run','prometheist','node','serve','--profile',$Profile,'--url',$Url,'--port',"$Port")
if ($InboxOnly) { $Arguments += '--inbox-only' }
& uv @Arguments
exit $LASTEXITCODE
