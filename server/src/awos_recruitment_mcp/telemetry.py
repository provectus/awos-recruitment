"""Usage telemetry powered by PostHog.

All tracking functions are silent no-ops when no API key is configured.
Errors from the PostHog SDK are caught internally and logged as warnings
so that telemetry failures never affect the main request path.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from posthog import Posthog

if TYPE_CHECKING:
    from awos_recruitment_mcp.config import Config

logger = logging.getLogger(__name__)

_client: Posthog | None = None


def init_telemetry(config: Config) -> None:
    """Create the PostHog client from *config*.

    If ``config.posthog_api_key`` is ``None`` the client is not created
    and all subsequent tracking calls become no-ops.
    """
    global _client  # noqa: PLW0603

    if config.posthog_api_key is None:
        logger.debug("PostHog API key not set — telemetry disabled")
        return

    try:
        _client = Posthog(
            project_api_key=config.posthog_api_key,
            host=config.posthog_host,
            on_error=lambda error: logger.warning("PostHog error: %s", error),
        )
        logger.info("PostHog telemetry initialised (host=%s)", config.posthog_host)
    except Exception:
        logger.warning("Failed to initialise PostHog client", exc_info=True)
        _client = None


def shutdown_telemetry() -> None:
    """Flush pending events and stop the PostHog background thread."""
    global _client  # noqa: PLW0603

    if _client is None:
        return

    try:
        _client.shutdown()
    except Exception:
        logger.warning("Error shutting down PostHog client", exc_info=True)
    finally:
        _client = None


def track_search(
    query: str,
    results: list[dict],
    type_filter: str | None = None,
) -> None:
    """Emit a ``capability_searched`` event.

    Besides the query and the result names, the event carries three flat
    properties for gap analysis: ``result_count``, ``top_score`` (the best
    similarity score in the list, ``None`` when the list is empty) and
    ``type_filter``. A zero ``result_count`` is a hard gap; a low
    ``top_score`` is a weak match the caller may still have rejected.

    Args:
        query: The raw search text entered by the user.
        results: The list of result dicts returned by the search index.
            Each dict is expected to contain ``"name"`` and ``"score"`` keys.
        type_filter: The capability type the search was restricted to, or
            ``None`` when the search covered every type.
    """
    if _client is None:
        return

    try:
        _client.capture(
            distinct_id="anonymous",
            event="capability_searched",
            properties={
                "query": query,
                "results": [r["name"] for r in results],
                "result_count": len(results),
                "top_score": max((r["score"] for r in results), default=None),
                "type_filter": type_filter,
            },
        )
    except Exception:
        logger.warning("Failed to track search event", exc_info=True)


def track_install(capability_name: str, capability_type: str) -> None:
    """Emit a ``capability_installed`` event.

    Args:
        capability_name: The name of the installed capability.
        capability_type: One of ``"skill"``, ``"agent"``, ``"hook"``, or
            ``"mcp_server"``.
    """
    if _client is None:
        return

    try:
        _client.capture(
            distinct_id="anonymous",
            event="capability_installed",
            properties={
                "capability_name": capability_name,
                "capability_type": capability_type,
            },
        )
    except Exception:
        logger.warning("Failed to track install event", exc_info=True)


def track_client_event(
    project_id: str,
    event: str,
    properties: dict[str, int | bool | str],
) -> None:
    """Emit an event reported by the CLI (``POST /telemetry``).

    The CLI's random ``project_id`` is the distinct id, so one project's
    checks and updates line up without a repo or user name.

    Args:
        project_id: Random id from the project's lock file.
        event: Allow-listed event name (validated by the route).
        properties: Scalar properties such as ``capability_name`` or counts.
    """
    if _client is None:
        return

    try:
        _client.capture(
            distinct_id=project_id,
            event=event,
            properties=properties,
        )
    except Exception:
        logger.warning("Failed to track client event %s", event, exc_info=True)
