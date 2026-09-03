# Finding issues — review engines

> **Part of:** [pr-review](../SKILL.md). How to find issues by orchestrating existing review plugins instead of hand-rolling analysis.

## Choosing engines

Work down the ladder; the first row that applies decides what runs, and later rows only add — they never override an earlier one. Never ask the user anything before the review: the ladder decides from what the request and the repo already say.

| Priority | When | Dispatch |
|---|---|---|
| 1 — the user's ask | The request already names a focus, depth, or budget ("just check the error handling", "quick pass", "be thorough") | Exactly what serves it — the matching specialists, the breadth pass, or everything applicable. |
| 2 — the policy | The base-branch policy defines `## Project rules` | The project-rules engine, alongside whatever else runs — no other engine covers that dimension. |
| 3 — the default | Otherwise | The toolkit engine: `code-reviewer` for breadth, plus the specialists selected from the diff's shape (table below). |
| 4 — availability | `pr-review-toolkit` is missing | The fallback bundle (the `code-review` plugin). Neither plugin installed → the lighter inline pass in "When a plugin is missing". |

**The selection is the main session's decision, made from the step 1 diff — nothing is spawned to decide, and an unselected agent is never spawned.** Everything selected dispatches in parallel and stays independent until the merge — wall-clock is the slowest agent, not the sum.

**Announce the run twice.** At dispatch (SKILL step 2): one chat line naming the engines and agents chosen and the focus applied, plus — when the repo has no `.claude/review-policy.md` — a one-line note that review rules can be configured there, then proceed with defaults. At the results gate (SKILL step 5): the Policy and Agents status lines explain how the finished review was made.

## The toolkit engine: pr-review-toolkit agents

The primary engine. Each agent is individually addressable — dispatch with the Agent tool (`subagent_type: "pr-review-toolkit:<agent>"`), giving each the diff and its scope:

| Agent | Dispatch when… | Looks for |
|---|---|---|
| `code-reviewer` | always — the breadth pass | General quality, bugs, project-convention adherence |
| `pr-test-analyzer` | the diff adds or changes tests | Coverage gaps, weak assertions, flaky-test risk |
| `silent-failure-hunter` | the diff touches error handling, catch blocks, fallbacks | Swallowed errors, misleading messages, silent failures |
| `type-design-analyzer` | the diff adds or changes types | Encapsulation, invariants, type-design quality |
| `comment-analyzer` | the diff is comment/doc-heavy | Comment accuracy vs. code, rot, completeness |

`code-simplifier` is for applying simplifications to a working tree, not for reviewing someone else's PR — skip it here.

Give each agent the context its dimension needs, not just the diff: `pr-test-analyzer` can't judge coverage gaps without the existing tests, and `comment-analyzer` needs the surrounding code to tell an outdated comment from a correct one. (These agents carry their own descriptions and system prompts — this skill selects them and feeds them scope; it doesn't re-prompt them.) For a large diff, chunk it by file or directory and dispatch per chunk — a diff that overflows the context window gets reviewed shallowly; note in the step 7 summary if a chunk was too big to cover fully.

## The project-rules engine (when the policy defines them)

When the base-branch `.claude/review-policy.md` has a `## Project rules` section, run one more engine. A repository's own conventions — "every endpoint needs an auth decorator", "no raw SQL outside `repositories/`", "migrations must be reversible" — are invisible to an engine that has never read them. Dispatch a subagent alongside the others, unnamed and in parallel, with the diff, the checkout path, and the rules **verbatim**. Don't push the rules into the toolkit agents instead — that re-prompts them and dilutes the dimension each is good at.

**This engine reports per rule, not only per finding.** Each rule comes back as checked-and-clean, violated (with the findings), or not-applicable-to-this-diff — the per-rule outcome is what shows a clean run as clean rather than silent. Findings come back in the same fields as the other engines ("Merge and carry forward" lists them), tagged source `project-rules` — the false-positive discipline keys on that tag — and scoped to changed lines.

## The fallback bundle: the code-review plugin

Only when `pr-review-toolkit` is missing. The `code-review` plugin is a single command, not addressable agents: invoke it with the Skill tool (`code-review:code-review`), follow its **analysis steps**, and **stop before the step that posts** — its final step comments on the PR in a fixed style, which this skill replaces. Keep the in-memory findings: file, line, what, why, suggested fix, confidence, and flag reason. Its bundle runs an eligibility check, five parallel reviewers, and per-finding confidence scorers with a <80 cut; honour the models its steps name, and keep the scorers — their cut is what stops the bundle handing triage its full noise floor.

## Model discipline

`model:` goes on every agent dispatch this skill makes, with exactly one exception — an agent dispatched without it silently inherits the session's model.

| Dispatch | Model | Why |
|---|---|---|
| Toolkit engine: `code-reviewer` and the selected specialists | Sonnet | A bounded pass over one dimension; an agent whose definition names a model keeps it |
| Project-rules agent | Sonnet | Matching a diff against written rules is checking, not judgment |
| Fallback bundle internals | What its recipe names per step (Haiku checks and scorers, Sonnet reviewers) | The recipe's own cost model |
| Triage's mechanical per-finding checks | Haiku | Matching, not judgment |
| **Step 3 triage subagent** | **none — inherits the session model** | The one deliberate exception: triage is judgment, not a bounded pass |

## Running engines

**"Choosing engines" decides what runs — nothing else joins.** No reviewers beyond the ladder's selection.

**Engines run one level deep.** An agent an engine dispatches does not dispatch agents of its own — verification belongs to the step-3 triage agent. Triage's own mechanical per-finding fan-out is the one sanctioned nesting. (The fallback bundle's internal fan-out is the recipe's own and runs from the main session.)

**Bound each engine.** Changed files plus one hop of context, then report.

**Engines read the repo, not the network.** Verification inside an engine means the code, the diff, and the repo's own artifacts — `Read` the file, `Grep` the sibling module, open the test that covers it. A finding that can't be settled from the repo — an API that may not exist, a spec version, an upstream default — comes back with the open question attached, confidence lowered, marked as needing external evidence; step 5's "Back findings with external sources" is where the user opts into that fetch.

**Hand context over by path, not inline.** `fetch-context` already wrote `diff.patch` and `context.json` — give each agent those paths plus its scope line (local mode: write the diff to one file first).

## Collecting the engines' results

**Dispatch engines as ordinary subagents — never as named background agents.** An unnamed `Agent` call returns its output as the tool result the moment it finishes; a named agent's completion arrives as a background teammate message that can land long after the work is done.

**Enumerate every agent dispatched — count, model, and depth — and carry that roster to the results gate.** The roster is what catches a named agent, an unpinned model, or a depth-2 dispatch while there's still time to abandon it.

**Never poll.** No `sleep` loops, no `until [ -s <file> ]; do sleep 30; done`, no watching a task's output file, no re-listing a directory. A wait loop means the dispatch was wrong: fix the dispatch.

**Never read agent transcripts to recover a result.** The `.jsonl` files under `subagents/` are harness internals; a mid-flight read returns a partial result indistinguishable from a finished one.

**An engine that never reports is a failed engine — an engine that reports nothing to raise is not.** The two are indistinguishable from the length of a findings list, so read each engine's outcome rather than its output: each toolkit agent reports on its own dimension, the project-rules engine reports per rule, and the fallback bundle reports whether its reviewers ran and what its scorers filtered out. A clean diff really does produce zero surviving findings.

When an engine genuinely didn't report, say so, degrade via *When a plugin is missing* below, and name it in the step 7 summary. Refuse outright to reconstruct an engine's output yourself and hand it to triage as engine findings — that is session-authored content entering the channel triage exists to keep independent.

## Merge and carry forward

Combine every engine that ran into one findings list and dedupe by file, line, and substance (agents overlap — two may flag the same real bug). Prefer the more specific phrasing. For each surviving finding keep: file, line, what, why, suggested fix, a confidence read (use the fallback bundle's score when it ran, otherwise judge from how decisively the agent verified it), the source, and whether it was marked as needing external evidence — the mark feeds the gate's optional evidence pass. Confidence and source feed the house-style ordering and the verdict reason back in the SKILL workflow.

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

- **No `pr-review-toolkit`:** ladder row 4 — the fallback bundle is the engine.
- **No `code-review` plugin:** nothing changes on the default path; it only matters when the toolkit is also missing.
- **Neither installed:** tell the user, then do a lighter inline review yourself — work from the diff step 1 already gathered (`fetch-pr-context` in public mode, `get-local-diff` in local), scan changed lines for real bugs and convention violations, assign a rough confidence, and note in the step 7 chat summary — never in the posted review text (house-style.md owns that rule) — that this was a lighter pass. The rest of the workflow (house style, approval gate, post) is unchanged.
- **Project rules with no agent dispatch:** fold them into the lighter inline pass rather than dropping them — read the diff against each rule yourself and still report per rule. No plugin covers this dimension, so it's the last thing to give up, not the first.
- **No Agent tool in this context** (rare: a subagent at the nesting depth limit, or a harness without agent dispatch — ordinary subagents and forked skills do have the Agent tool and should run the engines normally): same lighter inline pass as above, and tell the user the parallel engines were skipped and why — re-running the skill from a context with agent dispatch restores them.
