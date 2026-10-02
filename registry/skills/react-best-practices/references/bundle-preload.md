---
title: Preload Based on User Intent
impact: MEDIUM
impactDescription: reduces perceived latency
tags: bundle, preload, user-intent, hover
---

## Preload Based on User Intent

Preload heavy bundles before they're needed to reduce perceived latency.

**Incorrect (fetch starts only on click):**

```tsx
function EditorButton() {
  const [Editor, setEditor] = useState<React.ComponentType | null>(null)

  // The chunk request begins at click time, so the user stares at a spinner for
  // the whole download — the hundreds of milliseconds they spent moving the
  // cursor toward the button were wasted.
  const open = () => {
    void import('./monaco-editor').then(mod => setEditor(() => mod.Editor))
  }

  return Editor ? <Editor /> : <button onClick={open}>Open Editor</button>
}
```

**Correct (preload on hover/focus):**

```tsx
function EditorButton({ onClick }: { onClick: () => void }) {
  // Hover and focus both signal intent, and focus keeps the optimization for
  // keyboard users. The dynamic import is cached, so the click-time import that
  // actually renders the editor resolves from memory.
  const preload = () => {
    void import('./monaco-editor')
  }

  return (
    <button
      onMouseEnter={preload}
      onFocus={preload}
      onClick={onClick}
    >
      Open Editor
    </button>
  )
}
```

**Also correct (preload when a feature flag is enabled):**

```tsx
function FlagsProvider({ children, flags }: Props) {
  useEffect(() => {
    if (flags.editorEnabled) {
      void import('./monaco-editor').then(mod => mod.init())
    }
  }, [flags.editorEnabled])

  return <FlagsContext.Provider value={flags}>
    {children}
  </FlagsContext.Provider>
}
```
