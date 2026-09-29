"""Read-only local discovery providers. No outbound network or model calls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
from types import MappingProxyType
from uuid import uuid4

import psutil

from prometheist.environment_contracts import (
    DISCOVERY_TIMEOUT_SECONDS, MAX_DISCOVERY_BYTES, MAX_PROVIDER_RESOURCES,
    DiscoveredResource, EnvironmentScan, ProviderReport, ResourceKind,
    ScanStatus, SensorReading, resource_id,
)

CIM_TIMEOUT_SECONDS = 5
SENSOR_SAMPLE_SECONDS = 0.1
DIAGNOSTIC_CHAR_LIMIT = 512
ACPI_KELVIN_OFFSET = 273.15
ACPI_TEMPERATURE_SCALE = 10


@dataclass(frozen=True)
class ProviderContract:
    platform: str
    kind: ResourceKind
    identity_field: str
    label_field: str
    scope: str


PROVIDER_REGISTRY = MappingProxyType({
    "runtime": ProviderContract("any", ResourceKind.HOST, "", "", "OS, runtime, CPU/RAM and local sensor readings"),
    "runtime.network": ProviderContract("any", ResourceKind.NETWORK, "", "", "local network interfaces; no active probe"),
    "runtime.storage": ProviderContract("any", ResourceKind.VOLUME, "", "", "mounted local volumes and free space"),
    "runtime.sensors": ProviderContract("any", ResourceKind.SENSOR, "", "", "battery, fan and temperature APIs exposed by the OS"),
    "linux.devices": ProviderContract("Linux", ResourceKind.DEVICE, "", "", "USB, Bluetooth, PCI, DRM and IIO sysfs descriptors"),
    "linux.security": ProviderContract("Linux", ResourceKind.SECURITY, "", "", "process restrictions, AppArmor and SELinux; no privilege changes"),
    "macos.security": ProviderContract("Darwin", ResourceKind.SECURITY, "", "", "Gatekeeper, SIP, FileVault and application firewall status"),
    "windows.system": ProviderContract("Windows", ResourceKind.HOST, "Name", "Model", "local computer system"),
    "windows.cpu": ProviderContract("Windows", ResourceKind.CPU, "DeviceID", "Name", "processor cores, threads and firmware capabilities"),
    "windows.memory": ProviderContract("Windows", ResourceKind.MEMORY, "DeviceLocator", "DeviceLocator", "physical memory modules; channel mode not inferred"),
    "windows.gpu": ProviderContract("Windows", ResourceKind.GPU, "DeviceID", "Name", "graphics adapters; reported RAM is not an allocatable VRAM budget"),
    "windows.disks": ProviderContract("Windows", ResourceKind.STORAGE, "DeviceID", "Model", "disk descriptors and attached device identity"),
    "windows.storage": ProviderContract("Windows", ResourceKind.STORAGE, "DeviceId", "FriendlyName", "physical storage bus and health"),
    "windows.ports": ProviderContract("Windows", ResourceKind.CONNECTOR, "Tag", "ExternalReferenceDesignator", "firmware-reported physical connectors"),
    "windows.displays": ProviderContract("Windows", ResourceKind.DISPLAY, "InstanceName", "InstanceName", "active display connection technology including HDMI"),
    "windows.pnp": ProviderContract("Windows", ResourceKind.DEVICE, "InstanceId", "FriendlyName", "all present PnP devices and parent interfaces"),
    "windows.network": ProviderContract("Windows", ResourceKind.NETWORK, "InterfaceGuid", "Name", "physical and virtual network adapters"),
    "windows.connectivity": ProviderContract("Windows", ResourceKind.NETWORK, "InterfaceIndex", "InterfaceAlias", "cached OS-reported IPv4/IPv6 reachability"),
    "windows.battery": ProviderContract("Windows", ResourceKind.BATTERY, "DeviceID", "Name", "battery descriptors and readings"),
    "windows.thermal": ProviderContract("Windows", ResourceKind.SENSOR, "InstanceName", "InstanceName", "ACPI thermal zones; not necessarily CPU die temperature"),
    "windows.phone_link": ProviderContract("Windows", ResourceKind.INTEGRATION, "Name", "Name", "Phone Link package/process presence; phone connection not inferred"),
    **{f"windows.security.{name}": ProviderContract("Windows", ResourceKind.SECURITY, "Name", "Name", scope)
       for name, scope in {
           "firewall": "effective Firewall profiles and Prometheist-managed rule presence",
           "defender": "Defender health and protection status; no scans or exclusions changed",
           "tpm": "TPM presence and readiness; no key access",
           "secure_boot": "UEFI Secure Boot status",
           "encryption": "volume encryption status; no recovery keys",
           "privileges": "current process elevation; no automatic elevation",
       }.items()},
    **{f"windows.sensor.{name}": ProviderContract("Windows", ResourceKind.SENSOR, "DeviceId", "Name", "default sensor via Windows Runtime")
       for name in ("Accelerometer", "Gyrometer", "Compass", "Inclinometer", "LightSensor", "Barometer")},
})


def _resource(host_id, provider, native, name, *, kind=None, properties=None, available=None, parent=None):
    return DiscoveredResource(resource_id=resource_id(host_id, provider, str(native)), provider=provider,
        kind=kind or PROVIDER_REGISTRY[provider].kind, name=str(name), available=available,
        parent_id=parent or resource_id(host_id, "runtime", "host"), properties=properties or {})


def _reading(resource, metric, value, unit):
    return SensorReading(resource_id=resource.resource_id, metric=metric, value=value, unit=unit)


def _report(provider, resources, readings=(), *, diagnostic=None):
    truncated = len(resources) > MAX_PROVIDER_RESOURCES
    resources = resources[:MAX_PROVIDER_RESOURCES]
    retained = {r.resource_id for r in resources}
    return ProviderReport(provider=provider, status=ScanStatus.PARTIAL if truncated else ScanStatus.COMPLETE,
        resources=tuple(sorted(resources, key=lambda r: str(r.resource_id))),
        readings=tuple(sorted((r for r in readings if r.resource_id in retained), key=lambda r: (str(r.resource_id), r.metric))),
        diagnostic="resource bound exceeded; absence is unknown" if truncated else diagnostic)


def _error(provider, exc):
    return ProviderReport(provider=provider, status=ScanStatus.ERROR,
                          diagnostic=f"{type(exc).__name__}: {exc}"[:DIAGNOSTIC_CHAR_LIMIT])


def runtime_inventory(host_id):
    provider = "runtime"
    memory = psutil.virtual_memory()
    host = _resource(host_id, provider, "host", platform.node() or "local host", properties={
        "os": platform.system(), "release": platform.release(), "version": platform.version(),
        "machine": platform.machine(), "python": platform.python_version(), "boot_time": psutil.boot_time(),
        "logical_cpus": psutil.cpu_count(), "physical_cores": psutil.cpu_count(logical=False),
        "ram_bytes": memory.total,
    }, available=True).model_copy(update={"parent_id": None})
    return _report(provider, [host], [
        _reading(host, "cpu_utilization", psutil.cpu_percent(interval=SENSOR_SAMPLE_SECONDS), "percent"),
        _reading(host, "memory_available", memory.available, "bytes"),
        _reading(host, "memory_used", memory.used, "bytes"),
    ])


def network_inventory(host_id):
    provider = "runtime.network"
    stats, addresses = psutil.net_if_stats(), psutil.net_if_addrs()
    resources = []
    for name in sorted(set(stats) | set(addresses)):
        stat = stats.get(name)
        resources.append(_resource(host_id, provider, name, name, available=stat.isup if stat else None,
            properties={"mtu": stat.mtu if stat else None, "speed_mbps": stat.speed if stat else None,
                        "addresses": [{"family": str(a.family), "address": a.address, "netmask": a.netmask}
                                      for a in addresses.get(name, ())],
                        "internet_reachability": "UNKNOWN", "active_probe": False}))
    return _report(provider, resources)


def storage_inventory(host_id):
    provider = "runtime.storage"
    resources, readings = [], []
    for part in sorted(psutil.disk_partitions(all=False), key=lambda p: p.mountpoint):
        # Never stat remote mounts as a side effect of a supposedly local scan.
        if part.device.startswith(("\\\\", "//")) or ":" in part.device.removeprefix("/dev/")[2:]:
            continue
        if part.fstype.casefold() in {"nfs", "nfs4", "cifs", "smbfs", "sshfs", "fuse.sshfs"}:
            continue
        if platform.system() == "Windows":
            import ctypes
            if ctypes.windll.kernel32.GetDriveTypeW(str(part.mountpoint)) == 4:  # Win32 DRIVE_REMOTE
                continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            resource = _resource(host_id, provider, part.mountpoint, part.device,
                kind=ResourceKind.VOLUME, available=True,
                properties={"mountpoint": part.mountpoint, "filesystem": part.fstype, "total_bytes": usage.total})
            readings.extend([_reading(resource, "free_space", usage.free, "bytes"),
                             _reading(resource, "used_space", usage.used, "bytes")])
        except OSError as exc:
            resource = _resource(host_id, provider, part.mountpoint, part.device, available=None,
                properties={"mountpoint": part.mountpoint, "diagnostic": type(exc).__name__})
        resources.append(resource)
    return _report(provider, resources)


def sensor_inventory(host_id):
    provider = "runtime.sensors"
    resources, readings, unsupported = [], [], []
    battery = psutil.sensors_battery()
    if battery is not None:
        resource = _resource(host_id, provider, "battery", "System battery", kind=ResourceKind.BATTERY, available=True)
        resources.append(resource)
        readings.extend([_reading(resource, "charge", battery.percent, "percent"),
                         _reading(resource, "external_power", battery.power_plugged, "boolean")])
    for api, metric, unit in (("sensors_temperatures", "temperature", "celsius"),
                               ("sensors_fans", "fan_speed", "rpm")):
        function = getattr(psutil, api, None)
        if function is None:
            unsupported.append(api)
            continue
        for group, values in sorted(function().items()):
            for index, reading in enumerate(values):
                key = f"{api}:{group}:{index}:{reading.label}"
                resource = _resource(host_id, provider, key, reading.label or group, available=True,
                    properties={"api": api, "group": group})
                resources.append(resource)
                readings.append(_reading(resource, metric, reading.current, unit))
    return _report(provider, resources, readings, diagnostic=("Unavailable APIs: " + ", ".join(unsupported)) if unsupported else None)


def linux_devices(host_id):
    resources = []
    for bus, base in (("usb", "/sys/bus/usb/devices"), ("bluetooth", "/sys/class/bluetooth"),
                      ("pci", "/sys/bus/pci/devices"), ("display", "/sys/class/drm"),
                      ("sensor", "/sys/bus/iio/devices")):
        path = Path(base)
        if not path.exists():
            continue
        for entry in sorted(path.iterdir()):
            props = {"bus": bus, "inspection": "HOST_EXPOSED_INTERFACES_ONLY"}
            for name in ("manufacturer", "product", "idVendor", "idProduct", "vendor", "device", "name", "status"):
                value = entry / name
                if value.is_file():
                    try:
                        props[name] = value.read_text()[:DIAGNOSTIC_CHAR_LIMIT].strip()
                    except OSError:
                        props[name] = None
            kind = ResourceKind.SENSOR if bus == "sensor" else ResourceKind.DEVICE
            resources.append(_resource(host_id, "linux.devices", str(entry),
                props.get("product") or props.get("name") or entry.name, kind=kind, properties=props))
    return _report("linux.devices", resources)


def decode_windows_report(host_id, payload):
    provider = payload["provider"]
    contract = PROVIDER_REGISTRY[provider]
    status = ScanStatus(payload["status"])
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("Windows provider rows must be a JSON array")
    resources, readings = [], []
    truncated = len(rows) > MAX_PROVIDER_RESOURCES
    for row in rows[:MAX_PROVIDER_RESOURCES]:
        native = row.get(contract.identity_field)
        if native is None or str(native) == "":
            raise ValueError(f"{provider} omitted a stable resource identity")
        props = dict(row)
        parent = row.get("Parent") or row.get("PNPDeviceID")
        parent_id = resource_id(host_id, "windows.pnp", parent) if parent else None
        kind = contract.kind
        if provider == "windows.pnp" and row.get("Class", "").casefold() in {"sensor", "sensors"}:
            kind = ResourceKind.SENSOR
        available = (row.get("Status") == "OK") if row.get("Status") else None
        if provider == "windows.displays":
            props["connection_type"] = {5: "HDMI", 10: "DISPLAYPORT_EXTERNAL", 11: "DISPLAYPORT_EMBEDDED",
                4: "DVI", 6: "LVDS"}.get(row.get("VideoOutputTechnology"), "OTHER_OR_UNKNOWN")
            available = row.get("Active")
        sample_values = props.pop("Values", {})
        battery_level = props.pop("EstimatedChargeRemaining", None)
        thermal = props.pop("CurrentTemperature", None)
        resource = _resource(host_id, provider, native, row.get(contract.label_field) or native,
                             kind=kind, properties=props, available=available, parent=parent_id)
        resources.append(resource)
        if battery_level is not None:
            readings.append(_reading(resource, "charge", battery_level, "percent"))
        if thermal is not None:
            readings.append(_reading(resource, "temperature", thermal / ACPI_TEMPERATURE_SCALE - ACPI_KELVIN_OFFSET, "celsius"))
        for metric, value in sorted(sample_values.items()):
            unit = ("g" if metric.startswith("Acceleration") else "degrees_per_second" if metric.startswith("AngularVelocity")
                    else "lux" if metric == "IlluminanceInLux" else "hectopascal" if metric == "StationPressureInHectopascals" else "degrees")
            readings.append(_reading(resource, metric, value, unit))
    return _report(provider, resources, readings, diagnostic=payload.get("diagnostic")).model_copy(
        update={"status": ScanStatus.PARTIAL if truncated else status})


def windows_inventory(host_id, *, run=subprocess.run):
    windows_dir = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    executable = windows_dir / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive",
               "-File", str(Path(__file__).with_name("windows_environment.ps1")),
               "-MaxRows", str(MAX_PROVIDER_RESOURCES), "-CimTimeoutSeconds", str(CIM_TIMEOUT_SECONDS)]
    failure = None
    try:
        process = run(command, capture_output=True, timeout=DISCOVERY_TIMEOUT_SECONDS, check=False)
        output = process.stdout
        if process.returncode:
            failure = f"Windows collector exited with code {process.returncode}"
    except subprocess.TimeoutExpired as exc:
        output, failure = exc.stdout or b"", "Windows collector timed out; completed sections retained"
    except OSError as exc:
        output, failure = b"", f"Windows collector unavailable: {type(exc).__name__}"
    if len(output) > MAX_DISCOVERY_BYTES:
        output, failure = b"", "Windows collector exceeded output bound"
    found = {}
    for line in output.decode("utf-8-sig", errors="replace").splitlines():
        provider = None
        try:
            payload = json.loads(line)
            provider = payload["provider"]
            if provider not in PROVIDER_REGISTRY or PROVIDER_REGISTRY[provider].platform != "Windows":
                raise ValueError("unexpected collector provider")
            if provider in found:
                raise ValueError("duplicate collector provider")
            found[provider] = decode_windows_report(host_id, payload)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            failure = f"Malformed Windows collector output: {type(exc).__name__}"
            if provider in PROVIDER_REGISTRY and PROVIDER_REGISTRY[provider].platform == "Windows":
                found[provider] = _error(provider, exc)
    return tuple(found.get(key) or ProviderReport(provider=key, status=ScanStatus.ERROR,
                  diagnostic=failure or "collector omitted provider")
                 for key, contract in PROVIDER_REGISTRY.items() if contract.platform == "Windows")


def scan_environment(host_id, *, reason="MANUAL", system=None, clock=None):
    observed_at = (clock or (lambda: datetime.now(timezone.utc)))()
    system = system or platform.system()
    reports = []
    for provider, function in (("runtime", runtime_inventory), ("runtime.network", network_inventory),
                               ("runtime.storage", storage_inventory), ("runtime.sensors", sensor_inventory)):
        try:
            reports.append(function(host_id))
        except Exception as exc:
            reports.append(_error(provider, exc))
    if system == "Windows":
        reports.extend(windows_inventory(host_id))
    elif system == "Linux":
        try:
            reports.append(linux_devices(host_id))
        except Exception as exc:
            reports.append(_error("linux.devices", exc))
        try:
            reports.append(linux_security(host_id))
        except Exception as exc:
            reports.append(_error("linux.security", exc))
    elif system == "Darwin":
        reports.append(macos_security(host_id))
    else:
        reports.append(ProviderReport(provider="platform.devices", status=ScanStatus.UNAVAILABLE,
                                      diagnostic="No native device inventory provider for this platform"))
    return EnvironmentScan(host_id=host_id, scan_id=uuid4(), observed_at=observed_at, reason=reason,
                           platform=system, reports=tuple(sorted(reports, key=lambda r: r.provider)))


def linux_security(host_id):
    props = {"effective_uid": os.geteuid()}
    for path, label in (("/sys/fs/selinux/enforce", "selinux_enforce"),
                        ("/sys/module/apparmor/parameters/enabled", "apparmor_enabled")):
        try:
            props[label] = Path(path).read_text().strip()
        except OSError:
            props[label] = "UNKNOWN_OR_UNAVAILABLE"
    for line in Path("/proc/self/status").read_text().splitlines():
        name, _, value = line.partition(":")
        if name in {"NoNewPrivs", "Seccomp", "CapEff"}:
            props[name] = value.strip()
    props["firewall"] = "NOT_QUERIED_REQUIRES_PLATFORM_ADAPTER"
    return _report("linux.security", [_resource(host_id, "linux.security", "process", "Linux security", properties=props)])


def macos_security(host_id, *, run=subprocess.run):
    resources, failures = [], []
    for name, command in {
        "Gatekeeper": ["/usr/sbin/spctl", "--status"],
        "System Integrity Protection": ["/usr/bin/csrutil", "status"],
        "FileVault": ["/usr/bin/fdesetup", "status"],
        "Application Firewall": ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
    }.items():
        try:
            result = run(command, capture_output=True, timeout=CIM_TIMEOUT_SECONDS, check=False)
            if result.returncode:
                raise RuntimeError(f"status query exited {result.returncode}")
            resources.append(_resource(host_id, "macos.security", name, name,
                properties={"reported_status": result.stdout.decode(errors="replace")[:DIAGNOSTIC_CHAR_LIMIT].strip()}))
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            failures.append(name)
    report = _report("macos.security", resources, diagnostic="Unavailable: " + ", ".join(failures) if failures else None)
    return report.model_copy(update={"status": ScanStatus.PARTIAL}) if failures else report
