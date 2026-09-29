"""Typed, replayable observations of the digital embodiment; no model authority."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field, JsonValue, field_validator, model_validator

from prometheist.percept_context import FrozenRecord, aware

ENVIRONMENT_VERSION = "host-environment/v1"
MAX_PROVIDER_RESOURCES = 4096
MAX_SENSOR_READINGS = 4096
MAX_DISCOVERY_BYTES = 16_777_216
DISCOVERY_TIMEOUT_SECONDS = 90
MONITOR_INTERVAL_SECONDS = 60
MIN_MONITOR_INTERVAL_SECONDS = 10
MAX_MONITOR_INTERVAL_SECONDS = 3600
MONITOR_STOP_TIMEOUT_SECONDS = DISCOVERY_TIMEOUT_SECONDS + 10


class ScanStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class ResourceKind(str, Enum):
    HOST = "HOST"
    CPU = "CPU"
    MEMORY = "MEMORY"
    GPU = "GPU"
    STORAGE = "STORAGE"
    VOLUME = "VOLUME"
    NETWORK = "NETWORK"
    CONNECTOR = "CONNECTOR"
    DEVICE = "DEVICE"
    SENSOR = "SENSOR"
    DISPLAY = "DISPLAY"
    BATTERY = "BATTERY"
    INTEGRATION = "INTEGRATION"
    SECURITY = "SECURITY"


class ResourcePresence(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


def resource_id(host_id: UUID, provider: str, native_id: str) -> str:
    return str(uuid5(host_id, f"{provider}:{native_id}"))


def content_digest(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


class DiscoveredResource(FrozenRecord):
    resource_id: UUID
    provider: str
    kind: ResourceKind
    name: str
    parent_id: UUID | None = None
    available: bool | None = None
    # Driver metadata is evidence only. It never supplies executable commands.
    properties: dict[str, JsonValue] = Field(default_factory=dict)


class SensorReading(FrozenRecord):
    resource_id: UUID
    metric: str
    value: float | int | bool
    unit: str


class ProviderReport(FrozenRecord):
    provider: str
    status: ScanStatus
    resources: tuple[DiscoveredResource, ...] = Field(default=(), max_length=MAX_PROVIDER_RESOURCES)
    readings: tuple[SensorReading, ...] = Field(default=(), max_length=MAX_SENSOR_READINGS)
    diagnostic: str | None = None

    @model_validator(mode="after")
    def validate_identity(self):
        ids = [item.resource_id for item in self.resources]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate resource ID in provider report")
        if any(item.provider != self.provider for item in self.resources):
            raise ValueError("resource provider differs from report owner")
        if any(item.resource_id not in ids for item in self.readings):
            raise ValueError("sensor reading requires a resource in its report")
        keys = [(r.resource_id, r.metric) for r in self.readings]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate sensor metric in provider report")
        return self


class EnvironmentScan(FrozenRecord):
    schema_version: Literal["host-environment/v1"] = ENVIRONMENT_VERSION
    host_id: UUID
    scan_id: UUID
    observed_at: datetime
    reason: Literal["STARTUP", "POLL", "MANUAL", "DEVICE_EXPORT"]
    platform: str
    reports: tuple[ProviderReport, ...]
    _aware = field_validator("observed_at")(aware)

    @model_validator(mode="after")
    def validate_providers(self):
        providers = [report.provider for report in self.reports]
        ids = [item.resource_id for report in self.reports for item in report.resources]
        if len(providers) != len(set(providers)) or len(ids) != len(set(ids)):
            raise ValueError("duplicate provider or resource identity in scan")
        return self


class MappedResource(FrozenRecord):
    resource: DiscoveredResource
    presence: ResourcePresence


class EnvironmentMap(FrozenRecord):
    schema_version: Literal["environment-map/v1"] = "environment-map/v1"
    host_id: UUID
    resources: tuple[MappedResource, ...] = ()
    providers: dict[str, ScanStatus] = Field(default_factory=dict)


class ResourceChange(FrozenRecord):
    resource_id: UUID
    change: Literal["ADDED", "REMOVED", "CHANGED", "UNCERTAIN", "RECOVERED"]


def reconcile_environment(previous: EnvironmentMap | None, scan: EnvironmentScan):
    """Only a complete provider enumeration can establish a disappearance.

    Given the same prior map and observation this function produces byte-identical
    results. A driver timeout, permission error or partial page is not unplugging.
    """
    if previous is not None and previous.host_id != scan.host_id:
        raise ValueError("cannot reconcile observations from another host")
    prior = {item.resource.resource_id: item for item in previous.resources} if previous else {}
    reports = {report.provider: report for report in scan.reports}
    found = {item.resource_id: item for report in scan.reports for item in report.resources}
    result, changes = [], []
    for key in sorted(set(prior) | set(found), key=str):
        old = prior.get(key)
        if key in found:
            current = MappedResource(resource=found[key], presence=ResourcePresence.PRESENT)
        else:
            report = reports.get(old.resource.provider)
            presence = (ResourcePresence.ABSENT if report and report.status is ScanStatus.COMPLETE
                        else ResourcePresence.UNKNOWN)
            # A subsequent failed enumeration cannot resurrect a known removal.
            if old.presence is ResourcePresence.ABSENT:
                presence = ResourcePresence.ABSENT
            current = old.model_copy(update={"presence": presence})
        result.append(current)
        if current == old:
            continue
        if old is None or (old.presence is ResourcePresence.ABSENT and key in found):
            change = "ADDED"
        elif current.presence is ResourcePresence.ABSENT:
            change = "REMOVED"
        elif current.presence is ResourcePresence.UNKNOWN:
            change = "UNCERTAIN"
        elif old.presence is ResourcePresence.UNKNOWN:
            change = "RECOVERED"
        else:
            change = "CHANGED"
        changes.append(ResourceChange(resource_id=key, change=change))
    providers = {key: value.status for key, value in sorted(reports.items())}
    if previous:
        for key in previous.providers.keys() - providers.keys():
            providers[key] = ScanStatus.UNAVAILABLE
    return EnvironmentMap(host_id=scan.host_id, resources=tuple(result), providers=providers), tuple(changes)
