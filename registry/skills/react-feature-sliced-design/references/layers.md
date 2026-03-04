# FSD Layers Reference

## Layer Hierarchy

```
app        (highest)  — Providers, routing, global init
pages                 — Application routes
widgets               — Composite UI blocks
features              — User interactions
entities              — Business domain objects
shared     (lowest)   — Infrastructure code
```

---

## App (`src/app/`)

**Purpose**: Composition root — providers, router, global styles, entry point.

- Single entry point for the application
- Wraps in providers (query client, theme, auth, etc.)
- Defines router configuration
- **Divided directly into segments (no slices)** — it's the shell that assembles everything

**Can Import**: all layers | **Cannot Import**: —

---

## Pages (`src/pages/`)

**Purpose**: Route-level components that compose widgets, features, and entities into views.

- One page = one route
- Orchestrates lower layers into a complete screen
- Contains page-specific components, hooks, state

**Can Import**: widgets, features, entities, shared | **Cannot Import**: app, other pages

> See `examples/slice-examples.md` for directory tree and public API.

---

## Widgets (`src/widgets/`)

**Purpose**: Composite UI blocks that combine features and entities, reused across pages.

- Self-contained components with business meaning
- Combine multiple entities and/or features
- Should represent a meaningful unit, not just a visual grouping

**Can Import**: features, entities, shared | **Cannot Import**: app, pages, other widgets

**When to create**: UI block used in 2+ pages, combines multiple entities/features, too complex for a single entity.

> See `examples/slice-examples.md` for directory tree and public API.

---

## Features (`src/features/`)

**Purpose**: User interactions — things a user *does* in the app.

- Encapsulates a single user action or interaction flow
- Contains components + hooks + API calls for that action
- Examples: auth, search, comment, like, filter, share

**Can Import**: entities, shared | **Cannot Import**: app, pages, widgets, other features

**When to create**: it represents a user action (not a data entity), it has its own UI + logic + possibly API.

---

## Entities (`src/entities/`)

**Purpose**: Business domain objects with UI, data access, and logic.

- Core concepts: User, Customer, Project, Order
- Domain-specific components (cards, avatars, badges)
- Hooks for CRUD operations (data-fetching library)
- Reusable across features, widgets, and pages

**Can Import**: shared | **Cannot Import**: app, pages, widgets, features, other entities

> See `examples/slice-examples.md` for directory tree and public API.

---

## Shared (`src/shared/`)

**Purpose**: Reusable infrastructure with no business logic.

- **Divided directly into segments (no slices)** — `shared/ui/`, `shared/lib/`, `shared/api/`, `shared/config/`
- API client and request utilities
- Generic helpers (date formatting, `cn()` classname merge, debounce)
- Shared hooks (`useDebounce`, `useLocalStorage`, `useMediaQuery`)
- Extended components wrapping a UI component library

**Can Import**: — | **Cannot Import**: all other layers

**What does NOT belong**: business logic, domain types, entity-specific API hooks, feature-specific utilities.

---

## Cross-Entity Communication

Entities cannot import each other directly. Two approaches:

### 1. Compose in a higher layer (preferred)

- **Entity** exports its own components and hooks via public API
- **Widget/page/feature** imports from multiple entities and passes composed data down as props
- Use IDs or shared types from `shared/` to reference across entity boundaries

### 2. `@x` cross-imports (when composition is impractical)

When one entity genuinely needs types or data from another entity, use the `@x` notation — a special cross-import boundary:

```
entities/
├── user/
│   ├── @x/
│   │   └── customer.ts    # Exports specifically for the customer entity
│   ├── model/
│   ├── ui/
│   └── index.ts
└── customer/
    ├── model/
    │   └── use-customer.ts  # Can import from '@/entities/user/@x/customer'
    ├── ui/
    └── index.ts
```

**`@x` rules:**
- Only between entities on the same layer
- The exporting entity explicitly defines what is available via `@x/{consumer-name}.ts`
- Keep `@x` exports minimal — only what the consumer truly needs
- Prefer composition in a higher layer when possible; use `@x` as a last resort

---

## Detecting Violations

Any of these patterns is a violation:

- Same-layer import: entity → entity, widget → widget, feature → feature
- Upward import: entity → feature, feature → widget, widget → page
- Direct internal import: `@/entities/customer/ui/customer-card` instead of `@/entities/customer`

**Fixing**: move shared logic to a lower layer, or compose in a higher layer.

---

## Decision Tree

```
App-level setup (providers, routing, global styles)?
├── Yes → app
└── No
    Route/URL endpoint?
    ├── Yes → pages
    └── No
        User action or interaction flow?
        ├── Yes → features
        └── No
            Reused across multiple pages?
            ├── Yes
            │   Business entity? → entities
            │   Composite UI? → widgets
            └── No
                Page-specific? → keep in that page
                Generic infra? → shared
                Domain logic? → entities
                User action? → features
```

---

## Deprecated: Processes Layer

The original FSD spec included a `processes/` layer (between `pages/` and `app/`) for multi-page flows like checkout or onboarding. This layer is **deprecated** — use `features/` or `pages/` instead. Do not create a `processes/` layer in new projects.
