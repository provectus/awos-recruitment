# Android Auto Patterns Reference

> Target: Car App Library 1.4+

>[toc]


## Car App Library Architecture

### Core Components
---

The Car App Library (`androidx.car.app`) provides a host-agnostic framework for building Android Auto apps. The architecture follows a service-session-screen model.

#### CarAppService

`CarAppService` is the entry point. It is a bound `Service` that the car host connects to. Declare it in `AndroidManifest.xml` with the appropriate intent filter.

```xml
<service
    android:name=".MyCarAppService"
    android:exported="true">
    <intent-filter>
        <action android:name="androidx.car.app.CarAppService" />
        <category android:name="androidx.car.app.category.NAVIGATION" /> <!-- or POI, IOT, etc. -->
    </intent-filter>
</service>
```

```kotlin
class MyCarAppService : CarAppService() {
    override fun createHostValidator(): HostValidator {
        return HostValidator.ALLOW_ALL_HOSTS_VALIDATOR // use specific hosts in production
    }

    override fun onCreateSession(): Session {
        return MySession()
    }
}
```

#### Session

A `Session` represents a single connection to the car host. It owns the `Screen` back stack and receives lifecycle callbacks. Each connection creates a new `Session` instance.

```kotlin
class MySession : Session() {
    override fun onCreateScreen(intent: Intent): Screen {
        return MainScreen(carContext)
    }
}
```

#### Screen

A `Screen` is the basic UI unit. Each screen returns a single `Template` from `onGetTemplate()`. Screens are pushed/popped via `ScreenManager`.

```kotlin
class MainScreen(carContext: CarContext) : Screen(carContext) {
    override fun onGetTemplate(): Template {
        return ListTemplate.Builder()
            .setTitle("Main Menu")
            .setSingleList(buildItemList())
            .build()
    }
}
```

#### ScreenManager

`ScreenManager` manages a back stack of `Screen` instances. Use it to navigate between screens.

```kotlin
// Push a new screen
screenManager.push(DetailScreen(carContext))

// Pop back
screenManager.pop()

// Pop to root
screenManager.popToRoot()
```

The template depth limit (see Constraints below) applies to the back stack depth.


## Templates

### Template Catalog
---

Car App Library 1.4+ provides a set of templates designed for driver-safe interaction. Each template enforces distraction guidelines at the host level.

#### ListTemplate

Best for: browsable lists of items (settings, song lists, destinations).

```kotlin
val itemList = ItemList.Builder()
    .addItem(
        Row.Builder()
            .setTitle("Item Title")
            .addText("Secondary text")
            .setOnClickListener { screenManager.push(DetailScreen(carContext)) }
            .setImage(CarIcon.Builder(IconCompat.createWithResource(carContext, R.drawable.ic_item)).build())
            .build()
    )
    .build()

ListTemplate.Builder()
    .setTitle("Browse")
    .setSingleList(itemList)
    .setHeaderAction(Action.BACK)
    .build()
```

#### GridTemplate

Best for: icon-driven menus, category selection, home screens with visual tiles.

```kotlin
val gridItemList = ItemList.Builder()
    .addItem(
        GridItem.Builder()
            .setTitle("Category")
            .setImage(CarIcon.Builder(icon).build())
            .setOnClickListener { /* navigate */ }
            .build()
    )
    .build()

GridTemplate.Builder()
    .setTitle("Home")
    .setSingleList(gridItemList)
    .setHeaderAction(Action.APP_ICON)
    .build()
```

#### MessageTemplate

Best for: confirmation dialogs, error states, simple informational messages.

```kotlin
MessageTemplate.Builder("Are you sure you want to cancel navigation?")
    .setTitle("Confirm")
    .setIcon(CarIcon.Builder(iconCompat).build())
    .addAction(
        Action.Builder()
            .setTitle("Yes")
            .setOnClickListener { /* handle */ }
            .build()
    )
    .addAction(
        Action.Builder()
            .setTitle("No")
            .setOnClickListener { screenManager.pop() }
            .build()
    )
    .build()
```

#### NavigationTemplate

Best for: active turn-by-turn navigation with map rendering.

- Requires `androidx.car.app.category.NAVIGATION` category.
- Displays routing information, maneuver icons, and ETA.
- Draws map content via `SurfaceCallback`.

```kotlin
NavigationTemplate.Builder()
    .setNavigationInfo(
        RoutingInfo.Builder()
            .setCurrentStep(
                Step.Builder("Main Street")
                    .setManeuver(
                        Maneuver.Builder(Maneuver.TYPE_TURN_NORMAL_LEFT)
                            .setIcon(CarIcon.Builder(turnIcon).build())
                            .build()
                    )
                    .build(),
                Distance.create(0.5, Distance.UNIT_MILES)
            )
            .build()
    )
    .setActionStrip(actionStrip)
    .build()
```

#### MapTemplate

Best for: map-centric apps that need interactive content alongside the map (POI browsing, parking, charging stations). Available in Car App Library 1.4+.

```kotlin
MapTemplate.Builder()
    .setMapController(
        MapController.Builder()
            .setMapActionStrip(mapActionStrip)
            .build()
    )
    .setPane(
        Pane.Builder()
            .addRow(Row.Builder().setTitle("Station Name").addText("0.3 mi").build())
            .addAction(Action.Builder().setTitle("Navigate").setOnClickListener { /* ... */ }.build())
            .build()
    )
    .build()
```

### Template Selection Guide

| Use Case | Template | Notes |
|----------|----------|-------|
| Browsable list of items | `ListTemplate` | Most common; supports images, text rows |
| Visual category grid | `GridTemplate` | Icon-driven; limited text |
| Simple message/dialog | `MessageTemplate` | Max 2 actions |
| Active navigation | `NavigationTemplate` | Requires NAVIGATION category |
| Map with details pane | `MapTemplate` | 1.4+; for POI/charging |
| Long-form text | `LongMessageTemplate` | Terms of service, legal text |
| User input | `SearchTemplate` | Voice/keyboard input |
| Sign-in | `SignInTemplate` | QR code or PIN-based auth |


## Media Apps

### MediaBrowserService and MediaSession
---

Media apps for Android Auto do **not** use the Car App Library. They use the standard `MediaBrowserServiceCompat` + `MediaSessionCompat` pattern. The Auto host renders the UI automatically.

#### MediaBrowserService

Expose a browse tree of playable and browsable `MediaItem` objects.

```kotlin
class MyMediaBrowserService : MediaBrowserServiceCompat() {

    override fun onCreate() {
        super.onCreate()
        val session = MediaSessionCompat(this, "MyMediaService")
        sessionToken = session.sessionToken
        session.setCallback(MyMediaSessionCallback())
        session.isActive = true
    }

    override fun onGetRoot(
        clientPackageName: String,
        clientUid: Int,
        rootHints: Bundle?
    ): BrowserRoot {
        return BrowserRoot("ROOT_ID", null)
    }

    override fun onLoadChildren(
        parentId: String,
        result: Result<MutableList<MediaItem>>
    ) {
        result.detach()
        // Load items asynchronously, then result.sendResult(items)
    }
}
```

#### Browse Tree Structure

```
ROOT_ID
├── PLAYLISTS
│   ├── Playlist A
│   └── Playlist B
├── ALBUMS
│   ├── Album 1
│   └── Album 2
└── RECENTLY_PLAYED
    ├── Song X
    └── Song Y
```

- Use `MediaDescriptionCompat` to set title, subtitle, and icon URI.
- Mark items as `FLAG_BROWSABLE` (folder) or `FLAG_PLAYABLE` (leaf).
- Limit browse tree depth and breadth per Auto content guidelines.

#### Playback Controls

```kotlin
class MyMediaSessionCallback : MediaSessionCompat.Callback() {
    override fun onPlay() { /* start playback */ }
    override fun onPause() { /* pause */ }
    override fun onSkipToNext() { /* next track */ }
    override fun onSkipToPrevious() { /* previous track */ }
    override fun onPlayFromMediaId(mediaId: String?, extras: Bundle?) { /* play specific item */ }
    override fun onPlayFromSearch(query: String?, extras: Bundle?) { /* voice search */ }
}
```

Set `PlaybackStateCompat` actions to control which buttons appear:

```kotlin
val stateBuilder = PlaybackStateCompat.Builder()
    .setActions(
        PlaybackStateCompat.ACTION_PLAY or
        PlaybackStateCompat.ACTION_PAUSE or
        PlaybackStateCompat.ACTION_SKIP_TO_NEXT or
        PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS
    )
    .setState(PlaybackStateCompat.STATE_PLAYING, position, 1.0f)
mediaSession.setPlaybackState(stateBuilder.build())
```


## Messaging Apps

### Notifications-Based Messaging
---

Messaging apps on Android Auto work through notifications, not the Car App Library.

#### CarAppExtender

`CarAppExtender` extends standard notifications for the Auto environment. Use `NotificationCompat.Builder` with messaging style.

```kotlin
val messagingStyle = NotificationCompat.MessagingStyle(selfPerson)
    .setConversationTitle("Group Chat")
    .addMessage("Hey, are you on the way?", timestamp, senderPerson)

val replyAction = NotificationCompat.Action.Builder(
    R.drawable.ic_reply,
    "Reply",
    replyPendingIntent
)
    .addRemoteInput(
        RemoteInput.Builder("key_reply")
            .setLabel("Reply via voice")
            .build()
    )
    .setSemanticAction(NotificationCompat.Action.SEMANTIC_ACTION_REPLY)
    .setShowsUserInterface(false)
    .build()

val markAsReadAction = NotificationCompat.Action.Builder(
    R.drawable.ic_check,
    "Mark as Read",
    markAsReadPendingIntent
)
    .setSemanticAction(NotificationCompat.Action.SEMANTIC_ACTION_MARK_AS_READ)
    .setShowsUserInterface(false)
    .build()

val notification = NotificationCompat.Builder(context, CHANNEL_ID)
    .setSmallIcon(R.drawable.ic_message)
    .setStyle(messagingStyle)
    .addAction(replyAction)
    .addAction(markAsReadAction)
    .extend(
        CarAppExtender.Builder()
            .setImportance(NotificationManager.IMPORTANCE_HIGH)
            .build()
    )
    .build()
```

#### Voice Reply

Voice replies are delivered through `RemoteInput`. Handle the reply in a `BroadcastReceiver` or `Service`:

```kotlin
class ReplyReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val remoteInput = RemoteInput.getResultsFromIntent(intent)
        val replyText = remoteInput?.getCharSequence("key_reply")
        // Send the message, then update the notification
    }
}
```

Key requirements:
- Use `MessagingStyle` notifications (mandatory for Auto).
- Include `SEMANTIC_ACTION_REPLY` and `SEMANTIC_ACTION_MARK_AS_READ` actions.
- Set `setShowsUserInterface(false)` on both actions.


## Navigation Apps

### Turn-by-Turn Navigation
---

Navigation apps use the `NavigationTemplate` and the `NavigationManager` API.

#### SurfaceCallback

Implement `SurfaceCallback` to draw maps on the car display surface.

```kotlin
class MyNavigationSession : Session() {

    private val surfaceCallback = object : SurfaceCallback {
        override fun onSurfaceAvailable(surfaceContainer: SurfaceContainer) {
            val surface = surfaceContainer.surface ?: return
            // Initialize rendering (e.g., OpenGL, Canvas)
            drawMap(surface)
        }

        override fun onSurfaceDestroyed(surfaceContainer: SurfaceContainer) {
            // Release rendering resources
        }

        override fun onVisibleAreaChanged(visibleArea: Rect) {
            // Adjust map rendering to visible area (accounts for template overlays)
        }

        override fun onStableAreaChanged(stableArea: Rect) {
            // Area that remains constant (safe zone for persistent UI)
        }

        override fun onScroll(distanceX: Float, distanceY: Float) {
            // Handle pan gestures
        }

        override fun onScale(focusX: Float, focusY: Float, scaleFactor: Float) {
            // Handle pinch-to-zoom
        }
    }

    override fun onCreateScreen(intent: Intent): Screen {
        carContext.getCarService(AppManager::class.java)
            .setSurfaceCallback(surfaceCallback)
        return NavigationScreen(carContext)
    }
}
```

#### NavigationManager

Use `NavigationManager` to communicate navigation state to the host (cluster display, notifications).

```kotlin
val navigationManager = carContext.getCarService(NavigationManager::class.java)

// Start navigation
navigationManager.navigationStarted()

// Update trip information
navigationManager.updateTrip(
    Trip.Builder()
        .addStep(
            Step.Builder("Turn left onto Main Street")
                .setManeuver(Maneuver.Builder(Maneuver.TYPE_TURN_NORMAL_LEFT).build())
                .build(),
            Distance.create(200.0, Distance.UNIT_METERS)
        )
        .addDestination(
            Destination.Builder()
                .setName("Work")
                .setAddress("123 Main St")
                .build()
        )
        .build()
)

// End navigation
navigationManager.navigationEnded()
```

#### Maneuver Icons

`Maneuver.Builder` accepts a `TYPE_*` constant that maps to standard maneuver icons:

| Constant | Description |
|----------|-------------|
| `TYPE_TURN_NORMAL_LEFT` | Standard left turn |
| `TYPE_TURN_NORMAL_RIGHT` | Standard right turn |
| `TYPE_U_TURN_LEFT` | U-turn to the left |
| `TYPE_ROUNDABOUT_ENTER_AND_EXIT_CW` | Roundabout clockwise |
| `TYPE_MERGE_LEFT` | Merge left |
| `TYPE_FORK_LEFT` | Fork left |
| `TYPE_DESTINATION` | Arrival at destination |
| `TYPE_STRAIGHT` | Continue straight |

You can also provide a custom `CarIcon` for non-standard maneuvers.


## POI and Charging Apps

### Point-of-Interest Templates
---

POI and charging/EV apps use `MapTemplate` (1.4+) and `PlaceListMapTemplate` to display locations on the map alongside detail panes.

#### PlaceListMapTemplate

Shows a list of places pinned on a map.

```kotlin
val placeList = ItemList.Builder()
    .addItem(
        Row.Builder()
            .setTitle("Charging Station A")
            .addText("2 chargers available")
            .setMetadata(
                Metadata.Builder()
                    .setPlace(
                        Place.Builder(
                            CarLocation.create(37.7749, -122.4194)
                        )
                            .setMarker(PlaceMarker.Builder().build())
                            .build()
                    )
                    .build()
            )
            .setOnClickListener { screenManager.push(StationDetailScreen(carContext)) }
            .build()
    )
    .build()

PlaceListMapTemplate.Builder()
    .setTitle("Nearby Chargers")
    .setItemList(placeList)
    .setHeaderAction(Action.BACK)
    .build()
```

#### MapTemplate for Charging/POI Detail

Use `MapTemplate` with a `Pane` to show details alongside the map.

```kotlin
MapTemplate.Builder()
    .setMapController(
        MapController.Builder()
            .setMapActionStrip(
                ActionStrip.Builder()
                    .addAction(Action.PAN) // allow map panning
                    .build()
            )
            .build()
    )
    .setPane(
        Pane.Builder()
            .setHeader(PaneTemplate.Header.Builder().setTitle("Station A").build())
            .addRow(Row.Builder().setTitle("CCS 150kW").addText("Available").build())
            .addRow(Row.Builder().setTitle("Price").addText("$0.35/kWh").build())
            .addAction(
                Action.Builder()
                    .setTitle("Start Charging")
                    .setOnClickListener { /* initiate session */ }
                    .build()
            )
            .build()
    )
    .build()
```

Required category for POI apps:

```xml
<category android:name="androidx.car.app.category.POI" />
```

For EV charging apps specifically:

```xml
<category android:name="androidx.car.app.category.CHARGING" />
```


## Constraints and Limitations

### Distraction and Safety Guidelines
---

Android Auto enforces strict constraints to minimize driver distraction. These are enforced at the host level and cannot be bypassed.

#### Template Depth Limit

- Maximum **5 templates** in the back stack (screen depth).
- `Screen` pushes beyond this limit will throw an exception.
- `ScreenManager.popToRoot()` resets the depth counter.
- Refreshing the current template (calling `invalidate()` on the same `Screen`) does **not** count toward the depth limit.

#### List Item Limits

| Constraint | Limit |
|------------|-------|
| `ItemList` items (list/grid) | **6** items (may vary by OEM/host) |
| `ActionStrip` actions | **4** actions |
| `Pane` rows | **4** rows |
| `Pane` actions | **2** actions |
| `MessageTemplate` actions | **2** actions |

Use `ConstraintManager` to query the actual limits at runtime:

```kotlin
val constraintManager = carContext.getCarService(ConstraintManager::class.java)
val listLimit = constraintManager.getContentLimit(ConstraintManager.CONTENT_LIMIT_TYPE_LIST)
val gridLimit = constraintManager.getContentLimit(ConstraintManager.CONTENT_LIMIT_TYPE_GRID)
```

#### Additional Constraints

- **Text length**: long strings are truncated by the host. Keep titles and descriptions short.
- **Images**: use `CarIcon` with appropriate sizing. Large bitmaps are scaled/rejected.
- **Interaction**: no free-form text input while driving (keyboard disabled). `SearchTemplate` uses voice input while moving.
- **Refresh rate**: avoid calling `invalidate()` more than once per second. Excessive refreshes are throttled by the host.
- **No custom views**: all UI must go through templates. You cannot inflate custom layouts.
- **Dark mode**: support both light and dark `CarIcon` variants. The host switches automatically.


## Testing

### Desktop Head Unit (DHU)
---

The DHU simulates an Android Auto head unit on your development machine.

#### Setup

1. Install the DHU via Android Studio SDK Manager (under SDK Tools > Android Auto Desktop Head Unit Emulator).
2. Enable developer mode in the Android Auto app on your phone.
3. Start the head unit server on the phone (Developer settings > Start head unit server).
4. Connect via ADB:

```bash
# Forward the TCP port
adb forward tcp:5277 tcp:5277

# Launch DHU (path varies by SDK location)
cd $ANDROID_HOME/extras/google/auto
./desktop-head-unit
```

#### DHU Commands

```bash
# Simulate day/night mode toggle
day
night

# Simulate microphone input
mic play <audio_file.wav>

# Simulate navigation focus
nav focus
```

### TestCarContext
---

`TestCarContext` (from `androidx.car.app.testing`) provides a test-friendly `CarContext` for unit tests.

```kotlin
@Test
fun mainScreen_displaysListTemplate() {
    val testCarContext = TestCarContext.createCarContext(ApplicationProvider.getApplicationContext())
    val screen = MainScreen(testCarContext)
    val template = screen.onGetTemplate()

    assertThat(template).isInstanceOf(ListTemplate::class.java)
    val listTemplate = template as ListTemplate
    assertThat(listTemplate.title).isEqualTo("Main Menu")
}
```

#### Testing Screen Navigation

```kotlin
@Test
fun clickingItem_pushesDetailScreen() {
    val testCarContext = TestCarContext.createCarContext(ApplicationProvider.getApplicationContext())
    val screen = MainScreen(testCarContext)
    val template = screen.onGetTemplate() as ListTemplate

    // Simulate click on first item
    val firstItem = template.singleList!!.items[0] as Row
    firstItem.onClickDelegate.sendClick()

    val screenManager = testCarContext.getCarService(ScreenManager::class.java)
    assertThat(screenManager.screenStack).hasSize(2)
}
```

#### Instrumented Testing

Use `SessionController` for end-to-end session testing:

```kotlin
@Test
fun session_createsCorrectInitialScreen() {
    val session = MySession()
    val controller = SessionController(
        session,
        TestCarContext.createCarContext(ApplicationProvider.getApplicationContext())
    )
    controller.create(Intent())

    val currentScreen = session.carContext
        .getCarService(ScreenManager::class.java)
        .top

    assertThat(currentScreen).isInstanceOf(MainScreen::class.java)
}
```


## Lifecycle

### CarAppService Lifecycle
---

The `CarAppService` and `Session` lifecycle follows Android bound-service semantics, combined with Car App Library-specific callbacks.

#### Connection Flow

```
Host connects to CarAppService
    → CarAppService.onCreateSession()
        → Session.onCreateScreen(intent)
            → Screen.onGetTemplate()  (initial template rendered)
        → Session.onNewIntent(intent)  (subsequent intents)
    → Session lifecycle: ON_CREATE → ON_START → ON_RESUME
```

#### Disconnection Flow

```
Host disconnects
    → Session lifecycle: ON_PAUSE → ON_STOP → ON_DESTROY
    → CarAppService.onDestroy()  (if no more sessions)
```

#### Key Lifecycle Callbacks

```kotlin
class MySession : Session() {
    override fun onCreateScreen(intent: Intent): Screen {
        // Called once per session; return the root screen
        return MainScreen(carContext)
    }

    override fun onNewIntent(intent: Intent) {
        // Called when a new intent is sent to an existing session
        // e.g., notification tap while already connected
    }

    override fun onCarConfigurationChanged(newConfiguration: Configuration) {
        // Called when car configuration changes (e.g., day/night mode)
    }
}
```

#### Lifecycle-Aware Components

`Session` implements `LifecycleOwner`. Use it to scope work:

```kotlin
class MySession : Session() {
    override fun onCreateScreen(intent: Intent): Screen {
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) {
                // Start location updates
            }
            override fun onStop(owner: LifecycleOwner) {
                // Stop location updates
            }
        })
        return MainScreen(carContext)
    }
}
```

#### CarContext

`CarContext` is available after `onCreateScreen()`. It provides access to car services, navigation intents, and host info:

```kotlin
// Check API level supported by the connected host
val hostApiLevel = carContext.carAppApiLevel

// Start navigation in another app
carContext.startCarApp(
    Intent(CarContext.ACTION_NAVIGATE, Uri.parse("geo:37.7749,-122.4194"))
)

// Request permissions
carContext.requestPermissions(listOf(Manifest.permission.ACCESS_FINE_LOCATION)) { granted, rejected ->
    // handle result
}
```


## Distribution

### Play Store for Android Auto
---

#### App Categories

Declare the appropriate category in your manifest. Only approved categories are accepted:

| Category | Manifest Value |
|----------|---------------|
| Navigation | `androidx.car.app.category.NAVIGATION` |
| Parking / POI | `androidx.car.app.category.POI` |
| Charging (EV) | `androidx.car.app.category.CHARGING` |
| Media | Standard `MediaBrowserService` (no category needed) |
| Messaging | Standard notifications (no category needed) |
| IoT | `androidx.car.app.category.IOT` |

#### Minimum Requirements

- Declare `minCarAppApiLevel` in `AndroidManifest.xml`:

```xml
<meta-data
    android:name="androidx.car.app.minCarAppApiLevel"
    android:value="5" /> <!-- Car App Library 1.4 = API level 5+ -->
```

- Target API level 33+ for new submissions.
- Include both mobile and Auto experiences in the same APK/AAB (Auto is not a separate listing).

#### Review Guidelines

- **No distracting content**: all interaction must go through approved templates. Custom views are rejected.
- **Functional offline**: apps should handle offline/degraded states gracefully with `MessageTemplate`.
- **Voice-first**: messaging apps must support voice reply. Navigation apps should support voice-initiated destinations.
- **Template compliance**: stay within list limits and depth limits. Apps that crash from constraint violations are rejected.
- **Dark mode support**: provide dark-variant icons. The host controls theme switching.
- **Permissions**: request only permissions needed for Auto functionality. Justify location, microphone, and notification access.

#### Pre-Launch Checklist

- [ ] Tested on DHU with both day and night modes
- [ ] Verified list item counts against `ConstraintManager` limits
- [ ] Template back stack depth does not exceed 5
- [ ] All `CarIcon` resources include dark mode variants
- [ ] `minCarAppApiLevel` is set correctly in manifest
- [ ] Graceful handling of host disconnection
- [ ] Voice interactions tested (search, reply)
- [ ] No hardcoded host assumptions (works across different car brands)
- [ ] Privacy policy URL included in Play Store listing
- [ ] App category matches declared manifest category
