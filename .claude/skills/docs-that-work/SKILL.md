---
name: docs-that-work
description: >-
  Project documentation that serves humans and agents. Use when writing or
  auditing a CLAUDE.md or README.md, when adding a Design Intent section to a
  package, or when a commit is blocked because documentation went stale.
---

# Docs That Work

Write documentation that serves both humans and AI agents. Core principle: **document only what cannot be discovered from code, and only what changes what an agent does**. Codebase structure matters more than documentation volume — a well-organized project with 10 lines of docs beats a messy one with 200.

**Auditing or refreshing an existing `CLAUDE.md` / `README.md` — including any commit blocked by the `docs-that-work-gate` hook — starts by reading `references/audit-procedure.md` and following it. Never refresh a doc file from memory.**

## The Two Filters

Every candidate line clears two independent tests before it earns a place. Failing either one means cut.

### Filter 1 — discoverability

_"Could an agent find this by reading code or config files?"_

Directory trees, exports, types, linter rules, commands, dependencies, test locations, env var names — all discoverable from code and config files. See `references/anti-patterns.md` for the full catalog and the three-question test.

Two things survive this filter:

- **Intent, not actual shape.** Code reveals the **actual** shape of the codebase, not the **intended** one. Where they diverge — an anti-pattern that leaked in and spread — the divergence is undiscoverable from code and is exactly what needs documenting. See [Design Intent](#design-intent) below.
- **Expensive lookups.** Discoverable is not the same as cheap to discover. Where the answer takes a chain of files to reconstruct — the real entrypoint threaded through four Makefile includes, the suite CI actually gates on rather than the one `package.json` advertises — a doc line is a shortcut worth its cost. Where it takes one `grep`, the config file is the better home: config cannot drift from itself, a copy of it can.

### Filter 2 — no-op

_"Does this line change what the agent does, versus what it would do by default?"_

A line can be undiscoverable and still worthless. "Write clean code", "add tests for new features", "be careful with migrations" — nothing in the repo states them, and no agent behaves differently for having read them. They cost context on every turn and buy nothing.

- No-op: "Handle errors properly." → Live: "Every handler returns the `{error: {...}}` envelope — a bare 500 breaks the mobile client's parser."
- No-op: "Keep functions small." → Live: "Split service methods by transaction boundary, not by length — one DB transaction per method."

Measure against the **model's default**, not against a new hire's ignorance — the reader here already knows how to write code. When two people cannot agree that a line is a no-op, what they actually disagree about is how the agent behaves without it, and that is an experiment rather than a debate: pull the line, run the task, compare. A line that fails comes out whole — softening the wording of a no-op leaves a shorter no-op.

Every line that survives both filters still carries a maintenance cost that compounds across every session. Stale docs cause worse decisions than no docs.

## Write the Target, Not the Ban

A rule written as a ban has to describe the anti-pattern in order to forbid it — so the file spells out the wrong shape in detail and the right one not at all, and the shape an agent has just read in detail is the one it reaches for. Describe the shape you want, and the wrong one never enters the file:

- Weak: "Don't use floats for money." → Strong: "Money is stored as integer cents everywhere."
- Weak: "Never import from `internal/` outside its module." → Strong: "Cross-module access goes through the package's public `api.py`."

Keep a bare prohibition only as a hard guardrail you cannot phrase positively, and pair it with the positive target. Design Intent drift callouts are the sanctioned exception — they name a specific file and a located anti-pattern, which is a fact about this repo rather than a general ban.

## CLAUDE.md Rules

**Purpose:** non-obvious context that AI agents cannot discover from code.

**Content that belongs:**

- Project purpose — 1-2 sentences on what this does and why
- Undiscoverable conventions — naming patterns, architectural decisions, gotchas
- Non-obvious constraints — the prerequisite, the ordering rule, the surprising flag
- Design Intent — the intended shape of code in a package (package-level CLAUDE.md only, see below)

**Content that does NOT belong:** anything either filter cuts — commands, directory trees, exports, types, config rules, dependency lists, and generic advice the agent already follows.

**Structure and budget** — root and package files spend different budgets, because they load at different rates:

| File                | Loads                                       | Budget                                                                                       |
| ------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Root `CLAUDE.md`    | every turn of every session                 | ~25 lines; project-wide content only, never a Design Intent section                            |
| Package `CLAUDE.md` | when the agent works in that directory      | ~35 lines of non-obvious context, plus ~10–15 for Design Intent; ≤70 combined ceiling          |

The root file is charged on every turn whether or not the session touches the code it describes, so anything scoped to one module drops into that module's file. A package file never repeats root content. Past the ceiling, it's bloated — cut ruthlessly.

See `references/claude-md-guide.md` for templates and examples.

## Design Intent

Agents treat existing code as the strongest signal for how new code should look. When an anti-pattern leaks into a package, nothing in the code says which pattern is canonical and which is drift — so agents replicate it, and each copy makes the leak look more canonical to the next agent. A Design Intent section writes the intended shape down: a conflict preamble, a golden example pointer, 2–4 do/don't rules, and a sanctioned exception line for any file that deviates on purpose.

**Where:** package-level (i.e., service/module-level) CLAUDE.md, next to the code it shapes. The root `CLAUDE.md` keeps its usual project-wide content and never carries a Design Intent section.

**The conflict rule:** Design Intent outranks existing code. When existing code contradicts it, follow Design Intent and flag the contradicting file as drift — never silently replicate the drifted pattern, and never silently ignore the mismatch. To flag: name the file and the contradicted rule in your final summary or PR description — flagging is reporting, not fixing; editing the drifted file or the CLAUDE.md is a separate task. A file named in an Exception line is not drift — leave it alone, and never model new code on it; new code follows the golden example.

**Writing or editing a Design Intent section: read `references/design-intent.md` first.** The format is verbatim-sensitive (the preamble wording is load-bearing) and authoring is gated on a human — draft the golden example and rules from the dominant or best pattern, then get confirmation before it lands, because if the anti-pattern IS the majority pattern, inferring intent autonomously enshrines the drift. Never present inferred intent as confirmed, and never rewrite, downgrade, or delete a confirmed section without a human. The full format spec, the unconfirmed-proposal fallback, and the maintenance rules all live in that file.

## README.md Rules

**Purpose:** human onboarding — get someone from zero to productive.

**Content:** project description, prerequisites, setup, how to run, how to test, how to contribute. Keep it executable — commands that copy-paste and work beat prose.

Root `README.md` = full overview + setup. Service-level = purpose + how to run independently. Don't duplicate `CLAUDE.md` content — different audiences, different purposes. The two filters govern `CLAUDE.md`, not `README.md`: a human onboarding needs the setup commands spelled out even though an agent could find them.

## Grey Box Documentation

Every module is a grey box — clear public API, hidden internals. Documentation describes the **interface** (what it does, constraints, gotchas), NOT the **implementation** (file trees, data flow, internal functions).

Progressive disclosure: import from public API → read docs for context → read source only if needed.

You own the interface. AI owns the implementation. Tests keep it honest. If docs describe internal wiring, they couple consumers to implementation and break on every refactor.

## Document Separation

Each document has exactly one job:

| Document          | Job                     |
| ----------------- | ----------------------- |
| `README.md`       | Human onboarding        |
| `CLAUDE.md`       | AI agent context        |
| Architecture docs | System design decisions |
| API docs          | Endpoint contracts      |

Never duplicate between them. If the same info is in two places, delete the copy in the wrong file.

## When Documentation IS Needed

Some things genuinely need docs because no amount of code reading reveals them:

- **"Why" decisions** — architectural rationale, trade-off reasoning
- **Cross-service contracts** — agreements not enforced by types or schemas
- **Environment gotchas** — WSL quirks, VPN requirements, OS-specific steps
- **Historical context** — past decisions constraining current design
- **Security procedures** — auth flows, key rotation, access patterns
- **Non-obvious flags** — env vars or CLI flags with surprising behavior

Each still has to clear Filter 2: write the specific fact that changes a decision, not the topic heading. If you're unsure whether something needs docs, apply the three-question test and the no-op catalog in `references/anti-patterns.md`.
