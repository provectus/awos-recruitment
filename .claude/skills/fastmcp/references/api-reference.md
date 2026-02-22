# FastMCP API Reference

## FastMCP Constructor

```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="MyServer",                          # display name
    instructions="Server-level guidance",      # system instructions for AI
    version="1.0.0",                           # semantic version
    lifespan=lifespan_handler,                 # async context manager for startup/shutdown
    auth=auth_provider,                        # authentication provider
)
```

All parameters are optional. `name` defaults to `"FastMCP"` if omitted.

## Tool Decorator

### Basic usage

```python
@mcp.tool
def my_tool(param: str) -> str:
    """Tool description shown to the AI."""
    return result
```

### With options

```python
@mcp.tool(
    name="custom_name",                 # override function name
    description="Custom description",    # override docstring
    output_schema={                      # custom JSON schema for output
        "type": "object",
        "properties": {"status": {"type": "string"}},
    },
)
def my_tool(param: str) -> dict:
    return {"status": "ok"}
```

### Parameter types

FastMCP supports all JSON-serializable Python types:

| Python Type | JSON Schema |
|---|---|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list[T]` | `array` |
| `dict[str, T]` | `object` |
| `T \| None` | nullable |
| `BaseModel` subclass | object with properties |

Default values become optional parameters in the schema.

### Sync vs async

Both sync and async functions are supported. Use async for I/O-bound operations:

```python
@mcp.tool
def sync_tool(x: int) -> int:
    return x * 2

@mcp.tool
async def async_tool(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        return (await client.get(url)).json()
```

## Resource Decorator

### Static URI

```python
@mcp.resource("scheme://path")
def get_data() -> str:
    """Description of the resource."""
    return "data"
```

### With MIME type

```python
@mcp.resource("data://report", mime_type="application/json")
def get_report() -> dict:
    return {"key": "value"}
```

Common MIME types:
- `text/plain` — default for strings
- `application/json` — for dicts and lists (auto-serialized)
- `image/png`, `image/jpeg` — for binary image data
- `application/octet-stream` — for arbitrary binary

### Dynamic template

```python
@mcp.resource("items://{item_id}")
def get_item(item_id: str) -> dict:
    return {"id": item_id, "name": f"Item {item_id}"}
```

Multiple parameters:

```python
@mcp.resource("repos://{owner}/{repo}/readme")
def get_readme(owner: str, repo: str) -> str:
    return f"README for {owner}/{repo}"
```

### ResourceResult for advanced responses

```python
from fastmcp.resources import ResourceResult, ResourceContent

@mcp.resource("users://{user_id}/profile")
async def get_profile(user_id: str) -> ResourceResult:
    data = await fetch_user(user_id)
    return ResourceResult(
        contents=[ResourceContent(data, mime_type="application/json")],
        meta={"cached": False},
    )
```

## Prompt Decorator

### Basic prompt

```python
@mcp.prompt
def greeting() -> str:
    """A friendly greeting."""
    return "Hello! How can I help?"
```

### With parameters

```python
@mcp.prompt
def analyze_code(language: str, code: str) -> str:
    """Generate a code analysis prompt."""
    return f"Analyze this {language} code:\n```{language}\n{code}\n```"
```

### Multi-message prompt

```python
from fastmcp.prompts import Message

@mcp.prompt
def debug_session(error: str) -> list[Message]:
    """Start a debugging session."""
    return [
        Message(role="system", content="Act as a debugging expert."),
        Message(role="user", content=f"Help me debug this error:\n{error}"),
    ]
```

## Context Object

The `Context` object is injected by adding a `ctx: Context` parameter to any tool. It is not exposed to the AI.

```python
from fastmcp.server.context import Context
```

### Logging

```python
await ctx.info("Informational message")
await ctx.debug("Debug-level detail")
await ctx.warning("Warning message")
await ctx.error("Error message")
```

### Progress reporting

```python
await ctx.report_progress(current=5, total=10, message="Processing...")
```

### Lifespan resources

```python
http_client = ctx.lifespan_context["http_client"]
db = ctx.lifespan_context["db"]
```

Access shared resources initialized during server startup (see Lifespan in patterns.md).

## Authentication

### JWT authentication

```python
from fastmcp.server.auth import JWTAuthProvider

jwt_auth = JWTAuthProvider(
    jwks_uri="https://your-domain.auth0.com/.well-known/jwks.json",
    issuer="https://your-domain.auth0.com/",
    audience="your-api-audience",
)

mcp = FastMCP("SecureServer", auth=jwt_auth)
```

### Per-tool authorization

```python
from fastmcp.server.auth import AuthContext

async def require_admin(ctx: AuthContext) -> bool:
    token = ctx.token
    return token is not None and "admin" in token.get("roles", [])

@mcp.tool(auth=require_admin)
def admin_only() -> str:
    """Only accessible to admin users."""
    return "admin data"
```

### OAuth2 provider

```python
from fastmcp.server.auth.providers import GitHubOAuthProvider

github_auth = GitHubOAuthProvider(
    client_id="your-client-id",
    client_secret="your-client-secret",
)

mcp = FastMCP("GitHubServer", auth=github_auth)
```

## Server Configuration

### Transport options

```python
# STDIO — default, for local integrations
mcp.run()
mcp.run(transport="stdio")

# HTTP — Streamable HTTP, for remote servers
mcp.run(transport="http", host="0.0.0.0", port=8000)
```

### Dependencies via fastmcp.json

Place `fastmcp.json` alongside the server script:

```json
{
  "environment": {
    "dependencies": ["httpx", "pydantic"]
  }
}
```

Dependencies are installed in an isolated UV environment before the server starts.

## Client

### Connecting to servers

```python
from fastmcp.client import Client

# Remote HTTP server
async with Client("http://localhost:8000/mcp") as client:
    tools = await client.list_tools()
    result = await client.call_tool("add", {"a": 5, "b": 3})
    print(result.data)

# In-process server (for testing)
async with Client(mcp) as client:
    result = await client.call_tool("add", {"a": 1, "b": 2})
```

### Client methods

| Method | Description |
|---|---|
| `list_tools()` | List all available tools |
| `call_tool(name, args)` | Invoke a tool |
| `list_resources()` | List all resources |
| `read_resource(uri)` | Read a resource by URI |
| `list_prompts()` | List all prompts |
| `get_prompt(name, args)` | Render a prompt |
