---
name: pr-review
description: >-
  Authors a human-voice code review of someone else's pull request or merge request
  and posts it as a draft (pending) review for the user's approval — "review this PR",
  "do a code review on PR #N", "review this MR", "leave review comments". Also reviews
  the user's own branch when the request says "review locally", "review for myself",
  "just my branch", or "don't post": the review goes to a file and nothing is posted.
  Works on GitHub and GitLab. Finds issues by orchestrating the code-review and
  pr-review-toolkit plugins, drafts with no severity badges, and gates every post on
  the user's approval. This is the reviewer's side; to respond to feedback on a PR the
  user authored, use pr-comments-address.
argument-hint: "[PR URL | owner/repo#N | N | branch]"
---

# Author a Code Review

Produce a code review that reads like a sharp human wrote it and opens a conversation. You draft, the user steers, the user approves before anything is posted or saved.

## Modes

Decide the mode before starting the workflow, and state it in one line — the workflow branches on it.

- **public** (default): review a PR **someone else authored** on the hosting platform. Read the existing conversation, post the result as a **draft (pending) review** the user finalizes and submits. This is the primary use. Uses the platform reference selected below.
- **local**: review **your own working branch** for yourself. Nothing is posted or published — produce the review as a file. Use this when the request says "locally", "for myself", "just my branch", "don't post", or otherwise targets in-progress work rather than someone else's PR. The built-in `/review`-style tools also do this, but less reliably and without the human-gated, house-style flow here. Uses [references/local.md](references/local.md).

**Choosing:** if the request clearly signals local (the trigger words above, or a bare branch with no PR), use local. If it clearly targets a specific remote PR (a PR URL or `owner/repo#N`), use public. If it's ambiguous, ask with `AskUserQuestion`, offering Public as the default.

## Platform (public mode)

Resolve the platform before step 1 and state it alongside the mode. Resolve in this precedence order, taking the first that answers — a later signal never overrides an earlier one:

1. the host in the PR/MR URL the user gave;
2. the host of the repo's `git remote` (`git remote get-url origin`);
3. which CLI is authenticated (`gh auth status` / `glab auth status`).

`github.com` or a GitHub Enterprise host → [references/github.md](references/github.md). `gitlab.com` or a self-managed GitLab host → [references/gitlab.md](references/gitlab.md). If none of the three resolves, ask with `AskUserQuestion` — never guess, since the wrong reference posts nothing or posts to the wrong place.

The workflow below is platform-agnostic and names operations (`preflight`, `fetch-pr-context`, `create-draft-review`, …); the selected reference defines them. It says "PR" throughout — on GitLab read merge request, and `<NUM>` as the MR `iid`. Local mode needs none of this.

This skill orchestrates existing review engines rather than reinventing analysis (both modes). It depends on two plugins and degrades gracefully if absent — see [references/analysis.md](references/analysis.md):

- **code-review** — a confidence-scored multi-agent sweep for breadth.
- **pr-review-toolkit** — specialized agents (`code-reviewer`, `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`) for depth on the dimensions a diff actually touches.

Review voice and formatting rules are in [references/house-style.md](references/house-style.md).

## Input

`$ARGUMENTS` is a PR reference (public) or a branch/base hint (local): a PR URL, `owner/repo#N`, a bare `N` inside the repo, a branch name, or empty (use the current branch). Parse what you can; if public mode needs a PR you can't resolve, ask for a PR URL.

## Workflow

```
- [ ] 1. Gather the change and context
- [ ] 2. Find issues (code-review + applicable pr-review-toolkit agents)
- [ ] 3. Triage in a fresh subagent (merge, discipline; public: reconcile)
- [ ] 4. Draft in house style: summary, architectural notes, inline findings
- [ ] 5. Results gate: print the draft and ask — back with sources / proceed / change
- [ ] 6. Deliver (public: draft review; local: review file)
- [ ] 7. Summarize; loop on re-review (public)
```

### 1. Gather the change and context

- **both modes:** if the request links or references an off-platform discussion — a Slack thread, meeting notes, a roadmap or ticket, a design doc — read it **before** analysis (via whatever tool or link gives you access). It carries the change's intent and any decisions already settled, which the diff and the on-platform threads don't show; reviewing without it risks re-raising something the author and reviewer already worked out elsewhere.
- **public:** run `preflight`, `fetch-pr-context`, and `fetch-existing-comments` from the platform reference (selected above), **before** any analysis — so you know what the PR does, what's already been said, which threads are open, and whether you (or the user) have reviewed it before. `preflight` also settles **whether draft delivery is available on this platform and instance** — carry that answer to step 5, which needs it before it can ask the user anything. `fetch-existing-comments` includes an explicit pass to list your own prior comments; do it — they're the easiest set to duplicate. When the existing conversation is large, don't read the raw dump yourself: hand it to a subagent that returns a structured scratchpad — open threads, settled points, your own prior comments, each with `path:line` — and run that digest in parallel with fetching the diff. It's extraction, not judgment, so a small/fast model suffices if agent dispatch lets you pick one; with no agent dispatch, compact it inline. Either way the scratchpad, not the raw conversation, is what the analysis pass carries. Comment only on lines the PR changed.
- **local:** run `resolve-base` and `get-local-diff` from [references/local.md](references/local.md). There's no existing conversation to fetch.

### 2. Find issues

Follow [references/analysis.md](references/analysis.md) — the same engines work on a PR diff or a local diff. Run the `code-review` plugin's confidence-scored sweep and dispatch the `pr-review-toolkit` agents that match what the diff changed. Collect both engines' raw findings with each one's confidence and source; the merge, the false-positive discipline, and reconciliation all happen inside step 3's triage subagent, not here.

### 3. Triage in a fresh subagent

Triage runs in a **fresh subagent** that never sees this conversation, whether or not this session touched the change. Don't self-assess independence — a session that wrote or debated the change bends the merge toward its own decisions, and a model can't judge its own anchoring (background: [references/design-notes.md](references/design-notes.md)).

Dispatch one triage subagent with the Agent tool (`subagent_type: "general-purpose"` — a fresh context; **not** `"fork"`, which inherits this conversation and defeats the isolation). Hand it exactly:

- the diff and the repo checkout path;
- both engines' raw findings — file, line, what, why, suggested fix, confidence, source;
- **public:** the scratchpad from step 1 — open threads, settled points, `$ME`'s prior comments, each with `path:line` — plus any off-platform source material (verbatim or an extractive digest of what was decided, never your conclusions about the change);
- the path to [references/analysis.md](references/analysis.md), with the instruction to apply its "Merge and carry forward" and "False-positive discipline" sections.

Withhold everything else — what this session intended, designed, or argued about the change. The diff, the engines' output, and the recorded conversation are the subagent's whole world, so its verdicts can't be a defense of decisions it never saw.

The subagent merges and dedupes both engines into one findings list, then applies the false-positive discipline — it has repo access, and the verification work there (`Read` the file, `Grep` the sibling artifact) is its job; for a long list it may fan the mechanical per-finding checks out to its own nested subagents (duplicate-of-thread, `$ME`-commented line, line-in-diff — matching, not judgment, so a small/fast model suffices). **Public:** it also reconciles against the scratchpad: for any finding on a `path:line` `$ME` already commented on, plan a `reply-to-thread` that builds on that thread rather than a second comment — even if the prior thread is resolved; for any open thread, plan a `reply-to-thread` (agree, build on, or push back) instead of a duplicate inline comment; drop points already raised and settled — in a PR thread or off-platform — and keep only what's new. It returns the surviving findings (confidence and source intact) and the thread-reply plan. **Local:** same subagent, no scratchpad — nothing to reconcile.

If agent dispatch is unavailable (rare — e.g. running at the subagent nesting depth limit, where the engines already degraded to the inline pass): merge, apply the discipline, and reconcile inline, re-deriving each verdict from the diff and the engines' output rather than from what you remember intending, and carry a one-line independence caveat into the step 7 summary (never into the posted review).

### 4. Draft in house style

Turn the survivors into a review per [references/house-style.md](references/house-style.md). Separate the two buckets explicitly:

- **Inline findings** — anchored to `path:line`, each a plain-voice comment.
- **Architectural notes** — cross-cutting observations not tied to a single line. These go in the summary body (public) or the "Architectural notes" section of the file (local).

No severity badges, plain citations. Order by what matters, explained in words. Draft a one-line **verdict** intent for public mode (request changes / comment / approve), but don't act on it until delivery.

**Pick the verdict from what the remaining findings can cost, not from how many there are.** Classify each survivor by two things: how often that code actually runs, and what goes wrong when it does.

- **request changes** — it changes what the code does on a path that runs normally, or it loses data, corrupts state, or opens a security hole. Rarity doesn't rescue those: a one-in-a-million path that corrupts data still blocks.
- **approve** — nothing major remains. A finding is *not* major when it is confined to code that runs only in rare situations **and** its worst outcome is limited to visibility — log fields, alert payloads, diagnosability — or to performance. Docs, comments and test hygiene never block on their own.
- **comment** — the residue: a real defect on an ordinary path that isn't severe enough to block, or a question whose answer could change the design. If you're reaching for comment because approving *feels* presumptuous, that's not a reason — apply the rule.

Holding a PR open over log-field quality and comment accuracy costs more in cycle time than those findings cost in risk — and it costs most on a late round, where the remainder is nearly always visibility and hygiene. Approving is a statement about the verdict, never a reason to drop or soften a finding: post them all, and say plainly in the summary why you're approving anyway. This is the verdict *intent* either way — the user picks the verdict at delivery.

**Materialize the draft with `Write`** to `review/pr-<N>-draft.md` in the `review/` folder of **the repo whose code is under review** — the same one local mode delivers into (create it if missing; it stays out of commits, gitignored or per the user's preference). In a multi-repo or orchestrator checkout, that means the service's own clone, not the parent — say which path you used. A draft that exists only in thinking is not a draft; the file is what the user can open whatever happens to the chat. Don't proceed to the gate without it.

### 5. Results gate

Print the complete draft **as message text** — summary, architectural notes, and the inline findings (each with `path:line`) — then ask the user with `AskUserQuestion` how to proceed. The user can only approve what they can read: if the draft isn't in the message, the gate is void. Any session-wide brevity or compression mode (terse-output instructions, token-saving styles) governs your commentary, never the deliverable — a file path, a recap, or "the review is above" does not satisfy this step.

**Read the draft once more before printing it**, against [references/house-style.md](references/house-style.md)'s "What never goes in a posted review". Four things to strike: a finding that opens on mechanism instead of the defect; a sentence carrying more than one claim; any phrasing that implies you ran, tried, or reproduced something (this skill never executes anything); and any line about the review itself — what you read, how you checked, what you couldn't check. Then confirm the summary opens on the MR and your overall read, not on the first bug.

**The draft is the step 4 file, not your memory.** Print the file's full content as message text, then call `AskUserQuestion` with the file path in the question itself ("full draft in `review/pr-<N>-draft.md`"), so the user can open the draft from the path alone if the print gets squeezed out. Only the step 4 `Write` and text visible in this turn count as having presented it. If there is no step 4 file, there is no draft: go back and write it.

**Check delivery capability before you ask, not after.** `preflight` established whether this platform and instance support a draft. If they don't (a GitLab instance without the Draft Notes API, a token missing the scope, an MCP fallback with no draft tool), **the options below are wrong as written** — "Proceed" would publish the review immediately under a label the user read as "draft". Say plainly in the gate that draft delivery isn't available here and why, then offer **publish now** (post the findings and summary for real, right away) or **write to a file and post nothing** (local mode's artifact, so nothing reaches the platform) — and let the user pick with full knowledge of what lands. Never present a publishing action as a draft.

- **Proceed** — deliver as-is (post the draft review, or write the file).
- **Back findings with external sources** (optional) — before delivering, run the evidence pass: for each contestable finding, verify against a trusted source (official docs, the language/library spec, a high-signal StackOverflow answer, an issue in the project's own hosted repo — GitHub/GitLab/Gerrit/… — or, for an architectural claim about how the system fits together, the project's own sibling repos and artifacts, not just external docs), attach the link in the comment, and **drop claims you can't substantiate**. "Substantiate" means verified against the code or the spec — a project-specific finding grounded in the diff stands on its own and needs no external citation. Then re-present the revised draft and return to this gate — don't deliver until the user picks Proceed.
- **Change something** — take the user's edits (reword, drop, split a point into its own inline comment, re-anchor), restate, and confirm.

Respect the user's granularity choices — don't fold a distinct observation into the summary if they want it inline, and don't merge separate points. Post or write nothing before the user picks Proceed.

### 6. Deliver

- **public:** first run `find-pending-review`. If a draft already exists, apply the **never-destroy rule** (never delete or recreate it — it may hold the user's own comments; stop and ask, or append if the platform supports it and the user agrees). Otherwise `create-draft-review` — a pending review the user submits in the platform UI, the **default**. Only if the user explicitly chose to submit now, `submit-review` with the verdict. Send any approved `reply-to-thread` replies. Verify the summary actually posted, in whatever form the platform carries it. If the gate established that drafts aren't available here, deliver what the user chose there instead — publish now, or write the file and post nothing.
- **local:** `write-review-file` and print the path. Nothing is sent anywhere.

Posting/saving is automated after approval; judgment is not. In public mode, if the platform rejects a comment for an out-of-diff line, move it into the summary body and retry rather than dropping it silently.

### 7. Summarize and loop

Print what was delivered (the draft review URL and inline count, or the file path and counts) with the PR URL on its own line in public mode.

**Public mode: end the turn with the summary body verbatim, copy-paste ready.** Print the full summary text in a fenced markdown block, then the verdict intent and any thread replies sent, and make clear it's a draft awaiting their submit. A recap or description of the summary does not satisfy this — only the verbatim text does, and no session-wide brevity or compression mode shrinks it. Run the same self-check as the results gate: if the turn's final message doesn't visibly contain the fenced summary block, it wasn't delivered — text composed in thinking renders nothing. It applies to **every** turn that ends with the draft created or partially delivered, including turns cut short by errors or permission walls. The platform may not show the draft's summary until submit — or may have silently dropped it at creation — so this final message can be the user's only copy of the text to paste when submitting.

**Amendments after delivery (public).** The workflow doesn't end at step 6 — the user will ask for changes to what you just posted ("add architectural notes", "that finding is unclear", "cut the last one"). **Every one of those re-enters step 5 before anything is written to the platform:** draft the new or revised text, update the step 4 file, print it, `AskUserQuestion`, then post. Amend in place with the platform's edit operation; never delete and recreate.

A request to change something approves the **action**, never the **wording** — "yes, add architectural notes" is permission to draft them, not to publish whatever you draft. Drafting and posting an amendment in one step, with the text shown only afterwards, is the gate failing exactly where the user is watching most closely.

**Re-review loop (public).** This skill works under `/loop`. On a later round, repeat steps 1–6, but diff against your previous review's timestamp and treat your own prior comments as part of the conversation — raise only what's new or unaddressed and converge toward approve. **Don't itemize the fixes the author made since the last round** — not even a one-line recap of which items now look right; "everything from the last round is addressed" covers it. Confirm whether it's all addressed or say what still stands, thank them, and go straight to what's new — see the re-review summary example in [references/house-style.md](references/house-style.md). The user still approves each round; the loop automates the cadence, not the judgment.

## Boundaries

The workflow steps carry the gate, the triage isolation, and the print-in-full rules once each; these are the rules no step states.

- This skill reads code; it doesn't run it. Don't run builds, tests, typecheck, or lint to find issues — CI covers those, and flagging them is noise — and don't write the review as if you had.
- No severity badges, no performative praise, no "generated by" footer.
- Never delete or recreate an existing pending review draft without explicit approval — it may hold the user's own comments.
- Public mode: don't resolve other people's threads, and never auto-approve — the user picks the verdict.
- An engine that reports nothing has failed: say so and degrade, rather than authoring findings in its place. Dispatch and collection rules are in [references/analysis.md](references/analysis.md).
