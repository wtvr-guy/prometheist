# Android node: Galaxy A16 setup and recovery

Version **0.1.0**, protocol `prometheist-node/v1`. This is an initial native Android
node with a private laptop gateway. It is implemented in Java using Android's
platform APIs, SQLite and Android Keystore; no Ollama, Python runtime, telemetry
SDK or cloud model runs on the phone. Actual Galaxy A16 sensor availability is
discovered at runtime. Different A16 variants may expose different sensors.

**Status:** APK compilation, Android JVM tests/lint and portable Python tests have
been exercised. The app has been built from source, personally signed and installed
on the owner's Galaxy A16 (SM-A166U, Android 16) over authorized USB ADB; it opens
past the device-credential lock and renders every tab with no crash or ANR. Live
Tailscale pairing, Samsung background behavior and real sensor/battery calibration
still require native validation.

At revision `90481c4`, [laptop CI](https://github.com/wtvr-guy/prometheist/actions/runs/36590981197)
passed 710 tests (18 skipped), including synthetic PostgreSQL intake, with Windows
and browser checks also passing. [Android CI](https://github.com/wtvr-guy/prometheist/actions/runs/36590981162)
passed the build, unit tests, lint, installer-source verification, Windows script
parsing and two API 35 emulator tests for Keystore authentication and offline
storage. The bundled release APK contains the corrected atomic file publication
verified by that emulator run. These checks do not substitute for the A16 field
validation below.

## What works where

| Capability | Offline phone | Laptop connected through tunnel |
| --- | --- | --- |
| Notes, deliberate photos and voice memos | Encrypted capture and journal | Canonical observation intake |
| Selected sensor/location/device observations | Visible, pausable foreground collection | Source-attributed observation intake |
| Chat | Save a durable queued message; no generated answer | Existing guarded Prometheist stages using local Ollama |
| Memory | Recent local search and previously fetched laptop text | Refresh latest or fetch older text pages |
| Database | SQLite index with encrypted payloads | Encrypted SQLite inbox plus existing private PostgreSQL |
| Imprinting | Retain observations and their provenance | Existing explicit consolidation/review workflow |
| Model management, Files workspace, administrative controls | Not implemented | Use the laptop interface |

Observations are evidence, not automatic conclusions about your personality,
intentions, health or relationships. Photos/audio are preserved; this slice does
not add transcription, vision interpretation or continual self-model learning.
Offline search checks 200 recent records and displays up to 50; it is not a full
lifetime search. Fetched laptop pages contain 25 records, with long display text
explicitly marked as truncated; original laptop evidence remains authoritative.

## 1. Install the phone app from Windows

Use this repository revision, including `installers/android/`. Review scripts
before running them. While this change is in draft PR #36, get its branch from
your existing checkout (Git will refuse switching over conflicting local edits):

```powershell
git fetch origin
git switch feat/android-private-node
git pull --ff-only origin feat/android-private-node
```

Install Android Studio (or the standalone Android SDK and
JDK 17). In **SDK Manager**, install Android SDK Platform 35, **Build-Tools
35.0.0**, and **Platform-Tools**. `ANDROID_HOME` can override the default
`%LOCALAPPDATA%\Android\Sdk`. The script can find Android Studio's bundled Java;
otherwise set `JAVA_HOME` to a JDK installation.

On the phone, set a secure screen lock. Enable Developer options by tapping
**Settings > About phone > Software information > Build number** seven times,
then enable **USB debugging**. Connect the data cable, unlock the phone, and
approve the laptop's RSA debugging prompt. Only approve your own laptop.

From a PowerShell window in the repository:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\install_phone_node.ps1
```

This verifies the bundled unsigned APK's SHA-256, creates your personal signing
key, signs and verifies the APK, then installs it using `adb install -r`. Choose
and retain the signing-key password when prompted. Multiple connected devices
require `-Serial YOUR_ADB_SERIAL`. An organization-managed execution policy may
require its normal administrator-approved script procedure.

The resulting **signed, installable APK** and key are kept in:

```text
%LOCALAPPDATA%\Prometheist\android-signing\Prometheist-Node.apk
%LOCALAPPDATA%\Prometheist\android-signing\prometheist-node.p12
```

The password is cached using Windows DPAPI for your Windows account, in the same
restricted directory. Back up the `.p12` privately and keep its password in a
password manager. DPAPI's cached password alone is not portable to another
Windows account. **Keep the same signing key for all upgrades.** Do not uninstall
or clear app data to fix an update error: that destroys the Android evidence key.
The APK in Git is intentionally unsigned and cannot be installed directly.

To sign without USB installation, add `-SkipInstall` and transfer the resulting
signed APK to the phone. To rebuild from the checked-out source instead of using
the bundled binary, add `-Build`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\install_phone_node.ps1 -Build
```

Builds use the checked-in Gradle wrapper, AGP 8.9.2, Gradle 8.11.1 and API 35.
The minimum OS is Android 8/API 26. Release APKs are not debuggable. Debug builds
use Android's development key and cannot update a personally signed release.
After installation, USB debugging can be disabled; internet sync uses the tunnel.

## 2. Prepare the existing laptop identity

Keep using your existing private profile, PostgreSQL database and artifacts.
Do not create a second identity or move personal history into this repository.
See [private imprint setup](engineering/IMPRINTING_SETUP.md) and
[local app setup](engineering/LOCAL_APP.md) if the laptop has not been initialized.
The usual profile is:

```powershell
$Profile = "$env:LOCALAPPDATA\Prometheist\subject_001\profile.json"
```

Your normal private database environment variable must be available to the
PowerShell window running the gateway. Configure working **local Ollama** routes
in the laptop GUI before expecting chat replies. Mobile chat refuses cloud
providers and non-loopback Ollama endpoints, even if desktop cloud access is
otherwise enabled. No database credentials are sent to the phone.

## 3. Connect over a private internet tunnel

Install Tailscale on Windows and Android, sign both into your own tailnet, enable
MagicDNS and HTTPS, and connect both devices. Windows installation:

```powershell
winget install --id Tailscale.Tailscale --exact
```

Limit tailnet access to your devices. In a shared tailnet, use its access policy
to allow only your phone to reach the laptop gateway port; do not rely on the
permissive default tailnet policy. Tailscale is a third-party coordination service:
it handles account/device/network metadata. Its HTTPS certificate setup may
publish the device DNS name in certificate-transparency records. Use a neutral
machine name. Application evidence travels through the encrypted tunnel and HTTPS;
it is decrypted only at your endpoints. No public relay/application server is
introduced by this repository.

Start setup from the repository:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\setup_phone_node.ps1 -Profile $Profile
```

The script checks the tunnel, installs locked Python dependencies, configures
**Tailscale Serve**, prints private pairing JSON, and runs the gateway. It refuses
to overwrite an unrelated existing Serve/Funnel configuration. It does not use
Funnel, open router ports, expose PostgreSQL/Ollama, or publish the desktop GUI.

On the phone, open **Prometheist > Connect**, paste that JSON, and tap **Pair
laptop** within ten minutes. The code is single-use; retries from the same device
recover a lost reply. Keep the JSON private and remove clipboard copies after use.
Tap **Sync now**. Automatic sync is separately opt-in; unmetered connections are
required by default, including for manual sync. Disable that preference if you
want queued uploads on cellular. Explicit memory-fetch buttons can use the current
connection independently of the automatic upload preference.

Keep the gateway window running and the laptop awake. Closing it stops intake;
phone evidence stays queued. Tailscale Serve remains configured in the background
but cannot forward to a stopped gateway. Rerun the script to start again; an
already paired phone does not need the newly printed pairing code.

For a laptop without the full backend available:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\setup_phone_node.ps1 -Profile $Profile -InboxOnly
```

Inbox-only mode stores encrypted, acknowledged observations on the laptop without
PostgreSQL or an LLM. They remain **received**, not cognitively processed. Restart
without `-InboxOnly` to process the backlog after the full backend is ready.

### Manual tunnel setup / existing Serve users

Choose an unused HTTPS port supported by Tailscale Serve, for example 8443. Inspect
`tailscale serve status` first; preserve existing services. Substitute your actual
Tailscale hostname throughout:

```powershell
tailscale serve --bg --https=8443 http://127.0.0.1:8766
$NodeUrl = 'https://YOUR-LAPTOP.YOUR-TAILNET.ts.net:8443'
uv run prometheist node pair --profile $Profile --url $NodeUrl
uv run prometheist node serve --profile $Profile --url $NodeUrl --port 8766
```

The HTTPS URL must be the exact origin, without a path. The local gateway binds
only to `127.0.0.1`. A self-hosted WireGuard plus a properly trusted HTTPS reverse
proxy is compatible with the protocol, but no turnkey installer for that alternate
deployment is included. Never disable certificate checks or expose this listener
by opening a public firewall port.

## 4. Choose observation channels

All sensor collection starts disabled. In **Observe**, select the channels you
want, grant their Android permissions, and explicitly start collection. The
persistent notification says **Prometheist is observing** and includes **Pause**.
You can also pause collection and automatic sync together from **Connect**.
Changing collection choices stops the current session; start again deliberately.

| Channel | Retained data and limits |
| --- | --- |
| Motion/orientation | Available accelerometer, gyro, gravity, linear acceleration and rotation vector; 60-second windows of count, min/max/mean/last |
| Environmental | Available light, proximity, magnetic field, pressure, humidity and ambient temperature, with units, sensor vendor/name and reported accuracy |
| Steps | Available step counter/detector; Android activity-recognition permission; counter is since boot, not a verified daily total |
| Device state | Battery level/charging, power-saving mode and screen-interactive state per window |
| Location | Opt-in; approximate by default with coordinate rounding; precise GNSS requires a separate choice and permission; requested at five-minute/200-metre intervals |
| Ambient sound | Opt-in microphone; window RMS level in dBFS, not calibrated dB SPL; raw microphone samples are discarded |
| Photo | Deliberate in-app camera capture only; JPEG capped at 512 KiB, no gallery/cloud copy created by the app |
| Voice memo | Deliberate ten-second mono WAV capture; exact accepted audio retained privately |

Unsupported hardware is absent from the sensor choices. Fingerprints, call audio,
SMS, contacts, notification contents, other apps' screens, Wi-Fi/Bluetooth device
tracking, and health/wearable data are not collected. Cameras never start
remotely or as background observation. Manual photos/voice memos pause ambient
collection and do not restart it silently. Obtain others' consent before
purposefully preserving their private conversations or images.

The requested motion rate is 5 Hz, with batching where supported. These are
**pre-admission measurements**: selected window statistics become immutable
observations; this app does not claim to retain every raw sensor sample. Android
sleep, force-stop, thermal pressure, permission changes and vendor battery controls
can cause gaps. Collection never restarts automatically after reboot/process death.
After reboot, open the app to reschedule automatic sync and explicitly resume
collection. Review Samsung's per-app battery settings only if measured gaps warrant
it; no promise of continuous monitoring is made.

Collection pauses at OS low-memory status, severe thermal status, battery below
15% while unplugged, less than 256 MiB free storage, or a 512 MiB journal. These
are provisional safety tunables, not measured A16 capacity. Data is never silently
pruned to stay under a cap. Export and review retention before a vault fills.

## 5. Privacy, memory and failure behavior

Phone record payloads, the immutable journal and pairing configuration use
AES-256-GCM with an Android Keystore key. SQLite IDs, sequence/order, delivery state
and counts are metadata, not encrypted database pages. Android backup/device
transfer of app data is disabled. Viewing the app requires the device credential;
screenshots are blocked. The key is intentionally usable by authorized background
collection after device unlock; this does not provide protection from a compromised
OS, root or an attacker operating an unlocked authenticated device. Your keyboard
and any chosen backup destination are separate trust decisions.

The laptop mobile inbox has encrypted record payloads and an independent encrypted
journal. Its key is stored beside that private inbox, protected by the account;
existing canonical PostgreSQL/artifact contents keep the laptop's existing storage
security model. **Use laptop disk encryption and encrypted backups.** This is not
whole-database encryption or a remote key-management system.

The gateway exposes only pairing, authenticated sync and read-only memory pages.
Each paired phone is bound to one subject. Authenticated devices can fetch that
subject's memory, so pair only trusted devices. Per-device credentials can be
revoked; no phone command can change desktop settings, enroll another device or
start collection on a different phone. HTTPS redirects and browser-origin requests
are rejected. Pairing secrets and event bodies are omitted from gateway access logs.

Every accepted observation has a UUID, node ID, sequence, observed timestamp and
exact `data_json`. Independent encrypted files are fsynced before acknowledgement;
SQLite is a rebuildable index. Repeated batches deduplicate. Reusing an ID or
sequence for changed evidence produces a conflict rather than overwriting history.
Delivery states distinguish **received**, **started**, **imported/completed**,
**failed**, and **interrupted**. A transport acknowledgement is not a model answer.
Interrupted cognition is not automatically repeated: inspect laptop artifacts
before deliberately submitting another request. A lost response is retrievable
from the durable feed on the next sync.

In `src/prometheist/node_backend.py`, observations enter the existing intake:

```python
percept = ingest_percept(
    conn,
    source=PerceptSource(
        source_id=source_id, kind=policy.kind, modality=modality, interface="android-node"
    ),
    observation=observation,
    observed_at=event.observed_at,
    delivery_id=str(event.event_id),
    correlation_id=event.event_id,
    conversation_id=uuid5(event.node_id, "mobile-observations"),
)
```

Node/source identity and observation time survive ingestion. The source policy is
installed only after authenticated device enrollment. Mobile chat calls the same
`handle_percept_in_worker_processes(...)` pipeline as the laptop, with the mobile
event UUID as correlation ID. It uses the existing resource admission and
cross-process chat lock. Sensor evidence does not bypass consolidation/review or
silently become a personality claim. Pairing is the mobile source authorization;
the private profile's existing `manual_chat` setting is not rewritten.

## 6. Backup, recovery, revocation and stopping

Use **Memory > Export encrypted backup** with a strong passphrase, stored
separately. The app writes a portable authenticated `.pnode` archive to your chosen
Android document provider. Choose a local destination if you do not want even an
encrypted copy in a cloud account. It includes exact evidence and identity
metadata; it excludes the live device credential. Keep a copy off the phone.

Recover on encrypted laptop storage, outside Git:

```powershell
uv run python -m prometheist.node_backup 'D:\PrivateBackups\phone.pnode' 'D:\PrivateRecovery\phone-2026-09-29'
```

The command prompts for the passphrase, authenticates the complete archive before
publishing files, and refuses overwriting an existing recovery directory. Recovered
JSON is **plaintext** and must stay private. This is evidence recovery, not an
in-app restore or automatic merge into the live laptop identity. A fresh phone
installation has a new node/key and requires new pairing; preserve/export the
original history first. Do not assume a Samsung transfer or Android reinstall can
recover an app Keystore key.

Back up the laptop's whole private profile directory (including `phone-node`, its
`vault.key`, and artifacts) plus its PostgreSQL backup. If only the mobile SQLite
index is damaged, stop the gateway and run:

```powershell
uv run prometheist node rebuild --profile $Profile
```

Inspect and revoke a lost phone:

```powershell
uv run prometheist node devices --profile $Profile
uv run prometheist node revoke --profile $Profile --node-id ACTUAL_NODE_UUID
```

Also remove the lost device from Tailscale. Revocation blocks future API access;
it is not a remote wipe of evidence already on the phone. Historical evidence is
retained. To stop, pause collection/sync on the phone, close the gateway window and,
if no longer needed, disable **only this** Serve endpoint:

```powershell
tailscale serve --https=443 off
```

Use 8443 instead if you used the manual alternate port. Do not reset unrelated
Tailscale services. No scheduled task or Windows service is installed by these
scripts; startup after laptop reboot is manual.

## Validation and native acceptance

Portable commands:

```powershell
uv run ruff check .
uv run pytest tests/unit -q
uv run python scripts/audit_constraints.py --fail-unregistered
uv run pytest tests/test_node_intake.py -q  # dedicated test PostgreSQL only
cd android
.\gradlew.bat :app:assembleRelease :app:testDebugUnitTest :app:lintDebug
```

The Android CI workflow also runs Keystore authentication and offline storage
instrumentation on an API 35 emulator. Instrumentation is for disposable test
devices/emulators: it is not an instruction to replace a personal release with a
debug/test build. Portable tests cover pairing retries/expiry/revocation, identity
isolation, immutable replay/conflicts, interrupted workers, encryption and backup
authentication/path safety. PostgreSQL integration tests use synthetic evidence.

`ANDROID-NODE-001` in the constraint experiment registry tracks the remaining
native calibration: record the exact A16 model, OS, RAM/free storage and exposed
sensors; then measure battery drain, resident memory, temperature, admitted sample
counts and Doze gaps over a normal day. Exercise airplane mode/reconnection,
laptop sleep/restart, permission revocation, notification Pause, storage pressure,
backup recovery, device revocation and an app upgrade retaining its key/history.
Run one local-Ollama conversation and verify canonical source/correlation evidence
on the laptop. Keep these results private; publish only deliberate synthetic
results. No native calibration values or personal sensor data ship in Git.

Reference documentation: [Android SDK setup](https://developer.android.com/studio),
[app signing](https://developer.android.com/studio/publish/app-signing),
[foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types),
[Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve),
[Tailscale HTTPS](https://tailscale.com/docs/how-to/set-up-https-certificates).
