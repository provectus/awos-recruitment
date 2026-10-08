# Processing candidates

Applies when a scan returned `status: "candidates"`. The scanner already filtered, deduped, and sorted oldest-first — process the list in the given order, one at a time.

Every state write below is Read → modify → Write of `.claude/gh-watch-reviews.local.json` — always read the file from disk first (another write may have happened since you last saw it, including by the scanner itself), and write immediately: the file on disk IS the dedup mechanism across ticks and sessions; an intention to write it later does not survive a loop tick. Each entry records the candidate's `why` origin as `via` (`"requested"` for "review requested" / "re-requested…" / "…previously skipped" / "new commits…", else `"unrequested"`), `sha` — fetch it at decision time: `gh pr view <n> --repo <owner/repo> --json headRefOid` — and `at`, which is ALWAYS the verbatim output of `date -u +%FT%TZ` (UTC ISO-8601, e.g. `2026-07-28T13:24:21Z`): the scanner parses it for staleness and completion detection, and any other format makes the entry go stale instantly.

## Per candidate: ask or auto, per `config.review_target`

For each candidate show one line — `#N — title — @author — <why from the scanner>`. Then:

- `review_target: "ask"` → ONE `AskUserQuestion`:
  - **Review here** — run the review in this session, inline.
  - **Review in new tab** — hand the review to a separate TUI session (see references/review-target.md).
  - **Skip** — don't review; sticky (see setup.md).
  - **Stop watching** — end the pass.
- `review_target: "here"` → run the **Review here** action directly, no question.
- `review_target: "new-tab"` → run the **Review in new tab** action directly, no question.

The auto modes never publish anything unattended — `pr-review`'s own gates still control drafting and delivery — and the user can always interrupt or say "skip this one" (then apply the Skip action).

## Actions

- **Review here** →
  1. Write `state[number] = {sha, decision: "in_progress", via, at: <date -u +%FT%TZ>}` BEFORE anything else — this is what makes a mid-review scan a no-op.
  2. `Skill(skill="pr-review", args="<PR URL>")`. Its gates handle drafting and approval; post nothing outside it. If the handoff fails to start — `pr-review` isn't installed and the user declines the install, or the install fails — remove the `in_progress` entry immediately and move to the next candidate: a failed start must never leave the PR locked behind the in-flight guard until `config.stale_review_hours` elapses.
  3. When the review is submitted, flip the entry to `decision: "reviewed"` (same sha). If the user aborted the review, remove the entry (so it resurfaces) or mark `skipped` if they say so.
  4. **Immediately re-scan** (`scan.sh --once`, same flags as the pass): PRs that appeared while reviewing are handled now, same flow. Only an empty or `in_review` re-scan ends the pass.
- **Review in new tab** →
  1. Write `state[number] = {sha, decision: "in_progress", via, at: <date -u +%FT%TZ>}` BEFORE launching, same as above.
  2. Launch per references/review-target.md. If the launch itself fails (not the fallback — the fallback "launch" is printing the command), remove the entry and ask the user how to proceed.
  3. Move to the **next candidate immediately** — never wait for the external session. The scanner tracks its completion from GitHub (review-target.md § Completion tracking).
- **Skip** (asked mode, or the user says so) → write `{sha, decision: "skipped", via, at: <date -u +%FT%TZ>}`; next candidate. (Sticky — see setup.md.)
- **Stop watching** (asked mode, or the user says so) → stop processing, tell the user how to end the recurring check itself (it is a `/loop`, so stopping the loop stops the checks), and clear the marker so no later pass reports the check as stopped-unexpectedly:

  ```bash
  ${CLAUDE_SKILL_DIR}/scripts/scan.sh --mark-stopped   # the same scan.sh path SKILL.md gave you
  ```
While you're writing state anyway, prune entries whose PRs are closed or merged.

## After the pass

Just end the turn — the next scheduled tick runs on its own. Entries left `in_progress` by new-tab launches keep the scanner in a paused `in_review` state until those reviews are submitted; it resumes by itself.
