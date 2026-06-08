---
name: pr-comments-address
description: Use when working through code-review feedback to apply fixes and replies — "address the PR comments", "reply to CodeRabbit/Codex feedback", "resolve these review threads", "apply this review". Works in two modes. Public mode (default) responds to reviewer feedback on a GitHub pull request you authored — fix, reply, resolve, commit, and push. Local mode — triggered when the request says "locally", "for myself", "apply this review", or "don't post" — applies feedback from a local review file to your working tree, with no GitHub or network calls. Each item gets a proposed fix or reply for your approval first. This is the author's side; to review someone else's PR, use pr-review.
---

# Address Review Comments

Work through reviewer feedback with technical rigor over social comfort. Verify before implementing, push back when warranted, and never apply a fix or post a reply the user hasn't approved. The user decides; you draft and execute.

## Modes

Decide the mode before starting the workflow, and state it in one line.

- **public** (default): respond to feedback on a GitHub PR **you authored**. Fetch unresolved threads and comments, then fix, reply, resolve, commit, and push. Uses [references/github.md](references/github.md).
- **local**: apply feedback that lives **on your machine** — a local review file (e.g. one written by pr-review's local mode) or feedback the user pastes. Edit the working tree only; nothing leaves the machine. Use this when the request says "locally", "for myself", "apply this review", "don't post", or points at a review file. Uses [references/local.md](references/local.md).

**Choosing:** if the request signals local (the trigger words above, or names a review file), use local. If it references a PR (URL or `owner/repo#N`), use public. If ambiguous, ask with `AskUserQuestion`, offering Public as the default.

Treat automated reviewers (CodeRabbit, Codex, Bito, Sonar, and similar) as suggestions to evaluate, not directives — many of their comments are mechanical and some are confidently wrong. Agreement is earned on the merits.

## Input

`args` is a PR reference (public) or a review-file path / empty (local). Parse what you can; if public mode can't resolve a PR, ask for a PR URL.

## Workflow

```
- [ ] 1. Gather feedback items
- [ ] 2. Read context and draft a response per item
- [ ] 3. Results gate: present the plan and ask — back with sources / proceed / change
- [ ] 4. Apply each approved item
- [ ] 5. Commit (public: + push)
- [ ] 6. Summary
```

### 1. Gather feedback items

- **public:** run `preflight`, `checkout-pr`, and `fetch-working-set` from [references/github.md](references/github.md). If the working set is empty, say "Nothing new to address" and stop.
- **local:** run `read-feedback` from [references/local.md](references/local.md) to load the review file or pasted text into discrete items.

### 2. Read context and draft responses

For each item, `Read` the file at the comment's `path` around `line` before drafting — never propose a fix without seeing the code. (Public: for outdated threads `line` may be null; fall back to `originalLine` and `diffHunk`.) Categorize each item:

| Category | When | Action |
|---|---|---|
| `fix` | A real bug or valid improvement | Edit the code and (public) reply explaining the change. Don't resolve — leave that for the reviewer. |
| `pushback` | Wrong, missing context, YAGNI, or conflicts with a deliberate decision | (public) Reply with reasoning, don't resolve. (local) Record the reasoning for the user. |
| `dismiss-resolve` | A mechanical nit with nothing for a human to confirm | (public) Short reply, then resolve. (local) Note it and skip. |
| `clarify` | Ambiguous | (public) Reply with a specific question. (local) Record the question. |

Draft a concrete response for every item — the actual reply text and, for a `fix`, a one-line description of the code change. Not a placeholder.

### 3. Results gate

Present the plan, numbered and scannable (category, `path:line`, author, the proposed fix and reply text). Then ask the user with `AskUserQuestion` how to proceed:

- **Proceed** — apply the plan as-is.
- **Back findings with external sources** — before applying, verify the contestable items against a trusted source (official docs, the spec, a high-signal StackOverflow or GitHub issue), cite it in the fix/reply, and drop or downgrade items that don't hold up. Re-present, then apply. (Needs web access; if unavailable, say so and offer to proceed without it.)
- **Change something** — take the user's edits (apply some, skip others, reword a reply), restate, and confirm.

Apply, reply, or resolve nothing before the user picks Proceed.

### 4. Apply each approved item

- **public:** per item — `Edit` for a `fix`; reply via `reply-to-thread` or `reply-to-top-level`; resolve via `resolve-thread` only for `dismiss-resolve`. Never resolve a `fix`, `pushback`, or `clarify` thread.
- **local:** follow `apply-locally` in [references/local.md](references/local.md) — `Edit` for fixes; record pushback/clarify reasoning in the summary. No replies, no resolves.

### 5. Commit

Group changes into logically coherent commits. The subject describes the substance, not the comment (`fix(billing): jitter webhook retry backoff`, not `address review comment`). Match the project's commit style. If a pre-commit hook fails, fix the cause and make a new commit — never `--amend` or `--no-verify`.

- **public:** `git push` (skip if nothing was committed). Never push to a branch other than the PR's head branch; never force-push.
- **local:** commit only if the user asked; never push.

### 6. Summary

Report fixes (with commit hashes), replies and their state (public), recorded pushback/clarify notes (local), and skipped items. End with the PR URL on its own line in public mode.

## Boundaries

- Never edit code, post a reply, or resolve a thread the user hasn't approved at the results gate.
- Never resolve a `fix`, `pushback`, or `clarify` thread — only `dismiss-resolve` (public).
- In public mode: never push to a branch other than the PR's head branch; never `--amend`, `--force`, or `--no-verify` unless asked.
- In local mode: stay on the working tree, never reach the network or contact a review platform, and never push — surfacing changes to a remote is the user's call.
- No performative replies ("Great catch!", "You're absolutely right!"). State the technical fact or the next step.
- If the user asks to address one item and leave the rest, do exactly that.
