---
name: pr-review
description: Use when authoring a code review of a pull request — "review this PR", "do a code review on PR #N", "review my branch", "leave review comments". Works in two modes. Public mode (default) reviews someone else's PR on the hosting platform and posts the result as a draft review for your approval. Local mode — triggered when the request says "locally", "for myself", "just my branch", or "don't post" — reviews your own working branch and writes the review to a file, posting nothing to a review platform. Finds issues by orchestrating the code-review and pr-review-toolkit plugins, drafts in a human voice with no severity badges, and gates everything on your approval. This is the reviewer's side; to respond to feedback on a PR you authored, use pr-comments-address.
---

<!-- No `context: fork`: forked skills run as subagents, which cannot dispatch the Agent tool (the review engines in step 2) or AskUserQuestion (the results gate in step 5). For isolation from other work, invoke this skill in a dedicated session instead. -->

# Author a Code Review

Produce a code review that reads like a sharp human wrote it and opens a conversation. You draft, the user steers, the user approves before anything is posted or saved.

## Modes

Decide the mode before starting the workflow, and state it in one line — the workflow branches on it.

- **public** (default): review a PR **someone else authored** on the hosting platform. Read the existing conversation, post the result as a **draft (pending) review** the user finalizes and submits. This is the primary use. Uses the platform reference, selected by the PR URL's host — [references/github.md](references/github.md) for GitHub (the only one so far).
- **local**: review **your own working branch** for yourself. Nothing is posted or published — produce the review as a file. Use this when the request says "locally", "for myself", "just my branch", "don't post", or otherwise targets in-progress work rather than someone else's PR. The built-in `/review`-style tools also do this, but less reliably and without the human-gated, house-style flow here. Uses [references/local.md](references/local.md).

**Choosing:** if the request clearly signals local (the trigger words above, or a bare branch with no PR), use local. If it clearly targets a specific remote PR (a PR URL or `owner/repo#N`), use public. If it's ambiguous, ask with `AskUserQuestion`, offering Public as the default.

This skill orchestrates existing review engines rather than reinventing analysis (both modes). It depends on two plugins and degrades gracefully if absent — see [references/analysis.md](references/analysis.md):

- **code-review** — a confidence-scored multi-agent sweep for breadth.
- **pr-review-toolkit** — specialized agents (`code-reviewer`, `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`) for depth on the dimensions a diff actually touches.

Review voice and formatting rules are in [references/house-style.md](references/house-style.md).

## Input

`args` is a PR reference (public) or a branch/base hint (local): a PR URL, `owner/repo#N`, a bare `N` inside the repo, a branch name, or empty (use the current branch). Parse what you can; if public mode needs a PR you can't resolve, ask for a PR URL.

## Workflow

```
- [ ] 0. Bias gate: flag a contaminated session before reviewing
- [ ] 1. Gather the change and context
- [ ] 2. Find issues (code-review + applicable pr-review-toolkit agents)
- [ ] 3. Reconcile (public: against existing comments; local: skip)
- [ ] 4. Draft in house style: summary, architectural notes, inline findings
- [ ] 5. Results gate: print the draft and ask — back with sources / proceed / change
- [ ] 6. Deliver (public: draft review; local: review file)
- [ ] 7. Summarize; loop on re-review (public)
```

### 0. Bias gate

A review is worth only as much as its independence. Before anything else, inspect **this conversation** for contamination — evidence you'd be reviewing work you helped shape:

- you wrote, edited, or fixed any of the code under review in this session;
- you designed, planned, or debated the change here, or addressed review feedback on it;
- you already drafted, summarized, or argued a position on this change — your judgment is anchored to it.

If any apply, stop and say which one, then ask with `AskUserQuestion`:

- **Fresh session** (recommended) — you can't open one yourself, so hand off: end the turn by printing the exact invocation to carry over (`/pr-review <args>`, plus any constraints from this conversation worth keeping) and tell the user to run it after `/clear` or in a new session. Don't try to simulate it with a headless `claude -p` call — that runs without the interactive gates this skill depends on.
- **Proceed** — run the workflow normally, in-session knowledge and all. The user may have run the review here deliberately because the conversation led to it; respect that.
- **Proceed, quarantine session knowledge** — run the workflow but treat your in-session knowledge as untrusted: re-derive findings from the diff and the engines' output, not from what you remember intending, and carry a one-line independence caveat into the step 7 summary (never into the posted review).

A clean conversation — or one whose only relation to the change is this review — passes silently; don't ask.

A long session of unrelated work isn't bias, but it competes for attention; if context is already strained, recommend the fresh session for that reason instead.

### 1. Gather the change and context

- **public:** run `preflight`, `fetch-pr-context`, and `fetch-existing-comments` from the platform reference (selected in Modes), **before** any analysis — so you know what the PR does, what's already been said, which threads are open, and whether you (or the user) have reviewed it before. `fetch-existing-comments` includes an explicit pass to list your own prior comments; do it — they're the easiest set to duplicate. When the existing conversation is large, don't read the raw dump yourself: hand it to a subagent that returns a structured scratchpad — open threads, settled points, your own prior comments, each with `path:line` — and run that digest in parallel with fetching the diff. It's extraction, not judgment, so a small/fast model suffices if agent dispatch lets you pick one; with no agent dispatch, compact it inline. Either way the scratchpad, not the raw conversation, is what the analysis pass carries. Comment only on lines the PR changed.
- **local:** run `resolve-base` and `get-local-diff` from [references/local.md](references/local.md). There's no existing conversation to fetch.

### 2. Find issues

Follow [references/analysis.md](references/analysis.md) — the same engines work on a PR diff or a local diff. Run the `code-review` plugin's confidence-scored sweep and dispatch the `pr-review-toolkit` agents that match what the diff changed. Merge and dedupe into one findings list, carrying each finding's confidence and source forward. Apply the false-positive discipline there: a confident finding is not a correct finding.

### 3. Reconcile

- **public:** cross-check each finding against the existing conversation — **including your own prior review passes**, which are the easiest to duplicate. Use `$ME`'s comment list from `fetch-existing-comments`: for any finding that lands on a `path:line` you already commented on, build on that thread with a `reply-to-thread` rather than opening a second one — even if that prior thread is resolved. Drop points already raised and settled; for any open thread, plan a `reply-to-thread` (agree, build on, or push back) instead of a duplicate inline comment; keep only what's new. When the findings list is long, fan the mechanical checks out to parallel subagents — per finding: is it a duplicate of an existing thread, does it land on a `$ME`-commented `path:line`, is its line in the diff — each checking against the scratchpad and returning a verdict (a small/fast model suffices; it's matching, not judgment). The judgment calls — agree, build on, or push back — stay with you.
- **local:** nothing to reconcile.

### 4. Draft in house style

Turn the survivors into a review per [references/house-style.md](references/house-style.md). Separate the two buckets explicitly:

- **Inline findings** — anchored to `path:line`, each a plain-voice comment.
- **Architectural notes** — cross-cutting observations not tied to a single line. These go in the summary body (public) or the "Architectural notes" section of the file (local).

No severity badges, plain citations. Order by what matters, explained in words. Draft a one-line **verdict** intent for public mode (request changes / comment / approve), but don't act on it until delivery.

**Materialize the draft with `Write`** to the repo's `review/` folder — the same one local mode delivers into (create it if missing; it stays out of commits, gitignored or per the user's preference): `review/pr-<N>-draft.md`. A draft composed only in thinking does not exist — the `Write` call is the verifiable proof it does, and an in-repo file is one the user can open in their editor no matter what happens to the chat. Don't proceed to the gate without this file.

### 5. Results gate

Print the complete draft **as message text** — summary, architectural notes, and the inline findings (each with `path:line`) — then ask the user with `AskUserQuestion` how to proceed. The user can only approve what they can read: if the draft isn't in the message, the gate is void. Any session-wide brevity or compression mode (terse-output instructions, token-saving styles) governs your commentary, never the deliverable — a file path, a recap, or "the review is above" does not satisfy this step.

**Pre-gate protocol — the draft is the step 4 file, not your memory.** Present it by printing the file's full content as message text, then call `AskUserQuestion` — and always include the file path in the question itself ("full draft in `review/pr-<N>-draft.md`"), so even if the print gets squeezed out, the user opens the draft in their editor from the path alone. The documented failure of this step (three sessions running): composing the draft in thinking, then gating on "the draft is above" while the message contains nothing — your memory of having printed is not evidence; only the `Write` call from step 4 and text visible in this turn are. If there is no step 4 file, you have no draft: go back and write it.

- **Proceed** — deliver as-is (post the draft review, or write the file).
- **Back findings with external sources** (optional) — before delivering, run the evidence pass: for each contestable finding, verify against a trusted source (official docs, the language/library spec, a high-signal StackOverflow answer, or an issue in the project's own hosted repo — GitHub/GitLab/Gerrit/…), attach the link in the comment, and **drop claims you can't substantiate**. "Substantiate" means verified against the code or the spec — a project-specific finding grounded in the diff stands on its own and needs no external citation. Then re-present the revised draft and return to this gate — don't deliver until the user picks Proceed.
- **Change something** — take the user's edits (reword, drop, split a point into its own inline comment, re-anchor), restate, and confirm.

Respect the user's granularity choices — don't fold a distinct observation into the summary if they want it inline, and don't merge separate points. Post or write nothing before the user picks Proceed.

### 6. Deliver

- **public:** first run `find-pending-review`. If a draft already exists, apply the **never-destroy rule** (don't delete or recreate it — stop and ask; it may hold the user's own comments). Otherwise `create-draft-review` — a pending review the user submits in the platform UI, the **default**. Only if the user explicitly chose to submit now, `submit-review` with the verdict. Send any approved `reply-to-thread` replies. Verify the draft's summary body actually posted.
- **local:** `write-review-file` and print the path. Nothing is sent anywhere.

Posting/saving is automated after approval; judgment is not. In public mode, if the platform rejects a comment for an out-of-diff line, move it into the summary body and retry rather than dropping it silently.

### 7. Summarize and loop

Print what was delivered (the draft review URL and inline count, or the file path and counts) with the PR URL on its own line in public mode.

**Public mode: end the turn with the summary body verbatim, copy-paste ready.** Print the full summary text in a fenced markdown block, then the verdict intent and any thread replies sent, and make clear it's a draft awaiting their submit. A recap or description of the summary does not satisfy this — only the verbatim text does, and no session-wide brevity or compression mode shrinks it. Run the same self-check as the results gate: if the turn's final message doesn't visibly contain the fenced summary block, it wasn't delivered — text composed in thinking renders nothing. It applies to **every** turn that ends with the draft created or partially delivered, including turns cut short by errors or permission walls. The platform may not show the draft's summary until submit — or may have silently dropped it at creation — so this final message can be the user's only copy of the text to paste when submitting.

**Re-review loop (public).** This skill works under `/loop`. On a later round, repeat steps 1–6, but diff against your previous review's timestamp and treat your own prior comments as part of the conversation — raise only what's new or unaddressed, acknowledge fixes the author made, and converge toward approve. The user still approves each round; the loop automates the cadence, not the judgment.

## Boundaries

- Never post, submit, or save anything the user hasn't approved at the results gate.
- Never delete or recreate an existing pending review draft without explicit approval — it may hold the user's own comments.
- In public mode: comment only on lines in the PR diff; never resolve other people's threads; never auto-approve — the user chooses that verdict; default to a draft, not a direct submit.
- Don't re-raise a settled point unless the new changes make it live again; don't post a finding you couldn't verify — lower its confidence and drop it.
- No severity badges, no performative praise, no "generated by" footer.
- Session-wide brevity or compression modes never shrink a deliverable: the step 5 draft and step 7 summary print in full, verbatim, as message text.
- Don't run builds, typecheck, or lint to find issues — CI covers those; flagging them is noise.
