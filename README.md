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
npx @provectusinc/awos-recruitment@latest <command> <names...>
```

| Command | Description |
|---------|-------------|
| `skill <names...>` | Install skills into `.claude/skills/` |
| `mcp <names...>` | Install MCP server definitions into `.mcp.json` |
| `agent <names...>` | Install agents into `.claude/agents/` (auto-installs referenced skills) |
| `hook <names...>` | Install hooks into `.claude/hooks/` and inject their configuration into `.claude/settings.json` |

Examples:

```bash
npx @provectusinc/awos-recruitment@latest skill modern-python-development
npx @provectusinc/awos-recruitment@latest mcp context7 playwright
npx @provectusinc/awos-recruitment@latest agent testing-expert
npx @provectusinc/awos-recruitment@latest hook format-on-edit checks-before-stop
```

### Installed skills and updates

Every installed skill is recorded in `.claude/awos-recruitment.lock.json` with the sha256 of each file. Commit this file with the skills.

```bash
# Compare installed skills with the registry
npx @provectusinc/awos-recruitment@latest skill status

# Update the outdated ones
npx @provectusinc/awos-recruitment@latest skill update
npx @provectusinc/awos-recruitment@latest skill update --dry-run     # show the plan only
npx @provectusinc/awos-recruitment@latest skill update react-best-practices

# Replace one skill with the registry version, whatever its state
npx @provectusinc/awos-recruitment@latest skill modern-python-development --force

# Do not offer the current registry version of a skill again
npx @provectusinc/awos-recruitment@latest skill skip react-best-practices

# Show what an update would change (your files against the registry)
npx @provectusinc/awos-recruitment@latest skill diff

# Merge the registry version with your own edits (Claude does the editing)
npx @provectusinc/awos-recruitment@latest skill diff --keep react-best-practices
#   ... edit .claude/skills/react-best-practices/ ...
npx @provectusinc/awos-recruitment@latest skill merged react-best-practices
```

`skill diff --keep` saves the registry version and a backup of your copy to the project's cache folder, `~/.cache/awos-recruitment/projects/<folder>-<hash>/` (`$XDG_CACHE_HOME` when set), outside the project, so nothing of it lands in git. After the files in `.claude/skills/<name>/` have both the registry's changes and your edits, `skill merged` records the registry version as the base in the lock file and removes the saved copy. From then on the skill counts as current with your own edits, not as outdated. In Claude Code you only choose "update and keep my edits"; Claude runs these steps.

`skill skip` records the skipped registry version in the lock file. `status` shows the skill as `skipped by you`, and `update`, the session-start hook and the MCP check stay quiet about it until the registry publishes a newer version. `skill update <name>` still updates it. When the installed files are the registry's current version, the lock entry also records its registry `commit` and `released` date, and `status` shows them.

`skill status` prints one of: `up to date`, `outdated`, `modified locally`, `removed from registry` (with the replacement), `no lock entry`, `not in registry`, `missing locally`. Add `--json` for scripts.

Skills installed before the lock file existed are matched against the registry's version history (`GET /history.json`, generated from git at deploy time). A copy that equals a past version shows as `outdated` with the date of that version and `skill update` replaces it; a copy that matches no version shows as `no lock entry`, because it has local changes.

`skill update` replaces outdated skills and records them in the lock file. A skill you changed locally is not overwritten silently:

- in a terminal, `update` asks: overwrite, skip, or back up to `~/.cache/awos-recruitment/projects/<folder>-<hash>/backups/<name>/<timestamp>/` and overwrite;
- without a terminal (CI, `claude -p`), it keeps your copy and says so;
- `--overwrite` and `--no-overwrite` set the answer for every skill.

Both commands send anonymous counts (project id from the lock file, skill names, outcome) to the server. Set `AWOS_TELEMETRY=0` to turn that off. The server publishes the current hash of every skill and the list of removed ones at `GET /index.json`.

To be told at session start instead of remembering to run `skill status`, install the `skill-update-check` hook. It checks once a day, is silent offline, and prints one line when something is outdated or removed:

```bash
npx @provectusinc/awos-recruitment@latest hook skill-update-check
```

### Hooks

A hook runs on a Claude Code event, so it works every time, not only when Claude follows an instruction. The registry has these hooks:

| Hook | Event | What it does |
|------|-------|--------------|
| [`skill-update-check`](registry/hooks/skill-update-check/HOOK.md) | SessionStart | Once a day, prints one line when an installed skill is outdated or removed from the registry. |
| [`format-on-edit`](registry/hooks/format-on-edit/HOOK.md) | PostToolUse | Formats each file that Claude edits with the project's own formatter: Prettier or Biome, ruff or black, gofmt, terraform fmt. It never blocks an edit. |
| [`checks-before-stop`](registry/hooks/checks-before-stop/HOOK.md) | Stop | Runs the project's lint, type check and tests before Claude finishes. If a check fails, Claude gets the output and fixes the problem. |

Each hook name links to its page with the settings and the manual installation steps.


## Documentation

| Document | Description |
|----------|-------------|
| [Development Guide](docs/DEVELOPMENT.md) | Prerequisites, setup, commands, and project structure |
| [Contributing to the Registry](docs/CONTRIBUTING.md) | How to add skills, MCP definitions, agents, and hooks |
| [Philosophy](docs/PHILOSOPHY.md) | Why "Recruitment" and the vision behind the project |
