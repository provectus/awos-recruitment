---
name: gh-watch-reviews
description: Use when the user wants to watch the current GitHub repo for pull requests that need their review — new PRs, explicit review requests, re-requests after new commits — e.g. "watch for incoming reviews", "check PRs needing my review", or as the recurring body of a /loop invocation. GitHub-only (gh CLI). Not for reviewing one specific known PR (invoke pr-review directly).
argument-hint: "[reconfigure | exclude: <login>, ... | include-drafts]"
---

<!-- Deliberately NOT `context: fork`: this skill needs AskUserQuestion and the Skill tool, which forked/subagent skills cannot use (same constraint as pr-review). -->

# gh-watch-reviews

## Goal

Surface open PRs in the current repo that need the **user's** review, then hand each one — sequentially, one at a time, with the user's explicit approval — to the `pr-review` skill. This skill never reviews code itself and never posts anything to GitHub; `pr-review`'s own gates control publishing.

**Dependency:** the `pr-review` skill from this registry. If it isn't available when the user picks "Review now", offer to install it first: `npx @provectusinc/awos-recruitment skill pr-review`.

## Inputs

`args` — one of:

- empty → one watch pass over the repo of the current working directory (`gh repo view --json nameWithOwner -q .nameWithOwner`)
- `reconfigure` → re-run the config interview (step 1), keep `state` untouched, then do a normal pass
- ad-hoc overrides, applied to this invocation only (config file unchanged): `exclude: <login>[, <login>…]`, `include-drafts`

Recurring use is `/loop 10m /gh-watch-reviews` — the interval is `/loop`'s native parameter; this skill never schedules its own wakeups.

## The per-repo file: `.claude/gh-watch-reviews.local.json`

One file in the watched repo holds user config and machine-managed dedup state. Read it with the Read tool; write with Write. Never ask the user to edit `state` by hand.

```json
{
  "config": {
    "exclude_bots": true,
    "exclude_authors": [],
    "include_drafts": false,
    "watch_unrequested": true
  },
  "state": {
    "123": { "sha": "<headRefOid>", "decision": "reviewed|skipped|in_progress", "via": "requested|unrequested", "at": "<iso8601>" }
  }
}
```

## Process

### 1. Load file — interview on first run

Read `.claude/gh-watch-reviews.local.json`.

**If absent** (first run in this repo), build `config` via ONE `AskUserQuestion` call:

1. Skip PRs authored by bots (dependabot, renovate, github-actions…)? — default yes
2. Also surface PRs where review was NOT explicitly requested from the user (anything open they never reviewed, except their own)? — default yes
3. Include draft PRs / extra author logins to always exclude? — multiSelect; "Other" collects free-text logins
4. Only if `git check-ignore -q .claude/gh-watch-reviews.local.json` exits non-zero: where to add the ignore entry — global gitignore (recommended, covers every repo; `git config --global core.excludesFile`, default `~/.config/git/ignore`) / repo `.gitignore` / repo `.git/info/exclude` / skip

Write the file with the answers and empty `state`, apply the chosen gitignore entry, then continue.

**If present** and args say `reconfigure`: same interview, overwrite `config` only.

### 2. In-flight guard

If any `state` entry has `decision: "in_progress"`, a review is already being worked in this session and this tick fired mid-review: **stop silently — produce no output at all.**

Exception: if the `at` timestamp is older than 2 hours, ask the user whether a review is genuinely still running; on their confirmation that it is not, clear that entry and continue.

### 3. Config awareness (once per session)

On the first pass of this conversation session (skip on first run — the interview already showed the config), print exactly one compact line so the user knows what's being watched, e.g.:

```
watching owner/repo · bots excluded · drafts excluded · unrequested PRs on
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

Union by PR number (remember which query matched — it becomes the "why"). Then filter out:

- `author.is_bot == true` when `exclude_bots`
- `author.login` in `exclude_authors` or in an ad-hoc `exclude:` arg
- `isDraft == true` unless `include_drafts` or ad-hoc `include-drafts`

For each survivor fetch the head commit: `gh pr view <n> --repo <owner/repo> --json headRefOid` (fire these in parallel, one Bash call per PR in a single message).

### 5. Dedupe against state

For each candidate with a `state[number]` entry:

- `reviewed` → suppress unless it matched the review-requested query (after a submitted review it can only reappear there, and a re-request is a deliberate human act — surface it as "re-requested after your review").
- `skipped` → **skips are sticky.** Suppress every unrequested-query match, even when the SHA changed — new commits alone never resurface a skipped PR. Only a review-requested match resurfaces it ("review requested — previously skipped"), with one exception: `via: "requested"` and the same `headRefOid` means the user already declined this exact request at this exact commit — stay suppressed until new commits arrive.

Candidates without a state entry always surface. Opportunistically prune `state` entries whose PRs are no longer open.

### 6. Nothing to review → silence

Zero candidates after dedup: **end the turn with no output whatsoever.** No "nothing new", no status line. Silence is the contract for quiet ticks.

### 7. Process candidates — one at a time

Sort oldest-first by `createdAt`. For each candidate show one line — `#N — title — @author — <why: review requested / never reviewed / new commits since your last decision>` — then `AskUserQuestion` with options:

Every state write below also records `via`: `"requested"` if the candidate matched the review-requested query, else `"unrequested"`.

- **Review now** →
  1. Write `state[number] = {sha, decision: "in_progress", via, at: now}` to the file BEFORE anything else — this is what makes a mid-review loop tick no-op (step 2).
  2. `Skill(skill="pr-review", args="<PR URL>")`. Its gates handle drafting and approval; post nothing outside it.
  3. When the review is submitted, flip the entry to `decision: "reviewed"` (same sha). If the user aborted the review, remove the entry (so it resurfaces) or mark `skipped` if they say so.
  4. **Immediately re-run discovery** (steps 4–5): PRs that appeared while reviewing are handled now, same flow. Only an empty re-scan ends the pass.
- **Skip** → write `{sha, decision: "skipped", via, at: now}`; next candidate. (Sticky: see step 5 — the PR returns only on an explicit review request, or on new commits if this skip declined an explicit request.)
- **Stop watching** → stop processing; remind the user the `/loop` is still running and how to stop it.

## Notes

- Two loops watching the same repo are unsupported — the state file has no locking; last write wins.
- Ad-hoc args never persist; only the step-1 interview writes `config`.
- Don't shortcut the state writes: the file on disk IS the dedup mechanism across ticks and sessions — an intention to write it later does not survive a loop tick.
