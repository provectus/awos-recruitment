![AWOS Recruitment](docs/media/cover.png)

# AWOS Recruitment

A curated registry of Claude Code skills, agents, and tools with a smart search MCP server. The Provectus Way of assembling AI capabilities for your project.

Connect the MCP server to Claude Code, search for capabilities using natural language, and install them into your project with a single command.

> **Works best with [AWOS](https://github.com/provectus/awos)** — the AI Workflow Orchestration System for spec-driven development. AWOS drives the SDLC pipeline from spec to implementation; Recruitment provisions the right skills, agents, and tools for each task. Use the built-in `/awos:hire` command to fully automate capability provisioning — it searches, selects, and installs everything your project needs in one step.

## Connect MCP

**Claude Code CLI:**

```bash
claude mcp add awos-recruitment --transport http --scope project https://recruitment.awos.provectus.pro/mcp
```

> We recommend `--scope project` so the MCP config is stored in `.mcp.json` and shared with your team. If you don't need that, change the scope (e.g. `--scope user`).

**Or add to `.mcp.json` manually:**

```json
{
  "mcpServers": {
    "awos-recruitment": {
      "type": "url",
      "url": "https://recruitment.awos.provectus.pro/mcp"
    }
  }
}
```

Once connected, Claude Code gains access to the `search_capabilities` tool — search the registry using natural language with an optional type filter (`skill`, `agent`, `tool`).

## CLI

Install discovered capabilities directly into your project:

```bash
npx @provectusinc/awos-recruitment <command> <names...>
```

| Command | Description |
|---------|-------------|
| `skill <names...>` | Install skills into `.claude/skills/` |
| `mcp <names...>` | Install MCP server definitions into `.mcp.json` |
| `agent <names...>` | Install agents into `.claude/agents/` (auto-installs referenced skills) |

Examples:

```bash
npx @provectusinc/awos-recruitment skill modern-python-development
npx @provectusinc/awos-recruitment mcp context7 playwright
npx @provectusinc/awos-recruitment agent test-agent
```

## Documentation

| Document | Description |
|----------|-------------|
| [Development Guide](docs/DEVELOPMENT.md) | Prerequisites, setup, commands, and project structure |
| [Contributing to the Registry](docs/CONTRIBUTING.md) | How to add skills, MCP definitions, and agents |
| [Philosophy](docs/PHILOSOPHY.md) | Why "Recruitment" and the vision behind the project |
