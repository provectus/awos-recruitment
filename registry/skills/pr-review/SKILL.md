---
name: pr-review
description: Use when authoring a code review of a pull request — "review this PR", "do a code review on PR #N", "review my branch", "leave review comments". Works in two modes. Public mode (default) reviews someone else's GitHub PR and posts the result as a draft review for your approval. Local mode — triggered when the request says "locally", "for myself", "just my branch", or "don't post" — reviews your own working branch and writes the review to a file, with no GitHub or network calls. Finds issues by orchestrating the code-review and pr-review-toolkit plugins, drafts in a human voice with no severity badges or emojis, and gates everything on your approval. This is the reviewer's side; to respond to feedback on a PR you authored, use pr-comments-address.
---

# Author a Code Review

Produce a code review that reads like a sharp human wrote it and opens a conversation. You draft, the user steers, the user approves before anything is posted or saved.

## Modes

Decide the mode before starting the workflow, and state it in one line — the workflow branches on it.

- **public** (default): review a PR **someone else authored** on GitHub. Read the existing conversation, post the result as a **draft (pending) review** the user finalizes and submits. This is the primary use. Uses [references/github.md](references/github.md).
- **local**: review **your own working branch** for yourself. No GitHub, no network — produce the review as a file. Use this when the request says "locally", "for myself", "just my branch", "don't post", or otherwise targets in-progress work rather than someone else's PR. The built-in `/review`-style tools also do this, but less reliably and without the human-gated, house-style flow here. Uses [references/local.md](references/local.md).

**Choosing:** if the request clearly signals local (the trigger words above, or a bare branch with no PR), use local. If it clearly targets a specific remote PR (a PR URL or `owner/repo#N`), use public. If it's ambiguous, ask with `AskUserQuestion`, offering Public as the default.

This skill orchestrates existing review engines rather than reinventing analysis (both modes). It depends on two plugins and degrades gracefully if absent — see [references/analysis.md](references/analysis.md):

- **code-review** — a confidence-scored multi-agent sweep for breadth.
- **pr-review-toolkit** — specialized agents (`code-reviewer`, `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`) for depth on the dimensions a diff actually touches.

Review voice and formatting rules are in [references/house-style.md](references/house-style.md).

## Input

`args` is a PR reference (public) or a branch/base hint (local): a PR URL, `owner/repo#N`, a bare `N` inside the repo, a branch name, or empty (use the current branch). Parse what you can; if public mode needs a PR you can't resolve, ask for a PR URL.

## Workflow

```
- [ ] 1. Gather the change and context
- [ ] 2. Find issues (code-review + applicable pr-review-toolkit agents)
- [ ] 3. Reconcile (public: against existing comments; local: skip)
- [ ] 4. Draft in house style: summary, architectural notes, inline findings
- [ ] 5. Results gate: print the draft and ask — back with sources / proceed / change
- [ ] 6. Deliver (public: draft review; local: review file)
- [ ] 7. Summarize; loop on re-review (public)
```

### 1. Gather the change and context

- **public:** run `preflight`, `fetch-pr-context`, and `fetch-existing-comments` from [references/github.md](references/github.md), **before** any analysis — so you know what the PR does, what's already been said, which threads are open, and whether you've reviewed it before. Comment only on lines the PR changed.
- **local:** run `resolve-base` and `get-local-diff` from [references/local.md](references/local.md). There's no existing conversation to fetch.

### 2. Find issues

Follow [references/analysis.md](references/analysis.md) — the same engines work on a PR diff or a local diff. Run the `code-review` plugin's confidence-scored sweep and dispatch the `pr-review-toolkit` agents that match what the diff changed. Merge and dedupe into one findings list, carrying each finding's confidence and source forward. Apply the false-positive discipline there: a confident finding is not a correct finding.

### 3. Reconcile

- **public:** cross-check each finding against the existing conversation. Drop points already raised and settled; for an open thread, plan a `reply-to-thread` (agree, build on, or push back) instead of a duplicate inline comment; keep only what's new.
- **local:** nothing to reconcile.

### 4. Draft in house style

Turn the survivors into a review per [references/house-style.md](references/house-style.md). Separate the two buckets explicitly:

- **Inline findings** — anchored to `path:line`, each a plain-voice comment.
- **Architectural notes** — cross-cutting observations not tied to a single line. These go in the summary body (public) or the "Architectural notes" section of the file (local).

No severity badges, no emojis, plain citations. Order by what matters, explained in words. Draft a one-line **verdict** intent for public mode (request changes / comment / approve), but don't act on it until delivery.

### 5. Results gate

Print the complete draft — summary, architectural notes, and the inline findings (each with `path:line`) — then ask the user with `AskUserQuestion` how to proceed:

- **Proceed** — deliver as-is (post the draft review, or write the file).
- **Back findings with external sources** — before delivering, run the evidence pass: for each contestable finding, verify against a trusted source (official docs, the language/library spec, a high-signal StackOverflow or GitHub issue), attach the link in the comment, and **drop findings you can't substantiate**. Re-present, then deliver. (Needs web access; if unavailable, say so and offer to proceed without it.)
- **Change something** — take the user's edits (reword, drop, split a point into its own inline comment, re-anchor), restate, and confirm.

Respect the user's granularity choices — don't fold a distinct observation into the summary if they want it inline, and don't merge separate points. Post or write nothing before the user picks Proceed.

### 6. Deliver

- **public:** first run `find-pending-review`. If a draft already exists, apply the **never-destroy rule** (don't delete or recreate it — stop and ask; it may hold the user's own comments). Otherwise `create-draft-review` — a pending review the user submits in GitHub, the **default**. Only if the user explicitly chose to submit now, `submit-review` with the verdict. Send any approved `reply-to-thread` replies. Verify the draft's summary body actually posted.
- **local:** `write-review-file` and print the path. Nothing is sent anywhere.

Posting/saving is automated after approval; judgment is not. In public mode, if GitHub rejects a comment for an out-of-diff line, move it into the summary body and retry rather than dropping it silently.

### 7. Summarize and loop

Print what was delivered (the draft review URL and inline count, or the file path and counts) with the PR URL on its own line in public mode.

**Re-review loop (public).** This skill works under `/loop`. On a later round, repeat steps 1–6, but diff against your previous review's timestamp and treat your own prior comments as part of the conversation — raise only what's new or unaddressed, acknowledge fixes the author made, and converge toward approve. The user still approves each round; the loop automates the cadence, not the judgment.

## Boundaries

- Never post, submit, or save anything the user hasn't approved at the results gate.
- Never delete or recreate an existing pending review draft without explicit approval — it may hold the user's own comments.
- In public mode: comment only on lines in the PR diff; never resolve other people's threads; never auto-approve — the user chooses that verdict; default to a draft, not a direct submit.
- Never re-raise a settled point, or post a finding you couldn't verify — lower its confidence and drop it.
- No severity badges, no emojis, no performative praise, no "generated by" footer.
- Don't run builds, typecheck, or lint to find issues — CI covers those; flagging them is noise.
