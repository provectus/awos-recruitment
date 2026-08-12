---
name: expo-react-native
description: >-
  Mobile app development with Expo and React Native. Use when building UI with
  Expo Router, setting up EAS builds, deploying to App Store or Play Store,
  implementing data fetching, creating API routes, configuring CI/CD workflows,
  setting up NativeWind/Tailwind, upgrading Expo SDK, or handling Android safe
  area insets.
version: 0.1.0
---

# Expo & React Native Development

Build, test, and ship mobile apps with Expo and React Native. Covers UI development, EAS builds, store deployment, data fetching, CI/CD, styling, and SDK upgrades.

> Skills sourced from [expo/skills](https://github.com/expo/skills) (MIT License, © 2025-present 650 Industries, Inc.)

## Core Conventions

- **Expo-first**: prefer Expo APIs over bare React Native when an equivalent exists
- **Device testing**: always test on a physical device before store submission
- **Platform differences**: explicitly address iOS vs Android in layouts, permissions, navigation
- **EAS workflow**: use EAS Build for cloud builds, EAS Submit for store deployment
- **Version management**: bump `expo.version` + `ios.buildNumber` / `android.versionCode` before each submission
- **Safe area**: wrap root layout in `SafeAreaProvider`; use `useSafeAreaInsets` for custom headers

## UI Development

Build with Expo Router components, native navigation, animations (Reanimated v4), and platform-specific controls. Use `expo-router` for file-based routing.

Key patterns:
- Tab navigation with native headers
- Stack navigation with custom transitions
- Modal sheets and form sheets
- Search bars with filtering
- SF Symbols for icons (iOS)
- WebGPU and Three.js for 3D graphics

See `references/building-native-ui.md` and the `references/building-native-ui/` directory for 13 topic-specific guides.

## EAS Builds

Development clients enable custom native code testing without ejecting:

```bash
eas build --profile development --platform ios
eas build --profile development --platform android
```

See `references/expo-dev-client.md` for configuration details.

## Deployment

### App Store / Play Store / TestFlight

```bash
eas submit --platform ios     # App Store Connect
eas submit --platform android  # Google Play Console
```

Deployment guides cover TestFlight internal/external testing, App Store metadata optimization (ASO), Play Store listings, and release workflows.

See `references/expo-deployment.md` and the `references/expo-deployment/` directory.

## Data Fetching

Patterns for `fetch`, React Query, and SWR with offline support:

```typescript
import { useQuery } from '@tanstack/react-query';

function useUser(id: string) {
  return useQuery({
    queryKey: ['user', id],
    queryFn: () => fetch(`/api/users/${id}`).then(r => r.json()),
  });
}
```

See `references/native-data-fetching.md` for caching, optimistic updates, and offline patterns.

## API Routes

Create server-side routes with Expo Router + EAS Hosting:

```typescript
// app/api/hello+api.ts
export function GET(request: Request) {
  return Response.json({ hello: 'world' });
}
```

See `references/expo-api-routes.md`.

## CI/CD Workflows

EAS workflow YAML for automated builds and deployments:

```yaml
build:
  name: Build
  type: build
  params:
    platform: [ios, android]
    profile: production
```

See `references/expo-cicd-workflows.md`.

## Tailwind Styling

NativeWind v5 + Tailwind CSS v4 — no Babel plugin needed:

```typescript
import { Text, View } from 'react-native';

export default function App() {
  return (
    <View className="flex-1 items-center justify-center bg-white">
      <Text className="text-xl font-bold text-blue-600">Hello</Text>
    </View>
  );
}
```

Configure via `metro.config.js`. See `references/expo-tailwind-setup.md`.

## SDK Upgrades

```bash
npx expo install --fix  # Fix dependency versions after SDK bump
```

Migration guides cover new architecture, React 19, React Compiler, native tabs (SDK 55), and expo-av migrations.

See `references/upgrading-expo.md` and the `references/upgrading-expo/` directory.

## Additional Topics

- **Android Safe Area**: navigation bar inset handling — `references/expo-android-safe-area.md`
- **DOM Components**: web code in native apps — `references/use-dom.md`

## Reference Index

| Topic | Reference |
|---|---|
| UI, components, navigation, animations | `references/building-native-ui.md` + 13 sub-references |
| EAS development builds | `references/expo-dev-client.md` |
| App Store / Play Store / TestFlight | `references/expo-deployment.md` + 5 sub-references |
| Data fetching, React Query, SWR | `references/native-data-fetching.md` |
| API routes with Expo Router | `references/expo-api-routes.md` |
| CI/CD workflows | `references/expo-cicd-workflows.md` |
| NativeWind v5 + Tailwind CSS v4 | `references/expo-tailwind-setup.md` |
| SDK version upgrades | `references/upgrading-expo.md` + 6 sub-references |
| Android safe area | `references/expo-android-safe-area.md` |
| DOM components | `references/use-dom.md` |
