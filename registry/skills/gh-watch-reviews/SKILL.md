---
name: gh-watch-reviews
description: Use when the user wants to watch the current GitHub repo for pull requests that need their review — new PRs, explicit review requests, re-requests after new commits — e.g. "watch for incoming reviews", "check PRs needing my review", or to set up a recurring check. GitHub-only (gh CLI). Not for reviewing one specific known PR (invoke pr-review directly).
argument-hint: "[loop [interval] | reconfigure | exclude: <login>, ... | include-drafts]"
disable-model-invocation: true
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/scan.sh *)
---

# gh-watch-reviews

## Goal

Surface open PRs in the current repo that need the **user's** review and hand each to the `pr-review` skill, one at a time. This skill never reviews code itself and never posts anything to GitHub; `pr-review`'s own gates control publishing.

All discovery, filtering, and dedup logic is deterministic and lives in `${CLAUDE_SKILL_DIR}/scripts/scan.sh` — a pass costs one Bash call, and you act only on its JSON verdict. Don't re-derive its decisions.

**Requires:** `gh` (authenticated), `jq`, the `pr-review` skill from this registry, and — for Recurring mode only — the bundled `/loop` skill (missing when `disableBundledSkills` removes it). If `pr-review` isn't available when a review should start, offer to install it first: `npx @provectusinc/awos-recruitment skill pr-review`.

## Inputs

Input: `$ARGUMENTS` — one of:

- empty → one pass over the repo of the current working directory (`gh repo view --json nameWithOwner -q .nameWithOwner`)
- `loop [interval]` → set up the recurring check (see Recurring mode). `interval` accepts whole minutes or hours (`5m`/`15m`/`1h`; one minute is the floor, since the schedule's granularity is a minute) and overrides `config.poll_interval_minutes` for this invocation only
- `reconfigure` → re-run the config interview (references/setup.md), keep `state` untouched, then do a normal pass
- ad-hoc overrides, applied to this invocation only: `exclude: <login>[, <login>…]` → `--exclude <login>` per login; `include-drafts` → `--include-drafts`

The recurring form is `loop` (Recurring mode). If this invocation IS a `/loop` tick whose body re-injects this whole file — the expensive shape — complete the pass normally and, once per session, say so in one line and give the thin body from Recurring mode as the replacement.

## One pass

1. On the first pass of this conversation session only: resolve the repo (`gh repo view --json nameWithOwner -q .nameWithOwner`) and Read `.claude/gh-watch-reviews.local.json`. If the file is absent, this is the first run — read references/setup.md and follow it (interview → write file). Otherwise: if any of `config.review_target`, `config.poll_interval_minutes`, `config.stale_review_hours` is missing (config from an older skill version), ask ONLY for those, in one `AskUserQuestion` call, using the wording in references/setup.md § The interview (questions 4–6), and write the answers into `config` before anything else. Then print exactly one compact line so the user knows what's being watched — with the real `owner/repo`, so resolve it before printing — e.g. `gh-watch-reviews: watching owner/repo · bots excluded · drafts excluded · unrequested PRs on`. Later passes in the same session skip this step entirely — no re-read, no repeated line; a quiet later tick is exactly one tool call (the scanner reads the file itself, and its "state file not found" error is the first-run signal if the file has vanished).
2. Run the scanner — ONE Bash call:

```bash
${CLAUDE_SKILL_DIR}/scripts/scan.sh --once
```

3. Act on the JSON `status`:

- `error` (exit 1) → emit exactly one line — `gh-watch-reviews: search failed — <message>` — and stop the pass. Never continue past a failure: a silent "nothing needs review" is the one outcome a watch must never produce from an error. The JSON's `retryable` says which kind it was: `true` is a network or GitHub blip — the next scheduled tick will simply try again, so say what failed and stop; `false` needs the user (auth above all), so say what it needs.
- `in_review` → a review handed off earlier is still being worked and this tick fired mid-review: **stop silently — produce no output at all.**
- `stale_in_progress` → an `in_progress` entry has held the in-flight lock longer than `config.stale_review_hours` and the scanner could not resolve it from GitHub (no submitted review, PR still open). Quote the returned `held_for_over_hours` — never a number of your own — and ask the user whether that review is genuinely still running; if not, remove the listed entries from `state` (Read → modify → Write) and re-run the pass from step 2.
- `empty` → end the turn with exactly ONE compact heartbeat line and nothing else, using the returned `checked_at` verbatim (never invent, round, or approximate a timestamp): `gh-watch-reviews: owner/repo · no PRs need your review · checked <checked_at>`. This single line IS the entire quiet-tick deliverable — no second line, no summary of what was checked.
- `candidates` → read references/candidates.md and process them as it directs.

Independently of `status`, if the JSON carries **`check_stale: true`**, a recurring check was set up in this repo and has not run for more than twice its interval — almost always because the session that owned it was closed, since the schedule lives in memory and leaves nothing behind. Add exactly one line after whatever the status called for, quoting the returned values: `gh-watch-reviews: recurring check (every <check_interval_minutes>m) hasn't run since <check_last_at> — run /gh-watch-reviews loop to start it again`. It is the one case where a quiet pass gets a second line, because silence from a check that stopped is indistinguishable from silence meaning "nothing to review" — which is the failure this skill exists to prevent.

## Recurring mode

Run step 1 of "One pass" to resolve the repo, then invoke the `loop` skill with **this body verbatim** — substituting only the interval (`config.poll_interval_minutes` minutes, or the one given in the input):

```
Skill(skill="loop", args="15m Run this and nothing else: ${CLAUDE_SKILL_DIR}/scripts/scan.sh --once
Then: if the JSON has a \"line\", reply with exactly that line and nothing else. If \"status\" is \"candidates\", reply with one line per entry — `#<number> <title> (@<author>) — <why>` — then one final line: `run /gh-watch-reviews to start`. If \"status\" is \"stale_in_progress\", reply with one line naming the numbers in \"prs\" and the returned \"held_for_over_hours\", then `run /gh-watch-reviews`. Otherwise reply nothing.")
```

Then record that a check is meant to be running here — one Bash call — and say in one line what is being watched and how often. Convert an hour-form interval to minutes first (`1h` → `60`); `--mark-armed` accepts whole minutes only:

```bash
${CLAUDE_SKILL_DIR}/scripts/scan.sh --mark-armed <interval in whole minutes>
```

Rules for the recurring form:

- Keep the body exactly as written. A quiet tick is one Bash call and one printed line; the tick never loads this file. Never put `/gh-watch-reviews` in a `/loop` body.
- A tick only reports. The user starts a pass by typing `/gh-watch-reviews`; never start one from a tick's output.
- A failed tick needs no handling; the next tick simply runs.
- Always run `--mark-armed` after arming; without it, a check that stopped is indistinguishable from one that was never set up.
- The schedule is in-memory and belongs to the session that created it: closing Claude Code ends it, and it has to be set up again.

## Notes

- Two recurring checks on the same repo are unsupported — the state file has no locking; last write wins.
- Nothing checks while Claude Code is not running; nothing here is a daemon.
- Ad-hoc args never persist; only the setup interview writes `config`.
- Read references only when the pass needs them, not preemptively: first run, `reconfigure`, or state semantics → references/setup.md; a `candidates` verdict → references/candidates.md; new-tab launches (cmux/tmux detection, fallback command) → references/review-target.md; why the rules above are what they are (the `/loop` body shape, no `context: fork`) → references/design-notes.md, for maintainers editing this skill — never needed for a pass.
