"""Pydantic models for validating MCP server definition YAML files."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class McpServerConfig(BaseModel):
    """Configuration for a single MCP server transport.

    Uses ``extra="allow"`` because different transport types (stdio, sse, http,
    websocket) may carry transport-specific fields beyond the common ones
    listed here.

    Attributes:
        type: Transport type the server uses.
        command: Executable to launch (relevant for stdio transport).
        args: Arguments passed to *command*.
        env: Environment variables set for the child process.
        url: Endpoint URL (relevant for sse/http/websocket transports).
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["stdio", "sse", "http", "websocket"]
    command: str | None = Field(None)
    args: list[str] | None = Field(None)
    env: dict[str, str] | None = Field(None)
    url: str | None = Field(None)


class McpDefinition(BaseModel):
    """Validated representation of an MCP server definition YAML file.

    Attributes:
        name: Human-readable name for the MCP server.
        description: What the MCP server does.
        config: Mapping of server key to its transport configuration.
                Must contain exactly one entry.
    """

    name: str = Field(..., pattern=r"^[a-z0-9-]{1,64}$")
    description: str = Field(..., min_length=1)
    config: dict[str, McpServerConfig]

    @model_validator(mode="after")
    def _check_single_config_key(self) -> McpDefinition:
        """Ensure ``config`` contains exactly one server entry."""
        num_keys = len(self.config)
        if num_keys != 1:
            raise ValueError(
                f"config must have exactly 1 key, got {num_keys}"
            )
        return self
