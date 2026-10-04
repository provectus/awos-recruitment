---
name: expo-android-safe-area
description: Pattern for handling Android safe area insets in Expo apps with tabs. Prevents content from overlapping with system navigation bar.
version: 1.0.0
---

# Expo Android Safe Area Pattern

## Problem

On Android, content can overlap with the system navigation bar (software buttons or gesture bar). Static `paddingBottom` values don't work reliably across devices.

## Solution

Use `react-native-safe-area-context` to dynamically calculate padding based on device insets.

### Prerequisites

```bash
# Already included in Expo, but ensure it's available
npx expo install react-native-safe-area-context
```

### Step 1: Wrap App with SafeAreaProvider

In your root layout, wrap everything with `SafeAreaProvider`:

```tsx
// app/_layout.tsx
import { SafeAreaProvider } from 'react-native-safe-area-context';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      {/* Your Stack, GestureHandler, etc. */}
    </SafeAreaProvider>
  );
}
```

### Step 2: Adjust Tab Bar Height

In your tab layout, include the bottom inset in the tab bar height:

```tsx
// app/(tabs)/_layout.tsx
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  const tabBarHeight = 60 + insets.bottom;

  return (
    <Tabs
      screenOptions={{
        tabBarStyle: {
          height: tabBarHeight,
          paddingBottom: insets.bottom + 8,
        },
      }}
    >
      {/* Tab screens */}
    </Tabs>
  );
}
```

### Step 3: Dynamic Bottom Padding in Screens

In each screen with scrollable content, calculate padding dynamically:

```tsx
// Any tab screen
import { ScrollView } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function Screen() {
  const insets = useSafeAreaInsets();
  // 20 = minimum padding, 80 = tab bar height + extra spacing
  const bottomPadding = Math.max(insets.bottom, 20) + 80;

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingBottom: bottomPadding }}
      contentInsetAdjustmentBehavior="automatic"
    >
      {/* Screen content */}
    </ScrollView>
  );
}
```

### For FlatList

Same pattern applies to FlatList:

```tsx
<FlatList
  data={items}
  renderItem={renderItem}
  contentContainerStyle={{ paddingBottom: bottomPadding }}
  contentInsetAdjustmentBehavior="automatic"
/>
```

## Key Points

1. **SafeAreaProvider must wrap the entire app** - Without it, `useSafeAreaInsets()` returns zeros
2. **Tab bar needs dynamic height** - Include `insets.bottom` in the tab bar's height and paddingBottom
3. **Each scrollable screen needs dynamic padding** - Use `Math.max(insets.bottom, 20) + 80` formula
4. **Don't use static paddingBottom** - Values like `paddingBottom: 200` don't adapt to different devices

## Common Issues

### Insets returning 0
- Ensure `SafeAreaProvider` wraps the root layout
- Make sure you're not calling `useSafeAreaInsets` outside the provider

### Content still overlapping
- Check that the screen is using `contentContainerStyle` not `style` for padding
- Verify the tab bar height includes `insets.bottom`
