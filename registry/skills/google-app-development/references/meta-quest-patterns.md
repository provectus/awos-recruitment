# Meta Quest Patterns Reference

Adapting Android APK apps to run on Meta Quest headsets.

>[toc]


## Overview

Meta Quest headsets run a modified Android OS (based on AOSP). Standard Android APKs can run on Quest in a "2D panel" mode, but delivering a proper experience requires adapting for VR/MR interaction models.

Key differences from standard Android:
- **No touchscreen** — input comes from controllers, hand tracking, or gaze.
- **No Google Play Services** — no GMS, no Google Sign-In, no Google Maps, no Firebase Cloud Messaging via GMS.
- **Stereo rendering** — the system renders two eye buffers; performance budgets are tighter.
- **Fixed display** — no portrait/landscape switching; the headset has a fixed resolution and refresh rate.
- **Different distribution** — apps ship through Meta Quest Store, App Lab, or sideloading, not Google Play.
- **Spatial context** — apps can use passthrough, spatial anchors, and scene understanding for mixed reality.

A standard Android APK will run in a flat 2D panel inside the Quest environment without modification. To unlock VR/MR features, you integrate the Meta XR SDK and declare VR intent categories.


## Project Setup

### Meta XR SDK
---
Meta provides the Meta XR SDK (formerly Oculus SDK) as Android AAR libraries. For pure Android (non-Unity, non-Unreal) apps, use the **Meta Spatial SDK** or the **Platform SDK** depending on your needs.

Add the Meta Maven repository and dependencies in your module-level `build.gradle.kts`:

```kotlin
// settings.gradle.kts
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://maven.oculus.com/repository/maven-releases/") }
    }
}
```

```kotlin
// app/build.gradle.kts
android {
    defaultConfig {
        minSdk = 29 // Quest 2 minimum; Quest 3 supports 29+
        targetSdk = 32
    }

    buildTypes {
        // Quest-specific build variant
        create("quest") {
            initWith(getByName("release"))
            buildConfigField("boolean", "IS_QUEST_BUILD", "true")
            manifestPlaceholders["vrCategory"] = "com.oculus.intent.category.VR"
        }
    }
}

dependencies {
    implementation("com.meta.spatial:spatial-sdk:0.5.0")
    implementation("com.meta.platform:platform-sdk:67.0.0")
}
```

### Manifest Configuration

Declare VR intent category and Quest-specific metadata in `AndroidManifest.xml`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Required for Quest store submission -->
    <uses-feature android:name="android.hardware.vr.headtracking"
        android:required="true"
        android:version="1" />

    <!-- Declare supported controllers -->
    <uses-feature android:name="oculus.software.handtracking"
        android:required="false" />

    <application
        android:allowBackup="false"
        android:label="@string/app_name">

        <!-- Mark app as VR app -->
        <meta-data
            android:name="com.oculus.vr.focusaware"
            android:value="true" />

        <!-- Supported Quest devices -->
        <meta-data
            android:name="com.oculus.supportedDevices"
            android:value="quest2|questpro|quest3" />

        <activity
            android:name=".MainActivity"
            android:configChanges="density|keyboard|keyboardHidden|navigation|orientation|screenLayout|screenSize|uiMode"
            android:screenOrientation="landscape"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
                <!-- VR category: required for native VR mode -->
                <category android:name="com.oculus.intent.category.VR" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

Without `com.oculus.intent.category.VR`, the app runs in 2D panel mode (a flat window in the Quest home environment). Adding this category launches the app in immersive VR mode.

### Build Variants Strategy

For apps that target both phones and Quest, use build variants:

```kotlin
// app/build.gradle.kts
android {
    flavorDimensions += "platform"
    productFlavors {
        create("mobile") {
            dimension = "platform"
            buildConfigField("boolean", "IS_QUEST", "false")
        }
        create("quest") {
            dimension = "platform"
            buildConfigField("boolean", "IS_QUEST", "true")
            minSdk = 29
        }
    }
}
```

This lets you conditionally include Quest-specific code and dependencies while sharing the core business logic.


## Authentication and Entitlement

### Meta Platform SDK
---
Quest does not have Google Play Services. Authentication uses Meta accounts, and entitlement verification uses the Meta Platform SDK.

#### Entitlement Check

Every Quest app distributed through the Meta Quest Store must verify the user is entitled to run it. This prevents piracy and validates the purchase.

```kotlin
import com.oculus.platform.Platform
import com.oculus.platform.models.Entitlements

class QuestAuthManager(private val activity: Activity) {

    private val appId = "YOUR_META_APP_ID" // from Meta Developer Dashboard

    fun initialize() {
        // Initialize Platform SDK — must be called before any other Platform calls
        Platform.initializeAndroidAsync(activity, appId)
            .setOnCompleteListener { message ->
                if (message.isError) {
                    Log.e("QuestAuth", "Platform init failed: ${message.error}")
                    handleEntitlementFailure()
                    return@setOnCompleteListener
                }
                checkEntitlement()
            }
    }

    private fun checkEntitlement() {
        Entitlements.isViewerEntitled()
            .setOnCompleteListener { message ->
                if (message.isError) {
                    Log.e("QuestAuth", "User is NOT entitled")
                    handleEntitlementFailure()
                } else {
                    Log.i("QuestAuth", "User is entitled, proceeding")
                    onEntitlementVerified()
                }
            }
    }

    private fun handleEntitlementFailure() {
        // Required: quit the app if entitlement check fails
        // Meta rejects apps that continue running without entitlement
        activity.finish()
    }

    private fun onEntitlementVerified() {
        // Proceed with app logic
    }
}
```

#### Differences from Google Play Auth

| Aspect | Google Play | Meta Quest |
|--------|-------------|------------|
| Account system | Google Account | Meta Account |
| Auth library | Google Sign-In / Credential Manager | Meta Platform SDK |
| Entitlement check | Google Play Licensing | `Entitlements.isViewerEntitled()` |
| In-app purchases | Google Play Billing | Meta Platform IAP SDK |
| User identity | Google ID token | Oculus User ID |

If your app uses Firebase Auth with Google Sign-In on mobile, you need an alternative auth flow for Quest — typically a device code flow, email/password, or a companion app approach where the user authenticates on their phone and links the session.


## Spatial UI

### Adapting 2D Layouts for VR
---
When running in 2D panel mode, standard Android Views and Jetpack Compose UI render on a flat panel in VR space. This works but has limitations:

- **Text readability** — use minimum 24sp font size; small text is hard to read in VR.
- **Touch targets** — make interactive elements at least 56dp; precision is lower with controller raycasting.
- **Contrast** — use high-contrast colors; VR displays have different characteristics than phone screens.
- **Layout width** — panels have a fixed width in VR space; avoid layouts that assume phone-width screens.

#### Panel-Based UI

For native VR mode, Meta Spatial SDK supports panel-based UI where Android Views/Compose are rendered onto panels positioned in 3D space:

```kotlin
import com.meta.spatial.core.Panel
import com.meta.spatial.core.PanelConfig

class MainPanelActivity : PanelActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Create a panel with specific dimensions (in meters)
        val panelConfig = PanelConfig(
            width = 1.5f,  // 1.5 meters wide
            height = 1.0f, // 1 meter tall
            dpi = 320,
            layoutResource = R.layout.activity_main
        )

        createPanel(panelConfig)
    }
}
```

#### Jetpack Compose on Quest

Jetpack Compose works on Quest in 2D panel mode since Quest runs Android. For native VR panels, Compose support depends on the Meta Spatial SDK version — check current documentation. The general approach:

```kotlin
// Compose UI rendered onto a VR panel
@Composable
fun QuestDashboard() {
    MaterialTheme(
        colorScheme = darkColorScheme() // Dark themes work better in VR
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(32.dp) // Extra padding for VR readability
        ) {
            Text(
                text = "Dashboard",
                style = MaterialTheme.typography.headlineLarge,
                fontSize = 28.sp // Larger fonts for VR
            )
            Spacer(modifier = Modifier.height(24.dp))
            // Use large, well-spaced interactive elements
            Button(
                onClick = { /* action */ },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp)
            ) {
                Text("Action", fontSize = 20.sp)
            }
        }
    }
}
```

#### Recommended UI Patterns for VR

- Place primary panels at a comfortable distance (1.5–3 meters from the user).
- Avoid UI elements at the periphery of the field of view.
- Use curved panels for wide layouts to maintain readability at edges.
- Provide visual feedback on hover (controller raycast) before click.
- Avoid rapid panel transitions; use crossfades instead of slide animations.


## Input and Interaction

### Replacing Touch Events
---
Quest input comes from three sources: controllers, hand tracking, and gaze. The Meta Interaction SDK abstracts these into a unified interaction model.

#### Controller Input

Controllers provide button presses, trigger pulls, thumbstick input, and 6DoF pose:

```kotlin
import com.meta.spatial.core.Input
import com.meta.spatial.core.InputAction

class InputHandler {

    fun processInput(input: Input) {
        // Trigger press (equivalent to tap/click)
        if (input.isActionPressed(InputAction.TRIGGER)) {
            onSelect()
        }

        // Grip button (often used for grab interactions)
        if (input.isActionPressed(InputAction.GRIP)) {
            onGrab()
        }

        // Thumbstick for scrolling (replaces swipe gestures)
        val thumbstick = input.getThumbstickValue()
        if (thumbstick.y != 0f) {
            onScroll(thumbstick.y)
        }

        // Menu button
        if (input.isActionPressed(InputAction.MENU)) {
            onMenuToggle()
        }
    }
}
```

#### Hand Tracking

Hand tracking replaces touch input with pinch and poke gestures:

```kotlin
// Manifest: declare hand tracking support
// <uses-feature android:name="oculus.software.handtracking" android:required="false" />

class HandTrackingHandler {

    fun onPinchDetected(hand: Hand) {
        // Pinch = select/click equivalent
        // The system provides a raycast from the pinch point
        performAction(hand.pinchRayOrigin, hand.pinchRayDirection)
    }

    fun onPokeDetected(hand: Hand, target: Panel) {
        // Direct touch on a nearby panel
        // Poke maps to View touch events automatically for 2D panels
        target.dispatchTouchEvent(hand.pokePosition)
    }
}
```

#### Mapping Touch Events to VR Input

| Touch Event | Quest Equivalent |
|-------------|-----------------|
| `onClick` | Controller trigger press / hand pinch |
| `onLongClick` | Sustained trigger hold / sustained pinch |
| `onScroll` / `onFling` | Thumbstick Y-axis / hand swipe |
| `onSwipe` (horizontal) | Thumbstick X-axis |
| `pinch-to-zoom` | Two-controller distance change |
| `onDrag` | Grip hold + move controller |

For 2D panel apps, the system automatically maps controller raycast + trigger to touch events, so `OnClickListener` and similar still work. Hand tracking poke gestures also map to touch events on nearby panels.


## Rendering and Performance

### Frame Rate and Performance Budgets
---
Quest headsets require consistent frame rates to avoid discomfort:

| Device | Supported Refresh Rates | Frame Budget |
|--------|------------------------|--------------|
| Quest 2 | 72Hz, 90Hz, 120Hz | 13.9ms / 11.1ms / 8.3ms |
| Quest Pro | 72Hz, 90Hz | 13.9ms / 11.1ms |
| Quest 3 | 72Hz, 90Hz, 120Hz | 13.9ms / 11.1ms / 8.3ms |

Dropped frames cause judder and motion sickness. For adapted Android apps, 72Hz is the safest target.

#### Fixed Foveated Rendering (FFR)

FFR reduces GPU workload by rendering peripheral areas at lower resolution. Enable it to stay within frame budgets:

```kotlin
import com.meta.spatial.core.Renderer

class RenderConfig {

    fun configureRendering(renderer: Renderer) {
        // Set refresh rate
        renderer.setRefreshRate(72f) // Start conservative

        // Enable fixed foveated rendering
        // Levels: OFF, LOW, MEDIUM, HIGH, HIGH_TOP
        renderer.setFoveationLevel(FoveationLevel.HIGH)

        // Quest 3 supports dynamic foveation tied to eye tracking
        if (renderer.supportsDynamicFoveation()) {
            renderer.setDynamicFoveation(true)
        }
    }
}
```

#### GPU and Battery Optimization

- **Minimize overdraw** — flat UI panels have less concern here, but complex 3D scenes do.
- **Use texture compression** — ASTC is the preferred format on Quest (Adreno GPU).
- **Reduce draw calls** — batch where possible; Quest GPUs are mobile-class (Snapdragon XR2).
- **Thermal throttling** — Quest throttles CPU/GPU when hot; design for sustained performance, not peak. Test with extended play sessions (30+ minutes).
- **Battery** — Quest 2 has roughly 2–3 hours of battery. Avoid unnecessary background work; release resources when the headset enters standby.

```kotlin
// Respond to focus changes (headset on/off, guardian boundary)
override fun onVisibilityChanged(visible: Boolean) {
    if (!visible) {
        // User removed headset or hit guardian boundary
        pauseRendering()
        reduceBackgroundWork()
    } else {
        resumeRendering()
    }
}
```


## Passthrough and Mixed Reality

### Passthrough API
---
Quest 2 supports grayscale passthrough; Quest 3 and Quest Pro support full-color passthrough. This lets you overlay your app on the real world.

```kotlin
import com.meta.spatial.core.Passthrough

class MixedRealityManager {

    fun enablePassthrough(passthrough: Passthrough) {
        // Enable full passthrough (replaces VR background with camera feed)
        passthrough.setStyle(PassthroughStyle.FULL)
        passthrough.setEnabled(true)

        // Or use selective passthrough with a passthrough window
        passthrough.setStyle(PassthroughStyle.WINDOW)
    }
}
```

### Scene Understanding

Quest 3 provides scene understanding — the headset scans the room and identifies walls, floors, ceiling, furniture:

```kotlin
import com.meta.spatial.core.Scene

class SceneManager {

    fun queryRoom(scene: Scene) {
        scene.requestSceneCapture { result ->
            if (result.isSuccess) {
                val anchors = result.anchors
                for (anchor in anchors) {
                    when (anchor.semanticLabel) {
                        "FLOOR" -> placeContentOnFloor(anchor)
                        "WALL" -> attachPanelToWall(anchor)
                        "DESK" -> placeObjectOnDesk(anchor)
                        "CEILING" -> ignoreCeiling(anchor)
                    }
                }
            }
        }
    }

    private fun placeContentOnFloor(anchor: SceneAnchor) {
        // Position a 2D panel or 3D object at the anchor's pose
        val panel = createInfoPanel()
        panel.setPosition(anchor.pose.position)
        panel.setRotation(anchor.pose.rotation)
    }
}
```

### Spatial Anchors

Spatial anchors persist content placement across sessions:

```kotlin
import com.meta.spatial.core.SpatialAnchor

class AnchorManager {

    fun createPersistentAnchor(pose: Pose): SpatialAnchor {
        val anchor = SpatialAnchor.create(pose)
        // Save anchor UUID for next session
        anchor.persist { uuid ->
            preferences.edit().putString("saved_anchor", uuid.toString()).apply()
        }
        return anchor
    }

    fun restoreAnchor() {
        val uuid = preferences.getString("saved_anchor", null) ?: return
        SpatialAnchor.load(UUID.fromString(uuid)) { anchor ->
            if (anchor != null) {
                attachContentToAnchor(anchor)
            }
        }
    }
}
```


## Distribution

### Meta Quest Store vs App Lab vs Sideloading
---

| Channel | Review Process | Discoverability | Requirements |
|---------|---------------|-----------------|--------------|
| Quest Store | Full Meta review | Listed in store, searchable | Concept approval required before submission |
| App Lab | Lighter review | Direct link only, not browsable in store | Must meet technical requirements |
| Sideloading | None | Manual install via adb | Developer mode enabled on headset |

#### Submission Requirements

- **Entitlement check** — mandatory for Store and App Lab.
- **APK format** — Quest Store accepts APKs (not AABs, unlike Google Play).
- **Target API level** — must meet Meta's minimum (currently API 29+).
- **VR comfort rating** — apps must self-declare a comfort rating (comfortable, moderate, intense).
- **Performance** — must maintain target frame rate without sustained dropped frames.
- **Privacy policy** — required; must describe data collection.
- **Content guidelines** — Meta has its own content policies, separate from Google Play's.

#### APK vs AAB

Google Play requires Android App Bundles (AAB). Meta Quest Store accepts APKs directly. If you build both:

```kotlin
// app/build.gradle.kts
android {
    // For Quest builds, produce APK
    // For mobile builds, Android Studio generates AAB by default for Play
    buildTypes {
        getByName("release") {
            // Both variants use the same signing config
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

Build the Quest APK:
```bash
./gradlew assembleQuestRelease  # Produces APK for Quest
./gradlew bundleMobileRelease   # Produces AAB for Google Play
```


## Testing

### Development Setup
---

#### Meta Quest Developer Hub (MQDH)

MQDH is a desktop application for managing Quest devices during development. It provides:
- Device management and status monitoring
- APK installation and management
- Performance overlay and real-time metrics
- Screen casting for demos and debugging
- Log viewer

#### ADB Connection

```bash
# USB connection (recommended for initial setup)
adb devices
# Should show Quest serial number

# Enable Wi-Fi ADB (after USB connection established)
adb tcpip 5555
adb connect <quest-ip-address>:5555

# Install APK
adb install -r app-quest-release.apk

# View logs filtered to your app
adb logcat -s "YourAppTag"

# Launch app
adb shell am start -n com.yourpackage/.MainActivity
```

#### Quest Link

Quest Link (USB or Air Link) lets you run the Quest as a PC VR headset. For native Android app development, it is not directly useful — use direct APK deployment via adb instead. Quest Link is relevant if you are using a PC-based game engine (Unity/Unreal) for development.

#### Performance Profiling

```bash
# Enable OVR Metrics Tool overlay (shows FPS, GPU/CPU utilization, thermals)
adb shell setprop debug.oculus.gpuLevel 3
adb shell setprop debug.oculus.cpuLevel 3

# Capture a GPU trace
adb shell am broadcast -a com.oculus.ossystem.PERF_CAPTURE_START
# ... run your scenario ...
adb shell am broadcast -a com.oculus.ossystem.PERF_CAPTURE_STOP

# Use Android GPU Inspector (AGI) for detailed GPU analysis
# Quest devices are supported since they use Qualcomm Adreno GPUs
```

Use **OVR Metrics Tool** (installable from MQDH) to see a real-time overlay with:
- FPS and frame timing
- CPU/GPU utilization levels
- Thermal state
- Memory usage


## Common Pitfalls

### APIs Not Available on Quest
---

| Android API/Service | Available on Quest? | Alternative |
|---------------------|-------------------|-------------|
| Google Play Services | No | Meta Platform SDK |
| Google Maps | No | Custom map rendering or WebView-based |
| Google Sign-In | No | Meta account or custom auth |
| Firebase Cloud Messaging (GMS) | No | Polling, WebSockets, or Meta notifications |
| Firebase Analytics (GMS) | No | Meta analytics or custom solution |
| Camera/CameraX | Limited | Passthrough API for MR; no direct camera access |
| Telephony / SMS | No | N/A |
| NFC | No | N/A |
| Bluetooth (limited) | Partial | Controller pairing only; no general BT access |
| Location Services | No | N/A |
| Biometric (fingerprint/face) | No | Meta account entitlement |

### 2D App Mode vs Native VR

- Without `com.oculus.intent.category.VR` in the manifest, your app runs as a 2D panel — a floating window in the Quest home. This is the easiest path but limits the experience.
- 2D panel apps still receive controller input mapped to touch events, but cannot access hand tracking, passthrough, spatial anchors, or scene understanding.
- You can ship a 2D panel app as a first step and add VR features incrementally.

### Permission Model Differences

- Quest uses standard Android runtime permissions, but some permissions behave differently or are unavailable (camera, location, phone).
- Passthrough requires `com.oculus.permission.USE_SCENE` (declared in manifest, granted at runtime).
- Hand tracking does not require a runtime permission — it is a manifest-declared feature.
- Storage permissions follow standard Android scoped storage rules (API 29+).

### Orientation and Display

- Quest always renders in landscape. Setting `android:screenOrientation="portrait"` in the manifest will not produce a portrait display — it will either be ignored or cause layout issues.
- The display resolution is fixed per device (Quest 2: 1832x1920 per eye; Quest 3: 2064x2208 per eye). Do not assume standard phone resolutions.
- `DisplayMetrics` and `Configuration` may report unexpected values. Do not rely on these for layout decisions — use responsive layouts with `ConstraintLayout` or Compose.
- `WindowManager` reports the panel size, not the full headset resolution.

### Missing Google Play Services — Practical Workarounds

```kotlin
// Check at startup whether GMS is available
fun isGmsAvailable(context: Context): Boolean {
    return try {
        val result = GoogleApiAvailability.getInstance()
            .isGooglePlayServicesAvailable(context)
        result == ConnectionResult.SUCCESS
    } catch (e: Exception) {
        false // Not available on Quest
    }
}

// Branch your initialization based on platform
fun initializeApp(context: Context) {
    if (BuildConfig.IS_QUEST) {
        // Use Meta Platform SDK for auth, analytics, etc.
        initializeMetaPlatform(context)
    } else {
        // Standard Google Play Services path
        initializeGoogleServices(context)
    }
}
```

### Key Takeaways

- Always feature-detect rather than assume GMS availability.
- Use build variants to separate Quest and mobile code paths cleanly.
- Start with 2D panel mode for a quick port; add VR features iteratively.
- Test thermal behavior with extended sessions — Quest throttles aggressively.
- Entitlement checks are mandatory for store distribution and must block app usage on failure.
- Use large, high-contrast UI elements — VR readability is lower than phone screens.
