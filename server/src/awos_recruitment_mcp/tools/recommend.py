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
_MAX_TERM_LENGTH = 100
_MAX_EXCLUDE = 200


@mcp.tool
async def recommend_capabilities(
    stack: list[str],
    exclude: list[str] | None = None,
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
        exclude: Names of capabilities to leave out: the ones the project
            already has and the ones the user declined before.
    """
    if not isinstance(stack, list) or not any(
        isinstance(t, str) and t.strip() for t in stack
    ):
        return "Error: stack must be a non-empty list of technology names."

    terms = [
        t.strip()[:_MAX_TERM_LENGTH]
        for t in stack
        if isinstance(t, str) and t.strip()
    ][:_MAX_TERMS]
    excluded = [
        name for name in (exclude or []) if isinstance(name, str) and name.strip()
    ][:_MAX_EXCLUDE]

    items = recommendations.recommend(
        recs=ctx.lifespan_context["recommendations"],
        capabilities=ctx.lifespan_context["capabilities"],
        stack=terms,
        exclude=excluded,
    )

    track_recommendations(terms, items)

    return items


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
