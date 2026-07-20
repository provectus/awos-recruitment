"""Tests for the POST /bundle/skills, /bundle/mcp, /bundle/agents, and /bundle/hooks endpoints."""

from __future__ import annotations

import dataclasses
import io
import tarfile
from unittest.mock import patch

import httpx
import pytest
import awos_recruitment_mcp.server as server_module
from awos_recruitment_mcp.server import mcp


@pytest.fixture
def asgi_app():
    """Return the ASGI app from the FastMCP server for in-process HTTP testing."""
    return mcp.http_app()


@pytest.fixture
async def client(asgi_app):
    """An httpx.AsyncClient wired to the default (real registry) FastMCP app."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def client_factory(monkeypatch):
    """Build an httpx.AsyncClient against the FastMCP app rooted at a custom registry_path.

    The route handlers read the module-level ``config`` global at request time,
    so monkeypatching ``server_module.config`` to a copy with a different
    ``registry_path`` (via ``dataclasses.replace`` — ``Config`` is frozen) is
    enough to redirect every ``/bundle/*`` route without touching real registry
    data. Returns a callable that yields an async-context-manager client.
    """

    def _make_client(registry_path) -> httpx.AsyncClient:
        patched_config = dataclasses.replace(
            server_module.config, registry_path=str(registry_path)
        )
        monkeypatch.setattr(server_module, "config", patched_config)
        app = server_module.mcp.http_app()
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    return _make_client


def tar_member_names(content: bytes) -> list[str]:
    """Extract member names from raw gzip-compressed tar bytes."""
    buf = io.BytesIO(content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        return tar.getnames()


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
            json={"names": ["testing-expert"]},
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
            json={"names": ["testing-expert"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "testing-expert.md" in names, (
        f"Expected testing-expert.md in archive, got {names}"
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
            json={"names": ["testing-expert", "nonexistent-agent"]},
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
            json={"names": ["testing-expert", "nonexistent-agent"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "testing-expert.md" in names, (
        f"Expected testing-expert.md in archive, got {names}"
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


# ===========================================================================
# POST /bundle/hooks
# ===========================================================================


# ---------------------------------------------------------------------------
# Valid request
# ---------------------------------------------------------------------------


async def test_hook_valid_request_returns_200(asgi_app):
    """POST a single valid hook name and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": ["docs-that-work-gate"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_hook_valid_request_returns_tar_gz(asgi_app):
    """POST a single valid hook name and verify the archive contains HOOK.md and the entrypoint."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": ["docs-that-work-gate"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert "docs-that-work-gate/HOOK.md" in names, (
        f"Expected HOOK.md in archive, got {names}"
    )
    assert "docs-that-work-gate/docs-that-work-gate.sh" in names, (
        f"Expected entrypoint .sh in archive, got {names}"
    )


async def test_hook_entrypoint_carries_exec_bit(asgi_app):
    """The bundled entrypoint .sh tar member must retain its executable bit."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": ["docs-that-work-gate"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        member = tar.getmember("docs-that-work-gate/docs-that-work-gate.sh")

    assert member.mode & 0o111, (
        f"Expected entrypoint to carry the exec bit, got mode {oct(member.mode)}"
    )


# ---------------------------------------------------------------------------
# Partial matches
# ---------------------------------------------------------------------------


async def test_hook_partial_matches_returns_200(asgi_app):
    """POST a mix of existing and nonexistent hook names and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": ["docs-that-work-gate", "nonexistent-hook"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_hook_partial_matches_contains_only_existing(asgi_app):
    """POST a mix of existing and nonexistent hook names; archive contains only the existing one."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": ["docs-that-work-gate", "nonexistent-hook"]},
        )

    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()

    assert any(n.startswith("docs-that-work-gate/") for n in names), (
        f"Expected docs-that-work-gate entries in archive, got {names}"
    )
    assert not any(n.startswith("nonexistent-hook/") for n in names), (
        f"Did not expect nonexistent-hook entries in archive, got {names}"
    )


# ---------------------------------------------------------------------------
# All not-found
# ---------------------------------------------------------------------------


async def test_hook_all_not_found_returns_200(asgi_app):
    """POST hook names that do not match any hook and verify HTTP 200."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": ["does-not-exist"]},
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}"
    )


async def test_hook_all_not_found_returns_empty_archive(asgi_app):
    """POST hook names that do not match any hook and verify the archive is empty."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
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


async def test_hook_empty_names_returns_400(asgi_app):
    """POST an empty hook names list and verify HTTP 400."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": []},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Names exceeding limit
# ---------------------------------------------------------------------------


async def test_hook_too_many_names_returns_400(asgi_app):
    """POST 21 hook names (exceeding the limit of 20) and verify HTTP 400."""
    names = [f"hook-{i}" for i in range(21)]
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": names},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Invalid name pattern
# ---------------------------------------------------------------------------


async def test_hook_invalid_name_pattern_returns_400(asgi_app):
    """POST a hook name with uppercase letters (invalid pattern) and verify HTTP 400."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/bundle/hooks",
            json={"names": ["UPPERCASE"]},
        )

    assert response.status_code == 400, (
        f"Expected HTTP 400, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Defense-in-depth: entrypoint-less hooks, scripts/ filtering, traversal names
# ---------------------------------------------------------------------------


@patch("awos_recruitment_mcp.server.track_install")
async def test_bundle_hooks_skips_entrypointless_dir(
    mock_track_install, tmp_path, client_factory
):
    """A hook dir without its `<name>.sh` entrypoint must ship nothing at all.

    Shipping HOOK.md alone would let the CLI report the hook "installed"
    while pointing settings.json at a script that was never bundled. The
    same rule applies to telemetry: a hook that ships nothing was not
    installed, so track_install must not be called for it.
    """
    hooks = tmp_path / "hooks" / "broken-hook"
    hooks.mkdir(parents=True)
    (hooks / "HOOK.md").write_text(
        "---\nname: broken-hook\ndescription: d\nhooks:\n  - event: PreToolUse\n---\nbody\n"
    )

    async with client_factory(tmp_path) as client:
        response = await client.post("/bundle/hooks", json={"names": ["broken-hook"]})

    names = tar_member_names(response.content)
    assert names == [], "A hook without its entrypoint must not ship at all"
    mock_track_install.assert_not_called()


async def test_bundle_hooks_scripts_filtering(tmp_path, client_factory):
    """The scripts/ bundling branch keeps allowed .sh helpers, drops the rest."""
    hook = tmp_path / "hooks" / "my-hook"
    scripts = hook / "scripts"
    scripts.mkdir(parents=True)
    (hook / "HOOK.md").write_text(
        "---\nname: my-hook\ndescription: d\nhooks:\n  - event: PreToolUse\n---\nbody\n"
    )
    entry = hook / "my-hook.sh"
    entry.write_text("#!/bin/sh\nexit 0\n")
    entry.chmod(0o755)
    (scripts / "helper.sh").write_text("#!/bin/sh\n")
    (scripts / ".hidden").write_text("x")
    (scripts / "bad.rb").write_text("x")

    async with client_factory(tmp_path) as client:
        response = await client.post("/bundle/hooks", json={"names": ["my-hook"]})

    names = tar_member_names(response.content)
    assert "my-hook/scripts/helper.sh" in names
    assert not any(".hidden" in n or "bad.rb" in n for n in names)


@pytest.mark.parametrize("bad", [["../agents"], [".."], ["a/b"], ["/etc"]])
async def test_bundle_hooks_traversal_names_rejected(client, bad):
    """Path-traversal-shaped names are rejected by BundleRequest's name pattern.

    This is expected to already pass — it pins the existing
    `^[a-z0-9-]{1,64}$` regex on `BundleRequest.names`, not new behavior.
    """
    response = await client.post("/bundle/hooks", json={"names": bad})
    assert response.status_code == 400
