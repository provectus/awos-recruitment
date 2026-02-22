# Technical Specification: MCP Server & Protocol Integration

- **Functional Specification:** `context/spec/001-mcp-server-protocol-integration/functional-spec.md`
- **Status:** Draft
- **Author(s):** AWOS

---

## 1. High-Level Technical Approach

Stand up a Python FastMCP server that runs with Streamable HTTP transport. The server exposes a single MCP tool (`search_capabilities`) returning hardcoded mock data, and a custom HTTP health check endpoint. FastMCP handles all MCP protocol plumbing (handshake, JSON-RPC routing, capability negotiation) automatically — no manual protocol code is needed.

The project uses `uv` for dependency management, `pyproject.toml` as the single source of truth, and a `src/` layout.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. Project Structure

```
src/
└── awos_recruitment_mcp/
    ├── __init__.py            # Package version
    ├── __main__.py            # Entry point: python -m awos_recruitment_mcp
    ├── py.typed               # PEP 561 type marker
    ├── server.py              # FastMCP instance, health check route, tool imports
    ├── config.py              # Config dataclass, loads from env vars / .env
    ├── tools/
    │   ├── __init__.py
    │   └── search.py          # search_capabilities tool + mock data
    └── models/
        ├── __init__.py
        └── capability.py      # CapabilityResult Pydantic model
tests/
├── conftest.py                # Shared fixtures (FastMCP in-process client)
├── test_health.py             # Health check endpoint tests
└── test_search_tool.py        # search_capabilities tool tests
pyproject.toml                 # Project metadata, dependencies, scripts
.env.example                   # Documented env var template
```

### 2.2. Dependencies

| Package | Purpose |
|---|---|
| `fastmcp` | MCP server framework (includes Starlette, uvicorn) |
| `pydantic` | Data validation for tool input/output models (bundled with FastMCP, but listed explicitly) |
| `python-dotenv` | Load `.env` files for local development |
| `pytest` | Testing framework (dev dependency) |
| `pytest-asyncio` | Async test support for FastMCP client tests (dev dependency) |

### 2.3. Configuration

A frozen dataclass in `config.py` with a `from_env()` class method. Loads from environment variables, falling back to defaults. `python-dotenv` loads `.env` at import time.

| Env Variable | Default | Purpose |
|---|---|---|
| `AWOS_HOST` | `"0.0.0.0"` | Server bind address |
| `AWOS_PORT` | `8000` | Server port |
| `AWOS_VERSION` | `"0.1.0"` | Server version (returned in health check and MCP server info) |

An `.env.example` file documents these variables for developers.

### 2.4. Server Setup (`server.py`)

- Create a `FastMCP` instance with `name="AWOS Recruitment"`, `instructions` describing the server's purpose, and `version` from config.
- Register a custom route `GET /health` via `@mcp.custom_route("/health", methods=["GET"])` that returns `{"status": "ok", "version": "<version>"}` as JSON with HTTP 200.
- Import the `tools/` module to trigger tool registration via `@mcp.tool` decorators.

**Endpoints exposed:**

| Method | Path | Type | Purpose |
|---|---|---|---|
| POST | `/mcp` | MCP (Streamable HTTP) | MCP protocol endpoint (automatic) |
| GET | `/health` | HTTP | Health check |

### 2.5. MCP Tool: `search_capabilities` (`tools/search.py`)

- Decorated with `@mcp.tool`.
- Accepts `query: str` parameter.
- Returns `list[dict]` — each dict serialized from a `CapabilityResult` Pydantic model containing `name`, `description`, and `tags`.
- Phase 1: returns a hardcoded list of 3–5 mock capabilities regardless of query, sliced to a max of 10 results.
- The tool's docstring serves as the MCP tool description visible to AI assistants.

### 2.6. Data Model (`models/capability.py`)

A Pydantic `BaseModel`:

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Capability name |
| `description` | `str` | Short description |
| `tags` | `list[str]` | Associated tags |

### 2.7. Entry Point (`__main__.py`)

Calls `mcp.run(transport="http", host=config.host, port=config.port)` to start the server. The server can be run via `python -m awos_recruitment_mcp` or a `pyproject.toml` script alias.

---

## 3. Impact and Risk Analysis

### System Dependencies

- This is the first application code in the repository — no existing systems are affected.
- FastMCP depends on Starlette and uvicorn for the HTTP layer; these are bundled.

### Potential Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| FastMCP API changes in future versions | Tool definitions or transport config may break | Pin `fastmcp` version in `pyproject.toml`; reference official docs for exact API |
| Port conflicts on developer machines | Server fails to start | Configurable via `AWOS_PORT` env var |
| `.env` file accidentally committed | Could leak secrets in future phases | Already covered by `.gitignore`; `.env.example` used as template |

---

## 4. Testing Strategy

- **Framework:** pytest + pytest-asyncio
- **In-process MCP client:** FastMCP provides `async with Client(mcp) as client:` for testing tools without starting an HTTP server. This is the primary test approach.

| Test | Type | Validates |
|---|---|---|
| Health check returns 200 with `status` and `version` | Integration | Acceptance criteria: health check endpoint |
| `search_capabilities` is listed in tools | Unit | Acceptance criteria: tool is discoverable |
| `search_capabilities` returns valid response shape | Unit | Acceptance criteria: `name`, `description`, `tags` fields |
| `search_capabilities` returns max 10 results | Unit | Acceptance criteria: result limit |
| `search_capabilities` with empty string succeeds | Unit | Acceptance criteria: empty query handling |
| MCP client connects and completes handshake | Integration | Acceptance criteria: MCP initialization |
