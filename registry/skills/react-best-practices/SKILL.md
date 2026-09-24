---
name: react-best-practices
description: >-
  Performance optimization for React applications — rendering, re-renders,
  data-fetching waterfalls, bundle size, and the JavaScript hot paths inside
  components. Use when the user mentions slow or janky renders, unnecessary
  re-renders, memoization (React.memo / useMemo / useCallback), lazy loading,
  code splitting, bundle size, request waterfalls, laggy scrolling or typing, or
  asks to review, profile, or speed up React code. Not a general React authoring
  guide — for folder and layer structure use react-feature-sliced-design, for
  language and typing questions use typescript-development.
---

# React Best Practices

Performance optimization guide for React applications: 37 rules across 7 categories.

Categories are ordered by how much they typically move the needle, so work top-down
when reviewing. Each rule carries its own `impact:` value in the front matter of its
file in `references/`, and that per-rule value is what the Quick Reference below
shows — a lower-priority category can still hold a high-impact rule, which is why
the category order and the rule impacts are reported separately.

## Rule Categories by Priority

| Priority | Category                  | Prefix       | Rules |
| -------- | ------------------------- | ------------ | ----- |
| 1        | Eliminating Waterfalls    | `async-`     | 2     |
| 2        | Bundle Size Optimization  | `bundle-`    | 4     |
| 3        | Client-Side Data Fetching | `client-`    | 4     |
| 4        | Re-render Optimization    | `rerender-`  | 7     |
| 5        | Rendering Performance     | `rendering-` | 6     |
| 6        | JavaScript Performance    | `js-`        | 12    |
| 7        | Advanced Patterns         | `advanced-`  | 2     |

## Quick Reference

Impact labels below are the `impact:` value from each rule file's front matter.

### 1. Eliminating Waterfalls (`async-`)

- `async-defer-await` (HIGH) - Move await into branches where actually used
- `async-parallel` (CRITICAL) - Use Promise.all()/allSettled() for independent operations

### 2. Bundle Size Optimization (`bundle-`)

- `bundle-dynamic-imports` (CRITICAL) - React.lazy() for heavy components
- `bundle-conditional` (HIGH) - Load modules only when feature is activated
- `bundle-defer-third-party` (MEDIUM) - Load analytics/logging on demand
- `bundle-preload` (MEDIUM) - Preload on hover/focus for perceived speed

### 3. Client-Side Data Fetching (`client-`)

- `client-query-dedup` (MEDIUM-HIGH) - Use TanStack Query for automatic request deduplication
- `client-passive-event-listeners` (MEDIUM) - Use passive listeners for scroll performance
- `client-localstorage-schema` (MEDIUM) - Version and minimize localStorage data
- `client-event-listeners` (LOW) - Deduplicate global event listeners

### 4. Re-render Optimization (`rerender-`)

- `rerender-defer-reads` (MEDIUM) - Don't subscribe to state only used in callbacks
- `rerender-memo` (MEDIUM) - Extract expensive work into memoized components
- `rerender-derived-state` (MEDIUM) - Subscribe to derived booleans, not raw values
- `rerender-functional-setstate` (MEDIUM) - Use functional setState for stable callbacks
- `rerender-lazy-state-init` (MEDIUM) - Pass function to useState for expensive values
- `rerender-transitions` (MEDIUM) - Use startTransition for non-urgent updates
- `rerender-dependencies` (LOW) - Use primitive dependencies in effects

### 5. Rendering Performance (`rendering-`)

- `rendering-content-visibility` (HIGH) - Use content-visibility for long lists
- `rendering-activity` (MEDIUM) - Use Activity component for show/hide
- `rendering-animate-svg-wrapper` (LOW) - Animate div wrapper, not SVG element
- `rendering-hoist-jsx` (LOW) - Extract static JSX outside components
- `rendering-svg-precision` (LOW) - Reduce SVG coordinate precision
- `rendering-conditional-render` (LOW) - Use ternary, not && for conditionals

### 6. JavaScript Performance (`js-`)

These rules are framework-agnostic JavaScript. They are here because they pay off in
the hot paths React components run — render bodies, effects, event handlers, and the
helpers those call. Reach for them when profiling points at a specific loop or
lookup, not as general style guidance.

- `js-length-check-first` (MEDIUM-HIGH) - Check array length before expensive comparison
- `js-tosorted-immutable` (MEDIUM-HIGH) - Use toSorted() for immutability
- `js-batch-dom-css` (MEDIUM) - Group CSS changes via classes or cssText
- `js-cache-function-results` (MEDIUM) - Cache function results in module-level Map
- `js-index-maps` (LOW-MEDIUM) - Build Map for repeated lookups
- `js-cache-property-access` (LOW-MEDIUM) - Cache object properties in loops
- `js-cache-storage` (LOW-MEDIUM) - Cache localStorage/sessionStorage reads
- `js-combine-iterations` (LOW-MEDIUM) - Combine multiple filter/map into one loop
- `js-early-exit` (LOW-MEDIUM) - Return early from functions
- `js-hoist-regexp` (LOW-MEDIUM) - Hoist RegExp creation outside loops
- `js-set-map-lookups` (LOW-MEDIUM) - Use Set/Map for O(1) lookups
- `js-min-max-loop` (LOW) - Use loop for min/max instead of sort

### 7. Advanced Patterns (`advanced-`)

- `advanced-event-handler-refs` (LOW) - Store event handlers in refs
- `advanced-use-latest` (LOW) - useLatest for stable callback refs

## How to Use

Each rule file in `references/` contains: an explanation, an incorrect/correct code
pair, and context. Read individual files as needed.
