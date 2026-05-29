# Wear OS Patterns Reference

>[toc]

Target: latest **Wear OS** / **Compose for Wear OS** with Material 3 (`androidx.wear.compose.material3`).


## Compose for Wear OS

Wear OS uses a dedicated Compose toolkit (`androidx.wear.compose`) that accounts for round displays, limited screen real estate, and wrist-based interaction.

> **Important:** Use `androidx.wear.compose.material3` for Wear OS UI. This library supersedes `androidx.wear.compose:compose-material` and implements Material 3 Expressive design for Wear OS. Do not mix objects from this library with objects from the mobile Compose Material 3 library (`androidx.compose.material3`).

### Core Navigation — `SwipeDismissableNavHost`
---
All Wear OS Compose apps should use `SwipeDismissableNavHost` instead of the standard `NavHost`. It provides a built-in swipe-to-dismiss gesture that matches the platform back-navigation pattern.

```kotlin
val navController = rememberSwipeDismissableNavController()

SwipeDismissableNavHost(
    navController = navController,
    startDestination = "home"
) {
    composable("home") { HomeScreen(navController) }
    composable("detail/{id}") { backStackEntry ->
        DetailScreen(backStackEntry.arguments?.getString("id"))
    }
}
```

- Each destination automatically supports swipe-to-dismiss to go back.
- Avoid deeply nested navigation; prefer flat hierarchies (2-3 levels max).

### `TransformingLazyColumn` (Recommended)
---
The preferred scrollable list component for Wear OS. It provides morphing and scaling animations with better performance than `ScalingLazyColumn`.

```kotlin
val listState = rememberTransformingLazyColumnState()

TransformingLazyColumn(
    state = listState,
    modifier = Modifier.fillMaxSize(),
) {
    item { ListHeader { Text("Settings") } }
    items(options) { option ->
        Button(
            onClick = { /* handle */ },
            label = { Text(option.title) },
            modifier = Modifier.fillMaxWidth()
        )
    }
}
```

- Supports rotary input by default — no explicit `rotaryScrollable` setup needed.
- Use `TransformingLazyColumn` for all new Wear OS screens.

### `ScalingLazyColumn` (Legacy)
---
`TransformingLazyColumn` is the preferred replacement. Use `ScalingLazyColumn` only in existing codebases that have not migrated.

The primary scrollable list component for Wear OS. It applies scaling and transparency effects to items near the edges of the round screen so content feels natural on a circular viewport.

```kotlin
val listState = rememberScalingLazyListState()

ScalingLazyColumn(
    state = listState,
    modifier = Modifier.fillMaxSize(),
    anchorType = ScalingLazyListAnchorType.ItemCenter
) {
    item { ListHeader { Text("Settings") } }
    items(options) { option ->
        Chip(
            onClick = { /* handle */ },
            label = { Text(option.title) },
            modifier = Modifier.fillMaxWidth()
        )
    }
}
```

- Always pair with `PositionIndicator(scalingLazyListState = listState)` to show the scroll position on the side.
- Use `ScalingLazyListAnchorType.ItemCenter` for most content screens.

### `TimeText`
---
Displays the current time at the top of the screen (curved on round devices). It should be present on most screens so the user always sees the time.

```kotlin
Scaffold(
    timeText = { TimeText() },
    positionIndicator = { PositionIndicator(listState) },
    vignette = { Vignette(vignettePosition = VignettePosition.TopAndBottom) }
) {
    // Screen content
}
```

- `TimeText` automatically adapts to round vs. square screens.
- Custom leading/trailing content can be added via `startCurvedContent` and `endCurvedContent` parameters.

### Round vs. Square Screens
---
- Use `LocalConfiguration.current.isScreenRound` to detect screen shape when custom layouts are needed.
- Prefer Wear Compose components (`Scaffold`, `ScalingLazyColumn`, `CurvedLayout`) which handle shape differences automatically.
- For edge-aware padding on round screens, use `rememberResponsiveColumnPadding()` from the Horologist library.


## Tiles

Tiles are lightweight, glanceable surfaces accessible by swiping left/right from the watch face. They are **not** Compose UI — they use a layout-based rendering system for performance.

### `TileService`
---
Extend `TileService` to provide tile content. The system calls `onTileRequest()` to get layout and `onTileResourcesRequest()` to get images/resources.

```kotlin
class MyTileService : TileService() {

    override fun onTileRequest(requestParams: RequestBuilders.TileRequest) =
        Futures.immediateFuture(
            Tile.Builder()
                .setResourcesVersion("1")
                .setTileTimeline(
                    Timeline.fromLayoutElement(tileLayout())
                )
                .setFreshnessIntervalMillis(15 * 60 * 1000) // 15 min refresh
                .build()
        )

    override fun onTileResourcesRequest(requestParams: ResourcesRequest) =
        Futures.immediateFuture(
            Resources.Builder().setVersion("1").build()
        )
}
```

Register in `AndroidManifest.xml`:

```xml
<service
    android:name=".MyTileService"
    android:exported="true"
    android:permission="com.google.android.wearable.permission.BIND_TILE_PROVIDER">
    <intent-filter>
        <action android:name="androidx.wear.tiles.action.BIND_TILE_PROVIDER" />
    </intent-filter>
</service>
```

### Layout and Renderer
---
Tile layouts use `LayoutElementBuilders` (Box, Row, Column, Text, Image, Spacer, Arc). These are **not** Compose composables — they are serializable layout descriptions rendered by the system.

### Compose for Tiles (Recommended)
---
The `androidx.wear.protolayout.material3` library and the Tiles Material3 renderer let you build tile layouts with a Compose-like DSL while still producing protolayout elements under the hood.

```kotlin
// Using protolayout-material3 components
private fun tileLayout(): LayoutElement =
    PrimaryLayout.Builder(deviceParameters)
        .setContent(
            Text.Builder(this, "Steps: 8,432")
                .setTypography(Typography.TITLE3)
                .build()
        )
        .build()
```

- Keep tile content minimal — one or two pieces of information.
- Use `setFreshnessIntervalMillis` to control how often the system refreshes the tile.
- Tiles support click actions via `Clickable` that can launch activities or trigger tile updates.


## Complications

Complications are small data elements displayed on watch faces (step count, weather, battery, etc.). You supply data through a `ComplicationDataSourceService`.

### `ComplicationDataSourceService`
---

```kotlin
class StepsComplicationService : ComplicationDataSourceService() {

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        val data = ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder("8,432").build(),
            contentDescription = PlainComplicationText.Builder("Steps today").build()
        )
            .setTapAction(openAppPendingIntent())
            .build()

        listener.onComplicationData(data)
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData =
        ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder("--").build(),
            contentDescription = PlainComplicationText.Builder("Steps").build()
        ).build()
}
```

Register with supported types:

```xml
<service
    android:name=".StepsComplicationService"
    android:exported="true"
    android:permission="com.google.android.wearable.permission.BIND_COMPLICATION_PROVIDER">
    <intent-filter>
        <action android:name="android.support.wearable.complications.ACTION_COMPLICATION_UPDATE_REQUEST" />
    </intent-filter>
    <meta-data
        android:name="android.support.wearable.complications.SUPPORTED_TYPES"
        android:value="SHORT_TEXT,RANGED_VALUE" />
    <meta-data
        android:name="android.support.wearable.complications.UPDATE_PERIOD_SECONDS"
        android:value="600" />
</service>
```

### Complication Types
---
| Type | Description | Example |
|------|-------------|---------|
| `SHORT_TEXT` | Icon + short text | "72F" |
| `LONG_TEXT` | Longer text string | "Sunny, 72F, Low 58F" |
| `RANGED_VALUE` | Progress/gauge value | Step progress ring |
| `MONOCHROMATIC_IMAGE` | Single-color icon | Battery icon |
| `SMALL_IMAGE` | Small photo/icon | Contact photo |
| `PHOTO_IMAGE` | Full photo | Album art |
| `NO_DATA` | Placeholder / empty state | "--" |

- Provide `getPreviewData()` so the watch face editor can show a preview.
- Use `ComplicationDataTimeline` to schedule future data updates without waking the service.


## Health Services

The `androidx.health.services.client` library provides access to on-device sensors with built-in batching and power management.

### `ExerciseClient`
---
For active workout tracking with continuous sensor updates.

```kotlin
val healthServicesClient = HealthServices.getClient(context)
val exerciseClient = healthServicesClient.exerciseClient

// Check capabilities
val capabilities = exerciseClient.getCapabilitiesAsync().await()
val runCapabilities = capabilities.getExerciseTypeCapabilities(ExerciseType.RUNNING)

// Configure and start
val config = ExerciseConfig.builder(ExerciseType.RUNNING)
    .setDataTypes(setOf(DataType.HEART_RATE_BPM, DataType.DISTANCE_TOTAL, DataType.SPEED))
    .setIsAutoPauseAndResumeEnabled(true)
    .build()

exerciseClient.setUpdateCallback(exerciseUpdateCallback)
exerciseClient.startExerciseAsync(config).await()
```

- Only one exercise can be active at a time across the entire device.
- Always call `exerciseClient.endExerciseAsync()` in `onDestroy` or when the user stops.
- Use a `ForegroundService` with an ongoing notification during workouts.

### `PassiveMonitoringClient`
---
For background health data collection (e.g., daily steps, resting heart rate) without an active workout.

```kotlin
val passiveClient = healthServicesClient.passiveMonitoringClient

val passiveConfig = PassiveListenerConfig.builder()
    .setDataTypes(setOf(DataType.STEPS_DAILY, DataType.HEART_RATE_BPM))
    .setHealthEventTypes(setOf(HealthEvent.Type.FALL_DETECTED))
    .build()

passiveClient.setPassiveListenerServiceAsync(
    MyPassiveListenerService::class.java,
    passiveConfig
).await()
```

- Data is delivered in batches to reduce power consumption.
- Use a `PassiveListenerService` to receive data even when the app is not running.

### `MeasureClient`
---
For one-shot or short-duration measurements (e.g., check current heart rate before starting an exercise).

```kotlin
val measureClient = healthServicesClient.measureClient

val heartRateAvailable = measureClient
    .getCapabilitiesAsync()
    .await()
    .supportedDataTypesMeasure
    .contains(DataType.HEART_RATE_BPM)

if (heartRateAvailable) {
    measureClient.registerMeasureCallback(DataType.HEART_RATE_BPM, measureCallback)
}

// Unregister when done
measureClient.unregisterMeasureCallbackAsync(DataType.HEART_RATE_BPM, measureCallback)
```

- Always check capabilities before registering — not all sensors are present on all devices.
- Unregister callbacks promptly to save battery.


## Watch Face

### Watch Face Format (WFF)
---
Wear OS uses the **Watch Face Format**, a declarative XML-based format that replaces the legacy `CanvasWatchFaceService`. Watch faces are bundled as APKs containing XML configuration rather than custom drawing code.

> **Legacy watch faces (AndroidX or WSL-based) are no longer accepted on Google Play.** WFF is the only supported format for watch face distribution. Use Watch Face Studio for visual design.

```xml
<!-- res/raw/watchface.xml -->
<WatchFace width="450" height="450">
    <Scene>
        <AnalogClock>
            <HourHand resource="@drawable/hour_hand" />
            <MinuteHand resource="@drawable/minute_hand" />
            <SecondHand resource="@drawable/second_hand" />
        </AnalogClock>
    </Scene>
</WatchFace>
```

- WFF watch faces run in a system process — no custom code executes, which improves battery life and reliability.
- Use the **Watch Face Studio** tool (from Samsung/Google) for visual design.

### Complication Slots
---
Define slots in the watch face XML so users can add their preferred complications.

```xml
<ComplicationSlot
    slotId="1"
    name="Top"
    supportedTypes="SHORT_TEXT|RANGED_VALUE|MONOCHROMATIC_IMAGE"
    x="225" y="100"
    width="80" height="80" />
```

- Provide sensible default data sources for each slot.
- Support multiple complication types per slot for flexibility.

### Ambient Mode
---
When the watch enters ambient mode, the display switches to a low-power state.

- **Reduce color**: use white/gray on black; avoid large bright areas.
- **Remove animations**: no moving elements or frequent updates.
- **Burn-in protection**: shift content by a few pixels periodically on OLED screens. WFF handles this automatically via the `BurnInProtection` element.
- **Update cadence**: once per minute in ambient mode (system-enforced).


## Rotary Input

Most Wear OS devices have a rotating side button (crown) or bezel. Compose for Wear OS provides built-in support.

### `rotaryScrollable()`
---

> **Note:** `TransformingLazyColumn` and recent versions of `ScalingLazyColumn` support rotary input by default. Explicit `rotaryScrollable` setup is only needed for custom scrollable components.

```kotlin
val listState = rememberScalingLazyListState()
val focusRequester = rememberActiveFocusRequester()

ScalingLazyColumn(
    state = listState,
    modifier = Modifier
        .fillMaxSize()
        .rotaryScrollable(
            behavior = RotaryScrollableDefaults.behavior(listState),
            focusRequester = focusRequester
        )
) {
    // items
}
```

- Use `rememberActiveFocusRequester()` to automatically request focus when the composable is displayed.
- `rotaryScrollable` supports both smooth scrolling (crown) and snap/fling (bezel) automatically based on device hardware.
- For custom rotary handling (e.g., volume control), use `onRotaryScrollEvent` directly on a modifier.

```kotlin
Modifier.onRotaryScrollEvent { event ->
    volume += event.verticalScrollPixels / 100f
    true
}
```


## Data Layer

The Wearable Data Layer API enables communication between a phone app and a watch app.

### `DataClient`
---
Syncs key-value data items between devices. Changes are propagated automatically when devices are connected.

```kotlin
val dataClient = Wearable.getDataClient(context)

// Send data
val putDataRequest = PutDataMapRequest.create("/user/profile").apply {
    dataMap.putString("name", "Andrii")
    dataMap.putInt("steps", 8432)
    dataMap.putLong("timestamp", System.currentTimeMillis()) // force update
}.asPutDataRequest().setUrgent()

dataClient.putDataItem(putDataRequest).await()

// Listen for changes
dataClient.addListener { dataEvents ->
    dataEvents.forEach { event ->
        if (event.type == DataEvent.TYPE_CHANGED) {
            val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
            // process updated data
        }
    }
}
```

- Data items are limited to **100 KB**. Use `Asset` for larger payloads (images, files).
- Include a timestamp or counter to force propagation — identical data is not re-synced.

### `MessageClient`
---
For fire-and-forget messages. No guarantee of delivery if the other device is unreachable.

```kotlin
val messageClient = Wearable.getMessageClient(context)

// Find connected node
val nodes = Wearable.getNodeClient(context).connectedNodes.await()
val phoneNodeId = nodes.firstOrNull()?.id ?: return

// Send message
messageClient.sendMessage(phoneNodeId, "/action/start-tracking", byteArrayOf()).await()

// Receive on the other side
class MyMessageListenerService : WearableListenerService() {
    override fun onMessageReceived(messageEvent: MessageEvent) {
        when (messageEvent.path) {
            "/action/start-tracking" -> { /* handle */ }
        }
    }
}
```

- Messages are best for triggering actions (RPC-style), not for syncing state.
- Register `WearableListenerService` in the manifest to receive messages when the app is not running.

### Phone-Watch Sync Best Practices
---
- Use `DataClient` for state that must survive disconnection and be available on reconnection.
- Use `MessageClient` for transient commands or requests.
- Always check `CapabilityClient` to verify the companion app is installed on the other device.
- Minimize sync frequency; batch updates where possible to reduce battery drain.


## Standalone vs Companion

### Architecture Models
---

| Model | Description | Use Case |
|-------|-------------|----------|
| **Standalone** | Watch app works independently; no phone app required | Fitness tracker, music player with local storage |
| **Companion** | Watch app requires a paired phone app | Remote control, notification mirroring |
| **Hybrid** | Core features work standalone; enhanced features need phone | Messaging app (standalone read, companion for full sync) |

- Google Play requires declaring `<uses-feature android:name="android.hardware.type.watch" />` for Wear OS apps.
- Standalone apps must declare `meta-data android:name="com.google.android.wearable.standalone" android:value="true"` in the manifest.

### Detecting Connectivity
---

```kotlin
val capabilityClient = Wearable.getCapabilityClient(context)

// Check if phone app is installed
val capabilityInfo = capabilityClient
    .getCapability("companion_app_phone", CapabilityClient.FILTER_REACHABLE)
    .await()

val phoneNodeId = capabilityInfo.nodes.firstOrNull()?.id

if (phoneNodeId != null) {
    // Phone app is reachable — enable companion features
} else {
    // Running standalone — use local-only mode
}

// Listen for capability changes
capabilityClient.addListener({ info ->
    // Update UI based on phone connectivity
}, "companion_app_phone")
```

- Define capabilities in `res/values/wear.xml` on each device so `CapabilityClient` can discover them.
- Design for offline-first: assume the phone may be unreachable and degrade gracefully.


## Notifications

### Bridged vs Local Notifications
---

| Type | Origin | Behavior |
|------|--------|----------|
| **Bridged** | Phone app | Automatically forwarded to watch by the system |
| **Local** | Watch app | Created directly on the watch |

- Bridged notifications appear automatically — no watch-side code needed.
- To prevent bridging a specific notification, set `.setLocalOnly(true)` on the phone side.

### Wearable-Specific Actions
---

```kotlin
val replyAction = NotificationCompat.Action.Builder(
    R.drawable.ic_reply,
    "Reply",
    replyPendingIntent
)
    .addRemoteInput(
        RemoteInput.Builder("reply_key")
            .setLabel("Reply")
            .build()
    )
    .build()

val notification = NotificationCompat.Builder(context, CHANNEL_ID)
    .setSmallIcon(R.drawable.ic_message)
    .setContentTitle("New Message")
    .setContentText("Hey, are you coming?")
    .addAction(replyAction)
    .extend(
        NotificationCompat.WearableExtender()
            .addAction(replyAction)
    )
    .build()
```

- Use `RemoteInput` to allow voice or keyboard replies directly from the watch.
- Keep notification content concise — long text is hard to read on small screens.
- Use `BigTextStyle` or `InboxStyle` sparingly; they expand but still have limited viewport.
- Wearable actions added via `WearableExtender` appear as swipeable action buttons below the notification.


## Limitations

### Battery
---
- Wear OS devices have batteries typically between **300-600 mAh**. Every sensor read, network call, and screen wake has measurable impact.
- Use `PassiveMonitoringClient` over `ExerciseClient` for background data.
- Avoid wake locks; prefer `WorkManager` with appropriate constraints.
- Batch network requests; prefer syncing via `DataClient` over direct HTTP calls.
- Set `setFreshnessIntervalMillis` on tiles to the longest acceptable interval.

### Memory
---
- Typical Wear OS devices have **1-2 GB RAM** with limited per-app allocation.
- Avoid loading large bitmaps; use downsampled/vector images.
- Keep the composable tree shallow — deep nesting increases memory and measure/layout cost.
- Use `remember` and `derivedStateOf` judiciously to minimize recomposition.
- Profile with Android Studio's Memory Profiler connected to the watch/emulator.

### Screen Sizes
---
- Wear OS screens range from roughly **192 x 192 dp** to **228 x 228 dp**.
- Round screens have ~22% less usable area in corners compared to a bounding square.
- Always test on both round and square form factors.
- Avoid placing interactive elements near screen edges on round devices — they may be clipped or hard to tap.
- Minimum touch target size: **48 dp** (same as mobile, but even more critical on wrist).

### General Constraints
---
- **No multi-window**: only one app visible at a time.
- **Limited background execution**: the system aggressively kills background processes. Use `ForegroundService` for ongoing tasks (workouts, music).
- **Network**: prefer Bluetooth-proxied connections through the phone; direct Wi-Fi/LTE drains battery significantly.
- **Storage**: internal storage is limited (8-32 GB shared with system). Avoid caching large files.
- **Input**: no keyboard for most interactions — design for voice, tap, and rotary input as primary modalities.
