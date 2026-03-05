"""Tests for the search_capabilities MCP tool.

These are integration tests that exercise the full stack: the MCP client
connects to the in-process server, the lifespan handler loads the real
registry and builds a ChromaDB index, and the tool performs semantic search
against that index.
"""

import json
from pathlib import Path

import pytest

from awos_recruitment_mcp.registry import load_registry

_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "registry"
_ALL_CAPS = load_registry(_REGISTRY_PATH)
_SKILL_NAMES = {c.name for c in _ALL_CAPS if c.type == "skill"}
_TOOL_NAMES = {c.name for c in _ALL_CAPS if c.type == "tool"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_result(result) -> list[dict] | str:
    """Extract the tool payload from a CallToolResult.

    For successful searches the payload is a JSON list serialised as text.
    For validation errors the payload is a plain error string.
    When the tool returns an empty list, the MCP layer may produce an empty
    ``content`` list — we treat that as an empty result set.
    """
    if not result.content:
        return []
    text = result.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


# ---------------------------------------------------------------------------
# Basic tool registration
# ---------------------------------------------------------------------------


async def test_search_capabilities_listed(mcp_client):
    """Verify that search_capabilities appears in the MCP tool list."""
    tools = await mcp_client.list_tools()
    tool_names = [t.name for t in tools]
    assert "search_capabilities" in tool_names, (
        f"Expected 'search_capabilities' in tool list, got: {tool_names}"
    )


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


async def test_search_capabilities_returns_results(mcp_client):
    """Call the tool and verify each result has name, description, and score."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "Python development"}
    )
    assert not result.is_error, "Expected a successful response, got an error"

    parsed = _parse_result(result)
    assert isinstance(parsed, list), f"Expected a list, got: {type(parsed)}"
    assert len(parsed) > 0, "Expected at least one capability in the response"

    for i, item in enumerate(parsed):
        assert "name" in item, f"Result[{i}] is missing 'name' field: {item}"
        assert "description" in item, (
            f"Result[{i}] is missing 'description' field: {item}"
        )
        assert "score" in item, f"Result[{i}] is missing 'score' field: {item}"
        assert isinstance(item["name"], str), (
            f"Result[{i}]['name'] should be a string, got: {type(item['name'])}"
        )
        assert isinstance(item["description"], str), (
            f"Result[{i}]['description'] should be a string, got: {type(item['description'])}"
        )
        assert isinstance(item["score"], int), (
            f"Result[{i}]['score'] should be an int, got: {type(item['score'])}"
        )


async def test_search_capabilities_result_limit(mcp_client):
    """Verify the response contains no more than 10 results."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "programming"}
    )
    assert not result.is_error, "Expected a successful response, got an error"

    parsed = _parse_result(result)
    assert isinstance(parsed, list), f"Expected a list, got: {type(parsed)}"
    assert len(parsed) <= 10, f"Expected no more than 10 results, got {len(parsed)}"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


async def test_search_capabilities_empty_query(mcp_client):
    """An empty query string must return an error message."""
    result = await mcp_client.call_tool("search_capabilities", {"query": ""})

    parsed = _parse_result(result)
    assert isinstance(parsed, str), (
        f"Expected an error string for empty query, got: {type(parsed)}"
    )
    assert "error" in parsed.lower(), (
        f"Expected error message for empty query, got: {parsed}"
    )


async def test_search_capabilities_whitespace_query(mcp_client):
    """A whitespace-only query must return an error message."""
    result = await mcp_client.call_tool("search_capabilities", {"query": "   "})

    parsed = _parse_result(result)
    assert isinstance(parsed, str), (
        f"Expected an error string for whitespace query, got: {type(parsed)}"
    )
    assert "error" in parsed.lower(), (
        f"Expected error message for whitespace query, got: {parsed}"
    )


async def test_search_capabilities_invalid_type(mcp_client):
    """An invalid type filter must return an error message."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "Python", "type": "invalid"}
    )

    parsed = _parse_result(result)
    assert isinstance(parsed, str), (
        f"Expected an error string for invalid type, got: {type(parsed)}"
    )
    assert "error" in parsed.lower(), (
        f"Expected error message for invalid type, got: {parsed}"
    )
    assert "invalid" in parsed.lower(), (
        f"Expected 'invalid' mentioned in error, got: {parsed}"
    )


# ---------------------------------------------------------------------------
# Semantic search quality
# ---------------------------------------------------------------------------


async def test_search_python_ranks_python_skill_high(mcp_client):
    """Querying 'Python development' should rank the Python skill highest."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "Python development"}
    )
    assert not result.is_error

    parsed = _parse_result(result)
    assert isinstance(parsed, list) and len(parsed) > 0, (
        "Expected at least one result for 'Python development'"
    )

    # The first result should be the Python skill.
    assert parsed[0]["name"] == "modern-python-development", (
        f"Expected 'modern-python-development' as top result, got: {parsed[0]['name']}"
    )


# ---------------------------------------------------------------------------
# Type filtering
# ---------------------------------------------------------------------------


async def test_search_type_filter_skill(mcp_client):
    """Filtering by type='skill' should return only skills."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "programming language", "type": "skill"}
    )
    assert not result.is_error

    parsed = _parse_result(result)
    assert isinstance(parsed, list), f"Expected a list, got: {type(parsed)}"

    # All returned results must be skills.
    for item in parsed:
        assert item["name"] in _SKILL_NAMES, (
            f"Expected only skill names, but got: {item['name']}"
        )


async def test_search_type_filter_tool(mcp_client):
    """Filtering by type='tool' should return only tools."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "browser automation", "type": "tool"}
    )
    assert not result.is_error

    parsed = _parse_result(result)
    assert isinstance(parsed, list), f"Expected a list, got: {type(parsed)}"

    # All returned results must be tools.
    for item in parsed:
        assert item["name"] in _TOOL_NAMES, (
            f"Expected only tool names, but got: {item['name']}"
        )


# ---------------------------------------------------------------------------
# Threshold filtering
# ---------------------------------------------------------------------------


async def test_search_results_above_threshold(mcp_client):
    """All returned results must have a score >= the configured threshold (20)."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "code"}
    )
    assert not result.is_error

    parsed = _parse_result(result)
    assert isinstance(parsed, list), f"Expected a list, got: {type(parsed)}"

    for item in parsed:
        assert item["score"] >= 20, (
            f"Result '{item['name']}' has score {item['score']} which is below "
            f"the threshold of 20"
        )


async def test_search_results_ordered_by_score(mcp_client):
    """Results must be ordered by score descending."""
    result = await mcp_client.call_tool(
        "search_capabilities", {"query": "development"}
    )
    assert not result.is_error

    parsed = _parse_result(result)
    assert isinstance(parsed, list), f"Expected a list, got: {type(parsed)}"

    if len(parsed) > 1:
        scores = [item["score"] for item in parsed]
        assert scores == sorted(scores, reverse=True), (
            f"Results are not sorted by score descending: {scores}"
        )


# ---------------------------------------------------------------------------
# Unrelated query
# ---------------------------------------------------------------------------


async def test_search_unrelated_query_returns_few_or_no_results(mcp_client):
    """A completely unrelated query should return very few or no results."""
    result = await mcp_client.call_tool(
        "search_capabilities",
        {"query": "quantum physics thermodynamics molecular biology"},
    )
    assert not result.is_error

    parsed = _parse_result(result)
    assert isinstance(parsed, list), f"Expected a list, got: {type(parsed)}"

    # With a threshold of 20 and a registry focused on programming topics,
    # an unrelated query should yield very few or no results.
    assert len(parsed) <= 1, (
        f"Expected 0 or 1 results for an unrelated query, got {len(parsed)}: "
        f"{[item['name'] for item in parsed]}"
    )
