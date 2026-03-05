---
name: react-feature-sliced-design
description: This skill should be used when the user asks to "create a page", "add an entity", "build a widget", "create a feature", "scaffold FSD structure", "refactor to FSD", "where should I put this code", "what layer does X go in", "organize my React code", "FSD compliant", "fix layer violation", "explain FSD", "why is this in this layer", "review my FSD structure", or when writing, reviewing, or refactoring React/TypeScript code to ensure Feature-Sliced Design architecture compliance. Also triggers when the user places code in the wrong layer, imports across layers incorrectly, or breaks FSD conventions — the agent should proactively explain the violation and teach the correct approach.
version: 3.0.0
---

# React Feature-Sliced Design

Architectural guide for organizing React/TypeScript frontends following Feature-Sliced Design (FSD) — a methodology that splits code into layers and slices with strict dependency rules. Tailored for React function components, hooks, and the React ecosystem.

## Why FSD

FSD treats every slice as a **Grey Box module**: a clear public API (`index.ts`) with hidden internals (`ui/`, `model/`, `api/`, `lib/`). This is both human- and AI-friendly:

- **Progressive Disclosure** — import from `@/entities/customer`, not internal files
- **Navigability** — file structure = logical structure; code is where you expect it
- **SRP via layers** — each layer has one job, narrowing the scope of changes
- **Same-layer ban** — slices are isolated; changes don't cascade sideways

## Structure

```
src/
├── app/                # Providers, router, global styles, entry point (no slices)
├── pages/              # Route components (one per route)
├── widgets/            # Composite UI blocks
├── features/           # User interactions (auth, search, filters)
├── entities/           # Business domain (components, hooks, types)
└── shared/             # Reusable infrastructure (no slices)
```

> `app/` and `shared/` are divided directly into segments — they do not contain slices.

## Layer Dependencies (CRITICAL)

Imports flow DOWN only. Same-layer imports are FORBIDDEN.

| Layer    | Can Import From                            | Cannot Import From                      |
| -------- | ------------------------------------------ | --------------------------------------- |
| app      | pages, widgets, features, entities, shared | —                                       |
| pages    | widgets, features, entities, shared        | app                                     |
| widgets  | features, entities, shared                 | app, pages                              |
| features | entities, shared                           | app, pages, widgets                     |
| entities | shared                                     | app, pages, widgets, features           |
| shared   | —                                          | app, pages, widgets, features, entities |

## Layer Decision Guide

| Question                                           | Layer    |
| -------------------------------------------------- | -------- |
| App-level setup (providers, router, global init)?  | app      |
| Route/page?                                        | pages    |
| Reusable UI block used across multiple pages?      | widgets  |
| User action (submit form, search, filter, like)?   | features |
| Business entity (user, customer, project)?         | entities |
| Shared utilities, config, API client?              | shared   |

## Slice Structure

Every slice follows the same internal layout (all segments optional):

```
{slice-name}/
├── ui/                 # Components (.tsx, one per file)
├── model/              # Hooks, state, types
├── api/                # Data fetching (REST/GraphQL)
├── lib/                # Pure helpers, utility hooks
├── config.ts           # Constants, configuration
├── index.ts            # PUBLIC API — only exports for external use
└── CLAUDE.md           # Purpose + non-obvious context (required)
```

Each segment directory has its own `index.ts` re-exporting all items. External code imports ONLY from the slice's root `index.ts`.

## Naming Conventions

| Type        | Convention                  | Example               |
| ----------- | --------------------------- | --------------------- |
| All Files   | kebab-case                  | `employee-picker.tsx` |
| Components  | PascalCase                  | `EmployeePicker`      |
| Hooks       | camelCase with `use` prefix | `useEmployeeData`     |
| Utilities   | camelCase                   | `formatCurrency`      |
| Types       | PascalCase                  | `EmployeeData`        |
| Directories | kebab-case                  | `employee-picker/`    |

## UI Library Integration

If using a component library:

- Base components live outside FSD layers (`components/ui/` or `node_modules`)
- Never modify library components directly — wrap in `shared/ui/` or slice `ui/`
- Domain-specific wrappers belong in the slice that uses them

## CLAUDE.md in Every Slice

Every slice must have a `CLAUDE.md`. Keep it very short: what this module is for + anything non-obvious. Everything else is discoverable from code. See `references/claude-md-template.md` for the template.

## Teaching Behavior

This skill is not just a ruleset — it should actively teach engineers FSD principles. Follow these guidelines:

**When writing code**, briefly explain your FSD decisions:
- Why you chose a specific layer ("This is a `feature/` because it's a user action, not a domain entity")
- Why something goes in a specific segment ("Hooks that call the API go in `api/`, business logic hooks in `model/`")
- Keep explanations to 1-2 sentences — enough to teach, not lecture

**When you spot a violation**, proactively flag it and explain the fix:
- Layer violation: "This import goes upward (`entity → feature`) — FSD only allows downward imports. Move the shared logic to `shared/` or compose in a higher layer."
- Same-layer import: "Entities can't import other entities directly. Use `@x` cross-imports or compose in a `widget/` or `feature/`."
- Missing public API: "External code imports directly from `./ui/customer-card` — it should import from the slice's `index.ts`."
- Wildcard re-export: "`export * from` hides what's public — list exports explicitly."

**When the engineer asks "where should I put this?"**, walk them through the Layer Decision Guide and explain your reasoning.

**When reviewing code**, check for FSD compliance and suggest corrections with explanations, not just fixes.

**When the project deviates from this guide**, don't treat it as an error automatically. Real projects may have minor differences in naming, segment layout, or file organization — and that's fine as long as there's a clear reason behind it. Ask the engineer for their reasoning before suggesting changes. Consistency within the project matters more than strict compliance with this document.

## Code Generation Rules

1. Co-locate logic in the owning slice — don't scatter across layers
2. Don't create shared code unless reused in 2+ places
3. Follow existing naming conventions in the project
4. Never pollute `shared/` with domain-specific code
5. Always create proper `index.ts` public API
6. No wildcard re-exports — always list exports explicitly (`export * from` is forbidden)
7. When generating code, include a short comment or message explaining the FSD reasoning behind placement decisions

## Deep Dives

| Need                                                              | Read                               |
| ----------------------------------------------------------------- | ---------------------------------- |
| Layer rules, when to create each layer, cross-entity patterns     | `references/layers.md`             |
| Segment rules (ui, model, api, lib, config, index)                | `references/segments.md`           |
| CLAUDE.md template                                                | `references/claude-md-template.md` |
| Slice examples (entity, feature, widget, page)                    | `examples/slice-examples.md`       |

## Official FSD Specification

This skill is a React/TypeScript adaptation of Feature-Sliced Design. For the canonical spec, use `WebFetch` to read from [fsd.how/llms.txt](https://fsd.how/llms.txt):

- **Abridged**: [fsd.how/llms-small.txt](https://fsd.how/llms-small.txt) — compact reference
- **Complete**: [fsd.how/llms-full.txt](https://fsd.how/llms-full.txt) — full documentation

> **Do NOT fetch these URLs proactively.** Only use `WebFetch` when the engineer explicitly asks for the full FSD specification or you encounter a question this skill doesn't cover.

Consult the official spec when you need details beyond what this skill covers (e.g., migration strategies, advanced decomposition patterns, framework-agnostic rules).
