---
title: CSS content-visibility for Long Lists
impact: HIGH
impactDescription: faster initial render
tags: rendering, css, content-visibility, long-lists
---

## CSS content-visibility for Long Lists

Apply `content-visibility: auto` to defer off-screen rendering.

**Incorrect (every row is laid out and painted up front):**

```tsx
function MessageList({ messages }: { messages: Message[] }) {
  return (
    <div className="overflow-y-auto h-screen">
      {messages.map(msg => (
        // No containment hint, so the browser does layout and paint work for all
        // 1000 rows on first render even though ~10 are on screen.
        <div key={msg.id}>
          <Avatar user={msg.author} />
          <div>{msg.content}</div>
        </div>
      ))}
    </div>
  )
}
```

**Correct — CSS:**

```css
.message-item {
  content-visibility: auto;
  /* Placeholder size for skipped rows; without it the scrollbar jumps as rows
     come into view and get their real height. */
  contain-intrinsic-size: 0 80px;
}
```

**Correct — component:**

```tsx
function MessageList({ messages }: { messages: Message[] }) {
  return (
    <div className="overflow-y-auto h-screen">
      {messages.map(msg => (
        <div key={msg.id} className="message-item">
          <Avatar user={msg.author} />
          <div>{msg.content}</div>
        </div>
      ))}
    </div>
  )
}
```

For 1000 messages, browser skips layout/paint for ~990 off-screen items (10× faster initial render).
