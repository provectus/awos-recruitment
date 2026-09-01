import dataclasses

import httpx
import pytest
from fastmcp import Client

import awos_recruitment_mcp.server as server_module


@pytest.fixture
async def mcp_client():
    async with Client(server_module.mcp) as client:
        yield client


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


@pytest.fixture
def hook_registry(tmp_path):
    """A throwaway registry holding one complete hook, ``sample-gate``.

    The real registry ships no hooks, so the hook bundle contract is pinned
    against a synthetic one: a valid HOOK.md plus an executable ``<name>.sh``
    entrypoint. Use with ``client_factory(hook_registry)``.
    """
    hook = tmp_path / "hooks" / "sample-gate"
    hook.mkdir(parents=True)
    (hook / "HOOK.md").write_text(
        "---\nname: sample-gate\ndescription: d\nhooks:\n  - event: PreToolUse\n---\nbody\n"
    )
    entry = hook / "sample-gate.sh"
    entry.write_text("#!/bin/sh\nexit 0\n")
    entry.chmod(0o755)
    return tmp_path
