---
title: Parallel Execution for Independent Operations
impact: CRITICAL
impactDescription: 2-10× improvement
tags: async, parallelization, promises, waterfalls
---

## Parallel Execution for Independent Operations

When async operations have no interdependencies, execute them concurrently instead of sequentially.

**Incorrect (sequential execution, 3 round trips):**

```typescript
const user = await fetchUser()
const posts = await fetchPosts()
const comments = await fetchComments()
```

**Correct — `Promise.all()` (parallel, fails fast on first rejection):**

```typescript
const [user, posts, comments] = await Promise.all([
  fetchUser(),
  fetchPosts(),
  fetchComments()
])
```

**Correct — `Promise.allSettled()` (parallel, returns all results regardless of failures):**

Use when you need partial results or want to handle each failure individually.

```typescript
const results = await Promise.allSettled([
  fetchUser(),
  fetchPosts(),
  fetchComments()
])

const user = results[0].status === 'fulfilled' ? results[0].value : null
const posts = results[1].status === 'fulfilled' ? results[1].value : []
const comments = results[2].status === 'fulfilled' ? results[2].value : []
```
