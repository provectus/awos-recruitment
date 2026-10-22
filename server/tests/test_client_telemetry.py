"""Tests for POST /telemetry (events reported by the CLI)."""

from __future__ import annotations

from unittest.mock import call, patch

import httpx
import pytest
from awos_recruitment_mcp.server import mcp

PROJECT_ID = "b4252689-6fa4-4675-b630-ecb331160d84"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@patch("awos_recruitment_mcp.server.track_client_event")
async def test_events_are_tracked_with_project_id(mock_track, client):
    response = await client.post(
        "/telemetry",
        json={
            "project_id": PROJECT_ID,
            "events": [
                {"event": "capability_update_checked", "properties": {"outdated": 2}},
                {
                    "event": "capability_updated",
                    "capability_name": "pytest-best-practices",
                    "capability_type": "skill",
                    "properties": {"had_local_changes": False},
                },
            ],
        },
    )

    assert response.status_code == 204
    assert mock_track.call_args_list == [
        call(PROJECT_ID, "capability_update_checked", {"outdated": 2}),
        call(
            PROJECT_ID,
            "capability_updated",
            {
                "had_local_changes": False,
                "capability_name": "pytest-best-practices",
                "capability_type": "skill",
            },
        ),
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"project_id": PROJECT_ID, "events": []},
        {"project_id": "my-company/repo", "events": [{"event": "capability_updated"}]},
        {"project_id": PROJECT_ID, "events": [{"event": "user_logged_in"}]},
        {"project_id": PROJECT_ID, "events": [{"event": "capability_updated", "capability_name": "../x"}]},
        {"project_id": PROJECT_ID, "events": [{"event": "capability_updated", "properties": {"repo": {"a": 1}}}]},
    ],
)
@patch("awos_recruitment_mcp.server.track_client_event")
async def test_rejects_unknown_events_and_shapes(mock_track, client, body):
    response = await client.post("/telemetry", json=body)

    assert response.status_code == 400
    mock_track.assert_not_called()
