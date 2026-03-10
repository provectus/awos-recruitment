"""Unit tests for the telemetry module.

These tests mock the PostHog client so no real events are emitted.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from awos_recruitment_mcp import telemetry
from awos_recruitment_mcp.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    api_key: str | None = "phc_test_key",
    host: str = "https://us.i.posthog.com",
) -> Config:
    """Build a minimal Config with the given PostHog settings."""
    return Config(posthog_api_key=api_key, posthog_host=host)


def _sample_results() -> list[dict]:
    """Return a small list of fake search results."""
    return [
        {"name": "python-dev", "description": "Python skill", "score": 90},
        {"name": "fastapi", "description": "FastAPI skill", "score": 75},
    ]


# ---------------------------------------------------------------------------
# Tests — track_search calls capture with correct arguments
# ---------------------------------------------------------------------------


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_search_calls_capture(mock_client: MagicMock) -> None:
    """track_search() should call client.capture() with the expected event
    name, distinct_id, and properties containing the query and result names.
    """
    results = _sample_results()
    telemetry.track_search("Python development", results)

    mock_client.capture.assert_called_once_with(
        distinct_id="anonymous",
        event="capability_searched",
        properties={
            "query": "Python development",
            "results": ["python-dev", "fastapi"],
        },
    )


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_search_empty_results(mock_client: MagicMock) -> None:
    """track_search() should handle an empty results list correctly."""
    telemetry.track_search("niche query", [])

    mock_client.capture.assert_called_once_with(
        distinct_id="anonymous",
        event="capability_searched",
        properties={
            "query": "niche query",
            "results": [],
        },
    )


# ---------------------------------------------------------------------------
# Tests — no-op when API key is not configured
# ---------------------------------------------------------------------------


def test_track_search_noop_when_no_api_key() -> None:
    """When init_telemetry is called without an API key, track_search()
    must be a silent no-op — no exceptions, no side effects.
    """
    # Ensure the module-level client is None.
    original_client = telemetry._client
    try:
        telemetry._client = None
        # Should not raise.
        telemetry.track_search("any query", _sample_results())
    finally:
        telemetry._client = original_client


def test_init_telemetry_skips_when_no_api_key() -> None:
    """init_telemetry() with posthog_api_key=None should leave _client as None."""
    original_client = telemetry._client
    try:
        telemetry._client = None
        telemetry.init_telemetry(_make_config(api_key=None))
        assert telemetry._client is None
    finally:
        telemetry._client = original_client


def test_shutdown_telemetry_noop_when_no_client() -> None:
    """shutdown_telemetry() should be a silent no-op when _client is None."""
    original_client = telemetry._client
    try:
        telemetry._client = None
        # Should not raise.
        telemetry.shutdown_telemetry()
    finally:
        telemetry._client = original_client


# ---------------------------------------------------------------------------
# Tests — exceptions are caught and logged, never re-raised
# ---------------------------------------------------------------------------


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_search_catches_capture_exception(
    mock_client: MagicMock,
) -> None:
    """If client.capture() raises, track_search() must catch the exception
    and log a warning instead of propagating it.
    """
    mock_client.capture.side_effect = RuntimeError("network timeout")

    # Must not raise.
    telemetry.track_search("failing query", _sample_results())

    mock_client.capture.assert_called_once()


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_search_logs_warning_on_exception(
    mock_client: MagicMock,
    caplog,
) -> None:
    """Verify that the warning message is actually logged when capture fails."""
    mock_client.capture.side_effect = RuntimeError("boom")

    with caplog.at_level(logging.WARNING, logger="awos_recruitment_mcp.telemetry"):
        telemetry.track_search("failing query", _sample_results())

    assert any("Failed to track search event" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Tests — init / shutdown lifecycle
# ---------------------------------------------------------------------------


@patch("awos_recruitment_mcp.telemetry.Posthog")
def test_init_telemetry_creates_client(mock_posthog_cls: MagicMock) -> None:
    """init_telemetry() should instantiate a Posthog client when an API key
    is provided.
    """
    original_client = telemetry._client
    try:
        telemetry._client = None
        config = _make_config(api_key="phc_abc123", host="https://eu.i.posthog.com")
        telemetry.init_telemetry(config)

        mock_posthog_cls.assert_called_once()
        call_kwargs = mock_posthog_cls.call_args
        assert call_kwargs.kwargs["project_api_key"] == "phc_abc123"
        assert call_kwargs.kwargs["host"] == "https://eu.i.posthog.com"
        assert telemetry._client is not None
    finally:
        telemetry._client = original_client


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_shutdown_telemetry_calls_shutdown(mock_client: MagicMock) -> None:
    """shutdown_telemetry() should call client.shutdown() and reset _client."""
    telemetry.shutdown_telemetry()

    mock_client.shutdown.assert_called_once()
    assert telemetry._client is None


# ---------------------------------------------------------------------------
# Tests — track_install calls capture with correct arguments
# ---------------------------------------------------------------------------


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_install_calls_capture(mock_client: MagicMock) -> None:
    """track_install() should call client.capture() with the expected event
    name, distinct_id, and properties containing capability_name and
    capability_type.
    """
    telemetry.track_install("modern-python-development", "skill")

    mock_client.capture.assert_called_once_with(
        distinct_id="anonymous",
        event="capability_installed",
        properties={
            "capability_name": "modern-python-development",
            "capability_type": "skill",
        },
    )


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_install_mcp_server_type(mock_client: MagicMock) -> None:
    """track_install() should pass capability_type through to properties."""
    telemetry.track_install("context7", "mcp_server")

    mock_client.capture.assert_called_once_with(
        distinct_id="anonymous",
        event="capability_installed",
        properties={
            "capability_name": "context7",
            "capability_type": "mcp_server",
        },
    )


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_install_agent_type(mock_client: MagicMock) -> None:
    """track_install() should pass capability_type='agent' through to properties."""
    telemetry.track_install("test-agent", "agent")

    mock_client.capture.assert_called_once_with(
        distinct_id="anonymous",
        event="capability_installed",
        properties={
            "capability_name": "test-agent",
            "capability_type": "agent",
        },
    )


# ---------------------------------------------------------------------------
# Tests — track_install no-op when no API key configured
# ---------------------------------------------------------------------------


def test_track_install_noop_when_no_api_key() -> None:
    """When _client is None, track_install() must be a silent no-op."""
    original_client = telemetry._client
    try:
        telemetry._client = None
        # Should not raise.
        telemetry.track_install("some-skill", "skill")
    finally:
        telemetry._client = original_client


# ---------------------------------------------------------------------------
# Tests — track_install catches exceptions and logs warning
# ---------------------------------------------------------------------------


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_install_catches_capture_exception(
    mock_client: MagicMock,
) -> None:
    """If client.capture() raises, track_install() must catch the exception
    and not propagate it.
    """
    mock_client.capture.side_effect = RuntimeError("network timeout")

    # Must not raise.
    telemetry.track_install("failing-skill", "skill")

    mock_client.capture.assert_called_once()


@patch.object(telemetry, "_client", new_callable=MagicMock)
def test_track_install_logs_warning_on_exception(
    mock_client: MagicMock,
    caplog,
) -> None:
    """Verify that the warning message is actually logged when capture fails."""
    mock_client.capture.side_effect = RuntimeError("boom")

    with caplog.at_level(logging.WARNING, logger="awos_recruitment_mcp.telemetry"):
        telemetry.track_install("failing-skill", "skill")

    assert any("Failed to track install event" in record.message for record in caplog.records)
