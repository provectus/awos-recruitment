"""Pydantic model for validating SKILL.md front-matter metadata."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from awos_recruitment_mcp.models._frontmatter_fields import (
    FrontmatterDescription,
    FrontmatterName,
)


class SkillMetadata(BaseModel):
    """Validated representation of the YAML front matter in a SKILL.md file.

    Attributes:
        name: Kebab-case identifier for the skill (1-64 chars, lowercase
              alphanumeric and hyphens only, no reserved words
              ``anthropic``/``claude``, no XML tags).
        description: Human-readable description of the skill (1-1024
            chars, no XML tags).
        license: License covering the skill (Agent Skills spec field).
        compatibility: Environment requirements for the skill, such as
            intended products or system prerequisites (Agent Skills spec
            field; at most 500 characters).
        metadata: Free-form string-to-string map for catalog data the spec
            recommends keeping out of the top level — ``version``, ``author``
            and the like. Claude Code does not act on its contents.
        version: Optional SemVer-style version string. Still accepted at the
            top level, but the validator warns (``version-top-level``) and
            asks for it to move under ``metadata.version``.
        argument_hint: Optional hint text shown to the user for arguments.
            ``<placeholder>`` hints are conventional, so an XML-like tag here
            only warns (``frontmatter-xml-tags``) instead of failing.
        disable_model_invocation: If true, prevents the model from invoking
            this skill autonomously.
        user_invocable: Whether the user can invoke this skill directly.
        allowed_tools: Comma-separated list of tools the skill may use.
        model: Model identifier this skill is designed for.
        effort: Reasoning effort level the skill runs at. Lower levels cut
            thinking time and cost; omit it to follow the session's own
            effort setting.
        context: Additional context string.
        agent: Agent identifier.
        hooks: Arbitrary hook configuration dictionary.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: FrontmatterName = Field(...)
    description: FrontmatterDescription = Field(...)

    license: str | None = Field(None)
    compatibility: str | None = Field(None, max_length=500)
    metadata: dict[str, str] | None = Field(None)
    version: str | None = Field(None)
    argument_hint: str | None = Field(None, alias="argument-hint")
    disable_model_invocation: bool | None = Field(
        None, alias="disable-model-invocation"
    )
    user_invocable: bool | None = Field(None, alias="user-invocable")
    allowed_tools: str | None = Field(None, alias="allowed-tools")
    model: str | None = Field(None)
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = Field(None)
    context: str | None = Field(None)
    agent: str | None = Field(None)
    hooks: dict | None = Field(None)
