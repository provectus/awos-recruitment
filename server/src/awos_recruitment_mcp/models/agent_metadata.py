"""Pydantic model for validating agent front-matter metadata."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from awos_recruitment_mcp.models._frontmatter_fields import (
    FrontmatterDescription,
    FrontmatterName,
)


class AgentMetadata(BaseModel):
    """Validated representation of the YAML front matter in an agent ``.md`` file.

    Attributes:
        name: Kebab-case identifier for the agent (1-64 chars, lowercase
              alphanumeric and hyphens only, no reserved words
              ``anthropic``/``claude``, no XML tags).
        description: Human-readable description of what the agent does
            (1-1024 chars, no XML tags).
        model: Optional model identifier this agent is designed for.
        effort: Optional reasoning effort level the agent runs at. Lower
            levels cut thinking time and cost; omit it to follow the
            session's own effort setting.
        skills: Optional list of skill names (kebab-case) the agent depends on.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: FrontmatterName = Field(...)
    description: FrontmatterDescription = Field(...)

    # NOTE: ``model`` does not conflict with Pydantic's reserved ``model_``
    # prefix — only names starting with ``model_`` are reserved.  The field
    # name ``model`` is safe and follows the same pattern as SkillMetadata.
    model: str | None = Field(None)
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = Field(None)
    skills: list[
        Annotated[str, Field(pattern=r"^[a-z0-9-]{1,64}$")]
    ] | None = Field(None)
