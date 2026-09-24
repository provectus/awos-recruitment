# FastMCP API Reference

## Contents

- [FastMCP Constructor](#fastmcp-constructor) — constructor parameters
- [Tool Decorator](#tool-decorator) — options, parameter types, sync vs async
- [Resource Decorator](#resource-decorator) — static URIs, MIME types, templates
- [Prompt Decorator](#prompt-decorator) — simple, parameterized, multi-message
- [Context Object](#context-object) — logging, progress reporting, lifespan resources
- [Authentication](#authentication) — JWT verification, per-tool authorization, OAuth providers
- [Server Configuration](#server-configuration) — transports, `fastmcp.json`
- [Client](#client) — connecting, in-process testing, client methods

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
        Message(
            role="user",
            content=(
                "Act as a debugging expert. "
                f"Help me debug this error:\n{error}"
            ),
        ),
        Message(role="assistant", content="What have you tried so far?"),
    ]
```

`Message.role` accepts only `"user"` or `"assistant"` — MCP prompts have no system
role, and passing `role="system"` raises a `pydantic.ValidationError`. Put any
"act as an expert" framing in the first user message, or in the server's
`instructions` if it should apply to every interaction.

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
await ctx.report_progress(progress=5, total=10, message="Processing...")
```

The first parameter is named `progress` (`report_progress(progress, total=None,
message=None)`); `current=` is not accepted.

### Lifespan resources

```python
http_client = ctx.lifespan_context["http_client"]
db = ctx.lifespan_context["db"]
```

Access shared resources initialized during server startup. The lifespan handler
that populates this dict is an `asynccontextmanager` passed to the constructor:

```python
@asynccontextmanager
async def app_lifespan(server: FastMCP):
    http_client = httpx.AsyncClient(timeout=30.0)
    yield {"http_client": http_client}   # becomes ctx.lifespan_context
    await http_client.aclose()

mcp = FastMCP("MyServer", lifespan=app_lifespan)
```

For the full pattern — database pools, cleanup ordering, and when to prefer
lifespan over per-tool connections — use the Lifespan Management reference
listed in SKILL.md.

## Authentication

### JWT verification

```python
from fastmcp.server.auth import JWTVerifier

jwt_auth = JWTVerifier(
    jwks_uri="https://your-domain.auth0.com/.well-known/jwks.json",
    issuer="https://your-domain.auth0.com/",
    audience="your-api-audience",
    required_scopes=["read:data"],       # rejected server-wide if absent
)

mcp = FastMCP("SecureServer", auth=jwt_auth)
```

`JWTVerifier` validates a bearer token the client already holds. Pass
`public_key=` instead of `jwks_uri=` for a static key. For local experiments,
`StaticTokenVerifier` and `DebugTokenVerifier` accept fixed tokens — never use
them in production.

### Per-tool authorization

`@mcp.tool(auth=...)` takes an `AuthCheck` — a callable receiving an
`AuthContext` and returning a bool (sync or async), or a list of them. The
built-in `require_scopes` covers the common case:

```python
from fastmcp.server.auth import require_scopes

@mcp.tool(auth=require_scopes("admin"))
def admin_only() -> str:
    """Only callable by a token carrying the `admin` scope."""
    return "admin data"
```

For anything scopes cannot express, write the check yourself. `ctx.token` is an
`AccessToken` model (or `None` when unauthenticated) — read `.scopes` for OAuth
scopes and `.claims` for the decoded JWT payload. It is a Pydantic model, not a
dict, so use attribute access:

```python
from fastmcp.server.auth import AuthContext

def is_admin(ctx: AuthContext) -> bool:
    token = ctx.token
    return token is not None and "admin" in token.claims.get("roles", [])

@mcp.tool(auth=is_admin)
def admin_claim_only() -> str:
    """Only callable by a token whose `roles` claim contains `admin`."""
    return "admin data"
```

`AccessToken` fields: `token`, `client_id`, `scopes`, `expires_at`, `resource`,
`subject`, `claims`. `AuthContext` carries `token` plus `component` (the tool,
resource or prompt being accessed).

### OAuth providers

FastMCP ships per-vendor providers under `fastmcp.server.auth.providers.*` —
`github`, `google`, `azure`, `auth0`, `aws`, `clerk`, `descope`, `discord`,
`huggingface`, `keycloak`, `oci`, `propelauth`, `scalekit`, `supabase`,
`workos`. Each class is named `<Vendor>Provider`:

```python
from fastmcp.server.auth.providers.github import GitHubProvider

github_auth = GitHubProvider(
    client_id="your-client-id",
    client_secret="your-client-secret",
    base_url="https://your-server.example.com",   # required: this server's public URL
)

mcp = FastMCP("GitHubServer", auth=github_auth)
```

For an identity provider with no bundled class, use `OIDCProxy` (discovers
endpoints from the well-known config) or `OAuthProxy` (endpoints supplied
explicitly):

```python
from fastmcp.server.auth import OIDCProxy

oidc_auth = OIDCProxy(
    config_url="https://your-domain.auth0.com/.well-known/openid-configuration",
    client_id="your-client-id",
    client_secret="your-client-secret",
    base_url="https://your-server.example.com",
)
```

`OIDCProxy` fetches the discovery document when it is constructed, so the
`config_url` must be reachable at import time.

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
  "$schema": "https://gofastmcp.com/public/schemas/fastmcp.json/v1.json",
  "source": {
    "path": "server.py"
  },
  "environment": {
    "type": "uv",
    "dependencies": ["httpx", "pydantic"]
  }
}
```

`source` is the only required key — a config without it is rejected before the
server starts. Dependencies are installed in an isolated UV environment.

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
