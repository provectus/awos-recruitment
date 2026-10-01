import httpx
import pytest

from awos_recruitment_mcp.server import mcp

# Protocol versions that still open with an ``initialize`` request. The
# in-process ``mcp_client`` fixture speaks the sessionless 2026-07-28 protocol
# and never sends one, so these are only covered over HTTP below.
LEGACY_PROTOCOL_VERSIONS = ["2025-03-26", "2025-06-18", "2025-11-25"]


async def test_server_initializes(mcp_client):
    """Verify the MCP client connects to the server.

    Successfully entering the async context manager (via the fixture) IS the
    test: it proves the in-process server accepted the connection.
    """
    assert mcp_client.is_connected()


async def test_legacy_initialize_handshake():
    """Verify clients on pre-2026-07-28 protocols can still initialize over HTTP.

    Uses the same transport settings as ``__main__`` so the request takes the
    path deployed clients take.
    """
    app = mcp.http_app(stateless_http=True, json_response=True)
    transport = httpx.ASGITransport(app=app)

    async with app.lifespan(app), httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        for version in LEGACY_PROTOCOL_VERSIONS:
            response = await client.post(
                "/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": version,
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"},
                    },
                },
            )

            assert response.status_code == 200, (
                f"{version}: expected HTTP 200, got {response.status_code}"
            )
            result = response.json()["result"]
            assert result["protocolVersion"] == version, (
                f"{version}: server negotiated {result['protocolVersion']}"
            )
            assert result["serverInfo"]["name"] == "AWOS Recruitment"


async def test_server_info(mcp_client):
    """Verify the server reports the correct name and version."""
    server_info = mcp_client.server_info
    assert server_info is not None, "server_info should be populated after connect"

    assert server_info.name == "AWOS Recruitment", (
        f"Expected server name 'AWOS Recruitment', got '{server_info.name}'"
    )
    assert server_info.version == "0.1.0", (
        f"Expected version '0.1.0', got '{server_info.version}'"
    )
