"""Gap-report tool: the caller tells the registry a search did not help.

This module registers the ``report_gap`` tool on the shared
:pydata:`~awos_recruitment_mcp.server.mcp` instance.  It is imported by
``server.py`` at module level so that tool registration happens at startup.
"""

from __future__ import annotations

from awos_recruitment_mcp.server import mcp
from awos_recruitment_mcp.telemetry import GapReason, track_gap

_MAX_TEXT = 500


@mcp.tool
async def report_gap(
    query: str,
    reason: GapReason,
    offered: list[str] | None = None,
    needed_for: str | None = None,
    note: str | None = None,
) -> str:
    """Report that a capability search did not give you what you needed.

    Call this after ``search_capabilities`` when you decided not to use any
    of its results: the list was empty, nothing in it fit the need, or the
    results were the wrong kind of capability. The report is recorded for
    the registry maintainers so they can see which capabilities are missing.
    It changes nothing in the registry and returns a short confirmation.

    Args:
        query: The exact search text you used.
        reason: Why the results did not help. One of ``"no_results"``
            (the search returned nothing), ``"not_relevant"`` (results
            exist but none fits the need), ``"wrong_type"`` (results exist
            but are the wrong kind, e.g. an MCP server when a skill was
            needed).
        offered: The capability names the search returned, if any.
        needed_for: The role or agent you were searching for, e.g.
            ``"python-backend"``.
        note: One sentence on why the results did not fit.

    Do not put names of people, companies, clients or repositories in
    ``needed_for`` or ``note``: both are sent to telemetry as you write them.
    """
    if not query or not query.strip():
        return "Error: query must be a non-empty string."

    offered = [name for name in (offered or []) if isinstance(name, str) and name]

    if reason == "no_results" and offered:
        return "Error: reason 'no_results' requires an empty 'offered' list."

    track_gap(
        query=query.strip()[:_MAX_TEXT],
        offered=offered[:20],
        reason=reason,
        needed_for=needed_for.strip()[:100] if needed_for else None,
        note=note.strip()[:_MAX_TEXT] if note else None,
    )

    return f"Gap recorded for '{query.strip()}' ({reason})."
