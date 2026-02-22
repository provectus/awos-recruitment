import json
import pytest
from fastmcp import Client


async def test_search_capabilities_listed(mcp_client):
    """Verify that search_capabilities appears in the MCP tool list."""
    tools = await mcp_client.list_tools()
    tool_names = [t.name for t in tools]
    assert "search_capabilities" in tool_names, (
        f"Expected 'search_capabilities' in tool list, got: {tool_names}"
    )


async def test_search_capabilities_returns_results(mcp_client):
    """Call the tool with query 'test' and verify each result has name, description, and tags."""
    result = await mcp_client.call_tool("search_capabilities", {"query": "test"})

    assert not result.is_error, "Expected a successful response, got an error"
    assert result.content, "Expected non-empty content in the result"

    parsed = json.loads(result.content[0].text)

    assert isinstance(parsed, list), (
        f"Expected result to be a list, got: {type(parsed)}"
    )
    assert len(parsed) > 0, "Expected at least one capability in the response"

    for i, item in enumerate(parsed):
        assert "name" in item, f"Result[{i}] is missing 'name' field: {item}"
        assert "description" in item, (
            f"Result[{i}] is missing 'description' field: {item}"
        )
        assert "tags" in item, f"Result[{i}] is missing 'tags' field: {item}"
        assert isinstance(item["name"], str), (
            f"Result[{i}]['name'] should be a string, got: {type(item['name'])}"
        )
        assert isinstance(item["description"], str), (
            f"Result[{i}]['description'] should be a string, got: {type(item['description'])}"
        )
        assert isinstance(item["tags"], list), (
            f"Result[{i}]['tags'] should be a list, got: {type(item['tags'])}"
        )


async def test_search_capabilities_result_limit(mcp_client):
    """Verify the response contains no more than 10 results."""
    result = await mcp_client.call_tool("search_capabilities", {"query": "python"})

    assert not result.is_error, "Expected a successful response, got an error"
    assert result.content, "Expected non-empty content in the result"

    parsed = json.loads(result.content[0].text)

    assert isinstance(parsed, list), (
        f"Expected result to be a list, got: {type(parsed)}"
    )
    assert len(parsed) <= 10, (
        f"Expected no more than 10 results, got {len(parsed)}"
    )


async def test_search_capabilities_empty_query(mcp_client):
    """Call the tool with an empty string and verify it returns a successful response."""
    result = await mcp_client.call_tool("search_capabilities", {"query": ""})

    assert not result.is_error, (
        "Expected a successful response for empty query, got an error"
    )
    assert result.content, "Expected non-empty content in the result for empty query"

    parsed = json.loads(result.content[0].text)

    assert isinstance(parsed, list), (
        f"Expected result to be a list, got: {type(parsed)}"
    )
