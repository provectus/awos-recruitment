# Documentation Anti-Patterns

How to recognize and avoid documentation bloat.

## Bloated CLAUDE.md: Before & After

### Before (bloated)

```markdown
# MyApp — A Next.js e-commerce application.

## Directory Structure
- `src/components/` — React components
- `src/components/ui/` — Shared UI primitives
- `src/lib/` — Utility functions
- `src/hooks/` — Custom React hooks
- `src/types/` — TypeScript type definitions

## Exports
- `Button`, `Input`, `Modal` from `components/ui`
- `useAuth`, `useCart` from `hooks/`

## Types
- `User` — { id, name, email, role }
- `Product` — { id, title, price, stock }

## Dependencies
- next 14.1, react 18, tailwindcss 3.4, prisma 5.8

## Linting
- ESLint with next/core-web-vitals
- Prettier with single quotes, no semicolons

## Commands
- `npm run dev` / `npm run build` / `npm test` / `npm run lint`
```

### After (correct)

```markdown
# Purpose

E-commerce storefront. Handles product browsing, cart, and checkout. Payments delegate to the billing service via internal API.

# Conventions

- All pages use the `AppLayout` wrapper — never render a page without it
- Cart state lives in Zustand store, NOT React context — previous migration was partial, don't reintroduce context
- Prices are stored as integers (cents) everywhere — never use floats for money
- `npm run dev` requires `docker compose up db` first
```

Everything removed was discoverable. Everything kept requires human knowledge.

Note the Zustand line: it is a drift rule ("previous migration was partial"). A drift rule belongs in root conventions only when it applies repo-wide, as here; when it pins down the shape of one package's code, put it in that package's Design Intent section instead (see `design-intent.md`).

## Catalog of Discoverable Content

| Pattern | Why It's Discoverable | What an Agent Does Instead |
| --- | --- | --- |
| Directory trees | `glob` or `ls` | Scans the filesystem |
| Exports / public API | Read `index.ts` or `__init__.py` | Reads entry point files |
| Type definitions | Read source files | Reads the type/interface definitions |
| Linter rules | Read `.eslintrc`, `ruff.toml`, etc. | Reads config files |
| Test file locations | `glob` for `*.test.*` or `tests/` | Searches for test patterns |
| Dependencies | Read `package.json`, `pyproject.toml` | Reads manifest files |
| Env var names | Read `.env.example` or `.env.template` | Reads env template |
| Script commands | Read `package.json` scripts or `justfile` | Reads task runner config |
| CI pipeline steps | Read `.github/workflows/` | Reads CI config |

If it's in a file an agent can read, it doesn't need documentation — with one exception: when code has drifted from the intended pattern, the file shows the drift, not the intent. That case is covered by the guard in the test below.

## The Three-Question Test

Before adding any line to documentation, ask:

1. **Could an agent find this by reading a config file?**
2. **Could an agent find this by reading source code?**
3. **Could an agent find this by running a standard command?**
If any answer is **yes**, don't write it — with one guard:
   1. **Is what's discoverable actually what's intended?** If the code has drifted from the intended pattern, the intent is no longer discoverable. Write it — as a Design Intent section (see `design-intent.md` in this directory).

### Examples

- "All tests are in `__tests__/`" → `glob` finds them. **Don't write it.**
- "Prices are cents (integers), never floats" → no config or code pattern reveals this convention. **Write it.**
- "We use ESLint with airbnb config" → it's in `.eslintrc`. **Don't write it.**
- "Handlers never touch the DB directly" → most handlers show this, but `sales-report.ts` hits the DB (drift) — the intended pattern is no longer discoverable. **Write it as Design Intent.**

## Common Mistakes

When asked to "document the project," agents typically:

1. **Dump the init output** — list every file, directory, and config from the project root
2. **Mirror the filesystem** — reproduce the directory tree as a markdown list
3. **Copy type definitions** — paste interfaces and types into docs
4. **Write a novel** — produce 200+ line CLAUDE.md files that no agent will fully process
5. **Duplicate across files** — put the same commands in README, CLAUDE.md, and CONTRIBUTING.md

Recognize these patterns. When you catch yourself doing any of them, stop and apply the three-question test to every line.
