"""Tests for the POST /bundle/skills, POST /bundle/mcp, and POST /bundle/agents endpoints."""

from __future__ import annotations

import io
import tarfile

import httpx
import pytest
from awos_recruitment_mcp.server import mcp


@pytest.fixture
def asgi_app():
    """Return the ASGI app from the FastMCP server for in-process HTTP testing."""
    return mcp.http_app()


# ---------------------------------------------------------------------------
# Valid request
# ---------------------------------------------------------------------------


async def test_valid_request_returns_200(asgi_app):
    """POST a single valid skill name and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["modern-python-development"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_valid_request_returns_tar_gz(asgi_app):
    """POST a single valid skill name and verify the response is a valid tar.gz archive."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["modern-python-development"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "modern-python-development/SKILL.md" in names, (
        f"Expected SKILL.md in archive, got {names}"
    )

    reference_entries = [n for n in names if n.startswith("modern-python-development/references/")]
    assert len(reference_entries) > 0, (
        f"Expected at least one references/ entry, got {names}"
    )


async def test_valid_request_contains_all_references(asgi_app):
    """POST a single valid skill name and verify all reference files are present."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["modern-python-development"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    expected_refs = [
        "modern-python-development/references/modern-syntax.md",
        "modern-python-development/references/patterns.md",
        "modern-python-development/references/project-structure.md",
        "modern-python-development/references/type-hints.md",
    ]
    for ref in expected_refs:
        assert ref in names, (
            f"Expected '{ref}' in archive, got {names}"
        )


# ---------------------------------------------------------------------------
# Partial matches
# ---------------------------------------------------------------------------


async def test_partial_matches_returns_200(asgi_app):
    """POST a mix of existing and nonexistent skill names and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["modern-python-development", "nonexistent-skill"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_partial_matches_contains_only_existing(asgi_app):
    """POST a mix of existing and nonexistent names; archive contains only the existing skill."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["modern-python-development", "nonexistent-skill"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert any(n.startswith("modern-python-development/") for n in names), (
        f"Expected modern-python-development entries in archive, got {names}"
    )
    assert not any(n.startswith("nonexistent-skill/") for n in names), (
        f"Did not expect nonexistent-skill entries in archive, got {names}"
    )


# ---------------------------------------------------------------------------
# Empty names list
# ---------------------------------------------------------------------------


async def test_empty_names_returns_400(asgi_app):
    """POST an empty names list and verify HTTP 400."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": []},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


async def test_empty_names_returns_error_body(asgi_app):
    """POST an empty names list and verify the error body structure."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": []},
        )

    body = response.json()
    assert "error" in body, (
        f"Expected 'error' key in response body, got {body}"
    )


# ---------------------------------------------------------------------------
# Names exceeding limit
# ---------------------------------------------------------------------------


async def test_too_many_names_returns_400(asgi_app):
    """POST 21 names (exceeding the limit of 20) and verify HTTP 400."""
    names = [f"skill-{i}" for i in range(21)]
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": names},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


async def test_too_many_names_returns_error_body(asgi_app):
    """POST 21 names and verify the error body structure."""
    names = [f"skill-{i}" for i in range(21)]
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": names},
        )

    body = response.json()
    assert "error" in body, (
        f"Expected 'error' key in response body, got {body}"
    )


# ---------------------------------------------------------------------------
# All not-found
# ---------------------------------------------------------------------------


async def test_all_not_found_returns_200(asgi_app):
    """POST names that do not match any skill and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["does-not-exist"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_all_not_found_returns_empty_archive(asgi_app):
    """POST names that do not match any skill and verify the archive is empty."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["does-not-exist"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        members = tar.getmembers()

    assert len(members) == 0, (
        f"Expected empty archive, got {len(members)} members: {[m.name for m in members]}"
    )


# ---------------------------------------------------------------------------
# Invalid name pattern
# ---------------------------------------------------------------------------


async def test_invalid_name_pattern_returns_400(asgi_app):
    """POST a name with uppercase letters (invalid pattern) and verify HTTP 400."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["UPPERCASE"]},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


async def test_invalid_name_pattern_returns_error_body(asgi_app):
    """POST an invalid name and verify the error body structure."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/skills",
            json={"names": ["UPPERCASE"]},
        )

    body = response.json()
    assert "error" in body, (
        f"Expected 'error' key in response body, got {body}"
    )


# ===========================================================================
# POST /bundle/mcp
# ===========================================================================


# ---------------------------------------------------------------------------
# Valid request
# ---------------------------------------------------------------------------


async def test_mcp_valid_request_returns_200(asgi_app):
    """POST a single valid MCP name and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["context7"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_mcp_valid_request_returns_tar_gz(asgi_app):
    """POST a single valid MCP name and verify the archive contains its YAML file."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["context7"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "context7.yaml" in names, (
        f"Expected context7.yaml in archive, got {names}"
    )


# ---------------------------------------------------------------------------
# Multiple valid names
# ---------------------------------------------------------------------------


async def test_mcp_multiple_valid_names_returns_200(asgi_app):
    """POST two valid MCP names and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["context7", "playwright"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_mcp_multiple_valid_names_contains_all(asgi_app):
    """POST two valid MCP names and verify both YAML files are in the archive."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["context7", "playwright"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "context7.yaml" in names, (
        f"Expected context7.yaml in archive, got {names}"
    )
    assert "playwright.yaml" in names, (
        f"Expected playwright.yaml in archive, got {names}"
    )


# ---------------------------------------------------------------------------
# Partial matches
# ---------------------------------------------------------------------------


async def test_mcp_partial_matches_returns_200(asgi_app):
    """POST a mix of existing and nonexistent MCP names and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["context7", "nonexistent-tool"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_mcp_partial_matches_contains_only_existing(asgi_app):
    """POST a mix of existing and nonexistent MCP names; archive contains only the existing one."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["context7", "nonexistent-tool"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "context7.yaml" in names, (
        f"Expected context7.yaml in archive, got {names}"
    )
    assert "nonexistent-tool.yaml" not in names, (
        f"Did not expect nonexistent-tool.yaml in archive, got {names}"
    )


# ---------------------------------------------------------------------------
# Empty names list
# ---------------------------------------------------------------------------


async def test_mcp_empty_names_returns_400(asgi_app):
    """POST an empty MCP names list and verify HTTP 400."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": []},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# All not-found
# ---------------------------------------------------------------------------


async def test_mcp_all_not_found_returns_200(asgi_app):
    """POST MCP names that do not match any config and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["does-not-exist"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_mcp_all_not_found_returns_empty_archive(asgi_app):
    """POST MCP names that do not match any config and verify the archive is empty."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/mcp",
            json={"names": ["does-not-exist"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        members = tar.getmembers()

    assert len(members) == 0, (
        f"Expected empty archive, got {len(members)} members: {[m.name for m in members]}"
    )


# ===========================================================================
# POST /bundle/agents
# ===========================================================================


# ---------------------------------------------------------------------------
# Valid request
# ---------------------------------------------------------------------------


async def test_agent_valid_request_returns_200(asgi_app):
    """POST a single valid agent name and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": ["test-agent"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_agent_valid_request_returns_tar_gz(asgi_app):
    """POST a single valid agent name and verify the archive contains its .md file."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": ["test-agent"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "test-agent.md" in names, (
        f"Expected test-agent.md in archive, got {names}"
    )


# ---------------------------------------------------------------------------
# Partial matches
# ---------------------------------------------------------------------------


async def test_agent_partial_matches_returns_200(asgi_app):
    """POST a mix of existing and nonexistent agent names and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": ["test-agent", "nonexistent-agent"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_agent_partial_matches_contains_only_existing(asgi_app):
    """POST a mix of existing and nonexistent agent names; archive contains only the existing one."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": ["test-agent", "nonexistent-agent"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "test-agent.md" in names, (
        f"Expected test-agent.md in archive, got {names}"
    )
    assert "nonexistent-agent.md" not in names, (
        f"Did not expect nonexistent-agent.md in archive, got {names}"
    )


# ---------------------------------------------------------------------------
# All not-found
# ---------------------------------------------------------------------------


async def test_agent_all_not_found_returns_200(asgi_app):
    """POST agent names that do not match any agent and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": ["does-not-exist"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_agent_all_not_found_returns_empty_archive(asgi_app):
    """POST agent names that do not match any agent and verify the archive is empty."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": ["does-not-exist"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        members = tar.getmembers()

    assert len(members) == 0, (
        f"Expected empty archive, got {len(members)} members: {[m.name for m in members]}"
    )


# ---------------------------------------------------------------------------
# Empty names list
# ---------------------------------------------------------------------------


async def test_agent_empty_names_returns_400(asgi_app):
    """POST an empty agent names list and verify HTTP 400."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": []},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Names exceeding limit
# ---------------------------------------------------------------------------


async def test_agent_too_many_names_returns_400(asgi_app):
    """POST 21 agent names (exceeding the limit of 20) and verify HTTP 400."""
    names = [f"agent-{i}" for i in range(21)]
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": names},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Invalid name pattern
# ---------------------------------------------------------------------------


async def test_agent_invalid_name_pattern_returns_400(asgi_app):
    """POST an agent name with uppercase letters (invalid pattern) and verify HTTP 400."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/agents",
            json={"names": ["UPPERCASE"]},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )
