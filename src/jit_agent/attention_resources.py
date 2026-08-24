"""Deterministic execution-resource primitives for the JIT Attention Fabric."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ExecutionResourceClass(str, Enum):
    """Bounded execution-capacity classes exposed to JIT Attention."""

    CPU_GENERAL = "CPU_GENERAL"
    LLM_INFERENCE = "LLM_INFERENCE"
    DATABASE = "DATABASE"
    FILESYSTEM_IO = "FILESYSTEM_IO"
    NETWORK_IO = "NETWORK_IO"


_RESOURCE_CLASS_ORDER: dict[ExecutionResourceClass, int] = {
    resource_class: index
    for index, resource_class in enumerate(ExecutionResourceClass)
}


class ExecutionResource(BaseModel):
    """Durable definition of one execution-resource pool.

    ``capacity`` is an explicit policy/configuration value. It is deliberately
    independent of host CPU/thread count so resource classes such as local LLM
    inference can remain capacity 1 on otherwise highly parallel hardware.
    """

    resource_id: str = Field(min_length=1)
    resource_class: ExecutionResourceClass
    capacity: int = Field(ge=1)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("resource_id")
    @classmethod
    def normalize_resource_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource_id must not be empty")
        return normalized


def execution_resource_sort_key(
    resource: ExecutionResource,
) -> tuple[int, str]:
    """Return the total deterministic ordering key for resource definitions."""

    return (_RESOURCE_CLASS_ORDER[resource.resource_class], resource.resource_id)
