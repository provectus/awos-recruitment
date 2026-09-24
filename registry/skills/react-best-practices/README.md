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

Once installed, the skill activates when performance is the concern — slow or janky
renders, unnecessary re-renders, memoization, lazy loading, bundle size, request
waterfalls, or a request to review or profile React code for speed. It is not a
general React authoring guide: folder and layer structure belongs to
`react-feature-sliced-design`, language and typing questions to
`typescript-development`.

Each rule is a standalone `.md` file in `references/`:

```
references/async-parallel.md
references/rerender-memo.md
```

Every rule file contains:
- Why the pattern matters
- Incorrect code example
- Correct code example
- Additional context and references

## Rule Categories

`Impact` is the range of the per-rule `impact:` values in that category; `Priority`
is the suggested review order. See `SKILL.md` for the impact of each individual rule.

| Priority | Category | Impact | Rules |
|----------|----------|--------|-------|
| 1 | Eliminating Waterfalls | HIGH–CRITICAL | 2 |
| 2 | Bundle Size Optimization | MEDIUM–CRITICAL | 4 |
| 3 | Client-Side Data Fetching | LOW–MEDIUM-HIGH | 4 |
| 4 | Re-render Optimization | LOW–MEDIUM | 7 |
| 5 | Rendering Performance | LOW–HIGH | 6 |
| 6 | JavaScript Performance | LOW–MEDIUM-HIGH | 12 |
| 7 | Advanced Patterns | LOW | 2 |
