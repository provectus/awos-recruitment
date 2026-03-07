# Fire Tablet Patterns Reference

This reference covers Amazon Fire Tablet-specific concerns when adapting Android apps for the Fire Tablet lineup. General Android tablet patterns (adaptive layouts, WindowSizeClass, multi-window, input support) are documented in `tablet-patterns.md` and are not repeated here. Amazon ecosystem fundamentals (IAP, ADM, missing GMS, Login with Amazon, feature detection) are documented in `fire-tv-patterns.md` and are not repeated here.


## Overview

Fire Tablets are AOSP-based Android tablets manufactured by Amazon. They run standard Android APKs but diverge from mainstream Android tablets in several ways:

- **No Google Play Services** -- no GMS core, no Google Play Store, no FCM, no Google Sign-In. See `fire-tv-patterns.md` for the full missing-services table and Amazon alternatives (IAP, ADM, LWA).
- **Amazon ecosystem** -- apps are distributed through the Amazon Appstore, purchases use Amazon IAP, and Alexa is the voice assistant.
- **Fire OS** -- a fork of AOSP. Fire OS version determines the underlying Android API level. Fire OS 8 is based on Android 11 (API 30). Always check the [Fire OS version mapping](https://developer.amazon.com/docs/fire-tablets/fire-os-overview.html) when setting `minSdkVersion` / `targetSdkVersion`.
- **Touch-first device** -- unlike Fire TV, Fire Tablets are touchscreen devices. Standard Android touch UIs work, but you must account for the specific screen sizes, densities, and hardware constraints of the Fire lineup.
- **Price-driven hardware** -- Fire Tablets are budget to mid-range. Performance, RAM, and display quality vary significantly across the lineup. The Fire 7 in particular requires careful optimization.


## Device Lineup

### Hardware Comparison

| Model | Display | Resolution | Density | RAM | Storage | Fire OS | API Level |
|---|---|---|---|---|---|---|---|
| Fire 7 (2022) | 7" IPS | 1024 x 600 | ~170 dpi (mdpi) | 2 GB | 16/32 GB | 8 | 30 (Android 11) |
| Fire HD 8 (2022) | 8" IPS | 1280 x 800 | ~189 dpi (mdpi/hdpi) | 2 GB | 32/64 GB | 8 | 30 (Android 11) |
| Fire HD 10 (2023) | 10.1" IPS | 1920 x 1200 | ~224 dpi (hdpi) | 3 GB | 32/64 GB | 8 | 30 (Android 11) |
| Fire Max 11 (2023) | 11" IPS | 2000 x 1200 | ~213 dpi (hdpi) | 4 GB | 64/128 GB | 8 | 30 (Android 11) |

### Performance Tiers

- **Low tier** (Fire 7): Slowest SoC, 2 GB RAM, lowest resolution. Treat this as a constrained device -- reduce image cache sizes, avoid heavy animations, limit background work. The 1024x600 resolution at 7" yields ~170 dpi, which maps to `mdpi` density bucket.
- **Mid tier** (Fire HD 8): Modest improvement over Fire 7. Still 2 GB RAM but a faster processor and higher resolution. Standard experience with moderate asset quality.
- **High tier** (Fire HD 10, Fire Max 11): 3-4 GB RAM, faster SoCs, higher resolution displays. Full experience with richer layouts and larger assets. Fire Max 11 supports stylus input (Amazon-branded stylus).

### Density Bucket Mapping

Fire Tablets cluster around `mdpi` and `hdpi`. If your app only ships `xxhdpi` and `xxxhdpi` drawables (common for phone-optimized apps), resources will be downscaled at runtime, wasting memory. Ship `mdpi` and `hdpi` assets or use vector drawables to avoid this.


## Amazon Appstore for Tablets

### Publishing

- Apps are submitted through the [Amazon Developer Console](https://developer.amazon.com/apps-and-games).
- Amazon accepts signed APKs. AAB support is limited -- check current status before submitting.
- Provide **tablet-specific screenshots** in the listing. Amazon requires separate screenshot sets for different device categories. Upload screenshots at 1920x1200 or 2000x1200 for the HD 10 and Max 11 listings.
- Review typically takes 1-3 business days.

### Device Targeting

- In the Developer Console, select which Fire Tablet models your app supports.
- To restrict your app to Fire Tablets only (excluding Fire TV), avoid declaring `amazon.hardware.fire_tv` as required and instead rely on touchscreen and screen size features:

```xml
<uses-feature android:name="android.hardware.touchscreen" android:required="true" />
```

- To detect Fire Tablet at runtime:

```kotlin
fun isFireTablet(): Boolean {
    return Build.MANUFACTURER.equals("Amazon", ignoreCase = true) &&
        !context.packageManager.hasSystemFeature("amazon.hardware.fire_tv")
}
```

### Compatibility Testing

- Use the **Amazon App Testing Service** (in the Developer Console) to run automated compatibility checks on real Fire Tablet hardware before submission.
- Amazon runs its own compatibility tests during review and may reject apps that crash on targeted devices.


## UI Adaptation

### Screen Sizes and Density

Fire Tablets span from 7" to 11", mapping to `COMPACT` through `EXPANDED` WindowSizeClass in portrait and landscape. Key considerations:

- **Fire 7 (1024x600)**: At 7" this is roughly 600dp wide in landscape -- right at the `COMPACT` / `MEDIUM` boundary. Test both orientations carefully. In portrait, width is ~350dp (firmly `COMPACT`).
- **Fire HD 10 and Max 11**: These hit `EXPANDED` width in landscape (~960dp+) and `MEDIUM` in portrait (~600dp+). List-detail layouts should activate in landscape.

Use `WindowSizeClass` as documented in `tablet-patterns.md` rather than hardcoding Fire-specific breakpoints.

### Landscape and Portrait Handling

All Fire Tablets support both orientations. The default launcher orientation varies by model:

- Fire 7 and Fire HD 8 default to **portrait**.
- Fire HD 10 and Fire Max 11 default to **landscape** (wider form factor is more natural in landscape).

Ensure your app handles both orientations gracefully. Do not lock orientation unless your app genuinely requires it.

### Show Mode (Dock Mode)

Fire HD 8 and Fire HD 10 support **Show Mode**, which transforms the tablet into an Alexa-powered smart display when docked. In Show Mode:

- The device enters a simplified full-screen UI with large text and touch targets, similar to an Echo Show.
- Third-party apps are not directly affected unless they integrate with Alexa Smart Home or Alexa routines.
- Detect Show Mode with:

```kotlin
fun isShowMode(context: Context): Boolean {
    return Settings.Global.getInt(
        context.contentResolver,
        "show_mode_active", 0
    ) == 1
}
```

- If your app has a "kiosk" or "display" mode, consider activating it when Show Mode is detected.
- In Show Mode, the system UI is minimized. Avoid relying on the status bar or navigation bar being visible.

### Notch and Cutout Handling

Newer Fire Tablets (Fire Max 11) have a front camera cutout. Handle display cutouts using the standard Android API:

```kotlin
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
    window.attributes.layoutInDisplayCutoutMode =
        WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
}
```

Use `WindowInsets.displayCutout` in Compose to avoid placing interactive content under the cutout area.


## Amazon Services Integration

### Login with Amazon (LWA)

See `fire-tv-patterns.md` for the core LWA API. On Fire Tablets, LWA has an additional advantage: the user's Amazon account is already linked to the device, so the sign-in flow can be streamlined. The `AuthorizationManager` will use the device account if the user consents.

### Amazon Device Messaging (ADM)

See `fire-tv-patterns.md` for ADM setup. ADM works identically on Fire Tablets. The one difference: Fire Tablets are more likely to be in a low-power doze state (as personal devices, they sit idle more). Test that ADM messages wake the device and display notifications correctly when the tablet is in doze mode.

### Alexa on Tablet

Fire Tablets have built-in Alexa accessible via the home button (long press) or "Alexa" wake word (on supported models). Unlike Fire TV:

- Alexa on Fire Tablets is a general assistant, not a media-focused voice interface.
- There is no Video Skill API integration for tablets -- that is Fire TV only.
- You can use **Alexa for Apps** to handle deep links from Alexa into your app on tablets, similar to Fire TV.
- The Alexa Smart Home SDK can be used if your app controls IoT devices, but this is not tablet-specific.


## Kindle Integration

### Reading and Content Apps

If building reading or content apps, be aware of the Kindle ecosystem on Fire Tablets:

- The Kindle app is pre-installed. Users expect reading apps to behave similarly (page-turn gestures, adjustable font sizes, dark mode).
- **Whispersync**: Amazon's cross-device sync for bookmarks, highlights, and reading position. This is available only to Amazon's own Kindle app and is not exposed as a public API for third-party apps. If you need cross-device sync for your reading app, build it yourself (e.g., using AWS AppSync or a custom backend).

### Low-End Display Considerations (Fire 7)

The Fire 7's 1024x600 display at ~170 dpi is closer in pixel density to early e-readers than modern tablets:

- Text rendering at small font sizes can appear blurry. Default to larger font sizes (16sp minimum body text) and ensure users can adjust text size.
- High-frequency UI updates (animations, scrolling effects) may appear less smooth on the Fire 7's slower refresh rate. Simplify animations on this device tier.
- Use `mdpi` assets to avoid unnecessary downscaling overhead.


## Kids Edition and Amazon Kids+

### Overview

Fire Tablets are widely used as kids' devices. Amazon sells "Kids Edition" bundles and runs **Amazon Kids+** (formerly FreeTime Unlimited), a subscription service for curated kids' content.

### Parental Controls and Kid Profiles

- Fire Tablets support child profiles via **Amazon Kids** (built into the OS). When a child profile is active, the device runs in a restricted environment.
- In a kid profile, apps are subject to:
  - **No in-app purchases** -- IAP calls will fail or be blocked. Your app must handle `PurchaseResponse.RequestStatus.NOT_SUPPORTED` gracefully.
  - **No web browsing** -- WebView access may be restricted or filtered. Apps relying on WebView for core functionality should degrade gracefully.
  - **No social features** -- sharing, chat, and social login may be blocked by parental controls.
  - **Content filtering** -- only parent-approved apps appear in the child's app library.

### Detecting a Kid Profile

There is no public API to detect whether your app is running in an Amazon Kids profile. Instead, design defensively:

```kotlin
// Attempt IAP and handle restriction gracefully
PurchasingService.purchase("com.example.premium")

// In your PurchasingListener
override fun onPurchaseResponse(response: PurchaseResponse) {
    when (response.requestStatus) {
        PurchaseResponse.RequestStatus.SUCCESSFUL -> { /* deliver content */ }
        PurchaseResponse.RequestStatus.NOT_SUPPORTED -> {
            // Likely a restricted/kid profile -- hide purchase UI
            hidePurchaseOptions()
        }
        PurchaseResponse.RequestStatus.FAILED -> { /* handle error */ }
        else -> { /* handle other cases */ }
    }
}
```

### Amazon Kids+ App Integration

- If your app is part of the Amazon Kids+ catalog, Amazon handles distribution and parental consent.
- Amazon Kids+ apps must meet Amazon's content guidelines for children, including COPPA compliance.
- Test your app within a child profile to verify it functions correctly with restricted permissions.


## Ads and Lockscreen (Special Offers)

### Ad-Supported Fire Tablets

Many Fire Tablets are sold "with Special Offers" -- ad-supported models that display advertisements on the lockscreen at a reduced device price. Users can pay to remove ads.

### Implications for Your App

- **Lockscreen ads do not affect your app while it is running.** Special Offers ads only appear on the lockscreen and in the notification bar when the device is locked.
- **Your app's own ads are unaffected.** If you display ads (via Amazon Mobile Ads or a third-party SDK), they function independently of Special Offers.
- **No API to detect Special Offers vs. ad-free models.** Amazon does not expose this to third-party apps. Do not try to detect or change behavior based on the ad-supported status.

### Amazon Mobile Ads SDK

If displaying ads in your app on Fire Tablets, use the **Amazon Mobile Ads SDK** (Amazon Publisher Services) rather than Google AdMob, which depends on Google Play Services:

```groovy
implementation "com.amazon.android:aps-sdk:9.+"
```

AdMob mediation adapters exist for Amazon, so you can integrate Amazon ads as a mediation source if you also ship on Google Play.


## Testing

### ADB Connection

Fire Tablets support ADB over USB and (on some models) over Wi-Fi:

1. Enable **Developer Options**: Settings > Device Options > tap Serial Number 7 times.
2. Enable **ADB Debugging** (USB debugging).
3. Connect via USB cable.

```bash
adb devices
# Verify the Fire Tablet appears
```

For wireless ADB (Fire OS 8+):

```bash
# With tablet connected via USB first
adb tcpip 5555
adb connect <tablet-ip>:5555
```

### Emulator Availability

Amazon does not provide a dedicated Fire Tablet emulator. Use standard Android emulators configured to match Fire Tablet specs:

- Create an AVD with a custom hardware profile matching Fire Tablet resolutions (e.g., 1920x1200 for HD 10, 1024x600 for Fire 7).
- Set the density to match (189 dpi for HD 8, 224 dpi for HD 10).
- This covers layout testing but does not cover Amazon-specific APIs (IAP, ADM). For those, test on a physical device.

### Amazon App Testing Service

The **Amazon App Testing Service** (accessible from the Developer Console) runs your APK on real Fire Tablet hardware in the cloud. It performs:

- Installation and launch verification.
- Screenshot capture across device models.
- Basic crash detection and compatibility checks.

Use this before submission to catch device-specific issues without owning every Fire Tablet model.

### Testing Checklist for Fire Tablets

- [ ] App installs and launches without Google Play Services errors.
- [ ] Layout renders correctly on Fire 7 (1024x600) without clipping or overlap.
- [ ] Layout adapts properly on Fire HD 10 and Max 11 in both orientations.
- [ ] Amazon IAP flows complete (purchase, restore, subscription).
- [ ] ADM push notifications arrive, including from doze state.
- [ ] App handles restricted/kid profile gracefully (IAP blocked, WebView restricted).
- [ ] Show Mode does not break the UI on supported devices.
- [ ] Display cutout areas do not obscure interactive content (Fire Max 11).
- [ ] Performance is acceptable on Fire 7 (scrolling, transitions, memory usage).
- [ ] App passes Amazon Appstore submission checks.


## Common Pitfalls

### Fire 7 Performance

The Fire 7 is the weakest device in the lineup. Common issues:

- **Out of memory**: 2 GB total RAM, ~1-1.2 GB available to apps after system overhead. Large image caches or multiple retained Bitmaps will trigger OOM. Use `Coil` or `Glide` with strict memory cache limits.
- **Slow rendering**: The GPU is underpowered. Avoid stacked translucent layers, complex `Canvas` drawing, and blur effects. Simplify or skip animations on this tier.
- **1024x600 resolution**: This is below the `sw600dp` breakpoint commonly used for tablet layouts. Some apps treat this as a large phone rather than a small tablet. Test your `WindowSizeClass`-based layout decisions at this resolution.

### Memory Constraints

Monitor memory usage across the lineup:

```bash
adb shell dumpsys meminfo <package>
```

Set per-tier memory budgets:

| Tier | Device | App Heap Target |
|---|---|---|
| Low | Fire 7 | < 80 MB |
| Mid | Fire HD 8 | < 120 MB |
| High | Fire HD 10, Max 11 | < 200 MB |

### Missing Sensors

Fire Tablets lack several sensors common on mainstream Android tablets:

- **No GPS** (Wi-Fi-based location only via Amazon Location Service or IP geolocation).
- **No barometer, gyroscope** (Fire 7, Fire HD 8). The Fire HD 10 and Max 11 have an accelerometer but may lack a gyroscope.
- **No NFC, no IR blaster**.
- **Camera** -- front camera only on most models (no rear camera on Fire 7). Check `PackageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_FRONT)`.

Declare sensor features as optional in the manifest to avoid being filtered out on the Amazon Appstore:

```xml
<uses-feature android:name="android.hardware.sensor.gyroscope" android:required="false" />
<uses-feature android:name="android.hardware.location.gps" android:required="false" />
<uses-feature android:name="android.hardware.camera" android:required="false" />
```

### Google Play Services Feature Detection

Use the same detection pattern documented in `fire-tv-patterns.md`:

```kotlin
fun isAmazonDevice(): Boolean {
    return Build.MANUFACTURER.equals("Amazon", ignoreCase = true)
}
```

Guard all GMS-dependent code paths. Common failures on Fire Tablets:

- **Google Maps** -- use a WebView-based map (Mapbox, OpenStreetMap) or Amazon Maps API.
- **Firebase Analytics** -- use the REST-based Firebase SDK or Amazon Pinpoint.
- **FCM** -- use ADM (see `fire-tv-patterns.md`).
- **Google Play Billing** -- use Amazon IAP (see `fire-tv-patterns.md`).

### WebView Differences

Fire Tablets ship with **Amazon WebView**, which is Chromium-based but may lag behind the Chrome version on mainstream Android:

- Check `WebView.getCurrentWebViewPackage()` to determine the engine version.
- Test JavaScript-heavy web content on a physical Fire Tablet. Some modern Web APIs (WebGL 2, newer CSS features) may behave differently or be unavailable.
- Amazon WebView does not receive updates through the Play Store. Updates come through Fire OS system updates, which are less frequent.
- If your app relies on Chrome Custom Tabs, note that Fire Tablets do not have Chrome installed. The system will use the Silk browser (Amazon's default browser) or fall back to a basic WebView.

### Microphone and Alexa Conflict

Fire Tablets use the built-in microphone for Alexa. If your app needs microphone access (e.g., voice input, audio recording):

- Request `android.permission.RECORD_AUDIO` as usual.
- Be aware that Alexa's wake word detection may be listening concurrently. This can cause contention in rare cases. Test audio recording while Alexa is active.
- Users can disable the Alexa wake word, but your app should not assume this.

### Silk Browser as Default

The default browser on Fire Tablets is **Amazon Silk**, not Chrome. If your app opens URLs via `Intent.ACTION_VIEW`, they will open in Silk. Ensure any web content you link to works correctly in Silk (which is Chromium-based but may have minor rendering differences).
