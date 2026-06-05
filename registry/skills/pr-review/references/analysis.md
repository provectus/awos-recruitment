# Finding issues — review engines

> **Part of:** [pr-review](../SKILL.md). How to find issues by orchestrating existing review plugins instead of hand-rolling analysis. Run both engines, merge, and carry confidence forward.

## Contents

- [Engine 1: the code-review plugin (breadth)](#engine-1-the-code-review-plugin-breadth)
- [Engine 2: pr-review-toolkit agents (depth)](#engine-2-pr-review-toolkit-agents-depth)
- [Merge and carry forward](#merge-and-carry-forward)
- [False-positive discipline](#false-positive-discipline)
- [When a plugin is missing](#when-a-plugin-is-missing)

## Engine 1: the code-review plugin (breadth)

The `code-review` plugin runs a strong generic recipe: an eligibility check, CLAUDE.md collection, a change summary, five parallel agents (CLAUDE.md adherence, obvious bugs, git history, prior-PR comments, code-comment guidance), and a 0–100 confidence score per issue filtered at 80. Reuse it for breadth, but take only its findings — not its output format or posting.

Locate its command spec and follow its **analysis steps** to produce the scored, filtered findings list:

```sh
find ~/.claude/plugins -path '*code-review*/commands/code-review.md' -not -path '*/cache/*' 2>/dev/null | head -1
```

(If that finds nothing, drop the `-not -path` filter.) `Read` it and follow its analysis steps, then **stop before the step that posts** — its final step comments on the PR in a fixed style with an emoji footer, which this skill replaces. Keep the in-memory findings: file, line, what, why, suggested fix, confidence, and flag reason.

## Engine 2: pr-review-toolkit agents (depth)

The `pr-review-toolkit` plugin provides specialized review agents that go deeper than a generic pass on the dimension they own. Dispatch them with the Agent tool (`subagent_type: "pr-review-toolkit:<agent>"`), giving each the PR diff and scope. Select by what the diff actually changed — running an agent whose dimension the PR doesn't touch wastes tokens and invites false positives:

| Agent | Run when the diff… | Looks for |
|---|---|---|
| `code-reviewer` | always | General quality, bugs, project-convention adherence |
| `pr-test-analyzer` | adds or changes tests | Coverage gaps, weak assertions, flaky-test risk |
| `silent-failure-hunter` | touches error handling, catch blocks, fallbacks | Swallowed errors, misleading messages, silent failures |
| `type-design-analyzer` | adds or changes types | Encapsulation, invariants, type-design quality |
| `comment-analyzer` | adds or changes comments/docs | Comment accuracy vs. code, rot, completeness |

`code-simplifier` is for applying simplifications to a working tree, not for reviewing someone else's PR — skip it here.

Run the applicable agents in parallel. Each returns its own findings; treat them as high-signal for their dimension but still subject to the discipline below.

## Merge and carry forward

Combine both engines into one findings list and dedupe by file, line, and substance (the two engines will overlap — e.g. both may flag a real bug). Prefer the more specific phrasing. For each surviving finding keep: file, line, what, why, suggested fix, a confidence read (use the code-review plugin's score when present, otherwise judge from how decisively the specialized agent verified it), and the source. Confidence and source feed the house-style ordering and the verdict reason back in the SKILL workflow.

## False-positive discipline

Drop anything that doesn't clear this bar, regardless of which engine raised it:

- Pre-existing issues on lines this PR didn't change.
- Things a linter, typechecker, or compiler catches (imports, types, formatting) — CI runs those separately.
- Pedantic nitpicks a senior engineer wouldn't raise.
- Generic "add more tests / better docs / more security" that the codebase's own conventions don't call for.
- Issues silenced deliberately in code (lint-ignore, a documented constant).

Apply the same skepticism to automated findings that a careful human reviewer applies to any bot: a confident finding is not a correct finding. When you can't verify a finding, lower its confidence and drop it rather than posting a guess.

## When a plugin is missing

Degrade gracefully; don't hard-fail.

- **No `code-review` plugin:** rely on the `pr-review-toolkit` agents alone.
- **No `pr-review-toolkit`:** rely on the `code-review` plugin alone.
- **Neither installed:** tell the user, then do a lighter inline review yourself — read the diff from `fetch-pr-context`, scan changed lines for real bugs and convention violations, assign a rough confidence, and note in the summary that this was a lighter pass. The rest of the workflow (house style, approval gate, post) is unchanged.
