# AWOS Recruitment

A zero-setup, intelligent discovery engine for AI coding assistant capabilities — skills, agents, and tools.

AI assistants (like Claude Code) connect to the AWOS Recruitment MCP server to search for and install specialized capabilities matching their developer's needs, without manual setup or dependency management.

## Connect from Claude Code

Add the server to your MCP configuration:

```json
{
  "mcpServers": {
    "awos-recruitment": {
      "type": "url",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## MCP Tools

| Tool | Description |
|---|---|
| `search_capabilities` | Search the capability registry using natural language. Returns ranked results with name, description, and relevance score (0–100). Supports optional `type` filter (`skill`, `agent`, `tool`). |

## Quick Start

```bash
just serve
```

The server starts on `http://0.0.0.0:8000` with:
- **MCP endpoint:** `POST /mcp` (Streamable HTTP)
- **Health check:** `GET /health`

## Documentation

| Document | Description |
|----------|-------------|
| [Development Guide](docs/DEVELOPMENT.md) | Prerequisites, setup, commands, project structure, and AWOS workflow |
| [Contributing to the Registry](docs/CONTRIBUTING.md) | How to add skills and MCP definitions to the capability registry |
| [Philosophy](docs/PHILOSOPHY.md) | Why "Recruitment" and the vision behind the project |
