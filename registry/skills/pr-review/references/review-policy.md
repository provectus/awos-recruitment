# Review policy — what a project can tune

> **Part of:** [pr-review](../SKILL.md). How a repository adjusts what this skill judges by, via a committed `.claude/review-policy.md`. This file is guidance for *writing* one — it is not a policy to copy. The fragments below come from several different, deliberately incompatible imaginary projects; no two of them belong in the same file, and none of them belongs in yours unless you'd have written it anyway.

## The file

`.claude/review-policy.md`, committed in the repository under review. Markdown, four optional `##` sections, in any order:

```
## What blocks merge
## Scope
## How findings read
## Project rules
```

Every section is optional and so is the file. **The policy speaks to specific cases; everything it doesn't mention keeps the skill's default.** A three-line policy naming one blocking class is a complete, working policy — there is no requirement to restate defaults you're happy with, and restating them only creates something to drift.

**It is read from the base branch, not the PR head.** A pull request that edits the policy cannot govern its own review. Change it in a PR like any other file; it governs reviews from the merge onward. When a PR does modify it, the reviewer says so in chat, so the change isn't invisible.

## Write it to be read literally

The reviewer is a model reading prose. It cannot ask you what you meant, and a rule that depends on inference gets applied inconsistently — sometimes as you intended, sometimes not, with no signal telling you which happened. This is the main way a policy disappoints, and there is no mechanism that fixes it. Naming the trigger and the consequence is what makes a line reliable:

- Reliable, because there's nothing to infer: *"A change to any file under `api/` that adds a route without an auth decorator blocks."*
- Unreliable, because every word is a judgment call: *"Be strict about API security."*

Prefer a rule you can imagine checking yourself against a diff. If you can't tell whether a given diff violates it, neither can the reviewer.

## `## What blocks merge`

Adds or reclassifies finding classes for the verdict. By default the verdict comes from what a finding costs — how often the code runs, and what goes wrong when it does — and that rule still decides everything you don't name here.

Use it when your project's economics differ from the default. Three different projects, three different answers:

> A library with no CI at all: *"Type and lint findings block — nothing else catches them here."*
>
> A service with a coverage commitment: *"Changed behaviour without a test blocks."*
>
> A prototype repository: *"Nothing blocks. Every finding is a comment; we merge and iterate."*

This section also decides which findings carry the `[major]` mark, because "this blocks the merge" and "this won't be approved until it's resolved" are the same judgment at different scales. Name a class here and findings in it come back marked, and the verdict follows — a project that blocks on missing tests is one where a missing test is `[major]`. Nothing you name here is advisory.

**Project-rule violations get no automatic verdict weight.** Writing a rule under `## Project rules` makes it *checked*, not *blocking*. If you want a rule to block, say so here too — the natural assumption that writing a rule makes violating it a blocker is wrong, and it's the most common surprise with this file.

## `## Scope`

Moves findings in or out of the reviewer's false-positive discipline, which by default drops several classes as noise.

The two most useful moves are both re-enabling something the default drops, and both exist because the default assumes infrastructure you may not have:

> *"Report lint and type findings. We have no CI."*
>
> *"Report missing coverage on changed lines. We hold 80% and mean it."*

It works the other direction too — naming something to drop that the default keeps — but that's rarer, and worth a moment's thought: a class of finding you never want to see is often one worth fixing at the source instead.

**Suppressing nits belongs here.** `[nit]` findings are the ones the reviewer marks as safe to skip, and some teams would still rather not read them:

> *"Don't post nits. Wording and formatting go through a separate pass."*

Worth knowing what that costs before setting it: the mark already tells the author they can ignore those comments, so suppressing them buys a shorter review rather than less obligation. It also silently drops the "while we're here" observations, which are cheap to act on precisely because nobody has to.

## `## How findings read`

Tunes how findings are written, layering over [house-style.md](house-style.md).

What you can change is **trace depth** — whether a finding walks the path from a concrete input to what it costs, or trusts the reader to make that jump:

> *"Skip the worked trace on query and index findings. Everyone reviewing this repo writes SQL daily."*

What you **cannot** change is the density floor: one idea per sentence, plain words, no stacked clauses, no unexplained jargon. That floor exists because a review asked to "be terse" doesn't get shorter — it gets *denser*, packing the same content into harder sentences, and the reader pays the difference back decompressing it. A policy that could turn the floor off would reintroduce exactly the problem it was written to fix. Ask for less content, not tighter packing.

## `## Project rules`

Conventions specific to your codebase that no generic review engine knows to look for. These run as their own analysis engine, and the reviewer reports each rule as checked-and-clean, violated, or not applicable to the diff — so a clean run is visibly a clean run rather than silence.

Shape them as a trigger and a consequence, one rule per line:

> *"Anything under `handlers/` that opens a transaction must close it in the same function."*
>
> *"No raw SQL outside `repositories/`."*
>
> *"A migration without a tested `down` step is a violation."*

Rules are checked against **changed lines only**, like every other finding. A violation your PR introduces is reported; one that already existed in a file you happened to touch is not. That keeps the review about your change rather than about the repository's history — clean those up in their own PR.

## What a policy cannot do

The policy tunes what the review *thinks*, never what it is *allowed to do*. These are outside its reach, and a line reaching for one of them is ignored, with the reviewer naming that line in chat rather than silently dropping it:

- the human approval gate before anything is posted;
- the independence of the triage step;
- the rule against deleting or recreating an existing pending review draft;
- the ban on force-pushing.

A policy cannot make the reviewer post without asking, and that is deliberate: the gate is what makes everything above it safe to get wrong.

## Where policy notices show up

In the chat with whoever is running the review — which policy was loaded, any line that was ignored, and whether the PR modifies the policy. Never in the posted review. The PR author is owed findings about their code, not notes about the reviewer's configuration, and they can read the policy file themselves.
