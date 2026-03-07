# Fire TV Patterns Reference

This reference covers Amazon Fire TV-specific concerns when adapting Android TV apps. General TV patterns (focus management, D-pad navigation, media playback architecture) are documented in `tv-patterns.md` and are not repeated here.

## Overview

Fire TV runs on AOSP (Android Open Source Project) — not the Google-certified Android TV platform. Fire TV devices run standard Android APKs, but the runtime environment differs in important ways:

- **No Google Play Services** — no GMS core, no Google Play Store, no Google APIs that depend on Play Services.
- **Amazon ecosystem** — apps are distributed through the Amazon Appstore, purchases go through Amazon IAP, and the voice assistant is Alexa (not Google Assistant).
- **AOSP base** — Fire OS is a fork of Android. Fire OS 5 is based on Android 5.1 (API 22), Fire OS 6 on Android 7.1 (API 25), Fire OS 7 on Android 9 (API 28), and Fire OS 8 on Android 11 (API 30). Always check the Fire OS version mapping when setting `minSdkVersion` / `targetSdkVersion`.
- **Leanback library** — Fire TV supports `androidx.leanback` but with caveats (see Common Pitfalls).

A single codebase can target both Google TV / Android TV and Fire TV with proper feature detection and build flavors.


## Amazon Appstore

### Publishing

- Apps are submitted through the [Amazon Developer Console](https://developer.amazon.com/apps-and-games).
- You upload a signed APK (or AAB converted to APK — Amazon does not natively accept AAB as of Fire OS 8).
- The Amazon Appstore has its own review process, separate from Google Play. Expect 1-3 business days for review.
- Fire TV apps must declare the `android.software.leanback` feature (use `android:required="false"` if the app also runs on mobile).

### Device Targeting

- In the Amazon Developer Console, you select which Fire TV devices your app supports.
- Use the `amazon.hardware.fire_tv` feature in your manifest to restrict to Fire TV only:

```xml
<uses-feature android:name="amazon.hardware.fire_tv" android:required="true" />
```

### App Compatibility

- Apps targeting `android.hardware.touchscreen` with `required="true"` will be filtered out on Fire TV. Set it to `false`:

```xml
<uses-feature android:name="android.hardware.touchscreen" android:required="false" />
```

- Avoid declaring permissions or features that Fire TV cannot fulfill (e.g., telephony, camera, NFC, GPS).
- Amazon runs automated compatibility tests during submission. You can also use the **Amazon App Testing Service** to pre-validate.


## In-App Purchases

Fire TV does not support Google Play Billing. Use the **Amazon In-App Purchasing (IAP) API** instead.

### Setup

Add the Amazon Appstore SDK dependency:

```groovy
implementation "com.amazon.device:amazon-appstore-sdk:3.+"
```

### Core API

Amazon IAP uses two primary interfaces:

- **`PurchasingService`** — static methods to initiate purchases, check user data, and query product information.
- **`PurchasingListener`** — callback interface your app implements to receive purchase results.

```kotlin
// Register the listener (typically in Activity.onResume)
PurchasingService.registerListener(context, myPurchasingListener)

// Get user data
PurchasingService.getUserData()

// Get product data
PurchasingService.getProductData(setOf("com.example.premium"))

// Initiate a purchase
PurchasingService.purchase("com.example.premium")
```

### PurchasingListener Callbacks

```kotlin
class MyPurchasingListener : PurchasingListener {
    override fun onUserDataResponse(response: UserDataResponse) { /* user/marketplace info */ }
    override fun onProductDataResponse(response: ProductDataResponse) { /* product details */ }
    override fun onPurchaseResponse(response: PurchaseResponse) { /* purchase result + receipt */ }
    override fun onPurchaseUpdatesResponse(response: PurchaseUpdatesResponse) { /* pending/past purchases */ }
}
```

### Receipts and Validation

- Amazon returns a `Receipt` object with a `receiptId`. Validate receipts server-side using the [Amazon Receipt Verification Service (RVS)](https://developer.amazon.com/docs/in-app-purchasing/iap-rvs-for-android-apps.html).
- Always call `PurchasingService.notifyFulfillment()` after delivering the purchased content to avoid duplicate delivery.

### Subscriptions

- Amazon IAP supports subscriptions with auto-renewal.
- Subscription management (cancel, upgrade) is handled through the Amazon Appstore app, not in your app.
- Use `PurchasingService.getPurchaseUpdates(false)` to sync subscription state on app start.

### Multi-Platform Billing Strategy

Use build flavors or a billing abstraction layer:

```kotlin
interface BillingProvider {
    fun initialize(context: Context)
    fun queryProducts(skus: Set<String>)
    fun purchase(sku: String)
}

// Implementations: GooglePlayBillingProvider, AmazonIapProvider
```


## Alexa Integration

### Voice Search

- Fire TV uses **Alexa** for voice, not Google Assistant. The voice remote button triggers Alexa.
- Fire TV supports the Leanback `SearchFragment`, but voice queries come from Alexa, not the Google speech recognizer.
- To make your content discoverable by Alexa voice search, integrate with the **Alexa Video Skill API** (catalog integration on the Amazon side) or implement a deep link handler for Alexa-initiated searches.

### Video Skill API

- The Video Skill API allows Alexa to search, browse, and control playback within your app.
- This is configured on the Amazon developer portal (not purely in-app code). You provide a content catalog and implement directive handlers.
- Directives include: `SearchAndPlay`, `SearchAndDisplayResults`, `FastForward`, `Rewind`, `Pause`, `Play`.

### Alexa for Apps

- **Alexa for Apps** lets Alexa deep-link into your app or trigger specific actions via custom intents.
- Register a custom skill or use the App Links framework with Alexa.

### Voice Remote Differences

- Fire TV remotes send standard Android `KeyEvent` codes for D-pad and media buttons.
- The **microphone button** on Fire TV remotes triggers Alexa system-wide — your app does not receive this key event.
- Fire TV remotes include a dedicated **menu button** (`KEYCODE_MENU`), which Android TV remotes may not have.


## Missing Google Play Services

### What Is Unavailable

| Google Service | Status on Fire TV |
|---|---|
| Google Play Billing | Not available — use Amazon IAP |
| Firebase Cloud Messaging (FCM) | Not available — use Amazon Device Messaging (ADM) or Amazon SNS |
| Google Sign-In | Not available — use Login with Amazon (LWA) |
| Google Maps | Not available — Amazon Maps API (limited) or web-based maps |
| Google Cast | Not available — Fire TV has its own casting protocol |
| Google Analytics / Firebase Analytics | Partially available (REST-based Firebase works, but Play Services-dependent SDKs do not) |
| ML Kit (on-device) | Not available — use TensorFlow Lite directly or Amazon ML services |

### Alternatives

#### Push Notifications
Use **Amazon Device Messaging (ADM)**:

```xml
<uses-permission android:name="com.amazon.device.messaging.permission.RECEIVE" />
```

```kotlin
// Register for ADM
val adm = ADM(context)
if (adm.registrationId == null) {
    adm.startRegister()
}
```

ADM is structurally similar to FCM. Server-side, you can also use **Amazon SNS** as a unified push service that fans out to both FCM and ADM.

#### Authentication
Use **Login with Amazon (LWA)** for OAuth-based sign-in:

```kotlin
AuthorizationManager.authorize(
    AuthorizeRequest.Builder(requestContext)
        .addScopes(ProfileScope.profile(), ProfileScope.postalCode())
        .build()
)
```

#### Feature Detection Pattern

```kotlin
fun hasGooglePlayServices(context: Context): Boolean {
    return try {
        Class.forName("com.google.android.gms.common.GoogleApiAvailability")
        val availability = com.google.android.gms.common.GoogleApiAvailability.getInstance()
        availability.isGooglePlayServicesAvailable(context) == com.google.android.gms.common.ConnectionResult.SUCCESS
    } catch (e: ClassNotFoundException) {
        false
    }
}

fun isAmazonDevice(): Boolean {
    return Build.MANUFACTURER.equals("Amazon", ignoreCase = true)
}
```


## Media Playback

### ExoPlayer on Fire TV

- **ExoPlayer / Media3** works on Fire TV. It is the recommended player for streaming apps.
- No special configuration is needed beyond what you would do for Android TV.
- Ensure you bundle any required decoders — Fire TV does not ship Google Play Services media codecs.

### DRM

- Fire TV devices support **Widevine L1** (hardware-level) on most models, enabling HD and UHD DRM-protected content.
- Check the Widevine security level at runtime:

```kotlin
val mediaDrm = MediaDrm(C.WIDEVINE_UUID)
val securityLevel = mediaDrm.getPropertyString("securityLevel")
// "L1" = hardware, "L3" = software
```

- PlayReady DRM is also supported on Fire TV (not available on standard Android TV).

### Audio Output

- Fire TV supports Dolby Atmos (via Dolby Digital Plus) on supported devices (Fire TV Stick 4K, Fire TV Cube).
- Use `AudioManager` to query supported encodings before selecting an audio track.
- Pass-through audio (e.g., for AV receivers) is supported — configure via `AudioAttributes` with `CONTENT_TYPE_MOVIE` and `USAGE_MEDIA`.


## Device Capabilities

### Hardware Comparison

| Feature | Fire TV Stick (3rd Gen) | Fire TV Stick 4K Max | Fire TV Cube (3rd Gen) |
|---|---|---|---|
| Fire OS | 7 (Android 9) | 7 (Android 9) | 7 (Android 9) |
| Processor | Quad-core 1.7 GHz | Quad-core 1.8 GHz | Octa-core 2.2 GHz |
| RAM | 1 GB | 2 GB | 2 GB |
| Storage | 8 GB | 16 GB | 16 GB |
| Max Resolution | 1080p | 4K UHD, HDR10+, Dolby Vision | 4K UHD, HDR10+, Dolby Vision |
| Dolby Atmos | No | Yes | Yes |
| Ethernet | No (USB adapter) | No (USB adapter) | Built-in |
| Hands-free Alexa | No | No | Yes (built-in mic array) |

### Performance Tiers

For a multi-device app, consider defining performance tiers:

- **Low tier** (Fire TV Stick, 1 GB RAM): minimize background services, reduce image cache sizes, limit concurrent network requests, avoid complex animations.
- **Mid tier** (Fire TV Stick 4K, 2 GB RAM): standard experience, moderate caching.
- **High tier** (Fire TV Cube, 2 GB RAM + faster CPU): full experience, richer animations, background prefetching.

### Memory and Storage Constraints

- 1 GB devices have roughly 500-600 MB available to apps after system overhead. Budget your heap accordingly.
- Internal storage is limited (8-16 GB, minus OS). Use streaming over local storage. If caching, set strict eviction policies.
- Test with `adb shell dumpsys meminfo <package>` to monitor memory usage.


## Web App Support

### Fire TV Web Apps

- Fire TV supports web apps via the **Amazon WebView** (based on Chromium).
- You can wrap a web app in a WebView-based Android app or use the Amazon Web App Starter Kit.
- Web apps have access to D-pad navigation if the page handles keyboard events properly.

### Hybrid App Patterns

- For hybrid apps (native shell + web content), use `WebView` with hardware acceleration enabled.
- Inject a JavaScript interface to bridge between web content and native Amazon APIs (IAP, ADM):

```kotlin
webView.addJavascriptInterface(AmazonBridge(context), "AmazonBridge")
```

- Ensure the WebView content is optimized for TV: large touch targets replaced with focus-based navigation, 10-foot UI design principles.


## Testing

### Connecting via ADB

Fire TV devices support ADB over the network:

1. Enable **Developer Options** on the Fire TV (Settings > My Fire TV > About > click Build 7 times).
2. Enable **ADB Debugging** and **Apps from Unknown Sources**.
3. Find the device IP address in Settings > My Fire TV > About > Network.
4. Connect:

```bash
adb connect <fire-tv-ip>:5555
```

### Sideloading

```bash
adb install -r myapp.apk
```

### Fire TV Emulator Limitations

- There is no official Fire TV emulator from Amazon. Use the **standard Android TV emulator** (from Android SDK) for basic layout and navigation testing.
- For Amazon-specific features (IAP, ADM, Alexa), you must test on a physical Fire TV device.
- The **Amazon App Testing Service** (in the Developer Console) can run automated tests on real Fire TV hardware in the cloud.

### Testing Checklist for Fire TV

- [ ] App installs and launches without Google Play Services errors.
- [ ] D-pad navigation works on all screens (this is shared with Android TV — see `tv-patterns.md`).
- [ ] Amazon IAP flows complete (purchase, restore, subscription).
- [ ] ADM push notifications are received.
- [ ] Voice search deep links resolve correctly.
- [ ] App does not crash on 1 GB RAM devices under memory pressure.
- [ ] Content plays correctly with DRM (if applicable).
- [ ] App passes Amazon Appstore submission checks.


## Common Pitfalls

### Leanback Library Differences

- `BrowseSupportFragment` and `SearchSupportFragment` work on Fire TV, but the built-in voice search integration assumes Google Assistant. Override the speech recognizer or handle Alexa voice input separately.
- `Recommendation` API (legacy Leanback notifications for the home screen) does not work on Fire TV. Fire TV uses its own content recommendation API.
- Leanback's `DetailsFragment` renders correctly, but test thoroughly — some theme attributes may differ between Fire OS and stock Android TV.

### Missing APIs and Features

- **Google TV Channels / Watch Next**: not available on Fire TV. Fire TV has its own "Recent" row, populated through a different content provider.
- **Google Assistant App Actions**: not applicable. Use Alexa Video Skill API instead.
- **Cast Connect**: not available. Fire TV uses a proprietary casting/mirroring protocol.

### Feature Detection for Multi-Platform Builds

When shipping a single codebase for both Google TV and Fire TV, use build flavors combined with runtime detection:

```kotlin
// Build flavor approach (preferred for compile-time separation)
// build.gradle
flavorDimensions += "store"
productFlavors {
    create("google") { dimension = "store" }
    create("amazon") { dimension = "store" }
}

// Runtime detection (for shared code paths)
object TvPlatform {
    val isFireTv: Boolean by lazy {
        Build.MANUFACTURER.equals("Amazon", ignoreCase = true)
    }

    val isAndroidTv: Boolean by lazy {
        !isFireTv // simplistic — refine with feature checks
    }
}
```

### Other Gotchas

- **`PackageManager.hasSystemFeature("amazon.hardware.fire_tv")`** returns `true` only on Fire TV. Use this for definitive Fire TV detection at runtime.
- Fire TV devices may not have Bluetooth HID profile enabled by default — game controller support requires explicit testing.
- Fire OS updates lag behind AOSP releases. Do not assume the latest Android APIs are available; always check Fire OS version mappings.
- The Fire TV home screen launcher is Amazon-controlled. You cannot replace it or deeply customize home screen presence the way you might with Android TV's home screen channels.
