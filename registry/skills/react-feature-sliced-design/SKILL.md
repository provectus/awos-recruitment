---
name: react-feature-sliced-design
description: "Enforces Feature-Sliced Design (FSD) architecture in React/TypeScript projects by scaffolding compliant folder structures, validating layer boundaries and import directions, detecting and fixing layer violations, and teaching FSD conventions during code generation and review. Use when asked to 'create a page', 'add an entity', 'build a widget', 'scaffold FSD structure', 'refactor to FSD', 'where should I put this code', 'what layer does X go in', 'organize my React code', 'fix layer violation', or 'review my FSD structure'. Triggers on any React/TypeScript task involving FSD layers, slices, segments, cross-layer imports, or public API boundaries."
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

## Workflow: Adding a New Slice

1. **Decide the layer** — use the Layer Decision Guide above
2. **Scaffold** — create `src/{layer}/{slice-name}/` with needed segments (`ui/`, `model/`, `api/`, `lib/`)
3. **Write the public API** — create `index.ts` with explicit named exports (no `export *`)
4. **Validate imports** — verify all imports flow downward only; no same-layer imports exist
5. **Add CLAUDE.md** — 1-3 sentences on what this slice does + any non-obvious context
6. **Verify** — check: (a) no upward imports, (b) external code only imports from `index.ts`, (c) no `export *` re-exports

## Inline Example: Entity Slice

A minimal `entities/customer/` slice:

```typescript
// entities/customer/model/types.ts
export interface Customer {
  id: string;
  name: string;
  email: string;
  status: 'active' | 'inactive';
}

// entities/customer/model/use-customer.ts
import { useState, useEffect } from 'react';
import { fetchCustomer } from '../api';
import type { Customer } from './types';

export function useCustomer(id: string) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  useEffect(() => { fetchCustomer(id).then(setCustomer); }, [id]);
  return customer;
}

// entities/customer/api/customer-api.ts
import type { Customer } from '../model';
export async function fetchCustomer(id: string): Promise<Customer> {
  const res = await fetch(`/api/customers/${id}`);
  return res.json();
}

// entities/customer/index.ts — PUBLIC API
export { useCustomer } from './model';
export type { Customer } from './model';
export { CustomerCard } from './ui';
```

## Teaching Behavior

Actively teach FSD principles — explain decisions, don't just apply rules:

| Situation | Action |
|-----------|--------|
| Writing code | Explain layer/segment choice in 1-2 sentences |
| Spot a violation | Flag it, explain why it breaks FSD, show the fix |
| "Where should I put this?" | Walk through the Layer Decision Guide |
| Reviewing code | Check FSD compliance, suggest corrections with reasoning |
| Project deviates from guide | Ask for reasoning first — project consistency matters more than strict compliance |

### Common Violations Quick-Reference

| Violation | Fix |
|-----------|-----|
| Upward import (`entity → feature`) | Move shared logic to `shared/` or compose in a higher layer |
| Same-layer import (`entity → entity`) | Use `@x` cross-imports or compose in `widget/`/`feature/` |
| Direct internal import (`./ui/card`) | Import from slice's `index.ts` instead |
| Wildcard re-export (`export *`) | List exports explicitly |

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
| Slice examples (entity, feature, widget, page)                    | `references/slice-examples.md`     |

## Official FSD Specification

This skill is a React/TypeScript adaptation of Feature-Sliced Design. For the canonical spec, use `WebFetch` to read from [fsd.how/llms.txt](https://fsd.how/llms.txt):

- **Abridged**: [fsd.how/llms-small.txt](https://fsd.how/llms-small.txt) — compact reference
- **Complete**: [fsd.how/llms-full.txt](https://fsd.how/llms-full.txt) — full documentation

> **Do NOT fetch these URLs proactively.** Only use `WebFetch` when the engineer explicitly asks for the full FSD specification or you encounter a question this skill doesn't cover.

Consult the official spec when you need details beyond what this skill covers (e.g., migration strategies, advanced decomposition patterns, framework-agnostic rules).
