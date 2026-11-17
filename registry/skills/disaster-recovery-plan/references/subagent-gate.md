# Read-only checks in subagents

The skill's own hook runs in the main session only: Claude Code does not run a skill's hooks inside subagents. To check subagents' commands too, add this hook to the project's `.claude/settings.json` (or `.claude/settings.local.json`) once. Settings hooks run in subagents as well.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Read|Grep",
        "hooks": [
          {
            "type": "command",
            "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/skills/disaster-recovery-plan/scripts/block-writes.sh\"; [ -f \"$f\" ] || f=\"$HOME/.claude/skills/disaster-recovery-plan/scripts/block-writes.sh\"; [ -f \"$f\" ] || exit 0; exec env DRP_MODE=gate sh \"$f\""
          }
        ]
      }
    ]
  }
}
```

If the file already has a `hooks.PreToolUse` list, add the entry to that list.

What it does:

- It checks a Bash, Read or Grep call only in a subagent of a session that is running this skill. The skill's hook marks that session when the skill makes its first Bash or Agent call. Outside a DR run, and in the main session, which the skill's hook already checks, it allows every call.
- Its checks are the same as in the main session: the read-only list in `scripts/block-writes.sh` and `references/rules.md`.
- The mark is a file in `$TMPDIR/drp-active/`, named by the session id. A command that touches that folder is refused, so a run cannot turn off its own checks.
- If the skill is not installed, the hook allows every call.
