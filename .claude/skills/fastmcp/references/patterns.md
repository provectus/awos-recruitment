# FastMCP Architecture Patterns

## Server Composition

Split a large server into logical sub-servers mounted on a main server.

### Basic mounting

```python
from fastmcp import FastMCP

math_server = FastMCP("MathServer")
text_server = FastMCP("TextServer")

@math_server.tool
def add(a: int, b: int) -> int:
    return a + b

@text_server.tool
def uppercase(text: str) -> str:
    return text.upper()

main = FastMCP("MainServer")
main.mount(math_server, namespace="math")   # tool: math_add
main.mount(text_server)                      # tool: uppercase
```

### Custom tool name mapping

```python
main.mount(
    math_server,
    namespace="calc",
    tool_names={"add": "sum", "multiply": "product"},  # calc_sum, calc_product
)
```

### When to use composition

- Server has 10+ tools — split by domain.
- Multiple developers work on different modules.
- Sub-servers need independent testing.
- Different auth requirements per module.

## Lifespan Management

Use a lifespan handler to manage shared resources (HTTP clients, database pools, caches) that are created at startup and cleaned up at shutdown.

```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from fastmcp.server.context import Context
import httpx

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Initialize and clean up shared resources."""
    http_client = httpx.AsyncClient(timeout=30.0)
    db_pool = await create_db_pool()

    yield {
        "http_client": http_client,
        "db": db_pool,
    }

    await http_client.aclose()
    await db_pool.close()

mcp = FastMCP("MyServer", lifespan=app_lifespan)

@mcp.tool
async def fetch_url(url: str, ctx: Context) -> dict:
    """Fetch data using the shared HTTP client."""
    client = ctx.lifespan_context["http_client"]
    response = await client.get(url)
    return response.json()
```

### Rules for lifespan

- The handler must be an `asynccontextmanager`.
- `yield` a dict — its contents become `ctx.lifespan_context` in tools.
- Cleanup code goes after `yield`.
- All tools sharing a resource (DB, HTTP client) should use lifespan rather than creating their own connections.

## Proxy Servers

Create a proxy that forwards requests to another server (remote or in-process).

```python
from fastmcp import FastMCP
from fastmcp.server import create_proxy

# Proxy to a remote HTTP server
proxy = create_proxy("http://remote-server.com/mcp", name="RemoteProxy")

# Proxy to a local FastMCP instance
local_server = FastMCP("LocalServer")

@local_server.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"

proxy_to_local = create_proxy(local_server, name="LocalProxy")

# Mount proxies on main server
main = FastMCP("MainServer")
main.mount(proxy, namespace="remote")
main.mount(proxy_to_local, namespace="local")
```

Use proxies to:
- Aggregate multiple remote MCP servers behind a single endpoint.
- Test against a local instance that mirrors production.
- Bridge STDIO-based servers to HTTP.

## OpenAPI / FastAPI Import

Generate MCP servers automatically from existing APIs.

### From OpenAPI spec

```python
import httpx
from fastmcp import FastMCP

openapi_spec = {
    "openapi": "3.0.0",
    "info": {"title": "Pet Store", "version": "1.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "responses": {"200": {"description": "A list of pets"}},
            }
        }
    },
}

client = httpx.AsyncClient(base_url="https://petstore.example.com")
mcp = FastMCP.from_openapi(openapi_spec, client=client, name="PetStoreServer")
```

### From FastAPI app

```python
from fastapi import FastAPI
from fastmcp import FastMCP

app = FastAPI(title="My API")

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"id": user_id, "name": f"User {user_id}"}

mcp = FastMCP.from_fastapi(app, name="UserAPIServer")
```

Each API endpoint becomes an MCP tool. Parameters, types, and descriptions are preserved.

## Error Handling in Tools

### Return errors as values

For expected errors, return a structured response rather than raising:

```python
@mcp.tool
def divide(a: float, b: float) -> dict:
    """Divide two numbers."""
    if b == 0:
        return {"error": "Division by zero"}
    return {"result": a / b}
```

### Raise for unexpected errors

For unexpected failures, let the exception propagate. FastMCP catches it and returns an error to the client:

```python
@mcp.tool
async def fetch_data(url: str) -> dict:
    """Fetch JSON from a URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()  # raises on 4xx/5xx
        return response.json()
```

### Use Context for error logging

```python
@mcp.tool
async def process(data: str, ctx: Context) -> dict:
    """Process data with error logging."""
    try:
        result = parse_and_transform(data)
        return {"status": "success", "result": result}
    except ValueError as e:
        await ctx.error(f"Validation failed: {e}")
        return {"status": "error", "message": str(e)}
```

## Dependencies Management

### fastmcp.json

Place alongside the server script for isolated dependency management:

```json
{
  "environment": {
    "dependencies": ["httpx", "pydantic>=2.0"]
  }
}
```

Dependencies are installed in a UV-managed virtual environment before server start.

### When to use

- Server depends on packages not in the host environment.
- Deploying to environments where manual `pip install` is impractical.
- Ensuring reproducible dependency sets across machines.

## Project Structure

### Simple server (single file)

```
my-mcp-server/
├── server.py
├── fastmcp.json       # dependencies
└── pyproject.toml
```

### Composed server (multi-module)

```
my-mcp-server/
├── src/
│   └── my_server/
│       ├── __init__.py
│       ├── main.py          # FastMCP("Main"), mounts sub-servers
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── search.py    # FastMCP("Search"), search tools
│       │   └── ingest.py    # FastMCP("Ingest"), data ingestion tools
│       └── resources/
│           ├── __init__.py
│           └── data.py      # FastMCP("Data"), data resources
├── fastmcp.json
└── pyproject.toml
```

### Composition in main.py

```python
from fastmcp import FastMCP
from my_server.tools.search import search_server
from my_server.tools.ingest import ingest_server
from my_server.resources.data import data_server

main = FastMCP("MainServer")
main.mount(search_server, namespace="search")
main.mount(ingest_server, namespace="ingest")
main.mount(data_server, namespace="data")

if __name__ == "__main__":
    main.run(transport="http", host="0.0.0.0", port=8000)
```

## Testing

### In-process client testing

```python
from fastmcp.client import Client
import pytest

@pytest.mark.asyncio
async def test_add_tool():
    async with Client(mcp) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        assert result.data == 5
```

### Test sub-servers independently

```python
@pytest.mark.asyncio
async def test_search_server():
    async with Client(search_server) as client:
        tools = await client.list_tools()
        assert any(t.name == "semantic_search" for t in tools)

        result = await client.call_tool("semantic_search", {"query": "test"})
        assert "results" in result.data
```

The `Client` accepts a `FastMCP` instance directly, enabling fast in-process testing without starting an HTTP server.

## Transport Selection Guide

| Transport | Use case | Client connection |
|---|---|---|
| `stdio` (default) | Local integrations, Claude Desktop | Pipe stdin/stdout |
| `http` | Remote servers, production deployments | `http://host:port/mcp` |
| `sse` | Legacy clients needing Server-Sent Events | `http://host:port/sse` |

For new deployments, prefer `http` (Streamable HTTP) — it is the modern MCP standard and works behind standard load balancers.
