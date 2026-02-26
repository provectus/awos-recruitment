"""Pydantic model for validating agent front-matter metadata."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AgentMetadata(BaseModel):
    """Validated representation of the YAML front matter in an agent ``.md`` file.

    Attributes:
        name: Kebab-case identifier for the agent (1-64 chars, lowercase
              alphanumeric and hyphens only).
        description: Human-readable description of what the agent does.
        model: Optional model identifier this agent is designed for.
        skills: Optional list of skill names (kebab-case) the agent depends on.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(..., pattern=r"^[a-z0-9-]{1,64}$")
    description: str = Field(..., min_length=1)

    # NOTE: ``model`` does not conflict with Pydantic's reserved ``model_``
    # prefix — only names starting with ``model_`` are reserved.  The field
    # name ``model`` is safe and follows the same pattern as SkillMetadata.
    model: str | None = Field(None)
    skills: list[
        Annotated[str, Field(pattern=r"^[a-z0-9-]{1,64}$")]
    ] | None = Field(None)
