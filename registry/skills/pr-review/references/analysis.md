# Finding issues — review engines

> **Part of:** [pr-review](../SKILL.md). How to find issues by orchestrating existing review plugins instead of hand-rolling analysis. Run both engines, merge, and carry confidence forward.

The two engines are independent until the merge — don't run them back to back. Dispatch the `pr-review-toolkit` agents while the `code-review` sweep is still running; wall-clock is the slower engine, not the sum.

## Engine 1: the code-review plugin (breadth)

The `code-review` plugin runs a strong generic recipe: an eligibility check, CLAUDE.md collection, a change summary, five parallel agents (CLAUDE.md adherence, obvious bugs, git history, prior-PR comments, code-comment guidance), and a 0–100 confidence score per issue filtered at 80. Reuse it for breadth, but take only its findings — not its output format or posting. Treat that score as a breadth filter, not a truth signal: a model's self-reported confidence is unreliable on its own, so this skill never leans on it alone — every finding is cross-checked by a second, independent engine (the `pr-review-toolkit` agents) and the human gate, which is the cross-review that actually raises quality.

Locate its command spec and follow its **analysis steps** to produce the scored, filtered findings list:

```sh
find ~/.claude/plugins -path '*code-review*/commands/code-review.md' -not -path '*/cache/*' 2>/dev/null | head -1
```

(If that finds nothing, drop the `-not -path` filter.) `Read` it and follow its analysis steps, then **stop before the step that posts** — its final step comments on the PR in a fixed style with an emoji footer, which this skill replaces. Keep the in-memory findings: file, line, what, why, suggested fix, confidence, and flag reason.

## Engine 2: pr-review-toolkit agents (depth)

The `pr-review-toolkit` plugin provides specialized review agents that go deeper than a generic pass on the dimension they own. Dispatch them with the Agent tool (`subagent_type: "pr-review-toolkit:<agent>"`), giving each the PR diff and scope. For a large diff, chunk it by file or directory and dispatch per chunk rather than handing each agent the whole thing — a diff that overflows the context window gets reviewed shallowly; note in the summary if a chunk was too big to cover fully. Select by what the diff actually changed — running an agent whose dimension the PR doesn't touch wastes tokens and invites false positives:

| Agent | Run when the diff… | Looks for |
|---|---|---|
| `code-reviewer` | always | General quality, bugs, project-convention adherence |
| `pr-test-analyzer` | adds or changes tests | Coverage gaps, weak assertions, flaky-test risk |
| `silent-failure-hunter` | touches error handling, catch blocks, fallbacks | Swallowed errors, misleading messages, silent failures |
| `type-design-analyzer` | adds or changes types | Encapsulation, invariants, type-design quality |
| `comment-analyzer` | adds or changes comments/docs | Comment accuracy vs. code, rot, completeness |

`code-simplifier` is for applying simplifications to a working tree, not for reviewing someone else's PR — skip it here.

Give each agent the context its dimension needs, not just the diff: `pr-test-analyzer` can't judge coverage gaps without the existing tests, and `comment-analyzer` needs the surrounding code to tell an outdated comment from a correct one. (These agents carry their own descriptions and system prompts — this skill selects them and feeds them scope; it doesn't re-prompt them.) Run the applicable agents in parallel. Each returns its own findings; treat them as high-signal for their dimension but still subject to the discipline below.

## Merge and carry forward

Combine both engines into one findings list and dedupe by file, line, and substance (the two engines will overlap — e.g. both may flag a real bug). Prefer the more specific phrasing. For each surviving finding keep: file, line, what, why, suggested fix, a confidence read (use the code-review plugin's score when present, otherwise judge from how decisively the specialized agent verified it), and the source. Confidence and source feed the house-style ordering and the verdict reason back in the SKILL workflow.

## False-positive discipline

Drop anything that doesn't clear this bar, regardless of which engine raised it:

- Pre-existing issues on lines this PR didn't change — keep inline comments scoped to changed lines. The exception: if the PR propagates a pre-existing bad pattern (copied from code that served as the example), don't inline-comment the untouched original, but do call out the root in the architectural-notes/summary with a pointer, so the pattern doesn't get a free pass.
- Things a linter, typechecker, or compiler catches (imports, types, formatting) — when CI runs those separately. If the repo has no CI covering them, surface them briefly instead of staying silent, since nothing else will catch them.
- Pedantic nitpicks a senior engineer wouldn't raise.
- Generic "add more tests / better docs / more security" that the codebase's own conventions don't call for.
- Issues silenced deliberately in code (lint-ignore, a documented constant).
- Claims of duplication or misplacement — "this already exists in X", "this belongs in Y", "the other command already does this" — verified against the actual other artifact, not asserted from memory or the diff alone. `Read` the file, `Grep` the sibling repo, open the command you're claiming it duplicates. If you can't confirm the other side exists and says what you think it does, drop the finding or soften it to a question ("is this already covered by …?"). Asserting a duplication that isn't there wastes the author's time and burns the review's credibility.

Apply the same skepticism to automated findings that a careful human reviewer applies to any bot: a confident finding is not a correct finding. When you can't verify a finding, lower its confidence and drop it rather than posting a guess.

## When a plugin is missing

Degrade gracefully; don't hard-fail.

- **No `code-review` plugin:** rely on the `pr-review-toolkit` agents alone.
- **No `pr-review-toolkit`:** rely on the `code-review` plugin alone.
- **Neither installed:** tell the user, then do a lighter inline review yourself — read the diff from `fetch-pr-context`, scan changed lines for real bugs and convention violations, assign a rough confidence, and note in the summary that this was a lighter pass. The rest of the workflow (house style, approval gate, post) is unchanged.
- **No Agent tool in this context** (e.g. running inside a subagent or forked skill, where agent dispatch is unavailable): same lighter inline pass as above, and tell the user the parallel engines were skipped and why — re-running the skill from a main conversation restores them.
