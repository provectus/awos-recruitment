# Documentation Audit Procedure

The ordered process for refreshing an existing `CLAUDE.md` or `README.md` — a doc review, a "the docs are out of date" request, or a commit blocked by the `docs-that-work-gate` hook.

Reading the file and judging that it "looks fine" is not an audit. The audit is done when **every line of every doc file in scope has been classified**, and not before.

## 1. Scope the audit

List the doc files under review:

- **Blocked commit** — the hook names them. Each changed file is owned by the nearest ancestor directory containing a `CLAUDE.md` or `README.md`, and every doc file in that directory is in scope.
- **Direct request** — the files the user named, plus any package `CLAUDE.md` that owns code they mention.

Write the list down before editing anything. If it is longer than three files, audit them one at a time to completion rather than skimming all of them at once.

## 2. Read the change, then the docs

Read the pending diff (`git diff HEAD`, plus untracked files) before reading the docs. You are looking for two things: what the change made **wrong** in the docs, and what it made **missing**.

Then read each in-scope doc file in full. Never edit a doc you have not read end to end in this session.

## 3. Classify every line

Walk the doc top to bottom. Every line — including headings and list items — gets exactly one verdict:

| Verdict         | Trigger                                                                                  | Action                                          |
| --------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **keep**        | clears both filters, still true                                                            | leave untouched                                 |
| **cut: found**  | Filter 1 — an agent can read it out of code or config, and the lookup is cheap             | delete the line                                 |
| **cut: no-op**  | Filter 2 — it does not change what the agent does versus its default                       | delete the whole line, don't trim words          |
| **cut: stale**  | describes behavior, a file, or a constraint that no longer exists                          | delete the line                                 |
| **rewrite**     | true and load-bearing, but phrased as a bare ban, or drifted from what the code now does   | restate as the positive target, or correct it    |
| **move**        | true and load-bearing, but in the wrong file (root vs package, `CLAUDE.md` vs `README.md`) | cut here, add there — never leave both copies    |
| **ask-human**   | changes a confirmed Design Intent section, or sanctions an exception                       | leave the file alone, raise it in step 6         |

A line you cannot classify is a **cut: no-op** candidate: if you cannot say which decision it changes, it does not change one.

Two guards:

- **Drift, not discoverability.** Before cutting a line as `cut: found`, check that what the code shows is what is *intended*. If the code has drifted, the intent is no longer discoverable — that line becomes Design Intent material, not a cut. See `design-intent.md`.
- **Confirmed Design Intent is not yours to edit.** Deleting or rewriting a confirmed section — including its Exception lines — is `ask-human`, always. Fixing a re-pointed golden example path is the one mechanical exception, and only when the file was renamed in this very change.

## 4. Find what is missing

The diff introduced facts of its own. For each, ask whether it clears both filters — undiscoverable **and** behavior-changing:

- a new prerequisite or ordering rule ("the seed script must run before the first test run")
- a new cross-service contract not enforced by types
- a constraint the code cannot state ("this queue is at-least-once — every consumer must be idempotent")
- a deliberate deviation a future agent would otherwise "fix"

Add only these. A new module, a new export, a new dependency, a new command — all discoverable, all stay unwritten.

## 5. Apply and check the budget

Make the edits, then count lines against the budget in `SKILL.md`: ~25 for a root `CLAUDE.md`, ~35 plus ~10–15 of Design Intent for a package one, ≤70 as the hard ceiling. Over the ceiling, go back to step 3 and cut — the ceiling is not negotiated by exception, it is met by cutting.

## 6. Report

State, in the final summary or PR description:

- the files audited, and for each: lines cut, lines added, lines moved
- every `ask-human` item, as an explicit question
- every drift flagged against a Design Intent section — the file and the contradicted rule
- anything you deliberately left alone and why

## Completion criteria

The audit is complete when all of these hold:

1. Every line of every in-scope doc file carries a verdict from step 3.
2. Every step-4 candidate was either written down or rejected for a stated reason.
3. Every file in scope is within its budget.
4. The report in step 6 exists.

**"The docs are already accurate" is a legitimate outcome** — but only as the result of steps 1–3, not as a reason to skip them. Say so explicitly, name the files you audited, and re-run the blocked command; the hook's marker lets an unchanged retry through.
