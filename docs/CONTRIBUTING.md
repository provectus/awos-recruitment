# Contributing to the Capability Registry

This guide explains how to add new capabilities to the AWOS Recruitment registry.

The registry contains three types of capabilities:

- **Skills** — Claude Code skill definitions (YAML front matter + markdown instructions)
- **MCP Definitions** — MCP server configurations ready to be inserted into `.mcp.json`
- **Agents** — Claude Code agent definitions (YAML front matter + system prompt)

---

## Directory Structure

```
registry/
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md              # Required — front matter + instructions
│       └── references/           # Optional — supporting files
│           └── *.md
├── mcp/
│   └── <server-name>.yaml        # One YAML file per MCP server
└── agents/
    └── <agent-name>.md           # One markdown file per agent
```

- Each **skill** lives in its own subdirectory under `registry/skills/`. The directory must contain a `SKILL.md` file and may include additional reference files.
- Each **MCP definition** is a single `.yaml` file directly under `registry/mcp/`.
- Each **agent** is a single `.md` file directly under `registry/agents/`.

---

## Adding a Skill

Create a directory under `registry/skills/` and add a `SKILL.md` file with YAML front matter:

```markdown
---
name: my-skill-name
description: When to use this skill and what it does.
---

# My Skill

Instructions for the AI assistant go here...
```

### Required Fields

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | Kebab-case only (`a-z`, `0-9`, `-`). Max 64 characters. |
| `description` | string | Non-empty. Describes what the skill does and when to trigger it. |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Semver version string. |
| `argument-hint` | string | Hint for expected arguments (e.g., `[filename]`). |
| `disable-model-invocation` | boolean | Prevent Claude from auto-loading this skill. |
| `user-invocable` | boolean | Show/hide from the `/` slash command menu. |
| `allowed-tools` | string | Comma-separated list of tools Claude can use. |
| `model` | string | Model override when this skill is active. |
| `context` | string | Set to `fork` to run in an isolated subagent. |
| `agent` | string | Subagent type when `context: fork` is set. |
| `hooks` | object | Skill-scoped hooks configuration. |

**No other fields are allowed.** The validator rejects unknown front matter fields.

The markdown body below the front matter must be non-empty — it contains the actual instructions.

### Example

See `registry/skills/python/SKILL.md` for a complete example.

---

## Adding an MCP Definition

Create a `.yaml` file under `registry/mcp/`:

```yaml
name: "My Server"
description: "What this MCP server provides and when to use it."
config:
  my-server:
    type: stdio
    command: npx
    args:
      - -y
      - "@scope/package@latest"
```

### Required Fields

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | Non-empty. Human-readable display name. |
| `description` | string | Non-empty. What the server provides. |
| `config` | object | Must contain **exactly one key** — the server identifier. |

### Config Structure

The `config` block is a complete `.mcp.json` server entry. The key is the server identifier and the value is the server configuration:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Transport type: `stdio`, `sse`, `http`, or `websocket`. |
| `command` | string | No | Command to run (for `stdio` type). |
| `args` | list of strings | No | Command arguments. |
| `env` | map of strings | No | Environment variables. |
| `url` | string | No | Server URL (for `sse`, `http`, `websocket` types). |

Additional transport-specific fields are allowed.

### Example

See `registry/mcp/context7.yaml` for a complete example.

---

## Adding an Agent

Create a `.md` file under `registry/agents/`:

```markdown
---
name: my-agent-name
description: When to use this agent and what expertise it provides.
model: sonnet
skills:
  - skill-one
  - skill-two
---

# My Agent

You are an expert in...

System prompt instructions go here.
```

### Required Fields

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | Kebab-case only (`a-z`, `0-9`, `-`). Max 64 characters. Must match the filename (without `.md`). |
| `description` | string | Non-empty. Describes the agent's expertise and when to invoke it. |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | Target model identifier (e.g., `opus`, `sonnet`, `haiku`). |
| `skills` | list of strings | Skill names this agent references. Each must be kebab-case. **All referenced skills must exist in `registry/skills/`.** |

**No other fields are allowed.** The validator rejects unknown front matter fields.

The markdown body below the front matter must be non-empty — it contains the agent's system prompt.

When a user installs an agent, its referenced skills are automatically installed alongside it.

### Example

See `registry/agents/test-agent.md` for a complete example.

---

## Validating Your Changes

Before submitting, run the registry validator:

```bash
just validate-registry
```

This scans all entries under `registry/` and checks them against the schemas described above. You should see output like:

```
OK    skills/my-skill/SKILL.md
OK    mcp/my-server.yaml

All 2 entries valid.
```

If there are errors:

```
FAIL  skills/bad-skill/SKILL.md
  - Field 'name' contains invalid characters

1 errors in 1 files. Validation failed.
```

### JSON Output (for CI)

```bash
just validate-registry --format json
```

Returns structured JSON:

```json
{
  "valid": true,
  "errors": [],
  "summary": { "total": 4, "passed": 4, "failed": 0 }
}
```

The command exits with code `0` on success and `1` on any validation failure.

---

## Checklist

Before submitting a new capability:

- [ ] File is in the correct location (`registry/skills/<name>/SKILL.md`, `registry/mcp/<name>.yaml`, or `registry/agents/<name>.md`)
- [ ] All required fields are present and non-empty
- [ ] `name` is kebab-case, max 64 characters
- [ ] No unknown fields in front matter (skills and agents use `extra="forbid"`)
- [ ] MCP `config` has exactly one server key with a valid `type`
- [ ] Agent `skills` references only existing skills in `registry/skills/`
- [ ] `just validate-registry` passes with exit code 0
