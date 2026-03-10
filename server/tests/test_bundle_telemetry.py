"""Integration tests verifying that bundle endpoints trigger install telemetry.

These tests hit the actual ASGI endpoints and verify that track_install()
is called with the correct arguments for each found capability.
"""

from __future__ import annotations

from unittest.mock import call, patch

import httpx
import pytest
from awos_recruitment_mcp.server import mcp


@pytest.fixture
def asgi_app():
    """Return the ASGI app from the FastMCP server for in-process HTTP testing."""
    return mcp.http_app()


# ---------------------------------------------------------------------------
# POST /bundle/skills — telemetry
# ---------------------------------------------------------------------------


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_skills_tracks_found_capabilities(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/skills should call track_install for each found skill."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/skills",
            json={"names": ["modern-python-development"]},
        )

    mock_track_install.assert_called_once_with("modern-python-development", "skill")


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_skills_does_not_track_not_found(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/skills should not call track_install for not-found names."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/skills",
            json={"names": ["nonexistent-skill"]},
        )

    mock_track_install.assert_not_called()


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_skills_tracks_only_found_in_mixed_request(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/skills with a mix of found and not-found names should only
    track the found ones.
    """
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/skills",
            json={"names": ["modern-python-development", "nonexistent-skill"]},
        )

    mock_track_install.assert_called_once_with("modern-python-development", "skill")


# ---------------------------------------------------------------------------
# POST /bundle/mcp — telemetry
# ---------------------------------------------------------------------------


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_mcp_tracks_found_capabilities(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/mcp should call track_install for each found MCP server."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/mcp",
            json={"names": ["context7"]},
        )

    mock_track_install.assert_called_once_with("context7", "mcp_server")


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_mcp_does_not_track_not_found(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/mcp should not call track_install for not-found names."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/mcp",
            json={"names": ["nonexistent-tool"]},
        )

    mock_track_install.assert_not_called()


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_mcp_tracks_multiple_found(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/mcp with multiple valid names should call track_install for each."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/mcp",
            json={"names": ["context7", "playwright"]},
        )

    assert mock_track_install.call_count == 2
    mock_track_install.assert_any_call("context7", "mcp_server")
    mock_track_install.assert_any_call("playwright", "mcp_server")


# ---------------------------------------------------------------------------
# POST /bundle/agents — telemetry
# ---------------------------------------------------------------------------


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_agents_tracks_found_capabilities(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/agents should call track_install for each found agent."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/agents",
            json={"names": ["test-agent"]},
        )

    mock_track_install.assert_called_once_with("test-agent", "agent")


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_agents_does_not_track_not_found(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/agents should not call track_install for not-found names."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/agents",
            json={"names": ["nonexistent-agent"]},
        )

    mock_track_install.assert_not_called()


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_agents_tracks_only_found_in_mixed_request(
    mock_track_install,
    asgi_app,
) -> None:
    """POST /bundle/agents with a mix of found and not-found names should only
    track the found ones.
    """
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/bundle/agents",
            json={"names": ["test-agent", "nonexistent-agent"]},
        )

    mock_track_install.assert_called_once_with("test-agent", "agent")
