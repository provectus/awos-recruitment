"""Search tool for discovering capabilities in the registry.

This module registers the ``search_capabilities`` tool on the shared
:pydata:`~awos_recruitment_mcp.server.mcp` instance.  It is imported by
``server.py`` at module level so that tool registration happens at startup.
"""

from __future__ import annotations

from fastmcp.server.context import Context

from awos_recruitment_mcp import search_index
from awos_recruitment_mcp.server import config, mcp
from awos_recruitment_mcp.telemetry import track_search

VALID_TYPES = {"skill", "agent", "tool"}


@mcp.tool
async def search_capabilities(
    query: str,
    type: str | None = None,
    ctx: Context = None,  # type: ignore[assignment]
) -> list[dict] | str:
    """Search the capability registry for skills, agents, and tools matching a query.

    Returns a ranked list of capabilities.  Each result includes a name,
    description, and similarity score (0--100).  Returns at most 10 results.

    Args:
        query: Natural-language search query describing the capability
            you are looking for.
        type: Optional filter to restrict results to a specific capability
            type.  Must be one of ``"skill"``, ``"agent"``, or ``"tool"``.
    """
    # --- input validation ---------------------------------------------------
    if not query or not query.strip():
        return "Error: query must be a non-empty string."

    if type is not None and type not in VALID_TYPES:
        return (
            f"Error: invalid type '{type}'. "
            f"Must be one of: {', '.join(sorted(VALID_TYPES))}."
        )

    # --- retrieve collection from lifespan context --------------------------
    collection = ctx.lifespan_context["collection"]

    # --- perform semantic search --------------------------------------------
    results = search_index.query(
        collection=collection,
        query_text=query.strip(),
        n_results=10,
        type_filter=type,
        threshold=config.search_threshold,
    )

    track_search(query, results)

    return results
