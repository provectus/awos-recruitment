---
title: Conditional Module Loading
impact: HIGH
impactDescription: loads large data only when needed
tags: bundle, conditional-loading, lazy-loading
---

## Conditional Module Loading

Load large data or modules only when a feature is activated.

**Incorrect (ships the payload to everyone):**

```tsx
// A static import is resolved at build time, so `animation-frames.js` lands in the
// entry chunk and every visitor downloads and parses it — even those who never
// enable the animation.
import { frames } from './animation-frames.js'

function AnimationPlayer({ enabled }: { enabled: boolean }) {
  if (!enabled) return null
  return <Canvas frames={frames} />
}
```

**Correct (lazy-load animation frames):**

```tsx
function AnimationPlayer({ enabled, setEnabled }: { enabled: boolean; setEnabled: React.Dispatch<React.SetStateAction<boolean>> }) {
  const [frames, setFrames] = useState<Frame[] | null>(null)

  useEffect(() => {
    if (enabled && !frames) {
      import('./animation-frames.js')
        .then(mod => setFrames(mod.frames))
        .catch(() => setEnabled(false))
    }
  }, [enabled, frames, setEnabled])

  if (!frames) return <Skeleton />
  return <Canvas frames={frames} />
}
```
