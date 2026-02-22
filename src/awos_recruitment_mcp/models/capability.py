"""Capability result model returned by the search_capabilities tool."""

from __future__ import annotations

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
