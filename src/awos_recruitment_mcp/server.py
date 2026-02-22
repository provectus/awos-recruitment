"""FastMCP server instance for AWOS Recruitment.

This module instantiates the `FastMCP` server with project-level metadata.
Import `mcp` from here whenever you need to register tools, resources,
or prompts.
"""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from awos_recruitment_mcp.config import Config

config = Config.from_env()

mcp = FastMCP(
    name="AWOS Recruitment",
    version=config.version,
    instructions=(
        "This server provides AI coding assistants with a discovery engine "
        "for skills, agents, and tools. Use the search_capabilities tool to "
        "find capabilities matching a natural language query."
    ),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Return server health status and version."""
    return JSONResponse({"status": "ok", "version": config.version}, status_code=200)


# Import tool modules AFTER `mcp` is created so they can reference it without
# triggering a circular-import error.
import awos_recruitment_mcp.tools.search  # noqa: E402, F401 — registers MCP tools
