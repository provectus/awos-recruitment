"""Model for one entry of ``registry/recommendations.yaml``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationExamples(BaseModel):
    """Stack terms that must and must not trigger the entry.

    ``validate`` runs each example through the matcher, so a trigger word
    with a second meaning (``lambda``, ``ecs``, ``cloud``) fails the check
    before it reaches users.
    """

    model_config = ConfigDict(extra="forbid")

    match: list[str] = Field(min_length=1)
    no_match: list[str] = Field(min_length=1)


class Recommendation(BaseModel):
    """A capability that a project with a given stack probably needs.

    Attributes:
        id: Stable slug, sent back by ``report_recommendation``.
        recommend: Name of the capability, as ``search_capabilities``
            returns it.
        type: Kind of the capability: ``"skill"``, ``"tool"`` (an MCP
            server), ``"agent"``, or ``"hook"``.
        when_stack_has: Lowercase words or phrases. The entry triggers when
            one of them is a whole word in a stack term.
        unless_term_has: Lowercase words or phrases. A stack term that has
            one of them as a whole word does not trigger the entry, for
            example ``react native`` for a browser-only capability.
        reason: One sentence for the user: why this project needs it.
        examples: Stack terms that must and must not trigger the entry.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=64)
    recommend: str = Field(min_length=1)
    type: Literal["skill", "tool", "agent", "hook"]
    when_stack_has: list[str] = Field(min_length=1)
    unless_term_has: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=200)
    examples: RecommendationExamples
