---
name: pr-review
description: Use when authoring a code review OF SOMEONE ELSE'S GitHub pull request — "review this PR", "do a code review on PR #N", "leave review comments", "give feedback on their changes". Takes a PR URL (or owner/repo#N, or a bare number inside the repo). Reads existing comments first and reacts to them, finds issues with the code-review plugin and the pr-review-toolkit specialized agents, reformats findings into a human-toned review with no severity badges or emojis, shows you the full draft for per-finding approval and a verdict (approve / request changes / comment), then posts it as one PR review with inline comments. Supports pushback, discussion, and re-review loops. This is the GIVING side of code review; to respond to feedback on your OWN PR, use pr-comments-address. Works best with the code-review and pr-review-toolkit plugins installed.
---

# Author a PR Review

Review a GitHub pull request **someone else authored**. The user is the reviewer of record: you draft, they steer, they approve every word before it posts. Aim for a review that reads like a sharp human wrote it and that opens a conversation — not an automated pass that another agent will rubber-stamp.

This skill orchestrates existing review engines rather than reinventing analysis. It depends on two plugins (degrades gracefully if absent — see [references/analysis.md](references/analysis.md)):

- **code-review** — a confidence-scored multi-agent sweep for breadth.
- **pr-review-toolkit** — specialized agents (`code-reviewer`, `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`, `code-simplifier`) for depth on the dimensions a given diff actually touches.

GitHub commands are named operations in [references/github.md](references/github.md): `preflight`, `fetch-pr-context`, `fetch-existing-comments`, `post-review`, `reply-to-thread`. Review voice and formatting rules are in [references/house-style.md](references/house-style.md).

## Input

`args` is a PR reference: a full URL, `owner/repo#N`, or a bare `N` inside the repo. Parse into `OWNER`, `REPO`, `NUM`. If parsing fails, ask for a PR URL and stop.

## Workflow

```
- [ ] 1. Preflight
- [ ] 2. Read the PR and its existing conversation (first)
- [ ] 3. Find issues (code-review plugin + applicable pr-review-toolkit agents)
- [ ] 4. Reconcile against the existing conversation
- [ ] 5. Draft the review in house style
- [ ] 6. Present for per-finding approval and a verdict
- [ ] 7. Post one atomic review
- [ ] 8. Summarize; loop on re-review
```

### 1. Preflight

Run `preflight`. You are reviewing, not authoring — don't check out the branch or modify files.

### 2. Read the PR and its conversation first

Run `fetch-pr-context` (metadata and diff) and `fetch-existing-comments` (reviews, threads, top-level comments) **before** any analysis, so you know what the PR is trying to do, every point already raised, which threads are still open, and whether you've reviewed this PR before. The review surface is **only the lines this PR changed** — never comment on unchanged code.

### 3. Find issues

Follow [references/analysis.md](references/analysis.md): run the `code-review` plugin's confidence-scored sweep and dispatch the `pr-review-toolkit` agents that match what the diff changed (e.g. `pr-test-analyzer` when tests changed, `silent-failure-hunter` when error handling changed, `type-design-analyzer` when types changed, `comment-analyzer` when comments/docs changed, `code-reviewer` always). Merge and dedupe into one findings list, carrying each finding's confidence and source forward. Apply the false-positive discipline in that reference — a confident finding is not a correct finding.

### 4. Reconcile against the existing conversation

Before drafting, cross-check each finding against what's already been said:

- Already raised and settled → drop it.
- Already raised, thread still open → don't open a new inline comment; plan a `reply-to-thread` that agrees, builds on it, or pushes back.
- New and unraised → candidate inline finding.

### 5. Draft in house style

Turn the survivors into a review per [references/house-style.md](references/house-style.md): a short summary body plus inline comments in plain human voice — no severity badges, no emojis, plain citations. Order by what actually matters, explained in words rather than labels. Draft a **verdict** with a one-line reason: request changes if there's a real blocker, comment if it's non-blocking or you're unsure, approve only when you'd genuinely sign off.

### 6. Present for approval

Show the complete draft, scannable:

```
Review of owner/repo#N — <title>   (proposed verdict: request changes)

Summary:
<summary paragraph>

Inline (3):
1. src/billing/webhook.ts:142 — retry loop has no ceiling → thundering herd. [new]
   "<comment text in house voice>"
2. src/api/jobs.ts:88 — status query param trusted without validation. [new]
   "<comment text>"
3. reply to @alice on config.ts:20 — agree and add the shadowing point. [reply]
   "<reply text>"

Dropped (already covered): 1 (coderabbit nit, settled in thread).
```

Ask which inline comments to keep, edit, or drop; whether to send each reply; and confirm or change the verdict (use `AskUserQuestion` for the verdict). Post nothing before approval. If the user rewrites a comment, restate it and confirm that one item.

### 7. Post one atomic review

Build the approved set and run `post-review` (a single PR review = summary + inline comments + verdict). Send any approved replies via `reply-to-thread`. Posting is automated after approval; judgment is not. If GitHub rejects a comment for an out-of-diff line, move it into the summary body and retry rather than dropping it silently.

### 8. Summarize and loop

```
Posted review on owner/repo#N — verdict: request changes
Inline comments: 3 (2 new, 1 reply)
Dropped as already covered: 1
https://github.com/owner/repo/pull/N
```

**Re-review loop.** This skill works under `/loop`. On a later round, repeat steps 2–7, but diff against your previous review's timestamp and treat your own prior comments as part of the conversation — raise only what's new or unaddressed, and acknowledge fixes the author made. Converge toward approve; don't invent findings to look busy. The user still approves each round — the loop automates the cadence, not the judgment.

## Boundaries

- Never post a comment, reply, or verdict the user hasn't approved.
- Never comment on lines outside the PR diff.
- Never resolve other people's threads — you're the reviewer, not the author.
- Never auto-approve; the user must explicitly choose that verdict.
- Never re-raise a settled point, or post a finding you couldn't verify — lower its confidence and drop it.
- No severity badges, no emojis, no performative praise, no "generated by" footer.
- Don't run builds, typecheck, or lint to find issues — CI covers those; flagging them is noise.
