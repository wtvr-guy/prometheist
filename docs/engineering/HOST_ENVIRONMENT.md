# Local environment and security integration

Prometheist discovers its digital embodiment at runtime. The host inventory is
evidence, not configuration guessed from a laptop model name. Its deterministic
monitor needs neither Ollama nor a cloud service. Protecting the enrolled person
is the primary objective recorded in security enrollment; current defense is OS
posture monitoring and optional runtime egress confinement. This release is not
an endpoint detection product or a complete blue/red/purple security expert.

## Start and inspect

Create the private profile and database using [IMPRINTING_SETUP.md](IMPRINTING_SETUP.md).
Keep artifacts outside Git and cloud-synchronized folders. Known OneDrive roots
are rejected before discovery. This is a guard, not comprehensive sync software
detection; use a private local volume and local PostgreSQL.

```powershell
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json scan
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json show
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json watch
```

Chat and recovery perform a startup scan before cognition and monitor until they
exit. Percept ingestion/tick/consolidation perform one startup scan. Disposable
cognitive workers inherit the parent runtime's monitoring; offline artifact
inspection does not scan hardware. `watch` runs without a model until Ctrl+C.
Its default poll delay is 60 seconds after the preceding scan completes, so
change detection is best effort, not instantaneous. Sleep, shutdown and process
termination stop coverage. Startup scanning on the next launch refreshes state.
There is no silently installed Windows service, scheduled task or boot hook.

## Implemented coverage

| Area | Evidence and limits |
| --- | --- |
| CPU/RAM/runtime | OS, architecture, cores/threads, installed/available memory, utilization. Windows physical memory modules; channel mode is not inferred. |
| Storage | Local mounted volumes/free space, Windows disk size, bus and health. Known remote mounts are skipped. No file-content crawl. |
| GPU | Windows graphics-adapter descriptors and driver versions. Reported adapter RAM is not an allocatable VRAM budget. |
| Connections | Network interfaces, present PnP devices and parent topology, Bluetooth/USB interfaces, firmware ports, active display output technology including HDMI. A firmware port is not proof of a connected cable. |
| Sensors | Battery and available temperature/fan APIs; Windows default accelerometer, gyrometer, compass, inclinometer, light and barometer when exposed. Sensor-class PnP descriptors remain visible when a reading API is unavailable. No camera, microphone, GPS or screen-content capture. |
| Phone Link | Current-user package/process presence and host-exposed phone interfaces. Installation/running state does not prove a phone connection or permission to read phone sensors. |
| Windows security | Effective Firewall profiles and managed rules, Defender protection/signature status, current elevation, TPM readiness, Secure Boot and BitLocker volume protection status where supported. No recovery keys, exclusions or security settings are read/changed beyond the documented operations. |
| Linux/macOS | Portable resource APIs; Linux USB/Bluetooth/PCI/DRM/IIO descriptors and process/AppArmor/SELinux metadata; macOS Gatekeeper/SIP/FileVault/application-Firewall status. Non-Windows security enforcement and posture rules are not implemented. |

Each provider reports COMPLETE, PARTIAL, UNAVAILABLE or ERROR. Unsupported Windows
Home features, restricted WinRT APIs, denied permissions and driver failures are
reported explicitly. A failed provider makes prior presence UNKNOWN; only a
complete enumeration establishes disappearance. Current findings distinguish
PASS, FAIL and UNKNOWN. A Defender FAIL is a posture finding, not proof that no
third-party antivirus is installed. Thermal zones are not necessarily CPU die
temperatures. Native behavior and sensor availability depend on the actual host.

The scheduler still uses fresh CPU/RAM pressure and existing headroom policy at
each admission. Device inventories never manufacture LLM capacity, aggregate a
phone's RAM into the host, install a GPU backend, or change the one-model default.

## Durable evidence and device reports

Provider resource arrays are content-addressed; unchanged arrays share blobs.
Scan receipts, readings, topology transitions and posture assessments enter the
local canonical event journal. A staged transition resumes after interrupted
writes, exact retries are idempotent, and late observations cannot replace newer
maps. Hardware observations cannot become self-model evidence by default.
The current map retains absent devices for provenance; long-running retention
and disk growth need measurement. Monitoring performs no canonical deletion.

Connected-device inspection is limited to interfaces the host OS exposes. It
does not bypass pairing, Android permissions, device encryption or account
boundaries. A cooperating device running this package can write a versioned
local report with `environment export-device <file.json>`. The operator can
attach it using `environment import-device <file.json> --parent-id <observed-UUID>`.
The reporting host is bound to that parent, its report stays separately labeled
device-reported, and its resources do not become local scheduler capacity.
There is no autonomous report transfer. An Android companion and authenticated
gateway are still needed for the Galaxy phone's internal inventory and sensors.
Phone Link supplies no assumed general-purpose sensor API.

## Privacy and outbound consent

Discovery uses local OS APIs and does not initiate an application internet probe,
Bluetooth discovery broadcast, pairing, upload or model call. Windows connectivity
is cached OS-reported status; the OS may perform its own independent probes.
Prometheist does not control telemetry in Windows, Phone Link, drivers, local
forwarding services or other applications.

Application model/database connections accept literal loopback destinations by
default. Other endpoints require a local operator grant for the exact normalized
destination and purpose. Database `host`, `hostaddr` and environment alternatives
are checked; service-file indirection is rejected. HTTP clients ignore proxy
environment variables and follow no redirects. An active HTTPS HEAD internet
check always requires its own exact-URL consent, sends no inventory/body, and
only demonstrates reachability of that endpoint.

```powershell
# Print the disclosure and its SHA-256 first. Supply a URL you have chosen.
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json consent connectivity_check https://YOUR_ENDPOINT/health
# After review, repeat with --accept and the printed hash; then:
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json check-internet https://YOUR_ENDPOINT/health
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json revoke connectivity_check https://YOUR_ENDPOINT/health
```

`model_inference` discloses possible transmission of prompts and personal evidence;
`database_storage` discloses credentials and private records. These are separate
from connectivity consent. Grants are checked at each send and are not learned
from model text or telemetry. Consent revocation governs subsequent sends, not a
request already in flight. Operator files rely on the local account/volume access
controls; they are not a defense against malware already running as the owner.
Install/update/package-manager traffic and deliberate synthetic benchmark tools
are outside the private runtime policy.

## Security enrollment and Windows Firewall

Enrollment offers the entire implemented security capability set for the current
subject and host in one disclosure. It asserts ownership/administration authority,
records the protection objective, and is revocable. Newly implemented capabilities
require renewed enrollment; broad mission language does not silently grant them.
Models cannot change enrollment or directly invoke privileged commands. Native
privileges must still be granted by the OS and owner.

```powershell
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json security-enroll
# Review the full disclosure, then repeat with --accept PRINTED_SHA256.
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json firewall-plan C:\Prometheist\subject_001\firewall-apply.json
# Inspect the exact executable paths, impact and printed plan hash.
# From an elevated terminal using THE SAME Python environment and profile:
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json firewall-execute C:\Prometheist\subject_001\firewall-apply.json --accept PRINTED_PLAN_SHA256
```

The optional policy blocks all non-loopback outbound IPv4/IPv6 for the exact
runtime launcher and process image paths on all Firewall profiles. Local
PostgreSQL and Ollama remain usable. All programs sharing those Python images
are affected, including consented remote calls and LAN services. Use a dedicated
environment and review whether the real process image is a shared base Python.
The rules do not cover child executable images, OS DNS services, or a local
service that forwards traffic. They are an additional boundary, not a sandbox.
Phone Link's executable is outside this policy.

Windows explicit block rules override allow rules; loopback is excluded from the
blocked address ranges themselves. Global defaults and unrelated rules are never
changed. Exact rule ownership is checked before mutation. Readback checks effective
policy and profile enablement; disabled profiles or disallowed local rule merging
produce FAILED_OR_INCOMPLETE. Successful readback means VERIFIED_RULE_STATE, not
verified traffic containment. Partial installation keeps successful blocks and
writes a local receipt so the operator can inspect and undo them.

```powershell
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json security-revoke
uv run prometheist environment --profile C:\Prometheist\subject_001\profile.json firewall-plan C:\Prometheist\subject_001\firewall-remove.json --action REMOVE
# Review and execute the REMOVE plan with its own hash in an elevated terminal.
```

Revocation denies future privileged apply operations. It does not delete existing
Firewall rules or stop explicitly running passive discovery. Stop Prometheist to
stop monitoring. Reviewed removal remains available after revocation. Keep the
same executable paths for removal; after moving/removing an environment, inspect
the exact `Prometheist local privacy v1` group in Windows Firewall manually.

## Acceptance and remaining security work

CI checks pure replay/consent contracts, PostgreSQL crash recovery, PowerShell
syntax, native Windows core inventory and exact managed-rule create/read/remove
on a disposable runner. It prints no real device inventory. Native sensor and
traffic acceptance still must run on the intended machine: offline startup,
USB/HDMI unplug/replug, Bluetooth state changes, Phone Link on/off, denied queries,
restart recovery, CPU/RAM/scan latency, loopback service availability and blocked
non-loopback traffic for every runtime image. Do not call a skipped sensor API a
passing sensor integration. Bound calibration is HOST-ENVIRONMENT-001 and remains
provisional until the target-machine measurements exist.

The next security slices are authenticated OS event intake, tested incident
procedures, signed capability-specific privileged helpers, startup/service
supervision with explicit installation consent, and measured alert delivery.
Red work requires registered owner-authorized target scope and isolated test
procedures. Purple work replays known attacks against those defenses and records
coverage gaps. Neither is implemented as a general attack executor here.
Full protection also needs an always-on deployment if the personal laptop sleeps.

API references: [Microsoft Firewall precedence](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/rules),
[New-NetFirewallRule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule),
[Get-MpComputerStatus](https://learn.microsoft.com/en-us/powershell/module/defender/get-mpcomputerstatus),
[monitor connection metadata](https://learn.microsoft.com/en-us/windows/win32/wmicoreprov/wmimonitorconnectionparams).
