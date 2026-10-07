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
│       ├── README.md             # Optional — registry-local docs (not bundled)
│       ├── references/           # Optional — supporting files (flat)
│       ├── scripts/              # Optional — flat *.js|*.ts|*.py|*.sh
│       ├── assets/               # Optional — flat files of any type
│       └── evals/                # Optional — flat *.json|*.md test cases (not bundled)
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

- Each **skill** lives in its own subdirectory under `registry/skills/`. The directory must contain a `SKILL.md` file and may include the optional subdirectories listed above (see [Directory Layout](#directory-layout)).
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
| `name` | string | Kebab-case only (`a-z`, `0-9`, `-`). Max 64 characters. Must match the directory name. Must not contain the reserved words `anthropic` or `claude`, or XML tags. |
| `description` | string | 1–1024 characters, no XML tags. Describes what the skill does and when to trigger it. |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `license` | string | License covering the skill (Agent Skills spec field). |
| `compatibility` | string | Environment requirements — intended products, system prerequisites (Agent Skills spec field). Max 500 characters. |
| `metadata` | map of strings | Catalog data the spec keeps out of the top level: `version`, `author`, and the like. Claude Code does not act on its contents. |
| `version` | string | Still accepted at the top level, but the validator warns (`version-top-level`). Put it under `metadata.version` instead. |
| `argument-hint` | string | Hint for expected arguments. Use `[brackets]` for placeholders (e.g., `[filename]`); an angle-bracket placeholder such as `<PR URL>` is accepted with a warning (`frontmatter-xml-tags`). |
| `disable-model-invocation` | boolean | Prevent Claude from auto-loading this skill. |
| `user-invocable` | boolean | Show/hide from the `/` slash command menu. |
| `allowed-tools` | string | Comma-separated list of tools Claude can use. |
| `model` | string | Model override when this skill is active. |
| `effort` | string | Reasoning effort while this skill is active: `low`, `medium`, `high`, `xhigh`, or `max`. Omit to follow the session's own setting. |
| `context` | string | Set to `fork` to run in an isolated subagent. |
| `agent` | string | Subagent type when `context: fork` is set. |
| `hooks` | object | Skill-scoped hooks configuration. |

**No other fields are allowed.** The validator rejects unknown front matter fields.

The markdown body below the front matter must be non-empty — it contains the actual instructions.

### Directory Layout

The validator rejects anything the install bundle would silently drop. A skill directory may contain only:

| Entry | Contents | Bundled |
|-------|----------|---------|
| `SKILL.md` | Front matter + instructions. Required. | Yes |
| `README.md` | Registry-local documentation. | No |
| `references/` | Flat files of any type — supporting material linked from `SKILL.md`. | Yes |
| `scripts/` | Flat `.js`, `.ts`, `.py` or `.sh` files. | Yes |
| `assets/` | Flat files of any type (templates, images, data). | Yes |
| `evals/` | Flat `.json` or `.md` files — the skill's test cases (skill-creator's `evals.json` plus notes). | No |

"Flat" means no nested directories: the bundler only picks up regular files directly under each subdirectory. Dotfiles (`.DS_Store`) are ignored. Because `README.md` and `evals/` are not shipped, `SKILL.md` and reference files must not link to them (see `broken-link` below).

### Content Quality Rules

Beyond the schema, the validator checks every skill against the parts of Anthropic's [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) that can be tested mechanically. **Errors** fail validation; **warnings** are reported and fail only under `--strict`. Every finding carries its rule id and, where it has one, the line it points at, and names the guide section it enforces.

Links, emphasis and dates are only checked in prose — fenced code blocks and inline code spans are ignored. Body rules run on `SKILL.md` and on every `references/*.md` file.

| Rule | Severity | What it checks |
|------|----------|----------------|
| `skill-body-length` | error | The `SKILL.md` body (front matter excluded) is at most 500 lines. Move detail into `references/`. |
| `broken-link` | error | Every relative link in `SKILL.md` or a reference file resolves to a file the bundle ships: `SKILL.md` or a flat file under `references/`, `scripts/` or `assets/`. A link to a missing file, a file outside the skill directory, or an unbundled file (`README.md`, `evals/…`) fails. |
| `windows-path` | error | No backslash paths (`references\guide.md`) in links or inline code — use forward slashes. |
| `file-encoding` | error | Every `references/*.md` file is valid UTF-8. |
| `description-yaml-comment` | error | An unquoted `description` must not contain ` #` — YAML reads it as a comment and silently drops the rest, so the text Claude sees is shorter than what you wrote. Quote the value or use a folded block (`description: >-`). |
| `description-trigger` | warning | The description says when to use the skill — a trigger clause such as "Use when …". |
| `description-person` | warning | The description is written in third person ("Processes X…", not "I can…" or "helps you…"). |
| `frontmatter-xml-tags` | warning | `argument-hint` contains an XML-like tag such as `<file>`. `name` and `description` with tags are schema errors (see above); hints only warn because `<placeholder>` is the conventional way to write them. |
| `version-top-level` | warning | `version` is set at the top level of the front matter. Move it to `metadata.version`. |
| `reference-toc` | warning | A reference file longer than 100 lines has a contents section in its first 40 lines — a "Contents" heading or at least three `[..](#..)` anchor links. |
| `nested-reference` | warning | A reference file links to another reference file. Link it from `SKILL.md` instead so references stay one level deep. |
| `caps-emphasis` | warning | Fewer than five all-caps emphasis words (`CRITICAL`, `MUST`, `NEVER`, `ALWAYS`, `IMPORTANT`) per file outside code. State the rule plainly and keep emphasis for the one that matters. |
| `time-sensitive` | warning | No dated phrases ("before January 2025", "as of Q3 2024") outside a section headed "Old patterns", "Legacy", "Deprecated", "History" or "Changelog". |

Rules live in `server/src/awos_recruitment_mcp/validate/quality.py`; the front-matter limits (`name` pattern, reserved words, description length, XML tags) live in the Pydantic models under `server/src/awos_recruitment_mcp/models/` and are reported as schema errors without a rule id.

### Example

See `registry/skills/modern-python-development/SKILL.md` for a complete example.

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
| `name` | string | Kebab-case only (`a-z`, `0-9`, `-`). Max 64 characters. Must match the filename (without `.md`). Must not contain the reserved words `anthropic` or `claude`, or XML tags. |
| `description` | string | 1–1024 characters, no XML tags. Describes the agent's expertise and when to invoke it. |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | Target model identifier (e.g., `opus`, `sonnet`, `haiku`). |
| `effort` | string | Reasoning effort the agent runs at: `low`, `medium`, `high`, `xhigh`, or `max`. Subagents doing routine work should declare `effort: low` — it cuts thinking time and cost without changing the model. Omit to follow the session's own setting. |
| `skills` | list of strings | Skill names this agent references. Each must be kebab-case. **All referenced skills must exist in `registry/skills/`.** May be an empty list (`skills: []`) or omitted entirely when the agent does not depend on any skills (see `registry/agents/testing-expert.md` for an example with `skills: []`). |

**No other fields are allowed.** The validator rejects unknown front matter fields.

The markdown body below the front matter must be non-empty — it contains the agent's system prompt.

When a user installs an agent, its referenced skills are automatically installed alongside it.

### Content Quality Rules

Agents share the front-matter limits with skills (same `name` and `description` types) and get two rule-tagged checks on top:

| Rule | Severity | What it checks |
|------|----------|----------------|
| `description-yaml-comment` | error | An unquoted `description` must not contain ` #` — YAML drops the rest of the value. Quote it or use `description: >-`. |
| `agent-skill-exists` | error | Every name in `skills` is a directory under `registry/skills/`. |

The body-level skill rules (link checks, emphasis, dates) do not run on agents.

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

---

## Validating Your Changes

Before submitting, run the registry validator:

```bash
just validate-registry
```

This scans all entries under `registry/` and checks them against the schemas and content rules described above. You should see output like:

```
OK    skills/my-skill/SKILL.md
OK    mcp/my-server.yaml
OK    hooks/my-hook/HOOK.md

All 3 entries valid.
```

Entries with warnings are marked `WARN`; entries with errors are marked `FAIL`. Rule-tagged findings print the rule id and, when they have one, the line:

```
FAIL  skills/bad-skill/SKILL.md
  - name: String should match pattern '^[a-z0-9-]{1,64}$'
  - [broken-link] skills/bad-skill/SKILL.md:42: Link 'references/missing.md' does not exist (see 'Progressive disclosure patterns' in …)
WARN  skills/other-skill/SKILL.md
  - WARN [description-trigger] skills/other-skill/SKILL.md: Description does not say when to use the skill — add a trigger clause such as 'Use when …' (see 'Writing effective descriptions' in …)

2 errors, 1 warnings in 1 files. Validation failed.
```

### Options

The `just` recipe forwards its arguments to `uv run python -m awos_recruitment_mcp.validate` (run from `server/`):

| Flag | Effect |
|------|--------|
| `--format human` | Default. The output shown above. |
| `--format json` | Structured JSON (below). |
| `--format github` | One `::error`/`::warning` workflow annotation per finding, so findings show inline on the PR. CI uses this. |
| `--summary PATH` | Append a markdown summary — counts per rule, counts per entry, and the full list of findings — to `PATH` (CI passes `$GITHUB_STEP_SUMMARY`, since GitHub shows at most 10 annotations per severity). |
| `--strict` | Fail on warnings as well as errors. |
| `--registry-path PATH` | Registry directory (default `../registry`). |

### JSON Output (for CI)

```bash
just validate-registry --format json
```

Returns structured JSON:

```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    {
      "file": "skills/other-skill/SKILL.md",
      "field": "description",
      "message": "Description does not say when to use the skill — …",
      "severity": "warning",
      "rule": "description-trigger",
      "line": null
    }
  ],
  "summary": { "total": 4, "passed": 4, "failed": 0, "warnings": 1 }
}
```

### Exit Codes

The command exits with code `0` when no entry has errors and `1` otherwise. Warnings never change the exit code unless you pass `--strict`, in which case any warning also exits `1`. The CI workflow (`.github/workflows/validate.yml`) runs without `--strict`, so warnings show up as PR annotations but do not block the merge.

### Repo-Local Skill Copies

A few registry skills are also checked in under `.claude/skills/` so this repository's own Claude Code sessions pick them up without an install step. The two copies must stay in sync:

```bash
just check-skill-parity
```

This runs `uv run python -m awos_recruitment_mcp.validate.parity` (from `server/`; `--repo-root PATH` overrides the default `..`). The pairs are listed in `SKILL_PAIRS` in `server/src/awos_recruitment_mcp/validate/parity.py` — adding a pair is one line there. For every pair, every file must match byte for byte, except:

- the `name:` line of `SKILL.md` (the local alias is not the registry name);
- one leading `<!-- … -->` provenance comment at the top of the `SKILL.md` body, or above its front matter, pointing back at the registry copy;
- `README.md` and `evals/`, which are skipped on both sides.

The check exits `0` when every pair matches and `1` otherwise, printing a short unified diff for each file that differs. CI runs it after the registry validator. If you change a registry skill that has a local copy, re-copy it into `.claude/skills/<alias>/`, keeping only the local `name:` line and the provenance comment.

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
- [ ] Skill directory contains only `SKILL.md`, `README.md`, and flat files under `references/`, `scripts/`, `assets/` or `evals/`
- [ ] `just validate-registry` passes with exit code 0, and any `WARN` findings are either fixed or deliberate
- [ ] `just check-skill-parity` passes if the skill has a copy under `.claude/skills/`
