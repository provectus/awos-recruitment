---
name: checks-before-stop
description: >-
  Runs the project's lint, type check and tests before Claude finishes a task,
  and sends Claude back to fix them when they fail. Fires on Stop. Finds the
  checks in package.json scripts (lint, typecheck, test) or in .venv (ruff,
  pytest), or runs a command you set. Skips when nothing changed since the
  last green run. Use when a team wants a quality gate so the agent never
  says done with failing lint or tests.
hooks:
  - event: Stop
    timeout: 600
---

# Checks before stop

## What it does

When Claude is about to finish its reply, the hook runs the project's checks. If a check fails, the hook stops Claude from finishing (exit 2) and gives it the failed command and the last 60 lines of its output. Claude then fixes the problem and tries to finish again.

Which checks run:

1. `AWOS_STOP_CHECKS_CMD`, when set — one shell command, for example `make check`.
2. Otherwise, in a project with `package.json`: the scripts `lint`, `typecheck`, `type-check` and `test` that exist, in that order, with the package manager the lock file names (npm, pnpm, yarn or bun). The placeholder `test` script that `npm init` writes is skipped.
3. Otherwise, in a Python project: `.venv/bin/ruff check .` when the project configures ruff, and `.venv/bin/pytest -q` when pytest is in `.venv`.

If none of these apply, the hook does nothing. Checks run with `CI=1`, so test runners such as Vitest and Jest run once instead of watching.

## When it does not run

The hook keeps quiet so it does not slow down ordinary questions:

- The git working tree is clean: nothing changed, nothing to check.
- The working tree is the same as at the last green run (fingerprint under `${XDG_CACHE_HOME:-$HOME/.cache}/awos-recruitment/`).
- Claude is already continuing because of this hook (`stop_hook_active`). So the hook blocks at most once per turn and cannot loop. If the checks still fail, Claude finishes and the hook tries again on the next change.
- The project is not a git repository, or anything unexpected happens: the hook exits 0.

## Why a team wants it

An agent often ends with "done" while lint fails or a test it did not run is red. Prompts and specs can ask it to run the checks, but it can still skip them. A Stop hook is not a request: the checks run every time code changed.

## Settings

| Variable | Effect |
|----------|--------|
| `AWOS_STOP_CHECKS=0` | Turn the hook off. |
| `AWOS_STOP_CHECKS_CMD` | Run this command instead of the detected checks. |
| `AWOS_STOP_CHECKS_LINES` | Lines of failed output sent to Claude (default `60`). |

Set them in the `env` block of `.claude/settings.json` to share them with the team, or in `.claude/settings.local.json` for yourself.

## Manual installation

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/checks-before-stop/checks-before-stop.sh",
            "timeout": 600
          }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PROJECT_DIR` is a literal string that Claude Code expands at runtime. The CLI performs this merge: `npx @provectusinc/awos-recruitment@latest hook checks-before-stop`.
