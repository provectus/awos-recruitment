# Registry: Hooks

Claude Code lifecycle hooks distributed through the AWOS registry — event-driven guardrails (block risky tool calls, gate commits, run checks) that teams install with one command. Installation drops the hook directory into a project's `.claude/hooks/` and merges its configuration into `.claude/settings.json`.

## Anatomy of a Hook

Each hook is a directory named after the hook, containing a `HOOK.md` (metadata + docs) and an executable entrypoint script with the same name:

```text
registry/hooks/<hook-name>/
├── HOOK.md              # front matter + docs + manual injection fragment
├── <hook-name>.sh       # executable entrypoint (chmod +x, committed)
└── scripts/             # optional flat .sh helpers (see CONTRIBUTING.md)
```

`HOOK.md` front matter declares *when* the hook fires — never *what command runs* (the command is always derived from the name):

```yaml
---
name: <hook-name>          # kebab-case, must equal the directory name
description: What it does and when it fires — this is what search matches on.
hooks:
  - event: PreToolUse              # a documented Claude Code hook event (see models/hook_metadata.py)
    matcher: Bash                  # optional tool-name matcher
    timeout: 10                    # optional, seconds
---
```

The markdown body documents what the hook does, why a team wants it, and the exact `settings.json` fragment for manual installation. See [CONTRIBUTING.md](../../docs/CONTRIBUTING.md#adding-a-hook) for the complete field tables and entrypoint rules.

## Adding a New Hook

1. Create `registry/hooks/<name>/` — `<name>` is kebab-case (`a-z`, `0-9`, `-`, max 64 chars) and must match the front matter `name` and the entrypoint filename `<name>.sh`.
2. Write `HOOK.md` (front matter above + body with manual injection instructions).
3. Write the entrypoint script and make it executable: `chmod +x <name>.sh` (git commits the mode bit — validation fails without it).
4. Validate and test:

```bash
just validate-registry
just test
```

5. Add behavior tests as `server/tests/test_<name>_hook.py` — run the script via `subprocess` with tool-call JSON payloads and assert exit codes.
6. Open a PR — CI runs the same validation; review is the registry's quality gate.

## Trying a Hook Locally

```bash
just serve                                  # start the registry server
# in a second terminal — just serve blocks the foreground
AWOS_SERVER_URL=http://localhost:8000 \
  npx @provectusinc/awos-recruitment hook <name>   # install into the current project
```

Re-running the install is idempotent; it never overwrites existing files or settings entries.

Hook entries are written to the project's shared `.claude/settings.json` deliberately — a gate a team adopts should apply to every teammate after the settings commit merges. Use your project's code review of that commit as the checkpoint.
