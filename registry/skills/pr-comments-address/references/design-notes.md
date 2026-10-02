# Design notes — pr-comments-address

> **Part of:** [pr-comments-address](../SKILL.md). Why the skill is shaped the way it is: the incidents and reasoning behind rules that SKILL.md states without justification. This is for maintainers changing the skill; the running skill never needs to read it, and it is deliberately kept out of the loaded body so the rules don't compete with the diff and the feedback for context.

## Contents

- [No `context: fork`](#no-context-fork)
- [Triage runs in a fresh subagent](#triage-runs-in-a-fresh-subagent)
- [Withhold session context from the subagent](#withhold-session-context-from-the-subagent)
- [The plan is a file, not a memory](#the-plan-is-a-file-not-a-memory)
- [Amendments re-enter the gate](#amendments-re-enter-the-gate)
- [The `review/` folder is not gitignored automatically](#the-review-folder-is-not-gitignored-automatically)
- [Reply voice](#reply-voice)

## No `context: fork`

Forked skills run as subagents, and subagents cannot use `AskUserQuestion` — the per-item approval gate this skill is built around. Nested Agent dispatch is not the constraint (subagents can dispatch their own subagents, so step 2 would still work); the gate is. For isolation from other work, invoke the skill in a dedicated session instead.

## Triage runs in a fresh subagent

Knowing the work is the author's job; defending it is not. The dangerous judgment in this skill is triage — classifying an item as `fix` vs `pushback` — and a session that wrote or debated the code under feedback is anchored to its own decisions. A model is also a poor judge of its own anchoring, so the skill does not ask the session to self-assess independence; it removes the need for it. Triage runs in a `general-purpose` subagent that never sees the conversation, whether the session touched the code or not — the rule is unconditional so there is no judgment call about when it applies.

The subagent is handed `references/triage.md`, not `SKILL.md`: the full workflow contains three `AskUserQuestion` gates, a `git push`, and "apply each approved item", none of which the subagent should do (and `AskUserQuestion` is removed from every subagent anyway). Handing it only the brief it needs means it doesn't have to ignore most of what it was given.

## Withhold session context from the subagent

The urge to add "helpful context" about what the code was meant to do is exactly the anchoring the subagent exists to strip out. Off-platform material (a Slack thread, a ticket, a design doc) is passed verbatim or as an extractive digest of what was said and decided — never as the session's conclusions about the feedback — because the subagent may lack the tools or auth to fetch it itself, and because it may show that a reviewer's point was already settled elsewhere. If the session disagrees with a categorization the subagent returns, it adds a marked `session note:` rather than reclassifying: the disagreement is itself session knowledge, and the user rules on it at the gate.

## The plan is a file, not a memory

Observed across several sessions: the model composed the plan in thinking, then gated on "the plan is above" while the message contained nothing — its memory of having printed was not evidence. Hence the ordering in steps 2 and 3: `Write` the plan to `review/pr-<N>-comments-plan.md` first, print that file's content as message text, then call `AskUserQuestion` with the file path in the question itself so the user can reach the plan even if the print gets squeezed out. The `Write` call is the verifiable proof the plan exists, and an in-repo file is one the user can open in their editor no matter what happens to the chat. Session-wide brevity or compression modes are explicitly scoped to commentary, not deliverables, because a "compressed" plan is one the user cannot approve.

## Amendments re-enter the gate

A request to change something already posted or committed ("reword that reply", "revise the fix") approves the action, not the wording. Without the rule, the second round skipped the gate and posted text the user had never read. So every round drafts, updates the plan file, prints, asks, then applies.

## The `review/` folder is not gitignored automatically

A persisted review trail can be intentional — some teams commit plans and reviews alongside the code. The skill therefore creates `review/` when missing, tells the user it is new, and leaves the ignore decision to them.

## Reply voice

Replies are posted under the author's name and read by the reviewer. Performative openers ("Great catch!", "You're absolutely right!") read as filler at best and as a bot at worst; the technical fact or the next step is the whole reply. The subagent never mentions the skill, the subagent, or the session, and the independence caveat for inline triage goes into the step 6 summary, not into posted replies, for the same reason.
