---
name: feature-sliced-design
description: This skill should be used when the user asks to "create a page", "add an entity", "build a widget", "create a feature", "scaffold FSD structure", "refactor to FSD", "where should I put this code", "what layer does X go in", "organize my React code", "FSD compliant", "fix layer violation", or when writing, reviewing, or refactoring React/TypeScript code to ensure Feature-Sliced Design architecture compliance. Triggers on tasks involving frontend component creation, code organization, layer placement, or architectural decisions.
version: 2.1.0
---

# Feature-Sliced Design

Architectural guide for organizing React/TypeScript frontends following Feature-Sliced Design (FSD) — a methodology that splits code into layers and slices with strict dependency rules.

## Why FSD

FSD treats every slice as a **Grey Box module**: a clear public API (`index.ts`) with hidden internals (`ui/`, `hooks/`, `utils/`). This is both human- and AI-friendly:

- **Progressive Disclosure** — import from `@/entities/customer`, not internal files
- **Navigability** — file structure = logical structure; code is where you expect it
- **SRP via layers** — each layer has one job, narrowing the scope of changes
- **Same-layer ban** — slices are isolated; changes don't cascade sideways

## Structure

```
src/
├── app/                # Providers, routing, global styles, entry point
├── pages/              # Route-based entry points
├── widgets/            # Composite UI blocks
├── features/           # User interactions (auth, search, filters)
├── entities/           # Business domain logic
└── shared/             # Reusable infrastructure
```

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
| App-level setup (providers, routing, global init)? | app      |
| Route/page?                                        | pages    |
| Reusable UI block used across multiple pages?      | widgets  |
| User action (submit form, search, filter, like)?   | features |
| Business entity (user, customer, project)?         | entities |
| Shared utilities, config, API client?              | shared   |

## Slice Structure

Every slice follows the same internal layout:

```
{slice-name}/
├── ui/                 # Components (one per file)
├── hooks/              # React hooks (one per file)
├── utils/              # Pure helpers (one per file)
├── types.ts            # Local types and enums
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

If using a component library (ShadCN, MUI, Ant Design, etc.):

- Base components live outside FSD layers (`components/ui/` or `node_modules`)
- Never modify library components directly — wrap in `shared/ui/` or slice `ui/`
- Domain-specific wrappers belong in the slice that uses them

## CLAUDE.md in Every Slice

Every slice must have a `CLAUDE.md`. Keep it very short: what this module is for + anything non-obvious. Everything else is discoverable from code. See `references/claude-md-template.md` for the template.

## Code Generation Rules

1. Co-locate logic in the owning slice — don't scatter across layers
2. Don't create shared code unless reused in 2+ places
3. Follow existing naming conventions in the project
4. Never pollute `shared/` with domain-specific code
5. Always create proper `index.ts` public API

## Deep Dives

| Need                                                          | Read                               |
| ------------------------------------------------------------- | ---------------------------------- |
| Layer rules, when to create each layer, cross-entity patterns | `references/layers.md`             |
| Segment rules (ui, hooks, utils, types, config, index)        | `references/segments.md`           |
| CLAUDE.md template                                            | `references/claude-md-template.md` |
| Slice examples (entity, feature, widget, page)                | `examples/slice-examples.md`       |
