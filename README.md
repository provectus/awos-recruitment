![AWOS Recruitment](docs/media/cover.png)

# AWOS Recruitment

A curated registry of Claude Code skills, agents, tools, and hooks with a smart search MCP server. The Provectus Way of assembling AI capabilities for your project.

Connect the MCP server to Claude Code, search for capabilities using natural language, and install them into your project with a single command.

> **Works best with [AWOS](https://github.com/provectus/awos)** — the AI Workflow Orchestration System for spec-driven development. AWOS drives the SDLC pipeline from spec to implementation; Recruitment provisions the right skills, agents, tools, and hooks for each task. Use the built-in `/awos:hire` command to fully automate capability provisioning — it searches, selects, and installs everything your project needs in one step.

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

Once connected, Claude Code gains access to the `search_capabilities` tool — search the registry using natural language with an optional type filter (`skill`, `agent`, `tool`, `hook`).

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
| `hook <names...>` | Install hooks into `.claude/hooks/` and inject their configuration into `.claude/settings.json` |

Examples:

```bash
npx @provectusinc/awos-recruitment skill modern-python-development
npx @provectusinc/awos-recruitment mcp context7 playwright
npx @provectusinc/awos-recruitment agent testing-expert
```

### Installed skills and updates

Every installed skill is recorded in `.claude/awos-recruitment.lock.json` with the sha256 of each file. Commit this file with the skills. A skill that is already installed is not touched; pass `--force` to replace it with the registry version:

```bash
npx @provectusinc/awos-recruitment skill modern-python-development --force
```

The server publishes the current hash of every skill and the list of removed ones at `GET /index.json`. Compare it with the lock file to see which installed skills are outdated.

## Documentation

| Document | Description |
|----------|-------------|
| [Development Guide](docs/DEVELOPMENT.md) | Prerequisites, setup, commands, and project structure |
| [Contributing to the Registry](docs/CONTRIBUTING.md) | How to add skills, MCP definitions, agents, and hooks |
| [Philosophy](docs/PHILOSOPHY.md) | Why "Recruitment" and the vision behind the project |
