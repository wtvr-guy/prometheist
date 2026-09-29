# Only explicit local operator CLI calls this script. JSON is data, never code.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$changed = @()
try {
    $plan = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrator privileges required. Review the plan, then run firewall-execute from an elevated terminal with the same profile and Python environment.'
    }
    if ($plan.group -ne 'Prometheist local privacy v1' -or $plan.action -notin @('APPLY','REMOVE')) {
        throw 'Unsupported managed policy'
    }
    # Inspect every collision before making any changes. Never replace or
    # remove rules that merely share a name with our deterministic rule names.
    $existing = @{}
    foreach ($rule in $plan.rules) {
        $matches = @(Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object { $_.Name -eq $rule.name })
        if ($matches.Count -gt 1) { throw 'Ambiguous managed rule name' }
        if ($matches.Count) {
            $found = $matches[0]
            $app = $found | Get-NetFirewallApplicationFilter
            if ($found.Group -ne $plan.group -or $found.Description -ne $rule.name -or $app.Program -ne $rule.program) {
                throw 'Existing rule conflicts with managed policy; no rule overwritten'
            }
            $existing[$rule.name] = $found
        }
    }
    if ($plan.action -eq 'APPLY') {
        foreach ($rule in $plan.rules) {
            if (-not $existing.ContainsKey($rule.name)) {
                New-NetFirewallRule -PolicyStore PersistentStore -Name $rule.name -DisplayName $rule.name `
                    -Description $rule.name -Group $plan.group -Program $rule.program -Direction Outbound `
                    -Action Block -Enabled True -Profile Any -Protocol Any -RemoteAddress @($plan.remote_addresses) | Out-Null
                $changed += $rule.name
            }
        }
        # An installed rule does not necessarily become effective under GPO.
        $profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore)
        if (-not $profiles.Count) { throw 'No effective firewall profiles reported' }
        foreach ($profile in $profiles) {
            if ([string]$profile.Enabled -ne 'True' -or [string]$profile.AllowLocalFirewallRules -eq 'False') {
                throw 'Firewall profile disabled or local policy merge disallowed; protection not verified'
            }
        }
        foreach ($rule in $plan.rules) {
            $found = @(Get-NetFirewallRule -PolicyStore ActiveStore | Where-Object { $_.Name -eq $rule.name })
            if ($found.Count -ne 1) { throw 'Managed rule missing from effective policy' }
            $app = $found[0] | Get-NetFirewallApplicationFilter
            $address = $found[0] | Get-NetFirewallAddressFilter
            $port = $found[0] | Get-NetFirewallPortFilter
            $expected = @($plan.remote_addresses | ForEach-Object { $_.ToLowerInvariant() })
            $actual = @($address.RemoteAddress | ForEach-Object { $_.ToLowerInvariant() })
            if ($found[0].Group -ne $plan.group -or $app.Program -ne $rule.program -or
                [string]$found[0].Enabled -ne 'True' -or [string]$found[0].Direction -ne 'Outbound' -or
                [string]$found[0].Action -ne 'Block' -or [string]$found[0].Profile -ne 'Any' -or
                [string]$port.Protocol -ne 'Any' -or @(Compare-Object $expected $actual).Count) {
                throw 'Effective rule differs from reviewed policy'
            }
        }
    } else {
        foreach ($rule in $plan.rules) {
            if ($existing.ContainsKey($rule.name)) {
                $existing[$rule.name] | Remove-NetFirewallRule
                $changed += $rule.name
            }
        }
        $remaining = @(Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object { $_.Name -in @($plan.rules.name) })
        if ($remaining.Count) { throw 'Managed rules remain after removal' }
    }
    @{ status='VERIFIED_RULE_STATE'; action=$plan.action; changed=$changed; traffic_tested=$false } | ConvertTo-Json -Compress
} catch {
    # Keep any successful blocks on partial failure. A separately reviewed
    # REMOVE plan can undo exactly our rules; never weaken unrelated policy.
    @{ status='FAILED_OR_INCOMPLETE'; changed=$changed; error=$_.Exception.Message; traffic_tested=$false } | ConvertTo-Json -Compress
    exit 1
}
