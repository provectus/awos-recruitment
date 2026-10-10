---
title: Use Activity Component for Show/Hide
impact: MEDIUM
impactDescription: preserves state/DOM
tags: rendering, activity, visibility, state-preservation
---

## Use Activity Component for Show/Hide

Use React's `<Activity>` to preserve state/DOM for expensive components that frequently toggle visibility.

**Incorrect (unmounts on every toggle):**

```tsx
function Dropdown({ isOpen }: Props) {
  // Closing destroys the subtree — scroll position, focus, uncontrolled input
  // values and fetched data are all lost, and reopening pays the mount cost again.
  return isOpen ? <ExpensiveMenu /> : null
}
```

**Correct (hidden, not unmounted):**

```tsx
import { Activity } from 'react'

function Dropdown({ isOpen }: Props) {
  return (
    <Activity mode={isOpen ? 'visible' : 'hidden'}>
      <ExpensiveMenu />
    </Activity>
  )
}
```

A hidden `<Activity>` sets `display: none` on its children and cleans up their
Effects, but keeps their DOM and React state. Reopening is cheap and nothing is lost.

Because the DOM survives, side effects that live in the DOM survive too — a hidden
`<video>` keeps playing, for example — so components that own such effects need a
cleanup function that pauses them.

`<Activity>` is stable from React 19.2. On earlier versions, keep the component
mounted and hide it with CSS instead.
