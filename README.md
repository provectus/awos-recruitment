# AWOS Recruitment

A zero-setup, intelligent discovery engine for AI coding assistant capabilities — skills, agents, and tools.

AI assistants (like Claude Code) connect to the AWOS Recruitment MCP server to search for and install specialized capabilities matching their developer's needs, without manual setup or dependency management.

## Repository Structure

| Directory | Description | Status |
|---|---|---|
| `server/` | Python FastMCP MCP server — search and discovery engine | Active |
| `cli/` | TypeScript npx package — capability installation CLI | Planned |
| `registry/` | Git-managed catalog of skills, agents, and tools | Active |
| `context/` | Product documentation, specs, and roadmap | -- |

## Quick Start

### MCP Server

```bash
cd server
uv sync
uv run python -m awos_recruitment_mcp
```

The server starts on `http://0.0.0.0:8000` with:
- **MCP endpoint:** `POST /mcp` (Streamable HTTP)
- **Health check:** `GET /health`

### Configuration

| Variable | Default | Description |
|---|---|---|
| `AWOS_HOST` | `0.0.0.0` | Server bind address |
| `AWOS_PORT` | `8000` | Server port |
| `AWOS_VERSION` | `0.1.0` | Server version |

Copy `server/.env.example` to `server/.env` to override defaults.

### Validate Registry

```bash
just validate-registry                  # human-readable output (default)
just validate-registry --format json    # JSON output for CI
```

### Running Tests

```bash
cd server
uv run pytest -v
```

## Capability Registry

The `registry/` directory is the Git-managed catalog of capabilities that the server indexes and searches over.

| Path | Contents |
|---|---|
| `registry/skills/<name>/SKILL.md` | Claude Code skills — YAML front matter (name, description, etc.) + markdown instructions |
| `registry/mcp/<name>.yaml` | MCP server definitions — name, description, and `.mcp.json`-compatible config |

To add a new capability, create the appropriate file/directory and run `just validate-registry` to ensure it passes schema validation.

## MCP Tools

| Tool | Description |
|---|---|
| `search_capabilities` | Search the capability registry for skills, agents, and tools matching a natural language query. Returns name, description, and tags for each match. |

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
