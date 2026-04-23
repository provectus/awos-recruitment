# Car App Library Reference

> Target: latest stable Car App Library (`androidx.car.app`)

>[toc]

The Car App Library provides a **host-agnostic, template-driven UI framework** for building apps that run on both Android Auto (phone projection) and Android Automotive OS (embedded). Build once with the shared API surface below; see `android-auto-patterns.md` for Auto-specific patterns and `android-automotive-patterns.md` for AAOS-specific patterns.


## Architecture

### Core Components
---

The Car App Library follows a **service-session-screen** model. The car host (Auto or AAOS) connects to your `CarAppService`, which creates a `Session`, which manages a stack of `Screen` instances that each render a `Template`.

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

#### MapWithContentTemplate

Best for: map-centric apps that need interactive content alongside the map (POI browsing, parking, charging stations). Combines a map surface with List, Grid, Pane, or Message content.

```kotlin
MapWithContentTemplate.Builder()
    .setMapController(
        MapController.Builder()
            .setMapActionStrip(mapActionStrip)
            .build()
    )
    .setContentTemplate(
        ListTemplate.Builder()
            .setTitle("Nearby Chargers")
            .setSingleList(placeList)
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
| Map with details pane | `MapWithContentTemplate` | For POI/charging; combines map with any content template |
| Long-form text | `LongMessageTemplate` | Terms of service, legal text |
| User input | `SearchTemplate` | Voice/keyboard input |
| Sign-in | `SignInTemplate` | QR code or PIN-based auth |


## SurfaceCallback

### Map Rendering
---

Implement `SurfaceCallback` to draw maps on the car display surface. Used by navigation and POI apps.

```kotlin
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
```

Register the callback via `AppManager`:

```kotlin
class MySession : Session() {
    override fun onCreateScreen(intent: Intent): Screen {
        carContext.getCarService(AppManager::class.java)
            .setSurfaceCallback(surfaceCallback)
        return NavigationScreen(carContext)
    }
}
```


## Constraints and Limitations

### Distraction and Safety Guidelines
---

The car host enforces strict constraints to minimize driver distraction. These are enforced at the host level and cannot be bypassed.

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

> **Note:** AAOS supports broader limits than Android Auto for some constraints. See `android-automotive-patterns.md` for details.

#### Additional Constraints

- **Text length**: long strings are truncated by the host. Keep titles and descriptions short.
- **Images**: use `CarIcon` with appropriate sizing. Large bitmaps are scaled/rejected.
- **Interaction**: no free-form text input while driving (keyboard disabled). `SearchTemplate` uses voice input while moving.
- **Refresh rate**: avoid calling `invalidate()` more than once per second. Excessive refreshes are throttled by the host.
- **No custom views**: all UI must go through templates. You cannot inflate custom layouts.
- **Dark mode**: support both light and dark `CarIcon` variants. The host switches automatically.


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

### CarContext
---

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

#### API Level Awareness

```kotlin
// Check Car App API level for feature availability
if (carContext.carAppApiLevel >= CarAppApiLevels.LEVEL_5) {
    // Use TabTemplate, MapTemplate with content refresh
}
```

#### Platform Detection

```kotlin
// Check if running on AAOS (embedded) vs Android Auto (projection)
val isAutomotive = carContext.packageManager
    .hasSystemFeature("android.hardware.type.automotive")
```


## Testing

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

### SessionController
---

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


## App Categories

### Manifest Categories
---

Declare the appropriate category in your manifest. Only approved categories are accepted on both Android Auto and AAOS:

| Category | Manifest Value |
|----------|---------------|
| Navigation | `androidx.car.app.category.NAVIGATION` |
| Parking / POI | `androidx.car.app.category.POI` |
| Charging (EV) | `androidx.car.app.category.CHARGING` |
| IoT | `androidx.car.app.category.IOT` |
| Media | Standard `MediaBrowserService` / `MediaLibraryService` (no category needed) |
| Messaging | Standard notifications (no category needed) |

Set the minimum Car App API level:

```xml
<meta-data
    android:name="androidx.car.app.minCarAppApiLevel"
    android:value="<minimum-required>" />
```
