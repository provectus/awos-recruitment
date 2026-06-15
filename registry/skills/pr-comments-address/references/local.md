# Local operations — pr-comments-address (local mode)

> **Part of:** [pr-comments-address](../SKILL.md). **Local mode** applies review feedback to your own working tree for yourself — it posts nothing to GitHub, GitLab, or any review platform. Use this when the request says "locally", "for myself", "apply this review", "don't post", or points at a local review file rather than a PR. It pairs with pr-review's local mode: that skill writes `review/<timestamp>_<branch>.md`, this one applies it.

## read-feedback

The feedback lives locally, not on a platform. In priority order:

1. An explicit file the user named (e.g. `review/2026-06-05T..._my-branch.md`).
2. The most recent file under `review/` if one exists:
   ```sh
   ls -t review/*.md 2>/dev/null | head -1
   ```
3. Text the user pastes directly into the conversation.

`Read` the file (or take the pasted text) and parse it into discrete items. A review file in this repo's house style lists findings as `- path:line — comment` bullets under `## Findings`, plus a `## Architectural notes` section. Treat each bullet as one item and each architectural note as a non-line-anchored item.

If no feedback source is found, ask the user to point at a review file or paste the feedback, and stop.

## apply-locally

For each item, after the user approves at the results gate, act in the working tree only — no replies, no pushes, nothing leaves the machine:

- **fix** — `Read` the file at `path` around `line`, then `Edit` the change. Re-read first if it changed earlier in the session.
- **pushback / clarify** — there's no thread to answer; record the reasoning in the run summary so the user has it when they respond to the reviewer themselves.
- **architectural note** — apply if it's a concrete change the user approved; otherwise carry it into the summary as follow-up.

Commit only if the user asks (local mode shouldn't assume a commit). If committing, use a substance-describing subject and the project's commit style, the same as public mode. Never push and never run `gh` — surfacing changes to a remote is the user's call, out of this mode's scope.
