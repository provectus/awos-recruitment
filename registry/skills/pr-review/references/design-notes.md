# Design notes — why pr-review is shaped this way

> **Part of:** [pr-review](../SKILL.md). Background for maintainers: the incidents and reasoning behind rules that SKILL.md and [analysis.md](analysis.md) state without justification. Nothing here is needed to run a review — read it before changing a rule, not before following one.

## No `context: fork`

A forked skill runs as a subagent, and subagents cannot use `AskUserQuestion`; the step 5 results gate depends on it. The Agent tool is not the constraint — subagents can dispatch nested subagents, so the step 2 engines would run fine in a fork. For isolation from other work, invoke the skill in a dedicated session instead.

## Triage in a fresh subagent (step 3)

A review is worth only as much as its independence, and the merge is where independence quietly dies: deciding which findings survive, and at what confidence, is exactly the judgment a session that wrote, planned, or debated the change bends toward its own decisions. A model is a poor judge of its own anchoring, so the skill doesn't ask it to self-assess; it removes the need by running triage in a context that never saw the conversation — whether or not the session touched the change. A `"fork"` subagent inherits the conversation and defeats this, which is why step 3 names `"general-purpose"`.

## The draft is a file, printed in full (steps 4–5)

Observed in three consecutive sessions: the draft was composed in thinking, then the gate asked the user to approve "the draft above" while the message contained nothing. The model's memory of having printed is not evidence — only the step 4 `Write` call and text visible in the turn are. Hence: write the file before the gate, print the file's content, and put the path in the question so the user can open the draft even if the print is squeezed out. Session-wide brevity or compression modes are the usual cause of the squeeze, which is why the deliverable is exempt from them.

The four items the step 5 self-check strikes (mechanism-first findings, multi-claim sentences, claimed executions, narration about the review) each reached a real MR before the check existed; [house-style.md](house-style.md) has the before/after examples.

## Amendments re-enter the gate (step 7)

Observed across six consecutive amendments in one session: each was drafted and posted in a single step, with the text shown to the user only afterwards. The gate that governed first delivery silently stopped applying to everything after it — and post-delivery is exactly when the user is most engaged and most likely to be surprised. A request to change something therefore approves the action, never the wording.

## Collecting engine results (analysis.md)

Measured on one real run, 72 minutes end to end:

- Six engines dispatched as *named* background agents were all idle within 8 minutes. Their results were not collected for 28, and every completion notification arrived in one batch after the review had already been posted. Naming the agents is what broke it — an unnamed `Agent` call returns its output as the tool result, and the harness notifies on completion.
- 31 of the 72 minutes went to 35 polling calls (`sleep`/`until` loops on output files), 17 of them killed by the 120-second command timeout — while waiting on results that already existed.
- One scrape of a subagent `.jsonl` transcript for "the last assistant message" returned a 76-byte fragment of a triage that was still running. An evidence pass was likewise read mid-flight and posted on; the real report arrived afterwards carrying three corrections to text that was already live.

## An empty engine is a failed engine (analysis.md)

When an engine returned nothing, the observed reflex was to reconstruct its output from whatever was at hand and pass that to triage as engine findings. That is session-authored content entering the one channel the skill protects from session influence, so the rule is to report the engine as failed, degrade to the remaining engine, and tell the user.
