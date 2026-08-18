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

**Honour the model each step names.** The recipe assigns Haiku to the eligibility check, the CLAUDE.md path list, the change summary and the re-check, Sonnet to the five parallel reviewers, and Haiku to the per-finding confidence scorers. Those assignments are the recipe's cost model, and they only take effect if `model:` is passed explicitly on each `Agent` dispatch — an agent dispatched without one inherits *this session's* model instead. Engine 1 is 29–49% of a run's total token cost, so leaving it on an inherited model is the most expensive mistake available in this skill.

The per-finding scorers are worth keeping rather than cutting. Their score is a breadth filter, not a truth signal, and the <80 cut is what stops engine 1 handing triage its full noise floor — at Haiku, which is what the recipe intended, that filter is cheap.

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

Pass `model:` here too. These are depth passes over one bounded dimension, which is what Sonnet is for, and it matches what engine 1 gives its own reviewers. An agent whose definition names a model keeps it; one that doesn't will otherwise inherit the session's, which is how a review ends up running every specialist on the largest model available. Triage is the exception — that step is judgment, and it stays on the session model.

## Engine 3: project rules (only when the policy defines them)

When the base-branch `.claude/review-policy.md` has a `## Project rules` section, run one more engine. A repository's own conventions — "every endpoint needs an auth decorator", "no raw SQL outside `repositories/`", "migrations must be reversible" — are invisible to an engine that has never read them, so this is the one dimension the other two structurally cannot cover. Dispatch a subagent alongside the others, unnamed and in parallel, with the diff, the checkout path, and the rules **verbatim**.

Don't push the rules into the `pr-review-toolkit` agents instead. This skill selects those agents and feeds them scope; it doesn't re-prompt them, and injecting project rules into each one would both cross that line and dilute the dimension each agent is actually good at.

**This engine reports per rule, not only per finding.** Each rule comes back as checked-and-clean, violated (with the findings), or not-applicable-to-this-diff. That distinction matters because *An engine that returns no findings is a failed engine* below does **not** hold here: a project that follows its own rules produces zero violations, and that is success rather than breakage. The per-rule outcome is what keeps "nothing to report" separable from "never ran".

Sonnet, passed explicitly — matching a diff against rules someone already wrote down is checking, not judgment. Findings return in the usual shape, tagged source `project-rules`, scoped to changed lines like everything else — a sweep of the whole repository would bury the review in pre-existing violations the author didn't introduce.

## The engine budget

Three engines, and only three: the `code-review` plugin, the applicable `pr-review-toolkit` agents, and — when the policy defines rules — project rules. Spawning extra reviewers on top invents a fourth engine that re-covers ground engines 1 and 2 already cover, at roughly a fifth of the run's cost for nothing.

**Engines run one level deep.** An agent an engine dispatches does not dispatch agents of its own. Deeper fan-outs review the same subject several times over and their extra passes don't reach the posted review, so the cost is pure duplication. Verification isn't the engines' job — it belongs to the single step-3 triage agent, which is designed for it and costs a fraction of an ad-hoc verify swarm. Triage may still fan its own mechanical per-finding checks out, as the SKILL workflow describes; that is the one sanctioned nesting, and it's cheap.

**Bound each engine.** Changed files plus one hop of context, then report. An unbounded agent will happily run over a hundred turns at full context and cost more on its own than an entire disciplined run.

**Engines read the repo, not the network.** Verification inside an engine means the code, the diff, and the repo's own artifacts — `Read` the file, `Grep` the sibling module, open the test that covers it. Fetching documentation or searching the web is latency-bound rather than token-bound, so the cost never shows up as tokens; it shows up as the engine phase running two or three times longer, on the critical path, before the user has seen a single finding. Two engines doing it can add ten minutes to a review between them.

When a finding genuinely can't be settled from the repo — an API that may not exist, a spec version, an upstream default — don't fetch it. Return the finding with the open question attached and its confidence lowered, marked as needing external evidence. Step 5's "Back findings with external sources" is where that check belongs: by then the user has read the finding and can decide whether it's worth the wait. Most findings never need it, and the ones that do should get it on request rather than by default.

**Hand context over by path, not inline.** Write the diff and the PR context to one scratchpad file and give each agent the path plus its scope line. An agent handed them inline pays to rebuild that prompt in its own cache, and at 84–255k per agent across a dozen agents that is the largest avoidable cost after the model choice.

## Collecting the engines' results

Dispatching is the easy half. Getting the results back is where a review quietly loses half its wall-clock, so the mechanics are not optional.

**Dispatch engines as ordinary subagents — never as named background agents.** An unnamed `Agent` call returns the agent's output as the tool result and the harness notifies you the moment it finishes. A *named* agent runs as a background teammate whose completion arrives as a teammate message instead, and that message can land long after the work itself finished — engines that went idle in minutes routinely aren't collected for half an hour, sometimes not until after the review is already posted. Naming the agents is the whole cause.

Prose alone has proven unable to hold this rule, so it carries a check with an artifact behind it: **enumerate every agent dispatched — count, model, and depth — and carry that roster to the results gate.** Enumerating forces a look at what was actually spawned, which is what catches a named agent, an unpinned model, or a depth-2 dispatch while there's still time to abandon it.

**Never poll.** No `sleep` loops, no `until [ -s <file> ]; do sleep 30; done`, no watching a task's output file, no re-listing a directory to see if something appeared. Polling burns wall-clock waiting on results that already exist, and long waits get killed by the 120-second command timeout anyway, so it fails slowly and then fails again. A wait loop means the dispatch was wrong: fix the dispatch.

**Never read agent transcripts to recover a result.** The `.jsonl` files under the session's `subagents/` directory are harness internals, not an API. Scraping them for "the last assistant message" is how you end up acting on a **partial** result: a transcript read mid-flight returns whatever fragment exists at that instant, indistinguishable from a finished answer. Act on it and the real result lands afterwards, contradicting a review that is already posted.

**An engine that returns no findings is a failed engine.** Not an empty one — a failed one. Say so, degrade via *When a plugin is missing* below, and tell the user in the step 7 summary which engine didn't report. The failure mode to refuse outright: reconstructing an engine's output yourself from whatever you can find and handing it to the triage subagent as engine findings. That is session-authored content entering the one channel the skill protects from session influence, and it silently destroys the independence the whole triage step exists for. If an engine produced nothing, the review has one engine, and the user should know it.

## Merge and carry forward

Combine every engine that ran into one findings list and dedupe by file, line, and substance (they overlap — two engines may flag the same real bug). Prefer the more specific phrasing. For each surviving finding keep: file, line, what, why, suggested fix, a confidence read (use the code-review plugin's score when present, otherwise judge from how decisively the specialized agent verified it), the source, and whether it was marked as needing external evidence — that mark is what the gate's optional evidence pass works from, so losing it in the merge means the check silently never happens. Confidence and source feed the house-style ordering and the verdict reason back in the SKILL workflow.

## False-positive discipline

Drop anything that doesn't clear this bar, regardless of which engine raised it:

- Pre-existing issues on lines this PR didn't change — keep inline comments scoped to changed lines. The exception: if the PR propagates a pre-existing bad pattern (copied from code that served as the example), don't inline-comment the untouched original, but do call out the root in the architectural-notes/summary with a pointer, so the pattern doesn't get a free pass.
- Things a linter, typechecker, or compiler catches (imports, types, formatting) — when CI runs those separately. If the repo has no CI covering them, surface them briefly instead of staying silent, since nothing else will catch them.
- Pedantic nitpicks a senior engineer wouldn't raise.
- Generic "add more tests / better docs / more security" that the codebase's own conventions don't call for.
- Issues silenced deliberately in code (lint-ignore, a documented constant).
- Claims of duplication or misplacement — "this already exists in X", "this belongs in Y", "the other command already does this" — verified against the actual other artifact, not asserted from memory or the diff alone. `Read` the file, `Grep` the sibling repo, open the command you're claiming it duplicates. If you can't confirm the other side exists and says what you think it does, drop the finding or soften it to a question ("is this already covered by …?"). Asserting a duplication that isn't there wastes the author's time and burns the review's credibility.

Apply the same skepticism to automated findings that a careful human reviewer applies to any bot: a confident finding is not a correct finding. When you can't verify a finding, lower its confidence and drop it rather than posting a guess.

**Two of those drops don't apply to `project-rules` findings.** "Pedantic nitpick" and "generic, not called for by the codebase's conventions" are taste judgments — and a project rule *is* the codebase's convention, written down deliberately, so dropping one on taste overrules the decision the policy just made. Everything else applies in full, verification above all: a confidently wrong rule violation wastes the author's time exactly like any other false positive.

**A `## Scope` section in the policy moves items in or out of this list.** The likeliest real uses are re-enabling what it drops by default — lint and type findings where the project has no CI to catch them, coverage complaints where the project does have a coverage policy. Anything the policy doesn't name keeps the default above.

## When a plugin is missing

Degrade gracefully; don't hard-fail.

- **No `code-review` plugin:** rely on the `pr-review-toolkit` agents alone.
- **No `pr-review-toolkit`:** rely on the `code-review` plugin alone.
- **Neither installed:** tell the user, then do a lighter inline review yourself — read the diff from `fetch-pr-context`, scan changed lines for real bugs and convention violations, assign a rough confidence, and note in the summary that this was a lighter pass. The rest of the workflow (house style, approval gate, post) is unchanged.
- **Project rules with no agent dispatch:** fold them into the lighter inline pass rather than dropping them — read the diff against each rule yourself and still report per rule. No plugin covers this dimension, so it's the last thing to give up, not the first.
- **No Agent tool in this context** (rare: a subagent at the nesting depth limit, or a harness without agent dispatch — ordinary subagents and forked skills do have the Agent tool and should run the engines normally): same lighter inline pass as above, and tell the user the parallel engines were skipped and why — re-running the skill from a context with agent dispatch restores them.
