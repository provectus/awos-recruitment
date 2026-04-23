# Media Playback Reference (Media3 / ExoPlayer)

Comprehensive guide to media playback on Android. Covers ExoPlayer (via `androidx.media3`), MediaSession integration, audio focus, Picture-in-Picture, offline downloads, and performance. For platform-specific playback patterns see `tv-patterns.md`, `android-auto-patterns.md`, and `android-automotive-patterns.md`.

## Architecture Overview

| Layer | Library | Purpose |
|---|---|---|
| **UI** | `media3-ui` | `PlayerView`, `PlayerControlView` — standard transport controls, subtitles overlay |
| **UI (Compose)** | `media3-ui-compose` | Experimental Compose player components |
| **Playback** | `media3-exoplayer` | `ExoPlayer` — playback engine, adaptive streaming, codec selection |
| **Session** | `media3-session` | `MediaSession`, `MediaSessionService`, `MediaController` — system integration, remote control |
| **Common** | `media3-common` | `MediaItem`, `Player` interface, `Timeline`, `Tracks` — shared data types |
| **Data Sources** | `media3-datasource` | `DataSource`, `HttpDataSource`, `CacheDataSource` — network and cache I/O |
| **Extractors** | `media3-extractor` | Container parsers for MP4, MKV, FLV, Ogg, WAV, etc. |
| **DASH / HLS / RTSP** | `media3-dash`, `media3-hls`, `media3-exoplayer-rtsp` | Adaptive streaming protocol support |
| **Transformer** | `media3-transformer` | Media editing — trim, transcode, mux, apply effects |

**Rule:** Use `media3-ui` `PlayerView` for standard playback. Build custom Compose UI on top of the `Player` interface only when `PlayerView` doesn't fit your design.


## Gradle Setup

```kotlin
// version catalog (libs.versions.toml)
[versions]
media3 = "<latest>"

[libraries]
media3-exoplayer = { module = "androidx.media3:media3-exoplayer", version.ref = "media3" }
media3-ui = { module = "androidx.media3:media3-ui", version.ref = "media3" }
media3-session = { module = "androidx.media3:media3-session", version.ref = "media3" }
media3-common = { module = "androidx.media3:media3-common", version.ref = "media3" }
media3-hls = { module = "androidx.media3:media3-hls", version.ref = "media3" }
media3-dash = { module = "androidx.media3:media3-dash", version.ref = "media3" }
media3-datasource = { module = "androidx.media3:media3-datasource", version.ref = "media3" }
```

```kotlin
// build.gradle.kts (app module)
dependencies {
    implementation(libs.media3.exoplayer)
    implementation(libs.media3.ui)
    implementation(libs.media3.session)
    implementation(libs.media3.common)
    // Add as needed:
    implementation(libs.media3.hls)       // HLS support
    implementation(libs.media3.dash)      // DASH support
}
```


## ExoPlayer — Playback Engine

### Creating a Player
---

```kotlin
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.common.MediaItem

// Basic
val player = ExoPlayer.Builder(context).build()

// With custom configuration
val player = ExoPlayer.Builder(context)
    .setAudioAttributes(AudioAttributes.DEFAULT, /* handleAudioFocus = */ true)
    .setHandleAudioBecomingNoisy(true)  // Pause on headphone disconnect
    .setWakeMode(C.WAKE_MODE_NETWORK)  // Keep CPU/Wi-Fi for streaming
    .build()
```

### Setting Media
---

```kotlin
// Single item
val mediaItem = MediaItem.fromUri("https://example.com/video.m3u8")
player.setMediaItem(mediaItem)
player.prepare()
player.play()

// With metadata
val mediaItem = MediaItem.Builder()
    .setUri("https://example.com/video.m3u8")
    .setMediaId("episode-42")
    .setMediaMetadata(
        MediaMetadata.Builder()
            .setTitle("Episode Title")
            .setArtist("Show Name")
            .setArtworkUri(Uri.parse("https://example.com/poster.jpg"))
            .build()
    )
    .build()

// Playlist
val items = listOf(mediaItem1, mediaItem2, mediaItem3)
player.setMediaItems(items)
player.prepare()
player.play()
```

### Transport Controls
---

```kotlin
player.play()
player.pause()
player.setPlaybackSpeed(2.0f)

// Seek to position (milliseconds)
player.seekTo(30_000L)

// Seek to specific item in playlist
player.seekTo(/* mediaItemIndex = */ 2, /* positionMs = */ 0L)

// Next / previous
player.seekToNextMediaItem()
player.seekToPreviousMediaItem()

// Repeat modes
player.repeatMode = Player.REPEAT_MODE_OFF
player.repeatMode = Player.REPEAT_MODE_ONE
player.repeatMode = Player.REPEAT_MODE_ALL

// Shuffle
player.shuffleModeEnabled = true
```

### Observing Playback State
---

```kotlin
player.addListener(object : Player.Listener {
    override fun onPlaybackStateChanged(playbackState: Int) {
        when (playbackState) {
            Player.STATE_IDLE -> { /* Player created but not prepared */ }
            Player.STATE_BUFFERING -> { /* Buffering — show spinner */ }
            Player.STATE_READY -> { /* Ready to play */ }
            Player.STATE_ENDED -> { /* Playback ended — show replay UI */ }
        }
    }

    override fun onIsPlayingChanged(isPlaying: Boolean) {
        // True only when actually rendering frames/audio
        // Most reliable for updating play/pause UI
    }

    override fun onPlayerError(error: PlaybackException) {
        when (error.errorCode) {
            PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED ->
                showRetryUI("Network error")
            PlaybackException.ERROR_CODE_DECODER_INIT_FAILED ->
                showError("Codec not supported")
            else ->
                showError("Playback error: ${error.message}")
        }
    }

    override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
        // Playlist item changed — update UI, analytics
    }
})
```

### Progress Tracking
---

Poll `player.currentPosition` on a UI update loop — ExoPlayer does not push periodic time updates:

```kotlin
// In a ViewModel or Compose state holder
private fun startProgressUpdates() {
    viewModelScope.launch {
        while (isActive) {
            val position = player.currentPosition
            val duration = player.duration
            val buffered = player.bufferedPosition
            updateProgressUI(position, duration, buffered)
            delay(500L)
        }
    }
}
```

In Compose, use `LaunchedEffect`:

```kotlin
@Composable
fun ProgressBar(player: Player) {
    var progress by remember { mutableFloatStateOf(0f) }

    LaunchedEffect(player) {
        while (isActive) {
            val duration = player.duration.takeIf { it > 0 } ?: 1L
            progress = player.currentPosition.toFloat() / duration
            delay(500L)
        }
    }

    LinearProgressIndicator(progress = { progress })
}
```


## PlayerView — Standard UI

### XML Layout
---

```xml
<androidx.media3.ui.PlayerView
    android:id="@+id/player_view"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    app:show_buffering="when_playing"
    app:use_controller="true"
    app:resize_mode="fit" />
```

```kotlin
val playerView = findViewById<PlayerView>(R.id.player_view)
playerView.player = player
```

### In Jetpack Compose
---

```kotlin
@Composable
fun VideoPlayer(mediaItem: MediaItem) {
    val context = LocalContext.current
    val player = remember {
        ExoPlayer.Builder(context)
            .setAudioAttributes(AudioAttributes.DEFAULT, true)
            .build()
            .apply {
                setMediaItem(mediaItem)
                prepare()
            }
    }

    DisposableEffect(Unit) {
        onDispose { player.release() }
    }

    AndroidView(
        factory = { ctx ->
            PlayerView(ctx).apply {
                this.player = player
                useController = true
            }
        },
        modifier = Modifier.fillMaxWidth().aspectRatio(16f / 9f)
    )
}
```

### Lifecycle Integration
---

Pause on background, resume on foreground:

```kotlin
@Composable
fun LifecycleAwarePlayer(player: Player) {
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_PAUSE -> player.pause()
                Lifecycle.Event.ON_RESUME -> player.play()
                Lifecycle.Event.ON_DESTROY -> player.release()
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
}
```

### Resize Modes

| Mode | Behavior |
|---|---|
| `AspectRatioFrameLayout.RESIZE_MODE_FIT` | Fit within bounds, letterbox |
| `AspectRatioFrameLayout.RESIZE_MODE_FIXED_WIDTH` | Fixed width, adjust height |
| `AspectRatioFrameLayout.RESIZE_MODE_FIXED_HEIGHT` | Fixed height, adjust width |
| `AspectRatioFrameLayout.RESIZE_MODE_FILL` | Fill bounds, crop |
| `AspectRatioFrameLayout.RESIZE_MODE_ZOOM` | Fill bounds, center crop |


## MediaSession — System Integration
---

Required for lock screen controls, Bluetooth media buttons, Google Assistant voice commands, and Wear OS remote control.

### MediaSessionService
---

Use `MediaSessionService` for media apps that should continue playback in the background.

```kotlin
class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(AudioAttributes.DEFAULT, true)
            .setHandleAudioBecomingNoisy(true)
            .build()
        mediaSession = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? =
        mediaSession

    override fun onDestroy() {
        mediaSession?.run {
            player.release()
            release()
        }
        super.onDestroy()
    }
}
```

#### Manifest Declaration

```xml
<service
    android:name=".PlaybackService"
    android:foregroundServiceType="mediaPlayback"
    android:exported="true">
    <intent-filter>
        <action android:name="androidx.media3.session.MediaSessionService" />
    </intent-filter>
</service>
```

Also add the foreground service permission:

```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />
```

### MediaController (Client Side)
---

Connect to the playback service from your UI (Activity/Fragment/Compose):

```kotlin
class PlayerViewModel(application: Application) : AndroidViewModel(application) {
    private var controllerFuture: ListenableFuture<MediaController>? = null
    var controller: MediaController? = null
        private set

    fun connect() {
        val sessionToken = SessionToken(
            getApplication(),
            ComponentName(getApplication(), PlaybackService::class.java)
        )
        controllerFuture = MediaController.Builder(getApplication(), sessionToken).buildAsync().also {
            it.addListener(
                { controller = it.get() },
                MoreExecutors.directExecutor()
            )
        }
    }

    fun disconnect() {
        controllerFuture?.let { MediaController.releaseFuture(it) }
    }

    override fun onCleared() {
        disconnect()
    }
}
```

`MediaController` implements the `Player` interface — you can pass it directly to `PlayerView` or any composable that accepts `Player`.

### Custom Commands
---

```kotlin
// Define in shared code
val COMMAND_LIKE = SessionCommand("com.example.LIKE", Bundle.EMPTY)

// Service side: accept custom commands
MediaSession.Builder(this, player)
    .setCallback(object : MediaSession.Callback {
        override fun onConnect(
            session: MediaSession,
            controller: MediaSession.ControllerInfo
        ): MediaSession.ConnectionResult {
            return MediaSession.ConnectionResult.AcceptedResultBuilder(session)
                .setAvailableSessionCommands(
                    SessionCommands.Builder()
                        .add(COMMAND_LIKE)
                        .addSessionCommand(MediaSession.ConnectionResult.DEFAULT_SESSION_COMMANDS)
                        .build()
                )
                .build()
        }

        override fun onCustomCommand(
            session: MediaSession,
            controller: MediaSession.ControllerInfo,
            customCommand: SessionCommand,
            args: Bundle
        ): ListenableFuture<SessionResult> {
            if (customCommand == COMMAND_LIKE) {
                likeCurrentTrack()
                return Futures.immediateFuture(SessionResult(SessionResult.RESULT_SUCCESS))
            }
            return super.onCustomCommand(session, controller, customCommand, args)
        }
    })
    .build()

// Client side: send custom command
controller.sendCustomCommand(COMMAND_LIKE, Bundle.EMPTY)
```


## Audio Focus & Audio Becoming Noisy
---

### Automatic Audio Focus

ExoPlayer handles audio focus automatically when configured:

```kotlin
val player = ExoPlayer.Builder(context)
    .setAudioAttributes(AudioAttributes.DEFAULT, /* handleAudioFocus = */ true)
    .build()
```

With `handleAudioFocus = true`, ExoPlayer will:
- Request focus on `play()`
- Pause on transient focus loss (phone call)
- Duck volume on transient-may-duck focus loss (navigation prompt)
- Resume after transient focus loss ends
- Stop on permanent focus loss

### Audio Becoming Noisy (Headphone Disconnect)

```kotlin
val player = ExoPlayer.Builder(context)
    .setHandleAudioBecomingNoisy(true)
    .build()
```

Pauses automatically when headphones are disconnected or Bluetooth audio route is lost.

### AudioAttributes

```kotlin
// Video playback
val videoAttributes = AudioAttributes.Builder()
    .setUsage(C.USAGE_MEDIA)
    .setContentType(C.AUDIO_CONTENT_TYPE_MOVIE)
    .build()

// Music playback
val musicAttributes = AudioAttributes.Builder()
    .setUsage(C.USAGE_MEDIA)
    .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
    .build()

// Podcast / spoken content
val spokenAttributes = AudioAttributes.Builder()
    .setUsage(C.USAGE_MEDIA)
    .setContentType(C.AUDIO_CONTENT_TYPE_SPEECH)
    .setAllowedCapturePolicy(C.ALLOW_CAPTURE_BY_NONE) // DRM-protected
    .build()

player.setAudioAttributes(videoAttributes, /* handleAudioFocus = */ true)
```


## Picture-in-Picture (PiP)
---

### Activity Configuration

```xml
<activity
    android:name=".PlayerActivity"
    android:supportsPictureInPicture="true"
    android:configChanges="screenSize|smallestScreenSize|screenLayout|orientation"
    android:launchMode="singleTask" />
```

### Entering PiP

```kotlin
// API 31+ (Android 12): auto-enter on user leave
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        setPictureInPictureParams(
            PictureInPictureParams.Builder()
                .setAspectRatio(Rational(16, 9))
                .setAutoEnterEnabled(true)
                .build()
        )
    }
}

// Pre-API 31: manual entry
override fun onUserLeaveHint() {
    if (isPlaying) {
        enterPictureInPictureMode(
            PictureInPictureParams.Builder()
                .setAspectRatio(Rational(16, 9))
                .build()
        )
    }
}
```

### Custom PiP Actions

```kotlin
private fun updatePipActions(isPlaying: Boolean) {
    val action = if (isPlaying) {
        RemoteAction(
            Icon.createWithResource(this, R.drawable.ic_pause),
            "Pause", "Pause playback",
            PendingIntent.getBroadcast(
                this, 0,
                Intent("com.example.PAUSE"),
                PendingIntent.FLAG_IMMUTABLE
            )
        )
    } else {
        RemoteAction(
            Icon.createWithResource(this, R.drawable.ic_play),
            "Play", "Resume playback",
            PendingIntent.getBroadcast(
                this, 0,
                Intent("com.example.PLAY"),
                PendingIntent.FLAG_IMMUTABLE
            )
        )
    }

    setPictureInPictureParams(
        PictureInPictureParams.Builder()
            .setAspectRatio(Rational(16, 9))
            .setActions(listOf(action))
            .build()
    )
}
```

### Handling PiP Mode Changes

```kotlin
override fun onPictureInPictureModeChanged(isInPiP: Boolean, newConfig: Configuration) {
    if (isInPiP) {
        // Hide non-essential UI (buttons, info overlays)
        playerView.useController = false
    } else {
        // Restore full UI
        playerView.useController = true
    }
}
```

### PiP in Compose

```kotlin
@Composable
fun PipAwarePlayer(player: Player) {
    val context = LocalContext.current
    val activity = context.findActivity()
    val isInPipMode = rememberIsInPipMode()

    AndroidView(
        factory = { ctx ->
            PlayerView(ctx).apply {
                this.player = player
            }
        },
        update = { view ->
            view.useController = !isInPipMode
        }
    )
}

@Composable
fun rememberIsInPipMode(): Boolean {
    val activity = LocalContext.current.findActivity()
    var isInPipMode by remember { mutableStateOf(activity.isInPictureInPictureMode) }

    DisposableEffect(activity) {
        val callback = object : ComponentCallbacks2 {
            override fun onConfigurationChanged(newConfig: Configuration) {
                isInPipMode = activity.isInPictureInPictureMode
            }
            override fun onLowMemory() {}
            override fun onTrimMemory(level: Int) {}
        }
        activity.registerComponentCallbacks(callback)
        onDispose { activity.unregisterComponentCallbacks(callback) }
    }
    return isInPipMode
}
```


## Track Selection (Subtitles & Audio Tracks)
---

### Discovering Available Tracks

```kotlin
player.addListener(object : Player.Listener {
    override fun onTracksChanged(tracks: Tracks) {
        for (group in tracks.groups) {
            val trackType = group.type // C.TRACK_TYPE_VIDEO, C.TRACK_TYPE_AUDIO, C.TRACK_TYPE_TEXT
            for (i in 0 until group.length) {
                val format = group.getTrackFormat(i)
                val isSupported = group.isTrackSupported(i)
                val isSelected = group.isTrackSelected(i)
                Log.d("Tracks", "Type=$trackType lang=${format.language} " +
                    "label=${format.label} supported=$isSupported selected=$isSelected")
            }
        }
    }
})
```

### Setting Track Preferences

```kotlin
// Prefer French audio, English subtitles
player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
    .setPreferredAudioLanguage("fr")
    .setPreferredTextLanguage("en")
    .build()

// Force specific subtitle track
player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
    .setOverrideForType(
        TrackSelectionOverride(textTrackGroup.mediaTrackGroup, /* trackIndex = */ 0)
    )
    .build()

// Disable subtitles
player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
    .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true)
    .build()

// Limit video resolution (save bandwidth)
player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
    .setMaxVideoSize(1920, 1080)
    .setMaxVideoBitrate(5_000_000)
    .build()
```


## Offline Downloads
---

Download adaptive streams (HLS/DASH) for offline playback using Media3's download infrastructure.

### Download Setup

```kotlin
// Singleton — typically in Application or DI module
val downloadCache = SimpleCache(
    File(context.cacheDir, "media-downloads"),
    NoOpCacheEvictor(), // No eviction for offline downloads
    StandaloneDatabaseProvider(context)
)

val dataSourceFactory = DefaultHttpDataSource.Factory()

val downloadManager = DownloadManager(
    context,
    StandaloneDatabaseProvider(context),
    downloadCache,
    dataSourceFactory,
    Executors.newFixedThreadPool(4)
)

// Start the download service
val downloadNotificationHelper = DownloadNotificationHelper(context, CHANNEL_ID)
```

### DownloadService

```kotlin
class MediaDownloadService : DownloadService(
    FOREGROUND_NOTIFICATION_ID,
    DEFAULT_FOREGROUND_NOTIFICATION_UPDATE_INTERVAL,
    CHANNEL_ID,
    R.string.download_channel_name,
    R.string.download_channel_description
) {
    override fun getDownloadManager(): DownloadManager = appDownloadManager

    override fun getForegroundNotification(
        downloads: MutableList<Download>,
        notMetRequirements: Int
    ): Notification =
        downloadNotificationHelper.buildProgressNotification(
            this, R.drawable.ic_download, null, null, downloads, notMetRequirements
        )
}
```

### Starting a Download

```kotlin
// HLS
val downloadRequest = DownloadRequest.Builder(
    /* id = */ "episode-42",
    Uri.parse("https://example.com/video.m3u8")
).build()

DownloadService.sendAddDownload(
    context,
    MediaDownloadService::class.java,
    downloadRequest,
    /* foreground = */ false
)

// With specific track selection (audio language, subtitle)
val helper = DownloadHelper.forMediaItem(
    context,
    MediaItem.fromUri("https://example.com/video.m3u8"),
    DefaultRenderersFactory(context),
    dataSourceFactory
)
helper.prepare(object : DownloadHelper.Callback {
    override fun onPrepared(helper: DownloadHelper) {
        // Select specific tracks for download
        val parameters = DefaultTrackSelector.Parameters.Builder(context)
            .setPreferredAudioLanguage("en")
            .setPreferredTextLanguage("en")
            .build()
        for (i in 0 until helper.periodCount) {
            helper.clearTrackSelections(i)
            helper.addTrackSelection(i, parameters)
        }
        val request = helper.getDownloadRequest("episode-42", null)
        DownloadService.sendAddDownload(context, MediaDownloadService::class.java, request, false)
    }

    override fun onPrepareError(helper: DownloadHelper, e: IOException) {
        Log.e("Download", "Prepare failed", e)
    }
})
```

### Playing Downloaded Content

```kotlin
// Create a CacheDataSource that reads from the download cache
val cacheDataSourceFactory = CacheDataSource.Factory()
    .setCache(downloadCache)
    .setUpstreamDataSourceFactory(DefaultHttpDataSource.Factory())

val player = ExoPlayer.Builder(context)
    .setMediaSourceFactory(
        DefaultMediaSourceFactory(cacheDataSourceFactory)
    )
    .build()

// Play the same URI — ExoPlayer will read from cache
player.setMediaItem(MediaItem.fromUri("https://example.com/video.m3u8"))
player.prepare()
player.play()
```

### Monitoring Download Progress

```kotlin
downloadManager.addListener(object : DownloadManager.Listener {
    override fun onDownloadChanged(
        downloadManager: DownloadManager,
        download: Download,
        finalException: Exception?
    ) {
        when (download.state) {
            Download.STATE_DOWNLOADING -> {
                val percent = download.percentDownloaded
                updateUI(percent)
            }
            Download.STATE_COMPLETED -> showCompleted()
            Download.STATE_FAILED -> showError(finalException)
            Download.STATE_REMOVING -> { /* cleanup in progress */ }
            else -> {}
        }
    }
})
```


## DRM (Widevine)
---

```kotlin
val drmItem = MediaItem.Builder()
    .setUri("https://example.com/protected.mpd")
    .setDrmConfiguration(
        MediaItem.DrmConfiguration.Builder(C.WIDEVINE_UUID)
            .setLicenseUri("https://license.example.com/widevine")
            .setLicenseRequestHeaders(mapOf("Authorization" to "Bearer token"))
            .setMultiSession(false)
            .build()
    )
    .build()

player.setMediaItem(drmItem)
player.prepare()
```

For offline DRM, download the license alongside the content:

```kotlin
val drmItem = MediaItem.Builder()
    .setUri(contentUri)
    .setDrmConfiguration(
        MediaItem.DrmConfiguration.Builder(C.WIDEVINE_UUID)
            .setLicenseUri(licenseUri)
            .setKeySetId(offlineKeySetId) // Retrieved during license download
            .build()
    )
    .build()
```


## Notifications & Now Playing
---

`MediaSessionService` handles the media notification automatically when a `MediaSession` is active. Media3 creates a notification with transport controls, artwork, and metadata.

### Customizing the Notification

```kotlin
class PlaybackService : MediaSessionService() {
    override fun onCreate() {
        super.onCreate()
        val player = ExoPlayer.Builder(this).build()
        val mediaSession = MediaSession.Builder(this, player).build()

        // Customize notification
        setMediaNotificationProvider(
            DefaultMediaNotificationProvider.Builder(this)
                .setChannelId("playback")
                .setChannelName(R.string.playback_channel)
                .setNotificationId(1001)
                .build()
        )
    }
}
```

### Now Playing Metadata

Set metadata on `MediaItem` — the session propagates it to notifications, lock screen, Bluetooth AVRCP:

```kotlin
val item = MediaItem.Builder()
    .setUri(uri)
    .setMediaMetadata(
        MediaMetadata.Builder()
            .setTitle("Track Title")
            .setArtist("Artist Name")
            .setAlbumTitle("Album Name")
            .setArtworkUri(artworkUri)
            .setTrackNumber(3)
            .setTotalTrackCount(12)
            .build()
    )
    .build()
```


## Streaming Formats
---

| Format | Module | Use Case |
|---|---|---|
| **HLS** | `media3-hls` | Default for most streaming (Apple-origin, wide CDN support) |
| **DASH** | `media3-dash` | Google/YouTube-origin, better multi-period ad insertion |
| **RTSP** | `media3-exoplayer-rtsp` | IP cameras, live surveillance |
| **SmoothStreaming** | `media3-exoplayer` (built-in) | Legacy Microsoft streaming |
| **Progressive** | `media3-exoplayer` (built-in) | MP4, MP3, WebM, Ogg direct files |

ExoPlayer auto-detects the format from the URI or content type. Override when needed:

```kotlin
// Force HLS for ambiguous URI
val hlsItem = MediaItem.Builder()
    .setUri("https://example.com/stream")
    .setMimeType(MimeTypes.APPLICATION_M3U8)
    .build()
```

### Adaptive Bitrate Configuration

```kotlin
val trackSelector = DefaultTrackSelector(context).apply {
    parameters = buildUponParameters()
        .setMaxVideoSizeSd()                    // Cap at SD on mobile
        .setMinVideoFrameRate(24)
        .setForceHighestSupportedBitrate(false) // Let ABR algorithm decide
        .build()
}

val player = ExoPlayer.Builder(context)
    .setTrackSelector(trackSelector)
    .build()
```


## Caching (Streaming)
---

Cache progressive and adaptive streams for smoother playback and reduced data usage:

```kotlin
val cache = SimpleCache(
    File(context.cacheDir, "media-cache"),
    LeastRecentlyUsedCacheEvictor(100L * 1024 * 1024), // 100 MB max
    StandaloneDatabaseProvider(context)
)

val cacheDataSourceFactory = CacheDataSource.Factory()
    .setCache(cache)
    .setUpstreamDataSourceFactory(DefaultHttpDataSource.Factory())
    .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR)

val player = ExoPlayer.Builder(context)
    .setMediaSourceFactory(DefaultMediaSourceFactory(cacheDataSourceFactory))
    .build()
```


## Performance & Best Practices

### Memory Management

```kotlin
// Release player when not visible
fun releasePlayer() {
    player.stop()
    player.release()
}

// In Compose: always use DisposableEffect
DisposableEffect(Unit) {
    onDispose { player.release() }
}
```

### Preloading

```kotlin
// Preload next item for gapless playback
val loadControl = DefaultLoadControl.Builder()
    .setBufferDurationsMs(
        /* minBufferMs = */ 15_000,
        /* maxBufferMs = */ 50_000,
        /* bufferForPlaybackMs = */ 2_500,
        /* bufferForPlaybackAfterRebufferMs = */ 5_000
    )
    .build()

val player = ExoPlayer.Builder(context)
    .setLoadControl(loadControl)
    .build()
```

### Threading

- `Player` methods must be called from the **main thread** (unless you configure a custom application looper).
- `Player.Listener` callbacks arrive on the main thread.
- Heavy media processing (Transformer, custom DataSource) should run off the main thread.

### Analytics

```kotlin
player.addAnalyticsListener(object : AnalyticsListener {
    override fun onDroppedVideoFrames(
        eventTime: AnalyticsListener.EventTime,
        droppedFrames: Int,
        elapsedMs: Long
    ) {
        reportDroppedFrames(droppedFrames)
    }

    override fun onVideoDecoderInitialized(
        eventTime: AnalyticsListener.EventTime,
        decoderName: String,
        initializedTimestampMs: Long,
        initializationDurationMs: Long
    ) {
        reportDecoderInit(decoderName, initializationDurationMs)
    }

    override fun onBandwidthEstimate(
        eventTime: AnalyticsListener.EventTime,
        totalLoadTimeMs: Int,
        totalBytesLoaded: Long,
        bitrateEstimate: Long
    ) {
        reportBandwidth(bitrateEstimate)
    }
})
```


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| No audio — audio focus not requested | Set `handleAudioFocus = true` in `ExoPlayer.Builder` |
| No background playback | Use `MediaSessionService` with `foregroundServiceType="mediaPlayback"` and permissions |
| Playback stops on headphone disconnect | Set `setHandleAudioBecomingNoisy(true)` |
| Player crashes on rotation | Add `configChanges="orientation|screenSize"` to Activity, or manage player in ViewModel |
| Subtitles not showing | Ensure `PlayerView` has `app:use_controller="true"` and subtitle track is selected |
| PiP not entering automatically | Requires `setAutoEnterEnabled(true)` (API 31+) and `supportsPictureInPicture="true"` in manifest |
| Downloaded content won't play | Player must use `CacheDataSource` factory pointing at the same download cache |
| OOM with multiple players | Release players in `onDispose`/`onDestroy`; avoid creating more than 2 concurrent ExoPlayer instances |
| Notification not showing | Declare `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_MEDIA_PLAYBACK` permissions in manifest |
| DRM playback fails on emulator | Most emulators lack Widevine L1/L3 — test DRM on physical devices |
| Player methods called from wrong thread | All `Player` calls must be on the main (application) thread |
| Seek is slow on progressive MP4 | Ensure MP4 has `moov` atom at start (use `faststart` flag during encoding) |