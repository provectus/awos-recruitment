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

## Install Capabilities

Once connected, install discovered capabilities directly into your project:

```bash
# Install a skill
npx awos skill modern-python-development

# Install an MCP server definition
npx awos mcp context7

# Install an agent (also auto-installs its referenced skills)
npx awos agent test-agent

# Install multiple at once
npx awos skill modern-python-development typescript-development
npx awos mcp context7 playwright
npx awos agent test-agent another-agent
```

## Quick Start

```bash
just serve
```

The server starts on `http://0.0.0.0:8000` with:
- **MCP endpoint:** `POST /mcp` (Streamable HTTP)
- **Health check:** `GET /health`
- **Bundle endpoints:** `POST /bundle/skills`, `POST /bundle/mcp`, `POST /bundle/agents`

## Documentation

| Document | Description |
|----------|-------------|
| [Development Guide](docs/DEVELOPMENT.md) | Prerequisites, setup, commands, project structure, and AWOS workflow |
| [Contributing to the Registry](docs/CONTRIBUTING.md) | How to add skills and MCP definitions to the capability registry |
| [Philosophy](docs/PHILOSOPHY.md) | Why "Recruitment" and the vision behind the project |
