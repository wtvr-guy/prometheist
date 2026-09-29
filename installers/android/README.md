# Prometheist Node installer

Follow [the setup guide](../../docs/android-node.md).

`Prometheist-Node-0.1.0-unsigned.apk` is a release build, with no signing key or
personal configuration. It must be signed before Android will install it.
`manifest.json` records the binary checksum and source/toolchain provenance.

From the repository root on Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\install_phone_node.ps1
```

The installer verifies the checksum, creates/reuses a private personal signing
key on your laptop, signs/verifies the APK and installs through authorized USB
ADB. Add `-SkipInstall` to produce a signed APK for manual transfer, or `-Build`
to compile the source. Keep the key and its password for future upgrades.

Then run `scripts/setup_phone_node.ps1` for private Tailscale pairing. Native
Samsung acceptance and Windows installation remain owner-side validation steps.

Maintainers: after a clean release build, run `uv run python
scripts/package_phone_node.py` to refresh the bundle, then the same command with
`--verify` to check the checksum and source manifest. CI rejects a stale bundle.
