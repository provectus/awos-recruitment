# Android Automotive OS (AAOS) Patterns Reference

Target: latest stable AAOS

>[toc]


## AAOS vs Android Auto

### Architectural Distinction
---
Android Automotive OS (AAOS) is a **full embedded operating system** that runs directly on the vehicle's infotainment head unit. It replaces the OEM's proprietary OS entirely — Android is the platform, not a guest.

Android Auto is a **phone projection protocol**. The app runs on the user's phone and projects its UI onto the car's display via USB or wireless connection. The head unit acts as a remote display and input surface.

#### When to Use Which

| Factor | AAOS | Android Auto |
|--------|------|--------------|
| **Runtime** | On the vehicle's hardware | On the user's phone |
| **OS control** | Full (system services, sensors, HALs) | None (sandboxed projection) |
| **App lifecycle** | Managed by vehicle OS | Managed by phone OS |
| **Hardware access** | Direct via Car APIs and HALs | Limited via Car App Library abstractions |
| **Distribution** | Play Store for Automotive | Standard Play Store (phone) |
| **OEM dependency** | High — app runs on OEM hardware | Low — runs on any compatible phone |
| **Use case** | Deep vehicle integration, system apps, HVAC, native media | Portable companion apps, navigation, messaging |

#### Shared API Surface
The **Car App Library** (`androidx.car.app`) provides a common template-based API that works on both Android Auto and AAOS. Apps built with this library can target both platforms from a single codebase, with AAOS-specific capabilities available through runtime checks.

```kotlin
// Check if running on AAOS (embedded) vs Android Auto (projection)
val isAutomotive = context.packageManager
    .hasSystemFeature("android.hardware.type.automotive")
```

#### AAOS for Software-Defined Vehicles (AAOS SDV)

AAOS is expanding beyond infotainment to cover broader vehicle systems — seat actuators, climate, lighting, cameras, mirrors, and telemetry. This is primarily relevant for OEM system apps with platform-level signing. Third-party app developers should be aware of this direction but do not need to target AAOS SDV APIs directly.


## Car App Library on AAOS

### Same API, Additional Capabilities
---
On AAOS, the Car App Library provides the same template-driven UI model as Android Auto — `Screen`, `Template`, `Session` — but with expanded capabilities.

#### Key Differences on AAOS

- **Broader template support**: AAOS supports `MapTemplate`, `TabTemplate`, and longer lists without the strict item-count limits enforced on Android Auto.
- **Background execution**: Apps can perform background work more freely since they run natively on the vehicle OS, not projected from a phone.
- **Direct hardware access**: Apps can access vehicle hardware APIs alongside Car App Library UI, combining template UI with `CarHardwareManager` data.
- **Multiple display support**: AAOS supports rendering to instrument cluster and rear-seat displays via `CarAppService` and `SurfaceContainer`.

#### CarAppService on AAOS

```kotlin
class MyCarAppService : CarAppService() {
    override fun createHostValidator(): HostValidator {
        // On AAOS, the host is the system's car app host
        return HostValidator.ALLOW_ALL_HOSTS_VALIDATOR
    }

    override fun onCreateSession(): Session {
        return MySession()
    }
}

class MySession : Session() {
    override fun onCreateScreen(intent: Intent): Screen {
        return MainScreen(carContext)
    }
}
```

#### Manifest Declaration for AAOS

```xml
<manifest>
    <uses-feature
        android:name="android.hardware.type.automotive"
        android:required="true" />

    <!-- Declare supported template categories -->
    <application>
        <service
            android:name=".MyCarAppService"
            android:exported="true">
            <intent-filter>
                <action android:name="androidx.car.app.CarAppService" />
                <category android:name="androidx.car.app.category.NAVIGATION" />
            </intent-filter>
        </service>
    </application>
</manifest>
```

#### API Level Awareness

```kotlin
// Check Car App API level for feature availability
if (carContext.carAppApiLevel >= CarAppApiLevels.LEVEL_5) {
    // Use TabTemplate, MapTemplate with content refresh
}
```


## Car Hardware APIs

### CarHardwareManager and Vehicle Sensors
---
AAOS exposes vehicle hardware through the `android.car` package. The primary entry points are `Car`, `CarPropertyManager`, `CarSensorManager` (deprecated in favor of `CarPropertyManager`), and the Car App Library's `CarHardware` abstraction.

#### Connecting to the Car Service

```kotlin
private lateinit var car: Car
private lateinit var propertyManager: CarPropertyManager

fun connectCarService(context: Context) {
    car = Car.createCar(context)
    propertyManager = car.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager
}
```

#### CarInfo — Vehicle Metadata

`CarInfo` provides static and semi-static vehicle information accessible from the Car App Library.

```kotlin
val carHardware = carContext.getCarService(CarHardwareManager::class.java)
val carInfo = carHardware.carInfo

// Observe vehicle model info
carInfo.fetchModel { modelInfo ->
    val manufacturer = modelInfo.manufacturer?.value ?: "Unknown"
    val model = modelInfo.name?.value ?: "Unknown"
    val year = modelInfo.year?.value ?: 0
}

// Observe energy profile (fuel type, EV connector types)
carInfo.fetchEnergyProfile { profile ->
    val fuelTypes = profile.fuelTypes?.value ?: emptyList()
    val evConnectorTypes = profile.evConnectorTypes?.value ?: emptyList()
}
```

#### CarSensors — Live Vehicle Data

```kotlin
val carSensors = carHardware.carSensors

// Observe accelerometer
carSensors.addAccelerometerListener(
    CarSensors.UPDATE_RATE_NORMAL,
    executor
) { data ->
    val x = data.forces.value?.get(0) ?: 0f
    val y = data.forces.value?.get(1) ?: 0f
    val z = data.forces.value?.get(2) ?: 0f
}

// Observe compass
carSensors.addCompassListener(
    CarSensors.UPDATE_RATE_NORMAL,
    executor
) { data ->
    val bearings = data.orientations.value
}

// Observe gyroscope
carSensors.addGyroscopeListener(
    CarSensors.UPDATE_RATE_NORMAL,
    executor
) { data ->
    val rotations = data.rotations.value
}
```

#### CarPropertyManager — Direct Property Access

For system-privileged apps or apps with appropriate permissions, `CarPropertyManager` provides fine-grained access to the Vehicle HAL (VHAL).

```kotlin
// Read vehicle speed
val speed = propertyManager.getProperty<Float>(
    VehiclePropertyIds.PERF_VEHICLE_SPEED, 0
)

// Register for property change callbacks
propertyManager.registerCallback(
    object : CarPropertyManager.CarPropertyEventCallback {
        override fun onChangeEvent(event: CarPropertyValue<*>) {
            when (event.propertyId) {
                VehiclePropertyIds.PERF_VEHICLE_SPEED -> {
                    val speedKmh = event.value as Float
                }
                VehiclePropertyIds.ENGINE_RPM -> {
                    val rpm = event.value as Float
                }
            }
        }
        override fun onErrorEvent(propId: Int, zone: Int) {
            Log.e(TAG, "Error reading property $propId in zone $zone")
        }
    },
    VehiclePropertyIds.PERF_VEHICLE_SPEED,
    CarPropertyManager.SENSOR_RATE_NORMAL
)
```

#### Permissions

Vehicle sensor access requires specific permissions declared in the manifest:

```xml
<uses-permission android:name="android.car.permission.CAR_SPEED" />
<uses-permission android:name="android.car.permission.CAR_ENERGY" />
<uses-permission android:name="android.car.permission.CAR_DYNAMICS_STATE" />
```

Third-party apps have access to a limited subset. Many properties are restricted to system-signed apps.


## System UI Integration

### Status Bar, Navigation Bar, and Distraction Optimization
---

#### System Bars on AAOS

AAOS uses a custom system UI (`CarSystemUI`) that differs from phone/tablet Android:

- **Status bar**: Displays vehicle-specific indicators (connectivity, user, time). Located at the top. Apps cannot fully hide it — they render below it.
- **Navigation bar**: Provides the app launcher, home, and notification panel. Typically a persistent bar at the bottom or side of the screen. Not dismissible by third-party apps.
- **Control bar**: Some OEMs include a persistent climate/media control bar.

#### Insets and Layout

```kotlin
// Handle system bar insets properly
ViewCompat.setOnApplyWindowInsetsListener(rootView) { view, insets ->
    val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
    view.setPadding(
        systemBars.left,
        systemBars.top,
        systemBars.right,
        systemBars.bottom
    )
    WindowInsetsCompat.CONSUMED
}
```

#### Distraction Optimization (DO)

AAOS enforces **Driver Distraction** guidelines. When the vehicle is in motion, the platform restricts UI interactions:

- Lists are capped to a maximum number of visible items (typically 6).
- Text length is truncated.
- Keyboard input is blocked.
- Touch targets must meet minimum size requirements.

```kotlin
// Check driving state
val carUxRestrictionsManager = car.getCarManager(
    Car.CAR_UX_RESTRICTION_SERVICE
) as CarUxRestrictionsManager

carUxRestrictionsManager.registerListener { restrictions ->
    val isDistractionOptimized = restrictions.isRequiresDistractionOptimization
    val activeRestrictions = restrictions.activeRestrictions

    if (activeRestrictions and CarUxRestrictions.UX_RESTRICTIONS_NO_KEYBOARD != 0) {
        // Disable keyboard input
    }
    if (activeRestrictions and CarUxRestrictions.UX_RESTRICTIONS_LIMIT_STRING_LENGTH != 0) {
        // Truncate displayed strings
    }
}
```

#### Car App Library Built-in DO

When using the Car App Library, distraction optimization is handled automatically by the host. Templates enforce item limits, text truncation, and input restrictions without manual intervention.


## Media Apps on AAOS

### Native Playback and Audio Focus
---

#### MediaBrowserService Pattern

Media apps on AAOS follow the standard `MediaBrowserServiceCompat` pattern. The vehicle's system media app (OEM media center) browses and controls playback through this service.

```kotlin
class MyMediaBrowserService : MediaBrowserServiceCompat() {

    private lateinit var mediaSession: MediaSessionCompat

    override fun onCreate() {
        super.onCreate()
        mediaSession = MediaSessionCompat(this, "MyMediaService").apply {
            setCallback(mediaSessionCallback)
            isActive = true
        }
        sessionToken = mediaSession.sessionToken
    }

    override fun onGetRoot(
        clientPackageName: String,
        clientUid: Int,
        rootHints: Bundle?
    ): BrowserRoot {
        // Return browsable root; validate caller package
        return BrowserRoot("root", null)
    }

    override fun onLoadChildren(
        parentId: String,
        result: Result<MutableList<MediaBrowserCompat.MediaItem>>
    ) {
        result.detach()
        // Load and send media items asynchronously
        val items = loadMediaItems(parentId)
        result.sendResult(items)
    }
}
```

#### Audio Focus on AAOS

AAOS uses the standard `AudioManager` API for audio focus, but vehicle-specific behavior applies:

```kotlin
val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager

val focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).apply {
    setAudioAttributes(
        AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
            .build()
    )
    setOnAudioFocusChangeListener { focusChange ->
        when (focusChange) {
            AudioManager.AUDIOFOCUS_GAIN -> resumePlayback()
            AudioManager.AUDIOFOCUS_LOSS -> stopPlayback()
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> pausePlayback()
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> duckVolume()
        }
    }
}.build()

audioManager.requestAudioFocus(focusRequest)
```

#### Multi-Zone Audio

AAOS supports multi-zone audio for vehicles with multiple audio zones (front, rear, etc.):

```kotlin
val carAudioManager = car.getCarManager(Car.AUDIO_SERVICE) as CarAudioManager

// Get available audio zones
val audioZones = carAudioManager.audioZoneIds

// Get the zone for a specific occupant
val rearZone = carAudioManager.getZoneIdForOccupant(
    CarOccupantZoneManager.OCCUPANT_TYPE_REAR_PASSENGER
)

// Audio routing is typically handled at the system level.
// Third-party apps play audio normally; the system routes it
// to the appropriate zone based on the active user context.
```

#### Manifest for Media on AAOS

```xml
<service
    android:name=".MyMediaBrowserService"
    android:exported="true">
    <intent-filter>
        <action android:name="android.media.browse.MediaBrowserService" />
    </intent-filter>
</service>

<meta-data
    android:name="com.google.android.gms.car.application"
    android:resource="@xml/automotive_app_desc" />
```

`res/xml/automotive_app_desc.xml`:

```xml
<automotiveApp>
    <uses name="media" />
</automotiveApp>
```


## Maps and Navigation

### Full Map Rendering and Cluster Display
---

#### SurfaceContainer for Map Rendering

Navigation apps on AAOS can render directly to a `Surface` provided by the host, enabling full OpenGL/Vulkan map rendering instead of template-only UI.

```kotlin
class NavigationScreen(carContext: CarContext) : Screen(carContext) {

    private val surfaceCallback = object : SurfaceCallback {
        override fun onSurfaceAvailable(container: SurfaceContainer) {
            val surface = container.surface
            val width = container.width
            val height = container.height
            val dpi = container.dpi
            // Initialize map renderer with this surface
            mapRenderer.onSurfaceCreated(surface, width, height, dpi)
        }

        override fun onSurfaceDestroyed(container: SurfaceContainer) {
            mapRenderer.onSurfaceDestroyed()
        }

        override fun onVisibleAreaChanged(visibleArea: Rect) {
            // Adjust map UI to avoid overlap with template chrome
            mapRenderer.setVisibleArea(visibleArea)
        }

        override fun onStableAreaChanged(stableArea: Rect) {
            // Stable area excludes transient UI like notifications
            mapRenderer.setStableArea(stableArea)
        }

        override fun onScroll(distanceX: Float, distanceY: Float) {
            mapRenderer.pan(distanceX, distanceY)
        }

        override fun onScale(focusX: Float, focusY: Float, scaleFactor: Float) {
            mapRenderer.zoom(focusX, focusY, scaleFactor)
        }
    }

    override fun onGetTemplate(): Template {
        return NavigationTemplate.Builder()
            .setMapActionStrip(buildMapActions())
            .setActionStrip(buildActionStrip())
            .build()
    }
}
```

#### AppManager Surface Registration

```kotlin
class MySession : Session() {
    override fun onCreateScreen(intent: Intent): Screen {
        val appManager = carContext.getCarService(AppManager::class.java)
        appManager.setSurfaceCallback(surfaceCallback)
        return NavigationScreen(carContext)
    }
}
```

#### Cluster Display (Instrument Cluster)

AAOS supports rendering navigation information on the instrument cluster behind the steering wheel. This is exposed through the `NavigationManager`:

```kotlin
val navigationManager = carContext.getCarService(NavigationManager::class.java)

// Send navigation metadata to the cluster
navigationManager.navigationStarted()

// Update trip info
val trip = Trip.Builder()
    .addStep(
        Step.Builder("Turn right on Main St")
            .setManeuver(
                Maneuver.Builder(Maneuver.TYPE_TURN_NORMAL_RIGHT).build()
            )
            .build(),
        TravelEstimate.Builder(
            Distance.create(500.0, Distance.UNIT_METERS),
            DateTimeWithZone.create(arrivalTime, timeZone)
        ).build()
    )
    .addDestination(destination, destinationEstimate)
    .setLoading(false)
    .build()

navigationManager.updateTrip(trip)

// When navigation ends
navigationManager.navigationEnded()
```

#### Permissions for Navigation

```xml
<uses-permission android:name="androidx.car.app.NAVIGATION_TEMPLATES" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
```


## HVAC and Climate

### CarPropertyManager for Climate Control
---

HVAC control on AAOS is accessed through `CarPropertyManager` using VHAL property IDs. This is typically reserved for **system-privileged apps** (OEM climate apps).

#### Common HVAC Property IDs

| Property | ID Constant | Type | Description |
|----------|------------|------|-------------|
| Fan speed | `HVAC_FAN_SPEED` | `Int` | Fan speed level (0 to max) |
| Fan direction | `HVAC_FAN_DIRECTION` | `Int` | Airflow direction bitmask |
| Temperature set | `HVAC_TEMPERATURE_SET` | `Float` | Target temperature in Celsius |
| AC on/off | `HVAC_AC_ON` | `Boolean` | Air conditioning toggle |
| Auto mode | `HVAC_AUTO_ON` | `Boolean` | Automatic climate control |
| Defroster | `HVAC_DEFROSTER` | `Boolean` | Front/rear defroster state |
| Seat heating | `HVAC_SEAT_TEMPERATURE` | `Int` | Seat heater/cooler level |
| Steering wheel heating | `HVAC_STEERING_WHEEL_HEAT` | `Int` | Steering wheel heater level |

#### Reading and Writing HVAC Properties

```kotlin
val propertyManager = car.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager

// Read current temperature setpoint for driver zone
val driverTemp = propertyManager.getFloatProperty(
    VehiclePropertyIds.HVAC_TEMPERATURE_SET,
    VehicleAreaSeat.SEAT_ROW_1_LEFT
)

// Set temperature for driver zone
propertyManager.setFloatProperty(
    VehiclePropertyIds.HVAC_TEMPERATURE_SET,
    VehicleAreaSeat.SEAT_ROW_1_LEFT,
    22.0f  // Celsius
)

// Toggle AC
propertyManager.setBooleanProperty(
    VehiclePropertyIds.HVAC_AC_ON,
    VehicleAreaSeat.SEAT_ROW_1_LEFT,
    true
)
```

#### Zone Targeting

HVAC properties are **zoned** — each property can have different values per vehicle zone. Zones are defined by `VehicleAreaSeat`:

```kotlin
// Zone constants
VehicleAreaSeat.SEAT_ROW_1_LEFT   // Driver (LHD)
VehicleAreaSeat.SEAT_ROW_1_RIGHT  // Front passenger
VehicleAreaSeat.SEAT_ROW_2_LEFT   // Rear left
VehicleAreaSeat.SEAT_ROW_2_RIGHT  // Rear right
VehicleAreaSeat.SEAT_ROW_2_CENTER // Rear center

// Query supported zones for a property
val config = propertyManager.getCarPropertyConfig(
    VehiclePropertyIds.HVAC_TEMPERATURE_SET
)
val supportedZones = config?.areaIds ?: intArrayOf()

// Set temperature per zone
for (zone in supportedZones) {
    propertyManager.setFloatProperty(
        VehiclePropertyIds.HVAC_TEMPERATURE_SET,
        zone,
        22.0f
    )
}
```

#### Listening for HVAC Changes

```kotlin
propertyManager.registerCallback(
    object : CarPropertyManager.CarPropertyEventCallback {
        override fun onChangeEvent(event: CarPropertyValue<*>) {
            val zone = event.areaId
            when (event.propertyId) {
                VehiclePropertyIds.HVAC_TEMPERATURE_SET -> {
                    val temp = event.value as Float
                    updateTempDisplay(zone, temp)
                }
                VehiclePropertyIds.HVAC_AC_ON -> {
                    val isOn = event.value as Boolean
                    updateAcToggle(zone, isOn)
                }
            }
        }
        override fun onErrorEvent(propId: Int, zone: Int) {
            Log.e(TAG, "HVAC property error: $propId, zone: $zone")
        }
    },
    VehiclePropertyIds.HVAC_TEMPERATURE_SET,
    CarPropertyManager.SENSOR_RATE_ONCHANGE
)
```

#### Permissions

```xml
<uses-permission android:name="android.car.permission.CONTROL_CAR_CLIMATE" />
```

This permission is signature-level. Third-party apps cannot control HVAC unless explicitly granted by the OEM.


## User Management

### Multi-User, Driver Profiles, and Privacy
---

#### Multi-User Architecture

AAOS is a **multi-user OS**. Each driver or occupant can have their own Android user profile with separate:

- App data and preferences
- Accounts (Google, third-party)
- Media libraries and playback history
- Navigation favorites and history
- Notification state

#### User Lifecycle

```kotlin
val carUserManager = car.getCarManager(Car.CAR_USER_SERVICE) as CarUserManager

// Observe user switching events
carUserManager.addListener(executor) { event ->
    when (event.eventType) {
        CarUserManager.USER_LIFECYCLE_EVENT_TYPE_SWITCHING -> {
            // Clean up current user's state
            clearUserSession()
        }
        CarUserManager.USER_LIFECYCLE_EVENT_TYPE_UNLOCKED -> {
            // Initialize new user's data
            initializeUserSession(event.userId)
        }
    }
}
```

#### CarOccupantZoneManager

Maps physical zones (driver, front passenger, rear) to Android user profiles:

```kotlin
val occupantZoneManager = car.getCarManager(
    Car.CAR_OCCUPANT_ZONE_SERVICE
) as CarOccupantZoneManager

// Get all occupant zones
val zones = occupantZoneManager.allOccupantZones

for (zone in zones) {
    val userId = occupantZoneManager.getUserForOccupant(zone)
    val displays = occupantZoneManager.getAllDisplaysForOccupant(zone)
    Log.d(TAG, "Zone: ${zone.occupantType}, User: $userId, Displays: ${displays.size}")
}
```

#### Privacy Considerations

- **User isolation**: Each user profile is sandboxed. Apps cannot access other users' data without explicit system-level permissions.
- **Guest mode**: AAOS supports a guest user for temporary drivers (e.g., valets). Guest data is ephemeral and wiped on switch.
- **Location data**: Navigation history and location permissions are per-user. Clearing one user's data does not affect others.
- **Account data**: Apps should scope authentication tokens and session data to the current Android user ID.

```kotlin
// Scope data storage to current user
val currentUser = Process.myUserHandle()
val userSpecificPrefs = context.getSharedPreferences(
    "prefs_${currentUser.identifier}",
    Context.MODE_PRIVATE
)
```


## OEM Customization

### System vs Third-Party Apps and Privileged APIs
---

#### App Tiers on AAOS

| Tier | Signing | Capabilities | Examples |
|------|---------|-------------|----------|
| **System/Platform** | OEM platform key | Full VHAL access, system UI, privileged APIs | Settings, Climate, Instrument Cluster |
| **Privileged** | Pre-installed, allowlisted | Select privileged permissions | OEM media, OEM navigation |
| **Third-party** | Developer key | Car App Library, MediaBrowserService, standard Android APIs | Spotify, Waze, third-party apps |

#### Privileged API Access

System apps signed with the platform key can access the full `android.car` API surface:

```kotlin
// Only available to system apps
val vehicleManager = car.getCarManager(Car.VEHICLE_SERVICE) as VehicleManager
val diagnosticManager = car.getCarManager(Car.DIAGNOSTIC_SERVICE) as CarDiagnosticManager
val watchdogManager = car.getCarManager(Car.CAR_WATCHDOG_SERVICE) as CarWatchdogManager
```

#### OEM Customization Points

- **CarUiLib**: OEMs can customize shared UI components (toolbars, list items, preferences) via `car-ui-lib` resource overlays without modifying app source.
- **Runtime Resource Overlays (RRO)**: OEMs apply RROs to change colors, dimensions, drawables, and layouts system-wide.
- **System UI**: `CarSystemUI` is fully customizable — navigation bar position, status bar content, notification shade behavior.
- **VHAL extensions**: OEMs can define custom VHAL properties beyond the AOSP standard set for proprietary vehicle features.

#### Third-Party App Constraints

Third-party apps on AAOS:

- Must use Car App Library templates or `MediaBrowserService` — no arbitrary `Activity`-based UI (unless the app targets specific categories like video or browser on Android 14+).
- Cannot access privileged car properties (HVAC, diagnostics, etc.).
- Must comply with distraction optimization requirements.
- Are subject to Play Store for Automotive policies.


## Testing

### AAOS Emulator, GSI, and HAL Simulation
---

#### AAOS Emulator

Android Studio provides an AAOS system image for the emulator. This is the primary development and testing tool.

```bash
# Create an AAOS AVD via command line
sdkmanager "system-images;android-34;google_apis_playstore;x86_64"

avdmanager create avd \
    --name "AAOS_API_34" \
    --package "system-images;android-34;google_apis_playstore;x86_64" \
    --tag "google_apis_playstore" \
    --device "automotive_1024p_landscape"
```

The AAOS emulator includes:

- Simulated VHAL with configurable properties
- Multi-display support (main display + cluster)
- Multi-user support
- Audio zone simulation

#### VHAL Property Injection

The emulator's extended controls panel allows injecting VHAL property values at runtime for testing:

```bash
# Inject vehicle speed via ADB
adb shell cmd car_service inject-vhal-event 0x11600207 --value 60.0

# Inject gear selection (PARK = 4, DRIVE = 8)
adb shell cmd car_service inject-vhal-event 0x11400400 --value 8
```

#### Generic System Image (GSI)

For testing on real hardware without OEM customization:

```bash
# Flash GSI to a supported development board
fastboot flash system system-arm64-ab-vanilla.img
fastboot flash vbmeta vbmeta.img --disable-verity --disable-verification
fastboot reboot
```

#### Desktop Head Unit (DHU) for Car App Library

For testing Car App Library apps without the full AAOS emulator:

```bash
# Start the Desktop Head Unit
$ANDROID_HOME/extras/google/auto/desktop-head-unit

# Configure DHU for automotive mode
./desktop-head-unit --type=automotive
```

#### Automated Testing

```kotlin
// Use CarAppServiceController for testing Car App Library screens
@Test
fun testNavigationScreen() {
    val scenario = SessionScenario.launch(MyCarAppService::class.java)

    scenario.onSession { session ->
        val screen = session.carContext.getCarService(ScreenManager::class.java)
            .top as NavigationScreen

        val template = screen.onGetTemplate() as NavigationTemplate
        assertThat(template.actionStrip).isNotNull()
    }
}

// Unit test VHAL property handling
@Test
fun testHvacPropertyCallback() {
    val callback = HvacPropertyCallback()
    val event = CarPropertyValue(
        VehiclePropertyIds.HVAC_TEMPERATURE_SET,
        VehicleAreaSeat.SEAT_ROW_1_LEFT,
        22.0f
    )
    callback.onChangeEvent(event)
    assertThat(callback.currentTemp).isEqualTo(22.0f)
}
```

#### HAL Simulation

For development boards or custom hardware, AAOS provides a default VHAL implementation that can be configured:

```json
// Default VHAL config (hardware/interfaces/automotive/vehicle/aidl)
{
    "properties": [
        {
            "property": "VehicleProperty::PERF_VEHICLE_SPEED",
            "defaultValue": { "floatValues": [0.0] },
            "areas": [{ "areaId": 0 }]
        }
    ]
}
```


## Distribution

### Play Store for Automotive, Compliance, and Platform Variants
---

#### Play Store for Automotive

AAOS apps are distributed through the **Google Play Store for Automotive**, a separate track from the phone/tablet Play Store:

- Apps must be submitted specifically for the Automotive form factor.
- Separate APK/AAB or build variant targeting `android.hardware.type.automotive`.
- Independent review process with automotive-specific guidelines.
- OEMs can pre-install apps or make them available through the store.

#### Build Configuration

```kotlin
// build.gradle.kts
android {
    defaultConfig {
        minSdk = 29  // AAOS minimum
        targetSdk = <latest-stable-api>
    }

    flavorDimensions += "platform"
    productFlavors {
        create("auto") {
            dimension = "platform"
            // No uses-feature for phone
        }
        create("automotive") {
            dimension = "platform"
            // automotive-specific dependencies
        }
    }
}

dependencies {
    implementation("androidx.car.app:app:1.4.0")
    // Automotive-only dependency
    "automotiveImplementation"("androidx.car.app:app-automotive:1.4.0")
}
```

#### GAS vs AOSP Builds

| Aspect | GAS (Google Automotive Services) | AOSP-only |
|--------|----------------------------------|-----------|
| **Play Store** | Available | Not available |
| **Google Maps** | Pre-installed | Not available |
| **Google Assistant** | Integrated | Not available |
| **GMS APIs** | Full suite (Firebase, etc.) | Not available |
| **App distribution** | Play Store for Automotive | OEM sideloading or custom store |
| **OEM examples** | Polestar, Volvo, GM, Ford, Honda | Some Chinese OEMs, custom implementations |

#### AOSP-Only Considerations

For vehicles without GAS:

```kotlin
// Check for Google Play Services availability
fun hasGooglePlayServices(context: Context): Boolean {
    return try {
        GoogleApiAvailability.getInstance()
            .isGooglePlayServicesAvailable(context) == ConnectionResult.SUCCESS
    } catch (e: Exception) {
        false
    }
}

// Provide fallback for GMS-dependent features
if (hasGooglePlayServices(context)) {
    // Use Firebase, Google Maps, etc.
} else {
    // Use alternatives: OSM, custom analytics, etc.
}
```

#### Compliance Requirements

Apps submitted to Play Store for Automotive must meet:

- **Distraction optimization**: All interactive UI must comply with driver distraction guidelines.
- **Template usage**: Car App Library apps must use approved templates — no custom `Activity` rendering for navigation/POI categories.
- **Media apps**: Must implement `MediaBrowserService` correctly; no audio-only playback hacks.
- **Privacy**: Must comply with Automotive-specific data handling policies, especially for location and driving data.
- **Quality guidelines**: Must handle multi-user, screen size variation, day/night mode, and landscape orientation.

#### Android 14+ App Categories

Android 14 expanded the categories of apps allowed on AAOS:

| Category | UI Model | Notes |
|----------|----------|-------|
| **Navigation** | Car App Library (map surface) | Full map rendering via `SurfaceContainer` |
| **Media** | `MediaBrowserService` | System media app handles UI |
| **Messaging** | Car App Library | Template-based conversations |
| **POI / Parking** | Car App Library | Points of interest, charging, fuel |
| **Video** | Standard `Activity` | Only when parked; new in Android 13+ |
| **Browser** | Standard `Activity` | Only when parked; new in Android 14+ |
| **VoIP** | `ConnectionService` | In-app calling |
