---
title: Defer Non-Critical Third-Party Libraries
impact: MEDIUM
impactDescription: loads on demand
tags: bundle, third-party, analytics, defer
---

## Defer Non-Critical Third-Party Libraries

Analytics, logging, and error tracking don't block user interaction. Load them on demand.

**Incorrect (blocks initial bundle):**

```tsx
import { Analytics } from './analytics'

export default function App({ children }) {
  return (
    <div>
      {children}
      <Analytics />
    </div>
  )
}
```

**Correct (loads on demand):**

```tsx
import { lazy, Suspense } from 'react'

const Analytics = lazy(() =>
  import('./analytics').then(m => ({ default: m.Analytics }))
)

export default function App({ children }) {
  return (
    <div>
      {children}
      <Suspense fallback={null}>
        <Analytics />
      </Suspense>
    </div>
  )
}
```
