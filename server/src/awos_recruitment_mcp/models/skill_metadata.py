"""Pydantic model for validating SKILL.md front-matter metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkillMetadata(BaseModel):
    """Validated representation of the YAML front matter in a SKILL.md file.

    Attributes:
        name: Kebab-case identifier for the skill (1-64 chars, lowercase
              alphanumeric and hyphens only).
        description: Human-readable description of the skill.
        version: Optional SemVer-style version string.
        argument_hint: Optional hint text shown to the user for arguments.
        disable_model_invocation: If true, prevents the model from invoking
            this skill autonomously.
        user_invocable: Whether the user can invoke this skill directly.
        allowed_tools: Comma-separated list of tools the skill may use.
        model: Model identifier this skill is designed for.
        context: Additional context string.
        agent: Agent identifier.
        hooks: Arbitrary hook configuration dictionary.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(..., pattern=r"^[a-z0-9-]{1,64}$")
    description: str = Field(..., min_length=1)

    version: str | None = Field(None)
    argument_hint: str | None = Field(None, alias="argument-hint")
    disable_model_invocation: bool | None = Field(
        None, alias="disable-model-invocation"
    )
    user_invocable: bool | None = Field(None, alias="user-invocable")
    allowed_tools: str | None = Field(None, alias="allowed-tools")
    model: str | None = Field(None)
    context: str | None = Field(None)
    agent: str | None = Field(None)
    hooks: dict | None = Field(None)
