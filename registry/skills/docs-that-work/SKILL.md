---
name: docs-that-work
description: >-
  Project documentation guidelines. Use when asked to "write documentation",
  "create a CLAUDE.md", "write a README", "document this project",
  "improve documentation", or when creating/updating CLAUDE.md or README.md files.
---

# Docs That Work

Write documentation that serves both humans and AI agents. Core principle: **document only what cannot be discovered from code**. Codebase structure matters more than documentation volume — a well-organized project with 10 lines of docs beats a messy one with 200.

## The Discoverability Rule

Before writing any documentation line, ask: _"Could an agent find this by reading code or config files?"_

If yes, don't write it. Directory trees, exports, types, linter rules, commands, dependencies, test locations, env var names — all discoverable from code and config files. See `references/anti-patterns.md` for the full catalog.

Every line you add has a maintenance cost that compounds across every session. Stale docs cause worse decisions than no docs.

## CLAUDE.md Rules

**Purpose:** non-obvious context that AI agents cannot discover from code.

**Content that belongs:**

- Project purpose — 1-2 sentences on what this does and why
- Undiscoverable conventions — naming patterns, architectural decisions, gotchas
- Non-obvious constraints — "never import X from Y", "always run Z before W"

**Content that does NOT belong:** anything that passes the discoverability rule — commands, directory trees, exports, types, config rules, dependency lists.

**Structure:**

- Root `CLAUDE.md` — project-wide context applicable everywhere
- Service-level `CLAUDE.md` — that module's non-obvious constraints only, never repeat root content

**Size:** target <30 lines. If you're past 50 lines, it's bloated. Cut ruthlessly.

See `references/claude-md-guide.md` for templates and examples.

## README.md Rules

**Purpose:** human onboarding — get someone from zero to productive.

**Content:** project description, prerequisites, setup, how to run, how to test, how to contribute. Keep it executable — commands that copy-paste and work beat prose.

Root `README.md` = full overview + setup. Service-level = purpose + how to run independently. Don't duplicate `CLAUDE.md` content — different audiences, different purposes.

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

If you're unsure whether something needs docs, apply the three-question test from `references/anti-patterns.md`.

## Deep Dives

| Topic                                                  | Reference                       |
| ------------------------------------------------------ | ------------------------------- |
| CLAUDE.md and README templates                         | `references/claude-md-guide.md` |
| Anti-patterns, bloat examples, the three-question test | `references/anti-patterns.md`   |
