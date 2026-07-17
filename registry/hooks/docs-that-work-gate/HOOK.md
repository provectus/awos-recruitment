---
name: docs-that-work-gate
description: Blocks git commit when pending changes touch directories whose CLAUDE.md or README.md was not updated — instructs Claude to refresh the docs with the docs-that-work skill before committing, so documentation never goes stale. Fires on PreToolUse for Bash.
hooks:
  - event: PreToolUse
    matcher: Bash
    timeout: 10
---

# docs-that-work-gate

## What this hook does

This is a Claude Code `PreToolUse` hook that keeps documentation in sync with
the code it describes. Before Claude Code runs a `Bash` command containing
`git commit`, the hook inspects the pending changes (staged, unstaged, and
untracked — the whole `git status`). Every changed file is mapped to its
**owning documentation**: the nearest ancestor directory containing a
`CLAUDE.md` or `README.md`. If any owning doc file was *not* itself updated,
the commit is **blocked** (exit code `2`) with a message instructing Claude
to review those docs with the **docs-that-work skill**, stage the updates,
and re-run the commit.

Hooks cannot invoke skills directly — the block reason fed back to Claude is
the trigger. The hook is the tripwire; Claude does the documentation work.
The block message adapts to the project: when
`.claude/skills/docs-that-work/` is installed it instructs Claude to invoke
the skill (imperatively — "do not update the docs from memory"); when it is
missing, it instructs installing the skill first, so the reference is never
a dead pointer.

## Why a team would want it

Documentation goes stale one commit at a time: code in `server/src/` changes,
`server/CLAUDE.md` doesn't, and three months later agents and humans are
making decisions from a file that describes a system that no longer exists.
Stale docs cause worse decisions than no docs. This hook makes doc review a
structural part of every commit an agent makes — pairing with the
`docs-that-work` skill, which knows *how* to keep `CLAUDE.md`/`README.md`
lean and non-stale. Install both:

```shell
npx @provectusinc/awos-recruitment skill docs-that-work
npx @provectusinc/awos-recruitment hook docs-that-work-gate
```

## How it works

- **Ownership rule:** each changed file belongs to the *nearest* ancestor
  directory containing `CLAUDE.md` or `README.md`. Repo-root docs only own
  files that sit at the root itself — a root `README.md` does not tax every
  commit in the repository.
- **Freshness rule:** an owning doc file counts as fresh when it has pending
  changes of its own. Once Claude updates it, the retried commit passes.
- **Loop prevention** (worst case two blocks per commit, never a deadlock):
  1. Doc files with pending changes are fresh (above).
  2. On block, a checksum of the pending state (`git status --porcelain`
     plus the tracked-content diff) is stored in
     `.git/docs-that-work-gate.ok`. Re-running the *same* commit unchanged
     passes and consumes the marker — this is how "the docs are already
     accurate" is acknowledged. Any further edit invalidates it.
  3. Change sets consisting only of `CLAUDE.md`/`README.md` files always
     pass, so the follow-up docs commit is never gated.
- **Fail open:** anything unexpected — not a git repository, git missing,
  clean tree, non-commit command, unreadable payload — exits `0`.

The entrypoint is pure POSIX shell using only `git`, `grep`, `sed`, and
`cksum` — no python, no node, no other runtime dependencies.

## Limitations

- The matcher is tool-name based (`Bash`); commits made outside Claude Code
  (your own terminal, CI) are not gated — this is an agent guardrail, not a
  git hook.
- Commit detection is a substring scan of the command; a command merely
  *mentioning* `git commit` proceeds into the precise git checks, which is
  harmless (clean tree → allow).
- `git commit` invoked through wrappers the scan cannot see (aliases,
  scripts, `make release`) is not gated.

## Manual injection instructions

The CLI installer normally merges this configuration into your project's
`.claude/settings.json` for you. To wire it up **manually**, add the following
fragment to `.claude/settings.json` (merging into any existing `hooks` block):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/docs-that-work-gate/docs-that-work-gate.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

The `command` is always the derived entrypoint path
`$CLAUDE_PROJECT_DIR/.claude/hooks/<name>/<name>.sh` — `$CLAUDE_PROJECT_DIR` is
a literal string that Claude Code expands at runtime. Ensure the installed
`docs-that-work-gate.sh` retains its executable bit.
