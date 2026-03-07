# TV Patterns Reference (Google TV / Android TV)

>[toc]


## Compose for TV

Jetpack Compose for TV (library group `androidx.tv`) provides purpose-built composables that understand focus-driven interaction and the 10-foot UI paradigm. Target **androidx.tv:tv-material:1.0+** and **androidx.tv:tv-foundation:1.0+** with Material 3 theming.

### Core Composables
---

#### TvLazyColumn / TvLazyRow
Focus-aware replacements for standard `LazyColumn` / `LazyRow`. They handle focus restoration, scroll-to-focused-item behavior, and D-pad navigation out of the box.

```kotlin
TvLazyRow(
    pivotOffsets = PivotOffsets(parentFraction = 0.0f, childFraction = 0.0f),
    contentPadding = PaddingValues(horizontal = 48.dp),
    horizontalArrangement = Arrangement.spacedBy(16.dp)
) {
    items(catalog) { item ->
        TvCard(item)
    }
}
```

- Use `pivotOffsets` to control where the focused item aligns on screen.
- Wrap rows inside a `TvLazyColumn` to build a full browse grid.

#### ImmersiveList
Displays a large background image or video that updates as the user moves focus across a horizontal row of items.

```kotlin
ImmersiveList(
    background = { index, listHasFocus ->
        AnimatedContent(targetState = index) { idx ->
            ImmersiveListBackgroundImage(items[idx].backgroundUri)
        }
    }
) {
    TvLazyRow { items(items) { item -> FocusableCard(item) } }
}
```

- The `background` lambda receives the currently focused index and whether the list has focus, enabling animated transitions.

#### Carousel
Auto-advances through hero content; pauses on user interaction.

```kotlin
Carousel(
    itemCount = featured.size,
    autoScrollDurationMillis = 5_000L,
    modifier = Modifier
        .fillMaxWidth()
        .height(376.dp)
) { index ->
    CarouselSlide(featured[index])
}
```

- Responds to left/right D-pad for manual navigation.
- Pair with `ImmersiveList` for a full home-screen experience.

#### TvCard / WideCardContainer
Material 3 card surfaces designed for TV focus states (border glow, scaling).

```kotlin
CompactCard(
    onClick = { navigateToDetail(item) },
    image = { AsyncImage(model = item.posterUrl, contentDescription = null) },
    title = { Text(item.title) },
    modifier = Modifier.size(width = 196.dp, height = 120.dp),
    scale = CardDefaults.scale(focusedScale = 1.05f)
)
```

Card variants: `Card`, `CompactCard`, `WideCardContainer`, `ClassicCard`. Each accepts `scale`, `border`, `glow`, and `shape` customization through `CardDefaults`.


## Focus Management

TV has no touch; the focus system is the primary interaction model.

### FocusRequester
---
Programmatically request focus on a specific composable.

```kotlin
val focusRequester = remember { FocusRequester() }

Button(
    onClick = { /* ... */ },
    modifier = Modifier.focusRequester(focusRequester)
) { Text("Play") }

LaunchedEffect(Unit) {
    focusRequester.requestFocus()
}
```

### focusRestorer()
---
Remembers which child last held focus inside a `TvLazyRow` / `TvLazyColumn` so that returning to the row restores focus to the same item rather than resetting to the first.

```kotlin
TvLazyRow(
    modifier = Modifier.focusRestorer()
) {
    items(catalog) { item -> FocusableCard(item) }
}
```

- Apply `focusRestorer()` on every scrollable container to avoid disorienting jumps.
- Accepts an optional `FocusRequester` lambda for a fallback target when the previously-focused item is gone.

### D-Pad Navigation Ordering
---
Control focus traversal explicitly when the default spatial algorithm is insufficient:

```kotlin
val (left, right) = remember { FocusRequester.createRefs() }

Row {
    Button(
        modifier = Modifier
            .focusRequester(left)
            .focusProperties { this.right = right }
    ) { Text("A") }

    Button(
        modifier = Modifier
            .focusRequester(right)
            .focusProperties { this.left = left }
    ) { Text("B") }
}
```

### Focus Indication
---
Use `Modifier.onFocusChanged {}` or the built-in `IndicationNodeFactory` from `tv-material` to show visual highlights. Material 3 TV components handle this automatically through `border`, `glow`, and `scale` parameters.


## Leanback (Legacy)

The `androidx.leanback` library was the original TV UI toolkit built on Fragments and RecyclerView.

### BrowseSupportFragment
---
Provided the classic rows-of-cards TV interface with a sidebar of categories.

```kotlin
class MainFragment : BrowseSupportFragment() {
    override fun onActivityCreated(savedInstanceState: Bundle?) {
        super.onActivityCreated(savedInstanceState)
        title = "My TV App"
        adapter = ArrayObjectAdapter(ListRowPresenter()).apply {
            add(ListRow(HeaderItem("Action"), actionAdapter))
            add(ListRow(HeaderItem("Comedy"), comedyAdapter))
        }
    }
}
```

### Migration to Compose for TV
---
Leanback is in maintenance mode. Migration path:

| Leanback Component | Compose for TV Replacement |
|---|---|
| `BrowseSupportFragment` | `TvLazyColumn` + `TvLazyRow` with `ImmersiveList` |
| `DetailsSupportFragment` | Custom Compose detail screen |
| `SearchSupportFragment` | Custom search with `TextField` + results list |
| `PlaybackSupportFragment` | Media3 `PlayerView` + custom Compose overlay |
| `GuidedStepSupportFragment` | Compose dialogs / step-by-step UI |
| `ListRow` / `Presenter` | `TvLazyRow` + card composables |

Migration tips:
- Migrate screen-by-screen; Leanback fragments and Compose screens can coexist via `NavHostFragment` + Compose destinations.
- Replace `Presenter` / `ObjectAdapter` patterns with standard Compose state and `items()` lambdas.
- Remove the `leanback` dependency only after all fragments are migrated.


## Remote / D-Pad Navigation

### D-Pad Events
---
Intercept hardware key events with `Modifier.onKeyEvent` or `Modifier.onPreviewKeyEvent`:

```kotlin
Modifier.onKeyEvent { event ->
    when {
        event.key == Key.DirectionCenter && event.type == KeyEventType.KeyUp -> {
            onSelect()
            true
        }
        event.key == Key.DirectionRight && event.type == KeyEventType.KeyDown -> {
            onMoveRight()
            true
        }
        else -> false
    }
}
```

### KeyEvent Constants
---
| Remote Button | `Key` constant |
|---|---|
| D-Pad Up | `Key.DirectionUp` |
| D-Pad Down | `Key.DirectionDown` |
| D-Pad Left | `Key.DirectionLeft` |
| D-Pad Right | `Key.DirectionRight` |
| D-Pad Center / Select | `Key.DirectionCenter` |
| Back | `Key.Back` |
| Media Play/Pause | `Key.MediaPlayPause` |
| Media Rewind | `Key.MediaRewind` |
| Media Fast Forward | `Key.MediaFastForward` |

### Back Button Handling
---
Use `BackHandler` from `androidx.activity.compose`:

```kotlin
BackHandler(enabled = isOverlayVisible) {
    dismissOverlay()
}
```

- Do not intercept `Back` on top-level destinations; the system should exit the app.
- Inside detail/player screens, use `BackHandler` to return to browse.
- The system enforces that users can always exit; apps that block `Back` indefinitely are rejected in review.


## Media Playback

### Media3 / ExoPlayer
---
`androidx.media3` (the successor to standalone ExoPlayer) is the recommended playback stack.

```kotlin
@Composable
fun VideoPlayer(mediaItem: MediaItem) {
    val context = LocalContext.current
    val player = remember {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(mediaItem)
            prepare()
        }
    }

    DisposableEffect(Unit) {
        onDispose { player.release() }
    }

    AndroidView(
        factory = { ctx -> PlayerView(ctx).apply { this.player = player } },
        modifier = Modifier.fillMaxSize()
    )
}
```

### MediaSession
---
Required for media key routing and system integration (Now Playing card, Google Assistant "pause" commands).

```kotlin
class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val player = ExoPlayer.Builder(this).build()
        mediaSession = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo) = mediaSession

    override fun onDestroy() {
        mediaSession?.run { player.release(); release() }
        super.onDestroy()
    }
}
```

### Background Playback
---
- Use `MediaSessionService` so playback continues when the user presses Home.
- Bind a foreground notification for audio-only playback.
- For video, pause when the app loses focus unless PiP is active.

### Picture-in-Picture (PiP)
---
```kotlin
// In Activity
override fun onUserLeaveHint() {
    if (isPlaying) {
        enterPictureInPictureMode(
            PictureInPictureParams.Builder()
                .setAspectRatio(Rational(16, 9))
                .setAutoEnterEnabled(true)   // API 31+
                .build()
        )
    }
}
```

- Declare `android:supportsPictureInPicture="true"` and `android:configChanges="screenSize|smallestScreenSize|screenLayout|orientation"` on the Activity.
- On API 31+ (Android 12), use `setAutoEnterEnabled(true)` for seamless PiP on Home press.
- Hide non-essential UI in `onPictureInPictureModeChanged`.


## Layout for TV

### 1080p Baseline
---
- Design at **1920 x 1080 dp**. Most TV apps render at 1080p; the system scales to 4K displays.
- Use `dp` consistently. Avoid `px`.
- Minimum touch-target equivalent for focus: **48 dp** (but prefer larger cards for readability at 10 feet).

### Overscan / Safe Area
---
Legacy TVs may crop edges. Apply padding to keep content within safe bounds:

```kotlin
Modifier.padding(
    horizontal = 48.dp,   // 5% of 960
    vertical = 27.dp      // 5% of 540
)
```

Modern Google TV devices do not overscan, but the 48 dp horizontal margin remains a best practice for visual comfort.

### Focus Scaling
---
Material 3 TV cards scale up on focus (typically 1.05x-1.1x). Reserve space so that scaled cards do not clip:

```kotlin
CompactCard(
    scale = CardDefaults.scale(focusedScale = 1.05f),
    modifier = Modifier.padding(8.dp)   // breathing room for scale
)
```

### 10-Foot UI Guidelines
---
- **Typography**: minimum body text size ~14 sp; titles 20-24 sp; headlines 32+ sp.
- **Contrast**: WCAG AA minimum; prefer higher contrast given variable TV calibration.
- **Color**: avoid pure white backgrounds (harsh on large screens). Use dark themes by default.
- **Animation**: keep transitions smooth (60 fps) and purposeful. Avoid rapid or small animations that are invisible at distance.
- **Information density**: fewer items visible at once compared to mobile; prioritize hero content and linear browsing.


## Content Discovery

### Google TV Home Channels
---
Apps can publish rows of content to the Google TV home screen via the `TvProvider` API (`android.media.tv`).

```kotlin
val channelUri = context.contentResolver.insert(
    TvContractCompat.Channels.CONTENT_URI,
    ContentValues().apply {
        put(TvContractCompat.Channels.COLUMN_DISPLAY_NAME, "Trending")
        put(TvContractCompat.Channels.COLUMN_APP_LINK_INTENT_URI, deepLinkUri)
        put(TvContractCompat.Channels.COLUMN_TYPE, TvContractCompat.Channels.TYPE_PREVIEW)
    }
)
```

- Channels must be approved by the user (system shows an "Add to home" prompt).
- Keep channel content fresh; stale rows are deprioritized.

### Watch Next
---
Add programs to the system "Continue Watching" row:

```kotlin
val values = ContentValues().apply {
    put(TvContractCompat.WatchNextPrograms.COLUMN_TITLE, "Episode 5")
    put(TvContractCompat.WatchNextPrograms.COLUMN_WATCH_NEXT_TYPE,
        TvContractCompat.WatchNextPrograms.WATCH_NEXT_TYPE_CONTINUE)
    put(TvContractCompat.WatchNextPrograms.COLUMN_LAST_PLAYBACK_POSITION_MILLIS, positionMs)
    put(TvContractCompat.WatchNextPrograms.COLUMN_DURATION_MILLIS, durationMs)
    put(TvContractCompat.WatchNextPrograms.COLUMN_INTENT_URI, deepLinkUri)
}
context.contentResolver.insert(
    TvContractCompat.WatchNextPrograms.CONTENT_URI, values
)
```

Watch Next types: `WATCH_NEXT_TYPE_CONTINUE`, `WATCH_NEXT_TYPE_NEXT`, `WATCH_NEXT_TYPE_NEW`, `WATCH_NEXT_TYPE_WATCHLIST`.

### Recommendations
---
- The legacy `NotificationCompat` recommendation API is deprecated.
- Use **Engage SDK** (`com.google.android.engage`) for richer content clusters that surface across Google TV surfaces including Search, "For You", and entity pages.


## Search

### Voice Search Integration
---
Handle the system-level voice search intent:

```xml
<activity android:name=".SearchActivity">
    <intent-filter>
        <action android:name="android.intent.action.SEARCH" />
    </intent-filter>
    <meta-data
        android:name="android.app.searchable"
        android:resource="@xml/searchable" />
</activity>
```

Extract the query in the Activity:

```kotlin
val query = intent.getStringExtra(SearchManager.QUERY)
```

For deeper Google TV integration, provide a content provider that returns results matching `SearchManager` columns so the system can display your content inline in global search results.

### In-App Search with Suggestions
---
```kotlin
@Composable
fun TvSearchScreen(viewModel: SearchViewModel) {
    var query by remember { mutableStateOf("") }
    val suggestions by viewModel.suggestions.collectAsStateWithLifecycle()

    Column(modifier = Modifier.padding(48.dp)) {
        TextField(
            value = query,
            onValueChange = {
                query = it
                viewModel.onQueryChanged(it)
            },
            placeholder = { Text("Search movies, shows...") }
        )

        TvLazyColumn {
            items(suggestions) { suggestion ->
                ListItem(
                    selected = false,
                    onClick = { viewModel.select(suggestion) }
                ) { Text(suggestion.title) }
            }
        }
    }
}
```

- Prefer voice-initiated search on TV; typing with a remote is slow.
- Debounce search queries (300-500 ms) to reduce network calls.


## Input Methods

### Limited Text Input
---
On-screen keyboards with D-pad are cumbersome. Minimize text entry:

- Pre-populate fields where possible.
- Offer selection lists instead of free-text fields.
- Support the **companion app** or **phone remote** keyboard for unavoidable text entry.

### Voice Input
---
Trigger the system speech recognizer:

```kotlin
val speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
}
speechLauncher.launch(speechIntent)
```

- Always provide a D-pad fallback; not all remotes have a microphone.
- Show a microphone icon near search fields to indicate voice availability.

### QR Code Pairing / Second-Screen Sign-In
---
Avoid forcing users to type credentials on TV. Use device-code or QR-code flows:

1. App displays a short URL and a user code (or a QR code).
2. User scans on their phone and completes OAuth on mobile.
3. TV app polls or listens via WebSocket for the auth token.

Google Identity Services supports the **OAuth 2.0 Device Authorization Grant** (RFC 8628), which is the recommended pattern for TV sign-in.

```kotlin
// Pseudocode: device code flow
val deviceCodeResponse = authClient.requestDeviceCode(clientId, scopes)
showQrCode(deviceCodeResponse.verificationUri)
showUserCode(deviceCodeResponse.userCode)

// Poll for token
val tokenResponse = authClient.pollForToken(
    deviceCode = deviceCodeResponse.deviceCode,
    interval = deviceCodeResponse.interval
)
```


## Google TV vs Android TV

### Overview
---
| Aspect | Android TV (AOSP) | Google TV |
|---|---|---|
| **Base OS** | Android (TV profile) | Android TV + Google TV UI layer |
| **Launcher** | OEM or basic Android TV home | Google TV home with personalized recommendations |
| **Content Discovery** | Basic channel rows | AI-driven "For You", "Live", "Library" tabs |
| **Minimum API** | API 21 (Lollipop) | API 31+ on newer devices; varies by OEM |
| **Play Store** | Google Play for TV | Google Play for TV (same store) |
| **Assistant** | Google Assistant built-in | Google Assistant with deeper media integration |
| **Engage SDK** | Not available | Available for richer content surfacing |

### Key Differences
---
- **Google TV is a superset**: every Google TV device is an Android TV device, but not vice versa. Apps targeting `android.software.leanback` run on both.
- **Discovery surface**: Google TV prioritizes Engage SDK clusters and Watch Next for home-screen placement. Android TV (non-Google TV) relies on the legacy channel API.
- **Profile & personalization**: Google TV supports multiple user profiles and personalized recommendations.
- **Cast built-in**: Google TV devices include Chromecast built-in; consider supporting `CastReceiverContext` for cast-to-TV flows.

### Requirements for Google TV
---
- Declare `android.software.leanback` as a **used** feature (not required, to allow mobile+TV builds):
  ```xml
  <uses-feature android:name="android.software.leanback" android:required="false" />
  ```
- Declare that touch is **not** required:
  ```xml
  <uses-feature android:name="android.hardware.touchscreen" android:required="false" />
  ```
- Provide a **leanback launcher** banner (320 x 180 dp) for the app icon on the TV home screen.
- Meet **TV app quality guidelines**: no touch-dependent flows, all UI navigable by D-pad, no portrait-only layouts.
- For Google TV-specific features (Engage SDK, Watch Next), follow the [Engage SDK integration guide](https://developer.android.com/training/tv/discovery/engage).

### Build Configuration
---
```kotlin
// build.gradle.kts
android {
    defaultConfig {
        minSdk = 21           // broadest Android TV reach
        targetSdk = 35        // latest stable
    }
}

dependencies {
    // Compose for TV (Material 3)
    implementation("androidx.tv:tv-foundation:1.0.0")
    implementation("androidx.tv:tv-material:1.0.0")

    // Media3
    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-session:1.5.1")
    implementation("androidx.media3:media3-ui:1.5.1")

    // Engage SDK (Google TV discovery)
    implementation("com.google.android.engage:engage-core:1.5.5")

    // TV Provider (channels / Watch Next)
    implementation("androidx.tvprovider:tvprovider:1.0.0")
}
```
