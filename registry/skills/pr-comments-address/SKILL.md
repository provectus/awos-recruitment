---
name: pr-comments-address
description: Applies code-review feedback to the user's own pull request or merge request — triages every reviewer comment in a fresh subagent, drafts a fix or reply per item, and after the user approves the plan, edits, replies, resolves, commits, and pushes. Use when working through review feedback — "address the PR comments", "address the MR comments", "reply to CodeRabbit/Codex feedback", "resolve these review threads", "apply this review". Public mode (default) works against GitHub or GitLab. Local mode — "apply this review locally", "apply the review for myself", "apply it but don't post" — applies a local review file to the working tree and posts nothing. This is the author's side; to review someone else's PR, use pr-review.
argument-hint: "[PR URL | owner/repo#N | review-file]"
---

# Address Review Comments

Work through reviewer feedback with technical rigor over social comfort. Verify before implementing, push back when warranted, and apply or post nothing the user hasn't approved. The user decides; you draft and execute. The reasoning and incidents behind these rules are in [references/design-notes.md](references/design-notes.md) — for maintainers changing the skill, not for running it.

## Modes

Decide the mode before starting the workflow, and state it in one line.

- **public** (default): respond to feedback on a PR **the user authored**. Fetch unresolved threads and comments, then fix, reply, resolve, commit, and push. Uses the platform reference selected below.
- **local**: apply feedback that lives **on the user's machine** — a local review file (e.g. one written by pr-review's local mode) or feedback the user pastes. Edit the working tree only; nothing leaves the machine. Use this when the request says "locally", "for myself", "apply this review", "don't post", or points at a review file. Uses [references/local.md](references/local.md).

**Choosing:** if the request signals local (the trigger words above, or names a review file), use local. If it references a PR (URL or `owner/repo#N`), use public. If ambiguous, ask with `AskUserQuestion`, offering Public as the default.

## Platform (public mode)

Resolve the platform before step 1 and state it alongside the mode. Resolve in this precedence order, taking the first that answers — a later signal never overrides an earlier one:

1. the host in the PR/MR URL the user gave;
2. the host of the repo's `git remote` (`git remote get-url origin`);
3. which CLI is authenticated (`gh auth status` / `glab auth status`).

`github.com` or a GitHub Enterprise host → [references/github.md](references/github.md). `gitlab.com` or a self-managed GitLab host → [references/gitlab.md](references/gitlab.md). If none of the three resolves, ask with `AskUserQuestion` rather than guessing — the wrong reference fetches nothing or replies in the wrong place.

The workflow below is platform-agnostic and names operations (`preflight`, `checkout-pr`, `fetch-working-set`, `reply-to-thread`, `resolve-thread`); the selected reference defines them. It says "PR" throughout — on GitLab read merge request, `<NUM>` as the MR `iid`, and "thread" as discussion. Local mode needs none of this.

## Input

`$ARGUMENTS` is a PR URL or `owner/repo#N` (public), a review-file path (local), or empty. Parse what you can; if public mode can't resolve a PR, ask for a PR URL.

## Workflow

```
- [ ] 1. Gather feedback items
- [ ] 2. Triage in a fresh subagent; materialize the plan
- [ ] 3. Results gate: present the plan and ask — back with sources / proceed / change
- [ ] 4. Apply each approved item
- [ ] 5. Commit (public: + push)
- [ ] 6. Summary
```

### 1. Gather feedback items

- **public:** run `preflight`, `checkout-pr`, and `fetch-working-set` from the platform reference (selected above). `checkout-pr` handles the branch: if already **on the PR's head branch**, stay put and pull to the tip. Otherwise it defaults to an **isolated git worktree**, so the user's current branch and working tree stay untouched — check the branch out in place only if the user asked for that. If the working set is empty, say "Nothing new to address" and stop.
- **local:** run `read-feedback` from [references/local.md](references/local.md) to load the review file or pasted text into discrete items.

### 2. Triage in a fresh subagent

Triage — classifying an item as `fix` vs `pushback` — runs in a **fresh subagent** that never sees this conversation, whether or not this session touched the code. A session that wrote or debated the code is anchored to its own decisions and cannot judge its own anchoring; isolation removes the need to.

Before dispatching, fetch any off-platform discussion the request links or references — a Slack thread, meeting notes, a ticket, a design doc — since the subagent may lack the tools or auth to reach it. If reading it fails (no access, dead link, auth wall), tell the user and ask them to paste the relevant content or confirm you should proceed without it. Pass it on as source material — verbatim, or an extractive digest of what was said and decided — never as your conclusions about the feedback.

Dispatch one triage subagent with the Agent tool (`subagent_type: "general-purpose"` — a fresh context; **not** `"fork"`, which inherits this conversation and defeats the isolation). Hand it exactly:

- the PR ref and the checkout path from step 1 (local: the repo path and the review file's origin);
- every feedback item verbatim: author, `path:line`, full thread contents (public: include `originalLine` and `diffHunk` for outdated threads where `line` is null);
- the off-platform source material collected above;
- the path to [references/triage.md](references/triage.md), with the instruction to follow it — categories, drafting rules, reply voice, output format — and return the plan.

Withhold everything else — what this session intended, designed, or argued about the change. The code, the diff, and the reviewer's words are the subagent's whole world.

The subagent returns each item as `fix`, `pushback`, `dismiss-resolve`, or `clarify` (defined in [references/triage.md](references/triage.md)) with the actual reply text and, for a `fix`, a one-line description of the code change.

**Materialize the returned plan with `Write`** to `review/pr-<N>-comments-plan.md` in the repo. Create `review/` if missing and tell the user it's new; don't gitignore it automatically. A plan that exists only in the subagent's reply or in thinking does not exist for the gate — the `Write` call is the proof it does. Record the plan as the subagent returned it; if you disagree with a categorization, add a marked `session note: …` to that item instead of reclassifying, and let the user rule at the gate.

If agent dispatch is unavailable (e.g. this skill is already at the subagent nesting depth limit): triage inline following [references/triage.md](references/triage.md), and carry a one-line independence caveat into the step 6 summary (never into posted replies).

### 3. Results gate

Present the plan by printing the step 2 file's full content **as message text** — every item with its category, `path:line`, author, and the actual proposed fix and reply text, not placeholders. Then call `AskUserQuestion`, and include the plan file's path in the question itself. Only the `Write` call and the text visible in this turn count as having presented the plan; if there is no plan file, go back and write it. Session-wide brevity or compression modes govern your commentary, never the plan — a file path or a recap does not satisfy this step. Ask the user how to proceed:

- **Proceed** — apply the plan as-is.
- **Back findings with external sources** — before applying, verify the contestable items against a trusted source (official docs, the spec, a high-signal StackOverflow or GitHub issue, or — for an architectural claim about how the system fits together — the project's own sibling repos and artifacts, not just external docs), cite it in the fix/reply, and drop or downgrade items that don't hold up. Then re-present the revised plan and return to this gate.
- **Change something** — take the user's edits (apply some plan items, skip others, reword a reply — whatever the user directs), restate, and confirm.

Apply, reply, or resolve nothing before the user picks Proceed.

### 4. Apply each approved item

- **public:** per item — `Edit` for a `fix`; reply via `reply-to-thread` or `reply-to-top-level`; resolve via `resolve-thread` only for `dismiss-resolve`. Never resolve a `fix`, `pushback`, or `clarify` thread — the reviewer closes those.
- **local:** follow `apply-locally` in [references/local.md](references/local.md) — `Edit` for fixes; record pushback/clarify reasoning in the summary. No replies, no resolves.

### 5. Commit

Group changes into logically coherent commits. The subject describes the substance, not the comment (`fix(billing): jitter webhook retry backoff`, not `address review comment`). Match the project's commit style. If a pre-commit hook fails, fix the cause and make a new commit — no `--amend` or `--no-verify` unless the user explicitly asks.

- **public:** `git push` (skip if nothing was committed). Push only to the PR's head branch; never force-push.
- **local:** commit only if the user asked; never push.

**Amendments after applying.** If the user asks to change something already posted or committed — reword a reply, revise a fix, add an item — that request approves the **action**, not the **wording**. Draft the change, update the plan file, print it, `AskUserQuestion`, then apply. The step 3 gate governs every round, not just the first.

### 6. Summary

Report fixes (with commit hashes), replies and their state (public), recorded pushback/clarify notes (local), and skipped items. End with the PR URL on its own line in public mode.

## Boundaries

- No performative replies ("Great catch!", "You're absolutely right!"). State the technical fact or the next step.
- Session-wide brevity or compression modes never shrink a deliverable: the step 3 plan and step 6 summary print in full as message text.
- If the user asks to address one item and leave the rest, do exactly that.
