# FSD Segments Reference

Within each slice, code is organized into segments:

| Segment    | Purpose                                | Naming                        |
| ---------- | -------------------------------------- | ----------------------------- |
| `ui/`      | Components                             | PascalCase, one per file      |
| `model/`   | Business logic, state, types, hooks    | camelCase / PascalCase types  |
| `api/`     | Backend interactions, request functions| camelCase, one per file       |
| `lib/`     | Pure helpers, utility functions        | camelCase, one per file       |
| `config/`  | Constants and configuration            | UPPER_CASE constants          |
| `index.ts` | Public API exports                     | Single file per slice         |

All segments are **optional** — include only the ones the slice actually needs.

---

## `ui/`

- One function component per `.tsx` file, flat structure (no nested subdirectories)
- File name in kebab-case → component in PascalCase
- Each file exports a single named component (`export function CustomerCard(...)`)
- Co-locate component-scoped styles in the same file or next to it
- `index.ts` re-exports all components

---

## `model/`

Business logic and data layer for the slice. This is where hooks and state management live:

- **Custom hooks** — data access (`useCustomer`), mutations, derived state
- **State management** — stores, slices, atoms, or Context (whatever state library the project uses)
- **Types & interfaces** — domain types, enums, prop types consumed within the slice
- **Computed values** — derived data, selectors, transformations

File conventions:
- One hook per file: `use-{hook-name}.ts` → export `use{HookName}`
- Types can live in a dedicated `types.ts` inside `model/` or alongside related logic
- `index.ts` re-exports all public items

---

## `api/`

Backend interaction layer:

- **API hooks** — data-fetching hooks (`useQuery`, `useMutation` wrappers) or custom fetch hooks
- **Request functions** — underlying fetch calls (REST, GraphQL)
- **DTOs** — Data Transfer Objects for request/response shapes
- **Mappers** — transform API responses to domain models

File conventions:
- One file per resource or operation
- DTOs and request/response shapes can live in a dedicated `types.ts` inside `api/`
- `index.ts` re-exports all public items

---

## `lib/`

Pure helper functions and generic utility hooks:

- Pure functions — no side effects, no domain dependencies
- Utility hooks — generic, not tied to business logic
- Formatters, validators, mappers
- Utility types and generic type helpers can live in a dedicated `types.ts` inside `lib/`
- File in kebab-case → function in camelCase
- `index.ts` re-exports all utilities

---

## `config/`

- Constants in UPPER_CASE
- Status color maps, label maps, query key factories, default values
- Group related constants together
- Can be a single `config.ts` file or a `config/` directory with `index.ts`

---

## `index.ts` (Public API)

- Only export what external consumers need
- Never export internal implementation details
- Named exports only (no default exports)
- **No wildcard re-exports** — `export * from './model'` is forbidden; list exports explicitly
- Group by type: components, hooks, types, config, lib

---

## Best Practices

**Flat segments** — no nesting inside `ui/`, `model/`, `api/`, `lib/`:
```
ui/customer-card.tsx        ✓
ui/cards/customer-card.tsx  ✗
```

**One responsibility per file** — split by operation, not by entity:
```
model/use-customer.ts            # read one
model/use-customer-list.ts       # read list
model/use-customer-mutations.ts  # write operations (or move to api/)
```

**Always import via segment index** — never reach into individual files:
```
import { CustomerCard } from './ui';           ✓
import { CustomerCard } from './ui/customer-card';  ✗
```

**No wildcard re-exports** — always list exports explicitly:
```typescript
// ✗ Forbidden
export * from './model';

// ✓ Correct
export { useCustomer, useCustomerList } from './model';
export type { Customer, CustomerStatus } from './model';
```

> See `examples/slice-examples.md` for directory trees and public APIs across all layers.
