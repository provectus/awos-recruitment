"""Capability models for the AWOS Recruitment MCP server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CapabilityResult(BaseModel):
    """A single capability discovered in the registry.

    Attributes:
        name: Unique, human-readable identifier for the capability.
        description: Short prose description of what the capability does.
        score: Similarity score (0--100) indicating how well the capability
            matches the search query.
    """

    name: str
    description: str
    score: int


class RegistryCapability(BaseModel):
    """A capability loaded from the registry (skill, MCP tool, or agent).

    Attributes:
        name: The capability name extracted from registry metadata.
        description: Human-readable description of what the capability does.
        type: The kind of capability — ``"skill"``, ``"tool"``, or ``"agent"``.
    """

    name: str
    description: str
    type: Literal["skill", "tool", "agent"]
