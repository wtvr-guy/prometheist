# Personal signing happens on your Windows laptop. No shared signing key is shipped.
[CmdletBinding()]
param(
    [string]$Serial,
    [switch]$Build,
    [switch]$SkipInstall
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Sdk = $env:ANDROID_HOME
if (-not $Sdk) { $Sdk = "$env:LOCALAPPDATA\Android\Sdk" }
$Adb = Join-Path $Sdk 'platform-tools\adb.exe'
$Signer = Join-Path $Sdk 'build-tools\35.0.0\apksigner.bat'
$Align = Join-Path $Sdk 'build-tools\35.0.0\zipalign.exe'
if (-not (Test-Path $Signer) -or -not (Test-Path $Align)) {
    throw 'Install Android SDK Build-Tools 35.0.0 in Android Studio > SDK Manager. Set ANDROID_HOME if the SDK is elsewhere.'
}
if (-not $env:JAVA_HOME -and (Test-Path "$env:ProgramFiles\Android\Android Studio\jbr\bin\keytool.exe")) {
    $env:JAVA_HOME = "$env:ProgramFiles\Android\Android Studio\jbr"
}
$Keytool = if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME 'bin\keytool.exe' } else { (Get-Command keytool -ErrorAction SilentlyContinue).Source }
if (-not $Keytool -or -not (Test-Path $Keytool)) { throw 'Install JDK 17 or Android Studio, then set JAVA_HOME.' }
if ($Build) {
    Push-Location (Join-Path $RepoRoot 'android')
    try {
        & .\gradlew.bat --no-daemon :app:assembleRelease :app:testDebugUnitTest :app:lintDebug
        if ($LASTEXITCODE -ne 0) { throw 'Android build/validation failed' }
    } finally { Pop-Location }
    $Unsigned = Join-Path $RepoRoot 'android\app\build\outputs\apk\release\app-release-unsigned.apk'
} else {
    $Unsigned = Join-Path $RepoRoot 'installers\android\Prometheist-Node-0.1.0-unsigned.apk'
    $Manifest = Get-Content (Join-Path $RepoRoot 'installers\android\manifest.json') -Raw | ConvertFrom-Json
    if (-not (Test-Path $Unsigned)) { throw 'Bundled APK missing. Fetch the complete repository or use -Build.' }
    if ((Get-FileHash $Unsigned -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Manifest.sha256) {
        throw 'Bundled APK checksum mismatch. Nothing was signed or installed.'
    }
}
$PrivateRoot = Join-Path $env:LOCALAPPDATA 'Prometheist\android-signing'
New-Item -ItemType Directory -Force $PrivateRoot | Out-Null
# Restrict the private key directory to the current Windows user and SYSTEM.
$Acl = New-Object System.Security.AccessControl.DirectorySecurity
$Acl.SetAccessRuleProtection($true, $false)
$UserSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$SystemSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
foreach ($Sid in @($UserSid, $SystemSid)) {
    $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule($Sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $Acl.AddAccessRule($Rule)
}
# Set-Acl re-persists every descriptor section and fails without SeSecurityPrivilege once this
# directory is already protected, which broke re-runs and upgrades. SetAccessControl writes only
# the DACL that was modified above.
(Get-Item $PrivateRoot).SetAccessControl($Acl)
$Keystore = Join-Path $PrivateRoot 'prometheist-node.p12'
$PasswordFile = Join-Path $PrivateRoot 'password.dpapi'
if ((Test-Path $Keystore) -and -not (Test-Path $PasswordFile)) {
    Write-Host 'Existing signing key found. Enter its original password.'
    $Password = Read-Host 'Signing-key password' -AsSecureString
} elseif (Test-Path $PasswordFile) {
    if (-not (Test-Path $Keystore)) { throw 'Signing key missing. Restore the original .p12 backup; a new key cannot update your existing app.' }
    $Password = (Get-Content $PasswordFile -Raw).Trim() | ConvertTo-SecureString
} else {
    Write-Host 'Choose a signing-key password (12+ characters) and keep it in your password manager.'
    $Password = Read-Host 'New signing-key password' -AsSecureString
    if ($Password.Length -lt 12) { throw 'Use at least 12 characters.' }
}
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
try {
    # Pass secrets through the child-process environment, never command-line arguments.
    $env:PROMETHEIST_APK_STORE_PASS = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if (-not (Test-Path $Keystore)) {
        & $Keytool -genkeypair -keystore $Keystore -storetype PKCS12 -alias prometheist-node -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Prometheist Personal Node' -storepass:env PROMETHEIST_APK_STORE_PASS -keypass:env PROMETHEIST_APK_STORE_PASS
        if ($LASTEXITCODE -ne 0) { throw 'Signing key creation failed' }
    }
    & $Keytool -list -keystore $Keystore -storetype PKCS12 -alias prometheist-node -storepass:env PROMETHEIST_APK_STORE_PASS | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'The signing-key password could not unlock the existing key.' }
    $Password | ConvertFrom-SecureString | Set-Content $PasswordFile
    $Aligned = Join-Path $PrivateRoot 'node-aligned.apk'
    $Signed = Join-Path $PrivateRoot 'Prometheist-Node.apk'
    & $Align -f -p 4 $Unsigned $Aligned
    if ($LASTEXITCODE -ne 0) { throw 'APK alignment failed' }
    & $Signer sign --ks $Keystore --ks-key-alias prometheist-node --ks-pass env:PROMETHEIST_APK_STORE_PASS --key-pass env:PROMETHEIST_APK_STORE_PASS --out $Signed $Aligned
    if ($LASTEXITCODE -ne 0) { throw 'APK signing failed' }
    & $Signer verify --verbose $Signed
    if ($LASTEXITCODE -ne 0) { throw 'APK signature verification failed' }
    Remove-Item $Aligned
    Write-Host "Signed APK: $Signed"
    Write-Host "Back up $Keystore privately and retain its password for future updates."
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    Remove-Item Env:PROMETHEIST_APK_STORE_PASS -ErrorAction SilentlyContinue
    $Password.Dispose()
}
if ($SkipInstall) { return }
if (-not (Test-Path $Adb)) { throw 'Signed APK is ready. Install SDK Platform-Tools or rerun with -SkipInstall and transfer it manually.' }
$Devices = @(& $Adb devices | Select-String '^([^\s]+)\s+device$' | ForEach-Object { $_.Matches[0].Groups[1].Value })
if ($Serial) {
    if ($Serial -notin $Devices) { throw 'Selected serial is not an authorized ADB device.' }
} elseif ($Devices.Count -eq 1) { $Serial = $Devices[0] }
else { throw 'Signed APK is ready. Connect one phone, enable USB debugging, and approve its laptop RSA prompt. Phone Link alone does not authorize ADB.' }
& $Adb -s $Serial shell getprop ro.product.model
& $Adb -s $Serial shell getprop ro.build.version.release
& $Adb -s $Serial install -r $Signed
if ($LASTEXITCODE -ne 0) { throw 'Install failed. Do not uninstall an existing node: that destroys its local encryption key. Use the original signing key for upgrades.' }
& $Adb -s $Serial shell am start -n org.prometheist.node/.MainActivity
if ($LASTEXITCODE -ne 0) { throw 'Installed, but launch failed. Open Prometheist Node on the phone.' }
Write-Host 'Installed. Unlock the app, pair your laptop, then select the sensors you want.'
