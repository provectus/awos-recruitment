# React Best Practices

Performance optimization guidelines for React applications. 37 rules across 7 categories — from critical (eliminating waterfalls, reducing bundle size) to incremental (advanced patterns).

> This skill is based on the [React Best Practices](https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices) skill originally created by [Vercel Labs](https://github.com/vercel-labs). Big thanks to the authors for the foundational work.

## Install

```bash
npx @provectusinc/awos-recruitment skill react-best-practices
```

## Scope

The rules cover:

- Eliminating request waterfalls
- Bundle size optimization (code splitting, lazy loading)
- Client-side data fetching (TanStack Query, deduplication, caching)
- Re-render optimization (memoization, derived state, transitions)
- Rendering performance (SVG, content-visibility, static JSX hoisting)
- JavaScript micro-optimizations (Set/Map lookups, loop efficiency)
- Advanced patterns (event handler refs, stable callbacks)

## Usage

Once installed, the skill activates automatically when Claude Code detects React-related tasks — writing components, reviewing performance, refactoring code, or optimizing bundles.

Each rule is a standalone `.md` file in `rules/`:

```
rules/async-parallel.md
rules/rerender-memo.md
```

Every rule file contains:
- Why the pattern matters
- Incorrect code example
- Correct code example
- Additional context and references

## Rule Categories

| Priority | Category | Impact | Rules |
|----------|----------|--------|-------|
| 1 | Eliminating Waterfalls | CRITICAL | 2 |
| 2 | Bundle Size Optimization | CRITICAL | 4 |
| 3 | Client-Side Data Fetching | MEDIUM-HIGH | 4 |
| 4 | Re-render Optimization | MEDIUM | 7 |
| 5 | Rendering Performance | MEDIUM | 6 |
| 6 | JavaScript Performance | LOW-MEDIUM | 12 |
| 7 | Advanced Patterns | LOW | 2 |
