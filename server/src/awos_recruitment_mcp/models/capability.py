"""Capability models for the AWOS Recruitment MCP server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CapabilityResult(BaseModel):
    """A single capability discovered in the registry.

    Attributes:
        name: Unique, human-readable identifier for the capability.
        description: Short prose description of what the capability does.
        tags: Categorical labels used for filtering and ranking.
    """

    name: str
    description: str
    tags: list[str]


class RegistryCapability(BaseModel):
    """A capability loaded from the registry (skill or MCP tool).

    Attributes:
        name: The capability name extracted from registry metadata.
        description: Human-readable description of what the capability does.
        type: The kind of capability — either ``"skill"`` or ``"tool"``.
    """

    name: str
    description: str
    type: Literal["skill", "tool"]
