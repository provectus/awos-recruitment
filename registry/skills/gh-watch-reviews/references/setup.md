# First-run setup and the per-repo file

Applies on first run in a repo — `.claude/gh-watch-reviews.local.json` absent — or when the skill was invoked with `reconfigure`.

## The file

One file in the watched repo holds user config and machine-managed dedup state. `scripts/scan.sh` reads it on every scan; decision writes (see candidates.md) go through Read → modify → Write. Never ask the user to edit `state` by hand.


```json
{
  "config": {
    "exclude_bots": true,
    "exclude_authors": [],
    "include_drafts": false,
    "watch_unrequested": true,
    "review_target": "ask",
    "poll_interval_minutes": 15,
    "stale_review_hours": 2
  },
  "state": {
    "118": { "sha": "9f2c41d8b6a03e75c1d4f0a2b8e6519c3d7a0f4e", "decision": "reviewed", "via": "requested", "at": "2026-07-01T09:15:02Z" },
    "121": { "sha": "d05a7c3e91b48f26e0a3c5b7d9f2461a8c0e3b5f", "decision": "skipped", "via": "unrequested", "at": "2026-07-06T16:40:33Z" },
    "123": { "sha": "4e8b02a7c95df1360a2b8c4d9e7f1053a6b2c8d0", "decision": "in_progress", "via": "requested", "at": "2026-07-08T13:20:47Z" }
  }
}
```

A `check` block appears alongside `config` and `state` once a recurring check is set up (`--mark-armed`), and is removed when the user stops it (`--mark-stopped`). It records the cadence and when a scan last actually ran, which is the only way a later session can tell "the check stopped when that session closed" from "no check was ever set up" — the schedule itself lives in Claude Code's memory and leaves nothing behind. Machine-managed; never edit it by hand.

`sha` is the PR's `headRefOid` at decision time. `decision` is one of `reviewed`, `skipped`, `in_progress`; `via` records which search surfaced the PR (`requested` = explicit review request, `unrequested` = never-reviewed sweep). `at` is UTC ISO-8601 — write it with `date -u +%FT%TZ`, never local time: the scanner's staleness math depends on it.

`review_target` decides where a surfaced PR's review runs: `"ask"` — one question per candidate (here / new tab / skip / stop); `"here"` — always inline in the watch session, started without asking; `"new-tab"` — always a separate TUI session (references/review-target.md), launched without asking.

The two timing knobs:

- `poll_interval_minutes` (default 15) — how often the recurring check asks GitHub. A quiet tick is one Bash call and one printed line, so this trades new-PR latency against a little context and GitHub API traffic. Invoking with `loop <interval>` overrides it for that invocation only.
- `stale_review_hours` (default 2) — how long one review may hold the in-flight lock before the user gets asked about it. An `in_progress` entry pauses the whole scan, and the scanner clears it by itself when the review is submitted or the PR closes — but a review that died (closed tab, killed session) leaves nothing to clear, so the watch would stay paused forever. Past this many hours the scan returns `stale_in_progress` and asks instead. Set it longer than a review realistically takes: too short nags mid-review, too long is a silent watch.

How the scanner uses `state` (for awareness — the rules live in the script, not in your judgement):

- `reviewed` → suppressed unless the author re-requests review (a deliberate human act).
- `skipped` → sticky: new commits alone never resurface it; only an explicit review request does — and if the skip itself declined an explicit request at the same head SHA, only new commits since then.
- `in_progress` → the whole scan is a no-op (`status: "in_review"`) until the review completes. The scanner resolves these itself from GitHub (a review submitted after `at` flips the entry to `reviewed`; a closed/merged PR prunes it) — that's how reviews running in separate sessions finish without ever touching this file. An entry it can't resolve that is older than `stale_review_hours` comes back as `status: "stale_in_progress"` for the user to resolve.

## The interview

Build `config` via TWO `AskUserQuestion` calls. First call — what to watch and where to review:

1. Skip PRs authored by bots (dependabot, renovate, github-actions…)? — default yes
2. Also surface PRs where review was NOT explicitly requested from the user (anything open they never reviewed, except their own)? — default yes
3. Include draft PRs / extra author logins to always exclude? — multiSelect; "Other" collects free-text logins
4. Where should reviews run? — Ask each time (recommended) / Always here, in this session / Always in a new tab (separate session) → `review_target`

Second call — the two timings, each of which needs its explanation in the question text, because neither is guessable:

5. How often should I check GitHub? — `Every 15 minutes (recommended)` / `Every 5 minutes` / `Every hour` → `poll_interval_minutes`. Explain: a check with nothing to report is one Bash call and one printed line, so a shorter interval buys lower latency on a new PR and costs a little context and GitHub API traffic.
6. A review is handed off and then never finishes — the tab was closed, the session died. How long before I ask you about it? — `After 2 hours (recommended)` / `After 1 hour` / `After 8 hours` → `stale_review_hours`. Explain: while a review is marked in progress the watch is paused so it won't re-surface the PR you're on, and that pause normally ends by itself the moment the review is submitted or the PR is merged. Nothing can see whether a review session is still alive, so this timeout is the only thing that distinguishes "still working" from "gone" — after it, the watch asks you instead of staying quiet indefinitely.

Then one housekeeping step for the file this interview is about to create — it shouldn't be committed:

```bash
git check-ignore -q .claude/gh-watch-reviews.local.json && echo covered || echo needs-ignore
```

Only on `needs-ignore`, ask where to add the entry — use the glob `.claude/gh-watch-reviews.local.*` rather than the exact filename, so anything this skill adds later is covered too — global gitignore (recommended, covers every repo; `git config --global core.excludesFile`, default `~/.config/git/ignore`) / repo `.gitignore` / repo `.git/info/exclude` / skip

Write the file with the answers and empty `state`, apply the chosen gitignore entry, then continue with the invoked pass.

**On `reconfigure`:** same interview, overwrite `config` only — `state` stays untouched.

**Migration** (config written by an older skill version): SKILL.md step 1 asks only for the keys that are missing — `review_target` (question 4), `poll_interval_minutes` and `stale_review_hours` (questions 5–6) — and persists them. Never re-run the full interview for a migration.
