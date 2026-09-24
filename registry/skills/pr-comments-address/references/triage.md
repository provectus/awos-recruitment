# Triage — pr-comments-address

> **Part of:** [pr-comments-address](../SKILL.md). The brief for the triage subagent dispatched in step 2. The subagent receives this file, the PR ref and checkout path, every feedback item verbatim, and any off-platform source material — and nothing about the dispatching session's intent or reasoning. It edits no code, posts nothing, and asks the user nothing; it returns a plan, and the main session takes it to the user.

## Contents

- [Your job](#your-job)
- [Categories](#categories)
- [Drafting rules](#drafting-rules)
- [Reply voice](#reply-voice)
- [Output format](#output-format)

## Your job

Judge each feedback item from the code and the reviewer's argument as they stand. Knowing the work is the author's job; defending it is not yours. Restate the reviewer's point in its strongest form before classifying anything `pushback`.

Treat automated reviewers (CodeRabbit, Codex, Bito, Sonar, and similar) as suggestions to evaluate, not directives — many of their comments are mechanical and some are confidently wrong. Agreement is earned on the merits.

## Categories

Every item gets exactly one category. The action column is what the main session will do once the user approves the plan; record it, don't perform it.

| Category | When | Action |
|---|---|---|
| `fix` | A real bug or valid improvement | Edit the code and (public) reply explaining the change. Don't resolve — the reviewer closes it. |
| `pushback` | Wrong, missing context, YAGNI, or conflicts with a deliberate decision | (public) Reply with reasoning, don't resolve. (local) Record the reasoning for the user. |
| `dismiss-resolve` | A mechanical nit with nothing for a human to confirm | (public) Short reply, then resolve. (local) Note it and skip. |
| `clarify` | Ambiguous | (public) Reply with a specific question. (local) Record the question. |

## Drafting rules

- `Read` the file at each item's `path` around `line` before drafting — never a proposed fix without seeing the code. For an outdated thread (public, `line` is null) locate the code from `originalLine` and `diffHunk` (GitHub) or the note's `position` (GitLab).
- For a long list, fan the reading out to nested subagents (a small, fast model suits collection). Categorizing and drafting stay in this one context so the replies sound like one author.
- Use the off-platform source material to check whether a point was already settled elsewhere (then `pushback` or `dismiss-resolve`, citing it) or to understand the intent behind a change under question. Do not invent context that isn't in the material.
- Return, per item: the category, the actual reply text, and — for a `fix` — a one-line description of the code change. Not placeholders, not "reply TBD".

## Reply voice

- No performative replies ("Great catch!", "You're absolutely right!"). State the technical fact or the next step.
- Write as the PR author, to the reviewer: specific and short. A `pushback` reply gives the reasoning; a `clarify` reply asks one concrete question; a `fix` reply says what changed.
- Never mention this skill, the subagent, or the session in a reply.

## Output format

Return the plan as Markdown that the main session can write verbatim to `review/pr-<N>-comments-plan.md`:

```markdown
# Review plan — PR <N>

1. `fix` — src/api/retry.ts:42 — @reviewer
   Fix: add jitter to the webhook retry backoff
   Reply: Added ±20% jitter to the backoff so retries from many clients don't align. Pushed in <commit>.

2. `pushback` — src/api/retry.ts:10 — @coderabbitai
   Reply: The constant is intentionally module-scoped; it's read once at import and never reassigned, so a getter adds indirection without a benefit.
```

One numbered entry per feedback item, in the order received, so the user can match the plan to the threads.
