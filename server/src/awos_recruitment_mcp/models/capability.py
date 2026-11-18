"""Capability models for the AWOS Recruitment MCP server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CapabilityResult(BaseModel):
    """A single capability discovered in the registry.

    Attributes:
        name: Unique, human-readable identifier for the capability.
        description: Short prose description of what the capability does.
        type: The kind of capability — ``"skill"``, ``"tool"`` (an MCP
            server), ``"agent"``, or ``"hook"``.
        score: Similarity score (0--100) indicating how well the capability
            matches the search query.
        user_invoked: Set on skill results only. ``True`` when the skill's
            ``SKILL.md`` has ``disable-model-invocation: true``: the user
            starts it with its slash command, and an agent cannot preload it
            through the ``skills:`` field. ``None`` (key absent) for agents,
            tools, and hooks.
    """

    name: str
    description: str
    type: Literal["skill", "tool", "agent", "hook"]
    score: int
    user_invoked: bool | None = None


class RegistryCapability(BaseModel):
    """A capability loaded from the registry (skill, MCP tool, agent, or hook).

    Attributes:
        name: The capability name extracted from registry metadata.
        description: Human-readable description of what the capability does.
        type: The kind of capability — ``"skill"``, ``"tool"``, ``"agent"``,
            or ``"hook"``.
        user_invoked: For skills, ``True`` when the front matter has
            ``disable-model-invocation: true`` and ``False`` otherwise.
            ``None`` for every other type.
    """

    name: str
    description: str
    type: Literal["skill", "tool", "agent", "hook"]
    user_invoked: bool | None = None
