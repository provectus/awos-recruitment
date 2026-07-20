# Contributing to the Capability Registry

This guide explains how to add new capabilities to the AWOS Recruitment registry.

The registry contains four types of capabilities:

- **Skills** — best practices, code examples, and standards for a specific language, library, framework, or database
- **MCP Definitions** — MCP server configurations ready to be inserted into `.mcp.json`
- **Agents** — behavioral rules and constraints for specialized roles
- **Hooks** — Claude Code lifecycle hooks (shell scripts) that run on events like `PreToolUse`, injected into `.claude/settings.json`

**When to create a skill vs. an agent:**

- Create a **skill** when you want to teach the AI best practices, code examples, or standards for a specific language, library, framework, or database
- Create an **agent** when you need to enforce behavioral rules — for example, restrict a tester agent from reading source code so it stays unbiased

See [Philosophy](PHILOSOPHY.md) for the reasoning behind this distinction.

> **Before writing a skill**, read the official [Best Practices for Writing Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices). It covers structure, prompting techniques, and common pitfalls.

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
├── agents/
│   └── <agent-name>.md           # One markdown file per agent
└── hooks/
    └── <hook-name>/
        ├── HOOK.md               # Required — front matter + injection docs
        ├── <hook-name>.sh        # Required — executable entrypoint
        └── scripts/              # Optional — helper files
            └── *.py|*.js|*.ts
```

- Each **skill** lives in its own subdirectory under `registry/skills/`. The directory must contain a `SKILL.md` file and may include additional reference files.
- Each **MCP definition** is a single `.yaml` file directly under `registry/mcp/`.
- Each **agent** is a single `.md` file directly under `registry/agents/`.
- Each **hook** lives in its own subdirectory under `registry/hooks/`. The directory must contain a `HOOK.md` file and an executable entrypoint script named after the hook.

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
| `skills` | list of strings | Skill names this agent references. Each must be kebab-case. **All referenced skills must exist in `registry/skills/`.** May be an empty list (`skills: []`) or omitted entirely when the agent does not depend on any skills (see `registry/agents/testing-expert.md` for an example with `skills: []`). |

**No other fields are allowed.** The validator rejects unknown front matter fields.

The markdown body below the front matter must be non-empty — it contains the agent's system prompt.

When a user installs an agent, its referenced skills are automatically installed alongside it.

### Example

See `registry/agents/testing-expert.md` for a complete example.

---

## Adding a Hook

Create a directory under `registry/hooks/` containing a `HOOK.md` file and an executable entrypoint script named `<hook-name>.sh`:

```
registry/hooks/my-hook-name/
├── HOOK.md               # Required — front matter + injection docs
├── my-hook-name.sh       # Required — executable entrypoint
└── scripts/              # Optional — helper files (.sh only)
```

`HOOK.md` starts with YAML front matter:

```markdown
---
name: my-hook-name
description: What this hook does and when it fires.
hooks:
  - event: PreToolUse
    matcher: Edit|Write
    timeout: 10
---

# My Hook

What the hook does, why a team would want it, and manual injection
instructions go here...
```

### Required Fields

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | Kebab-case only (`a-z`, `0-9`, `-`). Max 64 characters. Must match the directory name. |
| `description` | string | Non-empty. Describes what the hook does and when it fires — this is what the search index matches against. |
| `hooks` | list | Non-empty list of hook entries (see below). |

### Hook Entries

Each entry in the `hooks` list has the following fields:

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `event` | string | Yes | A documented Claude Code hook event (see `server/src/awos_recruitment_mcp/models/hook_metadata.py` for the authoritative list), e.g. `PreToolUse`, `PostToolUse`, `SessionStart`. |
| `matcher` | string | No | Tool-name matcher (e.g. `Edit\|Write`). Omit for events that don't use matchers. |
| `timeout` | integer | No | Timeout in seconds. Must be greater than 0. |

**There is no `command` field.** The command injected into `.claude/settings.json` is always derived from the hook name: `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>/<name>.sh`. This keeps validation trivial and injection fully deterministic — the entrypoint script *is* the command.

**No other fields are allowed.** The validator rejects unknown front matter fields.

### The Entrypoint Script

Every hook must ship an executable script named `<hook-name>.sh` next to `HOOK.md`:

- It **must carry the executable bit** (`chmod +x my-hook-name.sh`). Git records the file mode, so the bit survives commits, bundling, and installation. Validation fails on a missing or non-executable entrypoint.
- Claude Code passes the event payload to the script on **stdin as JSON**. The script signals its decision via exit codes (e.g. exit `2` blocks a tool call on `PreToolUse`).
- **Multi-event hooks** declare several entries in the `hooks` list but still ship a single entrypoint — branch on the `hook_event_name` field from the stdin JSON to handle each event.
- Helper files go under `scripts/` — hooks allow only flat `.sh` files there (hooks are pure POSIX sh with zero runtime dependencies); anything else fails validation and is dropped from the install bundle.

> **POSIX shell note:** v1 assumes a POSIX shell is available. Windows users need Git Bash or a similar environment to run hook entrypoints.

### The Markdown Body

The body below the front matter must be non-empty. It should document:

- **What the hook does and why** — the behavior it enforces and the value for a team.
- **Manual injection instructions** — the exact JSON fragment to merge into `.claude/settings.json`, as a fallback for users who don't use the CLI. For example:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/my-hook-name/my-hook-name.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PROJECT_DIR` is a literal string that Claude Code expands at runtime — do not substitute it.

The CLI (`npx @provectusinc/awos-recruitment hook <names...>`) performs this merge automatically: it installs the hook files into `.claude/hooks/<name>/` and deterministically merges the derived entries into `.claude/settings.json`, skipping entries that are already present.

### Validation

`just validate-registry` checks every hook for:

- Valid front matter (`name`, `description`, non-empty `hooks` list with valid `event` values; unknown fields rejected)
- `name` matching the directory name
- Non-empty markdown body (the injection docs are mandatory content)
- An existing, executable `<name>.sh` entrypoint
- Directory layout: only `HOOK.md`, `README.md`, the entrypoint, and flat `.sh` files under `scripts/` are allowed (README.md is registry-local documentation — it validates but is not part of the install bundle)

### Example

See `registry/hooks/docs-that-work-gate/` for a complete example.

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
OK    hooks/my-hook/HOOK.md

All 3 entries valid.
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

- [ ] File is in the correct location (`registry/skills/<name>/SKILL.md`, `registry/mcp/<name>.yaml`, `registry/agents/<name>.md`, or `registry/hooks/<name>/HOOK.md`)
- [ ] All required fields are present and non-empty
- [ ] `name` is kebab-case, max 64 characters
- [ ] No unknown fields in front matter (skills, agents, and hooks use `extra="forbid"`)
- [ ] MCP `config` has exactly one server key with a valid `type`
- [ ] Agent `skills` references only existing skills in `registry/skills/`
- [ ] Hook ships an executable `<name>.sh` entrypoint (`chmod +x`) and documents manual injection in the `HOOK.md` body
- [ ] `just validate-registry` passes with exit code 0
