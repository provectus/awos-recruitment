---
name: FastMCP Server Development
description: This skill should be used when the user asks to "create an MCP server", "build an MCP tool", "add an MCP resource", "define MCP prompts", "set up FastMCP", "run an MCP server", "expose tools via MCP", "mount MCP sub-servers", "configure MCP transport", "add authentication to MCP", "test an MCP server", "use the MCP client", or when writing any Python code that uses the fastmcp package. Provides up-to-date FastMCP API patterns for tools, resources, prompts, server composition, authentication, and deployment.
version: 0.1.0
---

# FastMCP Server Development

FastMCP is a Python framework for building Model Context Protocol (MCP) servers. It provides a decorator-based API for exposing tools, resources, and prompts to AI assistants. This skill covers the core API for building production-ready MCP servers.

## Server Initialization

```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="MyServer",
    instructions="A helpful server for data processing",
    version="1.0.0",
)
```

- `name` — display name for the server.
- `instructions` — system-level guidance for AI assistants connecting to this server.
- `version` — semantic version string.

## Tools

Tools are functions that AI assistants can invoke. Decorate with `@mcp.tool`.

### Basic tool

```python
@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b
```

FastMCP auto-generates the JSON schema from the function signature and docstring. The docstring becomes the tool description shown to the AI.

### Async tool

```python
@mcp.tool
async def fetch_data(url: str) -> dict:
    """Fetch JSON data from a URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### Custom name and description

```python
@mcp.tool(name="multiply", description="Multiply two numbers")
async def multiply_numbers(x: float, y: float) -> float:
    return x * y
```

### Structured input with Pydantic

```python
from pydantic import BaseModel

class SearchQuery(BaseModel):
    query: str
    max_results: int = 10
    include_metadata: bool = False

@mcp.tool
def search(params: SearchQuery) -> list[dict]:
    """Search with structured parameters."""
    return [{"result": f"Found for: {params.query}"}]
```

Use Pydantic models when a tool has more than 3-4 parameters or when validation is needed.

### Context object

The `Context` parameter provides logging, progress reporting, and access to lifespan resources:

```python
from fastmcp.server.context import Context

@mcp.tool
async def process_files(file_paths: list[str], ctx: Context) -> dict:
    """Process multiple files with progress reporting."""
    total = len(file_paths)
    await ctx.info(f"Starting to process {total} files")

    for i, path in enumerate(file_paths):
        await ctx.report_progress(i, total, f"Processing {path}")
        try:
            # process file...
            pass
        except Exception as e:
            await ctx.error(f"Failed to process {path}: {e}")

    await ctx.report_progress(total, total, "Complete")
    return {"processed": total}
```

Context methods:
- `ctx.info(msg)`, `ctx.debug(msg)`, `ctx.warning(msg)`, `ctx.error(msg)` — structured logging.
- `ctx.report_progress(current, total, message)` — progress updates.
- `ctx.lifespan_context` — dict of resources from the lifespan handler.

Add `ctx: Context` as any parameter — FastMCP injects it automatically (it is not exposed to the AI).

## Resources

Resources expose data that AI assistants can read. Decorate with `@mcp.resource`.

### Static resource

```python
@mcp.resource("config://settings")
def get_settings() -> str:
    """Return application settings."""
    return "debug=true\nlog_level=INFO"
```

### JSON resource

```python
@mcp.resource("data://report", mime_type="application/json")
def get_report() -> dict:
    """Return JSON data (automatically serialized)."""
    return {"users": 150, "active": 42}
```

### Dynamic resource template

Use `{parameter}` in the URI for parameterized resources:

```python
@mcp.resource("users://{user_id}/profile")
async def get_user_profile(user_id: str) -> dict:
    """Fetch user profile by ID."""
    return {"id": user_id, "name": f"User {user_id}"}
```

The AI sees a URI template and can fill in the parameter to read specific resources.

## Prompts

Prompts are reusable templates that guide AI interactions. Decorate with `@mcp.prompt`.

### Simple prompt

```python
@mcp.prompt
def greeting() -> str:
    """A friendly greeting prompt."""
    return "Hello! How can I help you today?"
```

### Parameterized prompt

```python
@mcp.prompt
def analyze_code(language: str, code: str) -> str:
    """Generate a code analysis prompt."""
    return f"Please analyze this {language} code and suggest improvements:\n\n```{language}\n{code}\n```"
```

## Running the Server

### STDIO transport (default)

```python
if __name__ == "__main__":
    mcp.run()
```

STDIO is the default transport. Use for local integrations (e.g., Claude Desktop).

### HTTP transport (Streamable HTTP)

```python
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
```

Use HTTP for remote/deployed servers. Clients connect to `http://host:port/mcp`.

## Server Composition

Mount sub-servers to organize a large server into logical modules:

```python
math_server = FastMCP("MathServer")
text_server = FastMCP("TextServer")

@math_server.tool
def add(a: int, b: int) -> int:
    return a + b

@text_server.tool
def uppercase(text: str) -> str:
    return text.upper()

# Main server mounts sub-servers
main = FastMCP("MainServer")
main.mount(math_server, namespace="math")   # tools: math_add
main.mount(text_server)                      # tools: uppercase (no prefix)
```

- `namespace` — optional prefix added to all tool/resource names from the sub-server.
- Keeps each module independently testable.

## Common Patterns Quick Reference

| Pattern | Approach |
|---|---|
| Simple function → tool | `@mcp.tool` on a typed function |
| Complex input | Pydantic model as parameter |
| Logging in tools | Add `ctx: Context` parameter |
| Read-only data | `@mcp.resource` with URI |
| Parameterized data | `@mcp.resource("scheme://{param}")` |
| Reusable prompts | `@mcp.prompt` with parameters |
| Modular server | `main.mount(sub_server, namespace="ns")` |
| Shared resources (DB, HTTP) | Lifespan handler + `ctx.lifespan_context` |
| Auth | `JWTAuthProvider` or `OAuth2ProxyProvider` |

## Key Rules

1. **Always type-annotate** tool parameters and return types — FastMCP generates the schema from them.
2. **Write clear docstrings** — the docstring becomes the tool/resource/prompt description visible to the AI.
3. **Use `ctx: Context`** for logging and progress — do not use `print()`.
4. **Prefer Pydantic models** for tools with 4+ parameters or when input validation is needed.
5. **Use `namespace`** when mounting sub-servers to avoid tool name collisions.
6. **Choose the right transport** — STDIO for local, HTTP for remote/deployed servers.

## Additional Resources

### Reference Files

For detailed API documentation and advanced patterns, consult:
- **`references/api-reference.md`** — Tool decorator options, resource MIME types, prompt patterns, Context API, authentication (JWT/OAuth2), server configuration
- **`references/patterns.md`** — Server composition, lifespan management, OpenAPI/FastAPI import, proxy servers, dependencies, error handling, deployment
