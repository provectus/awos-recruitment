"""Recommendation tools: what a stack probably needs, and what the user chose.

This module registers ``recommend_capabilities`` and ``report_recommendation``
on the shared :pydata:`~awos_recruitment_mcp.server.mcp` instance.  It is
imported by ``server.py`` at module level so that tool registration happens
at startup.
"""

from __future__ import annotations

from fastmcp.server.context import Context

from awos_recruitment_mcp import recommendations
from awos_recruitment_mcp.server import mcp
from awos_recruitment_mcp.telemetry import (
    RecommendationOutcome,
    track_recommendation_outcome,
    track_recommendations,
)

_MAX_TERMS = 50
_MAX_EXCLUDE = 200


@mcp.tool
async def recommend_capabilities(
    stack: list[str],
    exclude: list[str] | None = None,
    declined: list[str] | None = None,
    ctx: Context = None,  # type: ignore[assignment]
) -> list[dict] | str:
    """Return capabilities that a project with this stack probably needs but did not search for.

    The registry maintainers keep a list of such cases, for example a
    disaster recovery plan for a system that runs on AWS. Call this one time
    per run, after your searches, with every technology and domain of the
    project. A result is not a search match: show each one to the user with
    its ``reason`` and install it only if the user selects it. Do not add a
    result to an agent's ``skills:`` list. Then call
    ``report_recommendation`` one time for each result.

    Returns at most 4 items, each with ``id``, ``name``, ``type``
    (``"skill"``, ``"tool"`` for an MCP server, ``"agent"``, or ``"hook"``),
    ``description``, ``reason`` and ``matched_term`` (the stack term that
    triggered it). A skill item also has ``user_invoked`` (bool), as in
    ``search_capabilities``. An empty list means there is nothing to
    recommend.

    Args:
        stack: The project's technologies and domains, one per item, for
            example ``["Python", "FastAPI", "AWS", "GitHub Actions"]``.
        exclude: Names of capabilities that the project already has or
            that this run already proposes. They are left out.
        declined: Names of capabilities that the user declined before. They
            are left out, and so is each result that needs one of them to
            work (``verify-ui`` when ``playwright`` was declined).
    """
    if not isinstance(stack, list) or not any(
        isinstance(t, str) and t.strip() for t in stack
    ):
        return "Error: stack must be a non-empty list of technology names."

    terms = [t.strip() for t in stack if isinstance(t, str) and t.strip()][
        :_MAX_TERMS
    ]

    items = recommendations.recommend(
        recs=ctx.lifespan_context["recommendations"],
        capabilities=ctx.lifespan_context["capabilities"],
        stack=terms,
        exclude=_names(exclude),
        declined=_names(declined),
    )

    track_recommendations(terms, items)

    return items


def _names(names: list[str] | None) -> list[str]:
    """Return the non-blank strings of *names*, at most ``_MAX_EXCLUDE``."""
    return [n for n in (names or []) if isinstance(n, str) and n.strip()][
        :_MAX_EXCLUDE
    ]


@mcp.tool
async def report_recommendation(
    id: str,
    outcome: RecommendationOutcome,
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """Report what the user did with one result of ``recommend_capabilities``.

    Call it one time for each result, after the user answered. The report is
    recorded for the registry maintainers, so they can see which
    recommendations help and which are noise. It changes nothing in the
    registry and returns a short confirmation.

    Args:
        id: The ``id`` of the result.
        outcome: ``"installed"`` (the user selected it and it was
            installed), ``"declined"`` (the user did not select it), or
            ``"not_answered"`` (the question got no answer, so nothing was
            installed).
    """
    recs = {rec.id: rec for rec in ctx.lifespan_context["recommendations"]}
    rec = recs.get(id)
    if rec is None:
        return f"Error: unknown recommendation id '{id}'."

    track_recommendation_outcome(rec.id, rec.recommend, rec.type, outcome)

    return f"Outcome recorded for '{rec.id}' ({outcome})."
