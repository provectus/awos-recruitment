---
name: gh-watch-reviews
description: Use when the user wants to watch the current GitHub repo for pull requests that need their review — new PRs, explicit review requests, re-requests after new commits — e.g. "watch for incoming reviews", "check PRs needing my review", or as the recurring body of a /loop invocation. GitHub-only (gh CLI). Not for reviewing one specific known PR (invoke pr-review directly).
argument-hint: "[reconfigure | exclude: <login>, ... | include-drafts]"
---

<!-- Deliberately NOT `context: fork`: this skill needs AskUserQuestion and the Skill tool, which forked/subagent skills cannot use (same constraint as pr-review). -->

# gh-watch-reviews

## Goal

Surface open PRs in the current repo that need the **user's** review and hand each to the `pr-review` skill, one at a time. The **first pass in a repo** triages the pre-existing backlog with the user's approval per PR; **every later pass auto-starts the review** of a newly-appeared PR without asking — that is the whole point of watching. This skill never reviews code itself and never posts anything to GitHub; `pr-review`'s own gates control publishing.

**Dependency:** the `pr-review` skill from this registry. If it isn't available when the user picks "Review now", offer to install it first: `npx @provectusinc/awos-recruitment skill pr-review`.

## Inputs

`args` — one of:

- empty → one watch pass over the repo of the current working directory (`gh repo view --json nameWithOwner -q .nameWithOwner`)
- `reconfigure` → re-run the config interview (step 1), keep `state` untouched, then do a normal pass
- ad-hoc overrides, applied to this invocation only (config file unchanged): `exclude: <login>[, <login>…]`, `include-drafts`

Recurring use is `/loop 10m /gh-watch-reviews` — the interval is `/loop`'s native parameter; this skill never schedules its own wakeups.

## The per-repo file: `.claude/gh-watch-reviews.local.json`

One file in the watched repo holds user config and machine-managed dedup state. Read it with the Read tool; write with Write. Never ask the user to edit `state` by hand.

Read the file **once per session** (first pass); later ticks reuse the in-context copy — this session is the file's only writer, and config changes go through `reconfigure`. Writes still go to disk immediately (they must survive the session), but a tick that decides nothing writes nothing. If the session has been compacted since the last read — the file's contents no longer sit verbatim in context — re-read it from disk before trusting anything: a summary's recollection of `state` is not `state`.

```json
{
  "config": {
    "exclude_bots": true,
    "exclude_authors": [],
    "include_drafts": false,
    "watch_unrequested": true
  },
  "state": {
    "118": { "sha": "9f2c41d8b6a03e75c1d4f0a2b8e6519c3d7a0f4e", "decision": "reviewed", "via": "requested", "at": "2026-07-01T09:15:02Z" },
    "121": { "sha": "d05a7c3e91b48f26e0a3c5b7d9f2461a8c0e3b5f", "decision": "skipped", "via": "unrequested", "at": "2026-07-06T16:40:33Z" },
    "123": { "sha": "4e8b02a7c95df1360a2b8c4d9e7f1053a6b2c8d0", "decision": "in_progress", "via": "requested", "at": "2026-07-08T13:20:47Z" }
  }
}
```

`sha` is the PR's `headRefOid` at decision time. `decision` is one of `reviewed`, `skipped`, `in_progress`; `via` records which step-4 query surfaced the PR. `at` is UTC ISO-8601 — write it with `date -u +%FT%TZ`, never local time: it feeds the step-2 staleness comparison, which must survive timezone changes.

## Process

### 1. Load file — interview on first run

Read `.claude/gh-watch-reviews.local.json`.

**If absent** (first run in this repo), build `config` via ONE `AskUserQuestion` call:

1. Skip PRs authored by bots (dependabot, renovate, github-actions…)? — default yes
2. Also surface PRs where review was NOT explicitly requested from the user (anything open they never reviewed, except their own)? — default yes
3. Include draft PRs / extra author logins to always exclude? — multiSelect; "Other" collects free-text logins
4. Housekeeping for the file this interview is about to create — it shouldn't be committed, so this is the moment to pick where to ignore it. Only if `git check-ignore -q .claude/gh-watch-reviews.local.json` exits non-zero: where to add the ignore entry — global gitignore (recommended, covers every repo; `git config --global core.excludesFile`, default `~/.config/git/ignore`) / repo `.gitignore` / repo `.git/info/exclude` / skip

Write the file with the answers and empty `state`, apply the chosen gitignore entry, then continue.

**If present** and args say `reconfigure`: same interview, overwrite `config` only.

### 2. In-flight guard

If any `state` entry has `decision: "in_progress"`, a review is already being worked in this session and this tick fired mid-review: **stop silently — produce no output at all.**

Exception: if the `at` timestamp is older than 2 hours, ask the user whether a review is genuinely still running; on their confirmation that it is not, clear that entry and continue.

### 3. Config awareness (once per session)

On the first pass of this conversation session (skip on first run — the interview already showed the config), print exactly one compact line so the user knows what's being watched, e.g.:

```
gh-watch-reviews: watching owner/repo · bots excluded · drafts excluded · unrequested PRs on
```

Later ticks in the same session never repeat it.

### 4. Discover candidates

On the first pass of a session, preflight with `gh auth status`; if unauthenticated, tell the user to run `gh auth login` and stop.

Run both searches (skip the second when `watch_unrequested` is false):

```bash
# explicit requests and re-requests — GitHub clears this when the user submits a review,
# so reappearance here means the author re-requested: an intended re-review
gh search prs --review-requested=@me --state open --repo <owner/repo> \
  --json number,title,author,url,isDraft,createdAt --limit 50

# PRs the user never reviewed, excluding their own
gh search prs --state open --repo <owner/repo> \
  --json number,title,author,url,isDraft,createdAt --limit 50 \
  -- -reviewed-by:@me -author:@me
```

Run both searches in ONE combined Bash call, and append `date '+%F %T %Z'` to that same call so the pass captures an accurate check time (to the second) without an extra tool call — on a quiet tick this keeps the entire pass to a single tool call.

Guard the result before trusting it: if the combined call exits nonzero, or either search returns anything that isn't a JSON array (an auth/network failure, a rate-limit banner, an empty string), treat it as an error — emit one line `gh-watch-reviews: search failed — <reason>` and stop the tick. Never continue to dedup or the heartbeat on a failed or malformed search: a silent "nothing needs review" is the one outcome a watch must never produce from a failure.

Union by PR number (remember which query matched — it becomes the "why"). Then filter out:

- `author.is_bot == true` when `exclude_bots`
- `author.login` in `exclude_authors` or in an ad-hoc `exclude:` arg
- `isDraft == true` unless `include_drafts` or ad-hoc `include-drafts`

### 5. Dedupe against state

For each candidate with a `state[number]` entry — every rule except one needs no extra API call:

- `reviewed` → suppress unless it matched the review-requested query (after a submitted review it can only reappear there, and a re-request is a deliberate human act — surface it as "re-requested after your review").
- `skipped` → **skips are sticky.** Suppress every unrequested-query match, even if new commits arrived — new commits alone never resurface a skipped PR. Only a review-requested match resurfaces it ("review requested — previously skipped"), with one exception: when the entry is `via: "requested"`, fetch the current head (`gh pr view <n> --repo <owner/repo> --json headRefOid`) — the same `headRefOid` as recorded means the user already declined this exact request at this exact commit, stay suppressed; a different one means new commits, surface as "new commits since your last decision".

Candidates without a state entry always surface. Fetch `headRefOid` only where the rule above demands it — surfaced candidates get their SHA at decision time (step 7), so a quiet tick fetches nothing. Prune `state` entries whose PRs are closed/merged when you're writing state anyway.

### 6. Nothing to review → one heartbeat line

Zero candidates after a successful search + dedup (step 4 already stopped the tick on any search failure, so reaching here means a real empty scan): **end the turn with exactly ONE compact heartbeat line and nothing else.** It carries the check time from step 4's `date` output, to the second, so a scrolled-back loop history shows the watch is alive and when it last looked:

```
gh-watch-reviews: owner/repo · no PRs need your review · checked 2026-07-08 13:20:47 PDT
```

Use the real timestamp from that tool output verbatim — never invent, round, or approximate one, and never omit it (an invented time is worse than none). This single line IS the entire quiet-tick deliverable: no second line, no summary of which queries ran or what was checked, and no text wrapped in tags — a `<system-reminder>`-style block you write yourself is ordinary output the user sees verbatim. One line, then stop.

### 7. Process candidates — one at a time

Sort oldest-first by `createdAt`. Every state write below records `via` (`"requested"` if the candidate matched the review-requested query, else `"unrequested"`) and `sha` — fetch it now if not already known: `gh pr view <n> --repo <owner/repo> --json headRefOid`.

**Whether to ask before reviewing depends on the pass — this is decided per pass, not per PR:**

- **First run in the repo** (the step-1 interview just ran this pass, so every candidate is pre-existing backlog the user never opted into): triage it so you don't auto-review history. For each candidate show one line — `#N — title — @author — <why: review requested / never reviewed>` — then `AskUserQuestion` (Review now / Skip / Stop watching) and act per the actions below. **This is the only pass that asks.**
- **Every later pass** (the config file already existed when the pass started — any session, any `/loop` tick): a surfaced candidate is exactly what the watch exists to catch. **Start its review immediately — no `AskUserQuestion`.** Show the one-line `#N — …` for visibility, then run the **Review now** action directly. Auto-starting can't publish anything unattended: `pr-review`'s own gates still control drafting and delivery.

Actions:

- **Review now** →
  1. Write `state[number] = {sha, decision: "in_progress", via, at: now}` to the file BEFORE anything else — this is what makes a mid-review loop tick no-op (step 2).
  2. `Skill(skill="pr-review", args="<PR URL>")`. Its gates handle drafting and approval; post nothing outside it. If the handoff fails to start — `pr-review` isn't installed and the user declines the install, or the install fails — remove the `in_progress` entry immediately and move to the next candidate: a failed start must never leave the PR locked for step 2's two-hour window.
  3. When the review is submitted, flip the entry to `decision: "reviewed"` (same sha). If the user aborted the review, remove the entry (so it resurfaces) or mark `skipped` if they say so.
  4. **Immediately re-run discovery** (steps 4–5): PRs that appeared while reviewing are handled now, same flow. Only an empty re-scan ends the pass.
- **Skip** (first-run triage only) → write `{sha, decision: "skipped", via, at: now}`; next candidate. (Sticky: see step 5 — the PR returns only on an explicit review request, or on new commits if this skip declined an explicit request.)
- **Stop watching** (first-run triage only) → stop processing; remind the user the `/loop` is still running and how to stop it.

## Notes

- Two loops watching the same repo are unsupported — the state file has no locking; last write wins.
- Ad-hoc args never persist; only the step-1 interview writes `config`.
- Don't shortcut the state writes: the file on disk IS the dedup mechanism across ticks and sessions — an intention to write it later does not survive a loop tick.
