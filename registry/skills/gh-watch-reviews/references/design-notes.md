# Design notes

For maintainers editing this skill. Nothing here is needed to run a pass: SKILL.md states the rules, this file records why they are what they are, so nobody "improves" them into something expensive.

## No `context: fork`

The skill needs `AskUserQuestion` and the `Skill` tool (to hand off to `pr-review` and to arm `/loop`), which forked/subagent skills cannot use. Same constraint as `pr-review`.

## Why the recurring body is shaped like that

- **The scanner returns `line`, ready to print.** A quiet tick is one Bash call and one echo — nothing for the model to compose, and no timestamp to round, reformat or invent.
- **SKILL.md is not part of the tick.** `disable-model-invocation: true` keeps the skill off the model's auto-invocation path, so a tick with work reports the PRs and hands back to the user, who starts the pass by typing `/gh-watch-reviews`. The earlier `/loop /gh-watch-reviews` form re-injected the whole SKILL.md every tick.
- **Nothing starts without the user typing the command.** A pass writes config, a gitignore entry, and — depending on `config.review_target` — launches reviews, so it never begins from the model's own judgement about context.
- **A failed check needs no special handling.** The tick reports it and the next tick simply runs, which is why this form shrugs off the scan that fires after the machine wakes, before Wi-Fi is back.
- **`${CLAUDE_SKILL_DIR}` does the path work.** Claude Code expands it when SKILL.md loads, so the `/loop` body carries the real absolute path without the model working it out, and the `allowed-tools` grant matches the same expanded command, so the first scan runs without a permission prompt. Reference files are not expanded, so they say "the path SKILL.md gave you" rather than relying on the variable.

## Why `--mark-armed` exists

The `/loop` schedule lives in Claude Code's memory and leaves nothing behind. Without a marker in the state file, a check that stopped when its session closed looks exactly like one that was never set up, and that silence reads as "no PRs need your review" — the failure this skill exists to prevent. Every scan stamps the marker, so a running check stays fresh by itself.

## Not a daemon

Nothing checks while Claude Code is not running. That costs nothing real — no review can happen then either. Polling that continues with no session at all is a launchd agent, not this skill.

## Token figures

Deliberately absent from SKILL.md and setup.md. The one measurement on record, taken on one build before the figures were removed: the re-injecting `/loop /gh-watch-reviews` form cost roughly 4.4k tokens a tick, the thin body roughly 950. Any edit to the loop body or the scanner output changes both numbers and nothing re-measures them, so describe a quiet tick as "one Bash call and one printed line" and re-measure before quoting a figure anywhere.
