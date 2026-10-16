---
name: skill-update-check
description: >-
  Tells you at session start when skills installed from the AWOS registry are
  outdated or removed. Once a day, silent offline. Fires on SessionStart,
  reads .claude/awos-recruitment.lock.json, asks the registry server, prints
  one line such as "2 skills outdated, run skill update". Use when a team
  wants to notice skill updates without remembering to run skill status.
hooks:
  - event: SessionStart
    timeout: 10
---

# Skill update check

## What it does

On every session start the hook reads `.claude/awos-recruitment.lock.json` (written by `npx @provectusinc/awos-recruitment skill ...`), sends it to the registry server (`POST /check`) and shows one line when something is outdated or removed:

```text
awos-recruitment: 2 skills outdated (pytest-best-practices, react-best-practices). Run `npx @provectusinc/awos-recruitment skill update`.
```

When everything is current it prints nothing. It checks at most once a day per project (stamp file under `${XDG_CACHE_HOME:-$HOME/.cache}/awos-recruitment/`), never on every start. It fails open: no lock file, no `curl`, no network, or a server error all end the hook silently with exit 0.

The message goes to you, not to Claude: the hook prints `{"systemMessage": ...}`, so it does not change what the model does.

## Why a team wants it

Skills are copies in the project. When the registry fixes one, nobody tells the copy. This hook is the reminder; `skill status` and `skill update` do the work.

## Settings

| Variable | Effect |
|----------|--------|
| `AWOS_SERVER_URL` | Registry server (default `https://recruitment.awos.provectus.pro`). |
| `AWOS_UPDATE_CHECK=0` | Turn the hook off. |
| `AWOS_UPDATE_CHECK_INTERVAL` | Seconds between checks (default `86400`). `0` checks every start. |

## Manual installation

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/skill-update-check/skill-update-check.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PROJECT_DIR` is a literal string that Claude Code expands at runtime. The CLI performs this merge: `npx @provectusinc/awos-recruitment hook skill-update-check`.
