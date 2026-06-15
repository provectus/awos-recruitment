---
name: pr-comments-address
description: Use when working through code-review feedback to apply fixes and replies — "address the PR comments", "reply to CodeRabbit/Codex feedback", "resolve these review threads", "apply this review". Works in two modes. Public mode (default) responds to reviewer feedback on a GitHub pull request you authored — fix, reply, resolve, commit, and push. Local mode — triggered when the request says "locally", "for myself", "apply this review", or "don't post" — applies feedback from a local review file to your working tree, posting nothing to a review platform. Each item gets a proposed fix or reply for your approval first. This is the author's side; to review someone else's PR, use pr-review.
---

<!-- No `context: fork`: forked skills run as subagents, which cannot use AskUserQuestion — the per-item approval gate this skill is built around. For isolation from other work, invoke this skill in a dedicated session instead. -->

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
- [ ] 0. Bias gate: flag a contaminated session before triaging
- [ ] 1. Gather feedback items
- [ ] 2. Read context and draft a response per item
- [ ] 3. Results gate: present the plan and ask — back with sources / proceed / change
- [ ] 4. Apply each approved item
- [ ] 5. Commit (public: + push)
- [ ] 6. Summary
```

### 0. Bias gate

Knowing the work is the author's job; defending it is not. The dangerous step here is triage — classifying an item as `fix` vs `pushback` — and a session that wrote the code under feedback is anchored to its own decisions. Before anything else, inspect **this conversation** for that contamination:

- this session wrote, edited, or designed the code the feedback targets;
- this session already debated these review points (e.g. it argued for the approach a reviewer now questions).

If either applies, stop and say which one, then ask with `AskUserQuestion`:

- **Fresh session** (recommended) — you can't open one yourself, so hand off: end the turn by printing the exact invocation to carry over (`/pr-comments-address <args>`, plus any constraints from this conversation worth keeping) and tell the user to run it after `/clear` or in a new session. Don't try to simulate it with a headless `claude -p` call — that runs without the interactive gates this skill depends on.
- **Proceed** — run the workflow normally, in-session knowledge and all. Addressing feedback right from the session that pushed the PR is a common, deliberate flow; respect it.
- **Proceed, quarantine session knowledge** — triage each item from the code and the reviewer's argument as they stand, not from what you remember intending; before classifying anything `pushback`, restate the reviewer's point in its strongest form and check it against the code. Note the caveat in the step 6 summary (never in posted replies).

A clean conversation — or one whose only relation to the PR is this skill's own prior rounds — passes silently; don't ask.

### 1. Gather feedback items

- **public:** run `preflight`, `checkout-pr`, and `fetch-working-set` from [references/github.md](references/github.md). If the working set is empty, say "Nothing new to address" and stop.
- **local:** run `read-feedback` from [references/local.md](references/local.md) to load the review file or pasted text into discrete items.

### 2. Read context and draft responses

For each item, `Read` the file at the comment's `path` around `line` before drafting — never propose a fix without seeing the code. (Public: for outdated threads `line` may be null; fall back to `originalLine` and `diffHunk`.) When the item list is long, parallelize the reading, not the judgment: fan out subagents — one per item or small batch — each returning structured facts: the code around the anchor, what it currently does, whether the concern is already addressed. That's collection, not evaluation, so a small/fast model suffices if agent dispatch lets you pick one; with no agent dispatch, read inline. Categorizing and drafting stay with you — fix-vs-pushback is the judgment the bias gate protects, and replies should sound like one author. Categorize each item:

| Category | When | Action |
|---|---|---|
| `fix` | A real bug or valid improvement | Edit the code and (public) reply explaining the change. Don't resolve — leave that for the reviewer. |
| `pushback` | Wrong, missing context, YAGNI, or conflicts with a deliberate decision | (public) Reply with reasoning, don't resolve. (local) Record the reasoning for the user. |
| `dismiss-resolve` | A mechanical nit with nothing for a human to confirm | (public) Short reply, then resolve. (local) Note it and skip. |
| `clarify` | Ambiguous | (public) Reply with a specific question. (local) Record the question. |

Draft a concrete response for every item — the actual reply text and, for a `fix`, a one-line description of the code change. Not a placeholder. **Materialize the plan with `Write`** to the repo's `review/` folder (create it if missing — and when you create the folder, tell the user it's new so they decide what to do with it; don't gitignore it automatically, since a persisted review trail can be intentional): `review/pr-<N>-comments-plan.md`. A plan composed only in thinking does not exist — the `Write` call is the verifiable proof it does, and an in-repo file is one the user can open in their editor no matter what happens to the chat.

### 3. Results gate

Present the plan **as message text**, numbered and scannable — every item with its category, `path:line`, author, and the actual proposed fix and reply text, not placeholders. The user can only approve what they can read: if the plan isn't in the message, the gate is void. Any session-wide brevity or compression mode governs your commentary, never the plan — a file path or a recap does not satisfy this step.

**Pre-gate protocol — the plan is the step 2 file, not your memory.** Present it by printing the file's full content as message text, then call `AskUserQuestion` — and always include the file path in the question itself, so the user can reach the plan even if the print gets squeezed out. The documented failure here: composing the plan in thinking, then gating on "the plan is above" while the message contains nothing — your memory of having printed is not evidence; only the `Write` call and text visible in this turn are. If there is no plan file, you have no plan: go back and write it. Then ask the user how to proceed:

- **Proceed** — apply the plan as-is.
- **Back findings with external sources** — before applying, verify the contestable items against a trusted source (official docs, the spec, a high-signal StackOverflow or GitHub issue), cite it in the fix/reply, and drop or downgrade items that don't hold up. Then re-present the revised plan and return to this gate — don't apply until the user picks Proceed.
- **Change something** — take the user's edits (apply some plan items, skip others, reword a reply — whatever the user directs), restate, and confirm.

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
- In public mode: never push to a branch other than the PR's head branch; never `--amend`, `--force`, or `--no-verify` unless the user explicitly asks.
- In local mode: stay on the working tree, never post to or contact a review platform, and never push — surfacing changes to a remote is the user's call.
- No performative replies ("Great catch!", "You're absolutely right!"). State the technical fact or the next step.
- Session-wide brevity or compression modes never shrink a deliverable: the step 3 plan and step 6 summary print in full as message text.
- If the user asks to address one item and leave the rest, do exactly that.
