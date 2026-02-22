# Tasks: MCP Server & Protocol Integration

---

## Slice 1: Bare MCP server starts and accepts connections

The smallest proof of life — a FastMCP server that starts, listens on Streamable HTTP, and completes the MCP handshake with a client.

- [ ] Initialize the Python project with `uv init`, create `pyproject.toml` with dependencies (`fastmcp`, `python-dotenv`), and dev dependencies (`pytest`, `pytest-asyncio`). Create the `src/awos_recruitment_mcp/` package structure with `__init__.py` and `py.typed`. **[Agent: python-expert]**
- [ ] Create `config.py` — frozen dataclass loading `AWOS_HOST` (default `0.0.0.0`), `AWOS_PORT` (default `8000`), `AWOS_VERSION` (default `0.1.0`) from environment variables with `.env` file support via `python-dotenv`. Create `.env.example` documenting the variables. **[Agent: python-expert]**
- [ ] Create `server.py` — instantiate `FastMCP` with name `"AWOS Recruitment"`, version from config, and instructions string. Create `__main__.py` — calls `mcp.run(transport="http", host=config.host, port=config.port)`. **[Agent: python-expert]**
- [ ] Verify: start the server with `python -m awos_recruitment_mcp`, confirm it starts without errors. Write a pytest integration test that connects an MCP `Client` to the server and completes the initialization handshake. Run `pytest` and confirm it passes. **[Agent: qa-tester]**
- [ ] Git commit: "Add MCP server scaffold with Streamable HTTP transport"

---

## Slice 2: Health check endpoint

Add the `GET /health` custom HTTP route so the server's liveness can be verified independently of MCP.

- [ ] Add a `GET /health` custom route to `server.py` using `@mcp.custom_route`. It returns a JSON response `{"status": "ok", "version": "<version>"}` with HTTP 200. **[Agent: python-expert]**
- [ ] Verify: start the server, `curl http://localhost:8000/health` returns 200 with the expected JSON body. Write a pytest test for the health check endpoint. Run `pytest` and confirm all tests pass (including Slice 1 tests). **[Agent: qa-tester]**
- [ ] Git commit: "Add health check endpoint"

---

## Slice 3: `search_capabilities` MCP tool with mock data

Wire up the MCP tool so a client can discover and invoke it, receiving mock capability results.

- [ ] Create `models/capability.py` with a `CapabilityResult` Pydantic model (`name: str`, `description: str`, `tags: list[str]`). **[Agent: python-expert]**
- [ ] Create `tools/search.py` — define a hardcoded list of 3–5 mock `CapabilityResult` instances. Implement the `search_capabilities` tool decorated with `@mcp.tool`, accepting `query: str`, returning `list[dict]` (serialized from mock data, sliced to max 10). Import the tools module in `server.py` to trigger registration. **[Agent: python-expert]**
- [ ] Verify: write pytest tests that confirm: (1) `search_capabilities` appears in the tool list, (2) calling it returns a list of results with `name`, `description`, `tags` fields, (3) results are capped at 10, (4) an empty string query returns a successful response. Run `pytest` and confirm all tests pass (including Slice 1 and 2 tests). **[Agent: qa-tester]**
- [ ] Git commit: "Add search_capabilities MCP tool with mock data"
