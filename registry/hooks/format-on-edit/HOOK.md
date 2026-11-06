---
name: format-on-edit
description: >-
  Formats code automatically after every edit Claude makes, with the formatter
  the project already uses: Prettier or Biome, ruff or black, gofmt, terraform
  fmt. Fires on PostToolUse for Edit and Write. Never installs a formatter and
  never fails the edit. Use when a team wants format on save for the agent, so
  Claude's changes match the project's style without a separate format step.
hooks:
  - event: PostToolUse
    matcher: Edit|Write|MultiEdit
    timeout: 30
---

# Format on edit

## What it does

After Claude edits or writes a file, the hook formats that one file with the formatter the project already has:

| File types | Formatter | Used when |
|------------|-----------|-----------|
| JS, TS, JSON, CSS, HTML, Markdown, YAML, Vue, Svelte, GraphQL | Biome | `node_modules/.bin/biome` and `biome.json` or `biome.jsonc` exist |
| the same | Prettier | `node_modules/.bin/prettier` exists (and no Biome config) |
| Python | ruff | `.venv/bin/ruff` exists and the project configures ruff (`ruff.toml`, `.ruff.toml` or `[tool.ruff]` in `pyproject.toml`) |
| Python | black | `.venv/bin/black` exists (and ruff does not apply) |
| Go | gofmt | `gofmt` is on `PATH` |
| Terraform | terraform fmt, tofu fmt | `terraform` or `tofu` is on `PATH` |

It uses only the project's own JS and Python tools, so the result matches what the team's own format command gives. It never installs anything. A formatter that is missing, fails or times out is skipped silently: the hook always exits 0 and never blocks an edit. Prettier and Biome honour the project's ignore files.

## Why a team wants it

Claude writes code that is close to the project's style but not always the same: quote style, line breaks, import order. Without this hook the diff fills with format noise, or a pre-commit hook or CI fails on the next push. With it, every file Claude touches is formatted the moment it changes.

## Settings

| Variable | Effect |
|----------|--------|
| `AWOS_FORMAT_ON_EDIT=0` | Turn the hook off. |

## Manual installation

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/format-on-edit/format-on-edit.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PROJECT_DIR` is a literal string that Claude Code expands at runtime. The CLI performs this merge: `npx @provectusinc/awos-recruitment@latest hook format-on-edit`.
