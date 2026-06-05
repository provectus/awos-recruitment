---
name: pr-comments-address
description: Use when responding to review comments on a GitHub pull request that YOU authored — addressing reviewer feedback, replying to CodeRabbit/Codex/human comments, resolving threads, and pushing fixes. Takes a PR URL (or owner/repo#N, or a bare number inside the repo). Checks out the branch, lists each unresolved thread with a proposed answer or fix, waits for your per-comment decision, applies the chosen response (fix-and-reply, pushback, clarify, or resolve-with-reply for mechanical bot nits), commits with substance-describing messages, pushes, and reports a summary. Fixes are committed but threads are left for the original commenter to resolve. This is the RECEIVING side of code review; to author a review of someone else's PR, use pr-review.
---

# Address PR Review Comments

Work through reviewer feedback on a GitHub pull request **you authored**. Posture: technical rigor over social comfort. Verify before implementing, push back when warranted, and never apply a fix or post a reply the user hasn't approved. The user decides; you draft and execute.

GitHub commands are named operations in [references/github.md](references/github.md): `preflight`, `checkout-pr`, `fetch-working-set`, `reply-to-thread`, `reply-to-top-level`, `resolve-thread`. Read that file when a step names one. The indirection is a platform seam — a GitLab or Azure DevOps variant swaps the reference, not this workflow.

## Input

`args` is a PR reference: a full URL `https://github.com/owner/repo/pull/N`, the short form `owner/repo#N` or `owner/repo/N`, or a bare number `N` when the current directory is the repo. Parse into `OWNER`, `REPO`, `NUM` first. If parsing fails, ask for a PR URL and stop.

## Workflow

```
- [ ] 1. Preflight and check out the PR branch
- [ ] 2. Fetch the working set of unaddressed comments
- [ ] 3. Read context and draft a response per item
- [ ] 4. Present the plan and wait for approval
- [ ] 5. Apply each approved item (edit, reply, resolve)
- [ ] 6. Commit fixes with substance-describing messages
- [ ] 7. Push
- [ ] 8. Report a summary
```

### 1. Preflight and checkout

Run `preflight` and `checkout-pr`. Bail early on auth, wrong-clone, or uncommitted-change problems as described there — don't paper over them.

### 2. Fetch the working set

Run `fetch-working-set`. If it's empty, tell the user "Nothing new to address on `<url>`" and stop.

### 3. Read context and draft responses

For each item, before drafting:

- `Read` the file at the comment's `path` around `line` — never propose a fix without seeing the surrounding code. For outdated threads `line` is often null; fall back to `originalLine` and the comment's `diffHunk`, and accept that the position is approximate.
- Treat automated reviewers (`coderabbitai`, `codex`, `bito-bot`, `sonarcloud`, `github-actions`, and similar) as suggestions to evaluate, not directives. Many of their comments are mechanical or stylistic; some are confidently wrong. Agreement is earned on the merits, not granted because a bot raised it.

Categorize each item:

| Category | When | Action |
|---|---|---|
| `fix` | A real bug or valid improvement | Edit the code and reply explaining the change. Do not resolve — leave that for the reviewer. |
| `pushback` | The suggestion is wrong, lacks context, violates YAGNI, or conflicts with a deliberate decision | Reply with technical reasoning. Do not resolve; let the reviewer respond. |
| `dismiss-resolve` | A mechanical nit or false positive with nothing for a human to confirm | Short reply explaining why it doesn't apply, then resolve. |
| `clarify` | The comment is ambiguous | Reply with a specific question. Do not edit or resolve. |

Draft a concrete response for every item — the actual reply text, and for a `fix`, a one-line description of the code change. Not a placeholder like "I'll address this."

### 4. Present and wait for approval

Output a numbered, scannable list:

```
1. [fix] src/billing/webhook.ts:142 — @alice
   "Retry loop has no jitter; will thunder on outages."
   Fix: add exponential backoff with jitter to retryWithBackoff.
   Reply: "Switched to backoff with ±25% jitter."

2. [dismiss-resolve] src/api/users.ts:58 — coderabbitai
   "Consider extracting magic number 30 to a constant."
   Reply: "30 is the documented session length from the RFC linked above; keeping it inline with that link."

3. [pushback] src/queue/worker.ts:201 — @bob
   "This should be async."
   Reply: "Intentionally sync — the caller depends on completion before the cron tick advances. Async would race the next invocation."
```

Ask which to apply as-is, change, or skip. Use `AskUserQuestion` only when the choices are small and discrete; otherwise ask in prose and wait. Do not edit, reply, or resolve anything before the user approves. If the user changes a suggestion, restate the new plan and confirm that one item.

### 5. Apply each approved item

In order, per item:

- **Edit** (for `fix` only): make the change. Re-read the file first if it changed earlier in the session.
- **Reply**: `reply-to-thread` for review threads, `reply-to-top-level` for top-level PR comments.
- **Resolve** (for `dismiss-resolve` only): `resolve-thread`. Never resolve a `fix`, `pushback`, or `clarify` thread — the reviewer owns that decision.

### 6. Commit fixes

Group changes into logically coherent commits. The subject describes the substance of the change, not the comment:

- Good: `fix(billing): jitter webhook retry backoff`
- Bad: `address review comment from @alice`
- Bad: `fix coderabbit nits`

Match the project's existing commit style if `git log` shows one; otherwise default to `<type>(<scope>): <imperative summary>`. Use a HEREDOC for multi-line messages. If a pre-commit hook fails, fix the underlying issue and make a new commit — never `--amend` or `--no-verify`.

### 7. Push

`git push`. Skip if nothing was committed (e.g., everything was replies and resolves).

### 8. Summary

```
Addressed on owner/repo#N — <PR title>

Fixes (2):
- Webhook retry jitter — src/billing/webhook.ts (abc1234)
- Worker shutdown race — src/queue/worker.ts (abc1234)

Replies (3):
- @alice: explained jitter approach (open for reviewer to resolve)
- coderabbitai: dismissed magic-number nit (resolved)
- @bob: pushback on async (awaiting response)

Skipped (1):
- @carol: needs clarification — following up after their reply

https://github.com/owner/repo/pull/N
```

End with the PR URL on its own line.

## Boundaries

- Never edit code or post a reply the user hasn't approved.
- Never resolve a `fix`, `pushback`, or `clarify` thread — only `dismiss-resolve`.
- Never push to a branch other than the PR's head branch (verify `git rev-parse --abbrev-ref HEAD` matches `headRefName`).
- Never use `--amend`, `--force`, or `--no-verify` unless the user explicitly asks.
- No performative replies ("Great catch!", "You're absolutely right!"). State the technical fact or the next step.
- If the user asks to address one item and leave the rest, do exactly that.
