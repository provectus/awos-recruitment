# FSD Slice Example

Every slice — regardless of layer — follows the same structure.

## `src/{layer}/{slice-name}/`

```
{slice-name}/
├── ui/
│   ├── {component-a}.tsx      # One component per file
│   ├── {component-b}.tsx
│   └── index.ts               # Re-exports all components
├── model/
│   ├── use-{something}.ts     # Hooks, state, business logic
│   ├── types.ts               # Domain types, interfaces, enums
│   └── index.ts               # Re-exports all model items
├── api/
│   ├── {resource}.ts          # API calls, data-fetching hooks
│   ├── types.ts               # DTOs, request/response shapes
│   └── index.ts               # Re-exports all API items
├── lib/
│   ├── {helper}.ts            # Pure helpers, utility functions
│   ├── types.ts               # Utility types, generic type helpers
│   └── index.ts               # Re-exports all lib items
├── config.ts                  # Constants, mappings, defaults
├── index.ts                   # PUBLIC API — the only file others import from
└── CLAUDE.md                  # What this module is for + non-obvious context
```

All segments are optional — include only the ones the slice actually needs.

## How the files work

**`index.ts`** — public API. The only entry point for external consumers. Selectively re-exports from segments (no wildcard re-exports):

```typescript
export { CustomerCard, CustomerAvatar } from './ui';
export { useCustomer, useCustomerList } from './model';
export type { Customer, CustomerStatus } from './model';
export { useCustomerQuery, useCreateCustomerMutation } from './api';
export { CUSTOMER_QUERY_KEYS } from './config';
```

**`ui/index.ts`**, **`model/index.ts`**, **`api/index.ts`**, **`lib/index.ts`** — segment indexes. Re-export everything from their segment so that `index.ts` and sibling files import from `'./ui'`, never from `'./ui/customer-card'`.

**`model/types.ts`** — all TypeScript types for the slice. Enums, interfaces, form data types. Lives inside `model/` alongside related business logic.

**`config.ts`** — constants: status color maps, label maps, query key factories, default values.

**`CLAUDE.md`** — 1-3 sentences: what this module is for. Plus a `## Notes` section if there are non-obvious behaviors or gotchas. Nothing else.

## What differs per layer

Nothing structural. The difference is only in **what the slice can import**:

- `entities/customer/` → can only import from `shared/`
- `features/search/` → can import from `entities/` and `shared/`
- `widgets/dashboard-header/` → can import from `features/`, `entities/`, `shared/`
- `pages/settings/` → can import from `widgets/`, `features/`, `entities/`, `shared/`
