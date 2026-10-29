"""Tests for the report_gap MCP tool.

The tool validates its input and forwards the report to telemetry. These
tests call it through the in-process MCP client and patch track_gap so no
real event is emitted.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastmcp.exceptions import ToolError


def _text(result) -> str:
    return result.content[0].text if result.content else ""


async def test_report_gap_listed(mcp_client):
    """report_gap appears in the MCP tool list next to search_capabilities."""
    tools = await mcp_client.list_tools()
    names = [t.name for t in tools]
    assert "report_gap" in names, f"Expected 'report_gap' in tool list, got: {names}"


@patch("awos_recruitment_mcp.tools.report_gap.track_gap")
async def test_report_gap_forwards_to_telemetry(mock_track_gap, mcp_client):
    """A valid report is forwarded to track_gap with trimmed fields."""
    result = await mcp_client.call_tool(
        "report_gap",
        {
            "query": "  GitHub App installation token auth ",
            "reason": "not_relevant",
            "offered": ["gha-diagnosis"],
            "needed_for": "python-backend",
            "note": "gha-diagnosis is about failed CI, not the GitHub API",
        },
    )
    assert not result.is_error, f"Expected success, got: {_text(result)}"
    assert "Gap recorded" in _text(result)

    mock_track_gap.assert_called_once_with(
        query="GitHub App installation token auth",
        offered=["gha-diagnosis"],
        reason="not_relevant",
        needed_for="python-backend",
        note="gha-diagnosis is about failed CI, not the GitHub API",
    )


@patch("awos_recruitment_mcp.tools.report_gap.track_gap")
async def test_report_gap_no_results_minimal(mock_track_gap, mcp_client):
    """A no_results report needs only query and reason."""
    result = await mcp_client.call_tool(
        "report_gap", {"query": "PHP Bitrix backend", "reason": "no_results"}
    )
    assert not result.is_error, f"Expected success, got: {_text(result)}"
    mock_track_gap.assert_called_once_with(
        query="PHP Bitrix backend",
        offered=[],
        reason="no_results",
        needed_for=None,
        note=None,
    )


@patch("awos_recruitment_mcp.tools.report_gap.track_gap")
async def test_report_gap_rejects_unknown_reason(mock_track_gap, mcp_client):
    """An unknown reason fails schema validation and records nothing."""
    with pytest.raises(ToolError):
        await mcp_client.call_tool("report_gap", {"query": "anything", "reason": "meh"})
    mock_track_gap.assert_not_called()


async def test_report_gap_schema_lists_reasons(mcp_client):
    """The input schema lists the allowed reason values."""
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "report_gap")
    assert tool.input_schema["properties"]["reason"]["enum"] == [
        "no_results",
        "not_relevant",
        "wrong_type",
    ]


@patch("awos_recruitment_mcp.tools.report_gap.track_gap")
async def test_report_gap_rejects_no_results_with_offered(mock_track_gap, mcp_client):
    """reason=no_results contradicts a non-empty offered list; nothing is recorded."""
    result = await mcp_client.call_tool(
        "report_gap",
        {"query": "anything", "reason": "no_results", "offered": ["x"]},
    )
    assert "requires an empty" in _text(result), (
        f"Expected a contradiction error, got: {_text(result)}"
    )
    mock_track_gap.assert_not_called()


@patch("awos_recruitment_mcp.tools.report_gap.track_gap")
async def test_report_gap_rejects_empty_query(mock_track_gap, mcp_client):
    """An empty query returns an error string and records nothing."""
    result = await mcp_client.call_tool(
        "report_gap", {"query": "   ", "reason": "no_results"}
    )
    assert "non-empty" in _text(result), f"Expected an empty-query error, got: {_text(result)}"
    mock_track_gap.assert_not_called()
