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


def track_search(query: str, results: list[dict]) -> None:
    """Emit a ``capability_searched`` event.

    Args:
        query: The raw search text entered by the user.
        results: The list of result dicts returned by the search index.
            Each dict is expected to contain a ``"name"`` key.
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
            },
        )
    except Exception:
        logger.warning("Failed to track search event", exc_info=True)
