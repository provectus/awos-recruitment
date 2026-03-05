---
name: react-best-practices
description: React performance optimization guidelines. This skill should be used when writing, reviewing, or refactoring React code to ensure optimal performance patterns. Triggers on tasks involving React components, data fetching, bundle optimization, or performance improvements.
---

# React Best Practices

Comprehensive performance optimization guide for React applications. Contains 37 rules across 7 categories, prioritized by impact.

## Rule Categories by Priority

| Priority | Category                  | Impact      | Prefix       |
| -------- | ------------------------- | ----------- | ------------ |
| 1        | Eliminating Waterfalls    | CRITICAL    | `async-`     |
| 2        | Bundle Size Optimization  | CRITICAL    | `bundle-`    |
| 3        | Client-Side Data Fetching | MEDIUM-HIGH | `client-`    |
| 4        | Re-render Optimization    | MEDIUM      | `rerender-`  |
| 5        | Rendering Performance     | MEDIUM      | `rendering-` |
| 6        | JavaScript Performance    | LOW-MEDIUM  | `js-`        |
| 7        | Advanced Patterns         | LOW         | `advanced-`  |

## Quick Reference

### 1. Eliminating Waterfalls (CRITICAL)

- `async-defer-await` - Move await into branches where actually used
- `async-parallel` - Use Promise.all()/allSettled() for independent operations

### 2. Bundle Size Optimization (CRITICAL)

- `bundle-dynamic-imports` - React.lazy() for heavy components
- `bundle-defer-third-party` - Load analytics/logging on demand
- `bundle-conditional` - Load modules only when feature is activated
- `bundle-preload` - Preload on hover/focus for perceived speed

### 3. Client-Side Data Fetching (MEDIUM-HIGH)

- `client-query-dedup` - Use TanStack Query for automatic request deduplication
- `client-event-listeners` - Deduplicate global event listeners
- `client-passive-event-listeners` - Use passive listeners for scroll performance
- `client-localstorage-schema` - Version and minimize localStorage data

### 4. Re-render Optimization (MEDIUM)

- `rerender-defer-reads` - Don't subscribe to state only used in callbacks
- `rerender-memo` - Extract expensive work into memoized components
- `rerender-dependencies` - Use primitive dependencies in effects
- `rerender-derived-state` - Subscribe to derived booleans, not raw values
- `rerender-functional-setstate` - Use functional setState for stable callbacks
- `rerender-lazy-state-init` - Pass function to useState for expensive values
- `rerender-transitions` - Use startTransition for non-urgent updates

### 5. Rendering Performance (MEDIUM)

- `rendering-animate-svg-wrapper` - Animate div wrapper, not SVG element
- `rendering-content-visibility` - Use content-visibility for long lists
- `rendering-hoist-jsx` - Extract static JSX outside components
- `rendering-svg-precision` - Reduce SVG coordinate precision
- `rendering-activity` - Use Activity component for show/hide
- `rendering-conditional-render` - Use ternary, not && for conditionals

### 6. JavaScript Performance (LOW-MEDIUM)

- `js-batch-dom-css` - Group CSS changes via classes or cssText
- `js-index-maps` - Build Map for repeated lookups
- `js-cache-property-access` - Cache object properties in loops
- `js-cache-function-results` - Cache function results in module-level Map
- `js-cache-storage` - Cache localStorage/sessionStorage reads
- `js-combine-iterations` - Combine multiple filter/map into one loop
- `js-length-check-first` - Check array length before expensive comparison
- `js-early-exit` - Return early from functions
- `js-hoist-regexp` - Hoist RegExp creation outside loops
- `js-min-max-loop` - Use loop for min/max instead of sort
- `js-set-map-lookups` - Use Set/Map for O(1) lookups
- `js-tosorted-immutable` - Use toSorted() for immutability

### 7. Advanced Patterns (LOW)

- `advanced-event-handler-refs` - Store event handlers in refs
- `advanced-use-latest` - useLatest for stable callback refs

## How to Use

Each rule file in `rules/` contains: explanation, incorrect/correct code examples, and context. Read individual files as needed.
