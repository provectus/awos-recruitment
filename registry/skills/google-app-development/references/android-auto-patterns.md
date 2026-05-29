# Android Auto Patterns Reference

> Target: latest stable Car App Library

>[toc]

Android Auto is a **phone projection protocol** — the app runs on the user's phone and projects its UI onto the car's display via USB or wireless connection. For the shared Car App Library API (CarAppService, Session, Screen, Templates, Constraints, Lifecycle, Testing), see `car-app-library.md`. This file covers Auto-specific patterns only.


## Media Apps

### Media3 MediaLibraryService
---

Media apps for Android Auto do **not** use the Car App Library. They expose a browsable media tree via Media3's `MediaLibraryService`. The Auto host renders the UI automatically.

#### MediaLibraryService

`MediaLibraryService` is the Media3 replacement for the deprecated `MediaBrowserServiceCompat`. It exposes a browse tree of `MediaItem` objects that the Auto host navigates and plays.

```kotlin
class AutoMediaService : MediaLibraryService() {

    private var mediaSession: MediaLibrarySession? = null

    override fun onCreate() {
        super.onCreate()
        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(C.USAGE_MEDIA)
                    .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                    .build(),
                true // handle audio focus
            )
            .setHandleAudioBecomingNoisy(true)
            .build()

        mediaSession = MediaLibrarySession.Builder(this, player, LibrarySessionCallback())
            .build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaLibrarySession? =
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

#### Browse Tree

Expose a hierarchical browse tree via `LibrarySessionCallback`. The Auto host calls `onGetLibraryRoot` and `onGetChildren` to navigate the tree.

```kotlin
class LibrarySessionCallback : MediaLibrarySession.Callback {

    override fun onGetLibraryRoot(
        session: MediaLibrarySession,
        browser: MediaSession.ControllerInfo,
        params: LibraryParams?
    ): ListenableFuture<LibraryResult<MediaItem>> {
        val root = MediaItem.Builder()
            .setMediaId("ROOT")
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setIsBrowsable(true)
                    .setIsPlayable(false)
                    .setTitle("My Music")
                    .setMediaType(MediaMetadata.MEDIA_TYPE_FOLDER_MIXED)
                    .build()
            )
            .build()
        return Futures.immediateFuture(LibraryResult.ofItem(root, params))
    }

    override fun onGetChildren(
        session: MediaLibrarySession,
        browser: MediaSession.ControllerInfo,
        parentId: String,
        page: Int,
        pageSize: Int,
        params: LibraryParams?
    ): ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> {
        val children = when (parentId) {
            "ROOT" -> listOf(
                buildBrowsableItem("PLAYLISTS", "Playlists", MediaMetadata.MEDIA_TYPE_FOLDER_PLAYLISTS),
                buildBrowsableItem("ALBUMS", "Albums", MediaMetadata.MEDIA_TYPE_FOLDER_ALBUMS),
                buildBrowsableItem("RECENT", "Recently Played", MediaMetadata.MEDIA_TYPE_FOLDER_MIXED),
            )
            "PLAYLISTS" -> loadPlaylists()
            "ALBUMS" -> loadAlbums()
            "RECENT" -> loadRecentTracks()
            else -> emptyList()
        }
        return Futures.immediateFuture(LibraryResult.ofItemList(children, params))
    }

    private fun buildBrowsableItem(
        mediaId: String,
        title: String,
        mediaType: @MediaMetadata.MediaType Int,
    ): MediaItem {
        return MediaItem.Builder()
            .setMediaId(mediaId)
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setIsBrowsable(true)
                    .setIsPlayable(false)
                    .setTitle(title)
                    .setMediaType(mediaType)
                    .build()
            )
            .build()
    }
}
```

#### Browse Tree Structure

```
ROOT
├── PLAYLISTS      (browsable)
│   ├── Playlist A (playable)
│   └── Playlist B (playable)
├── ALBUMS         (browsable)
│   ├── Album 1    (browsable → tracks)
│   └── Album 2    (browsable → tracks)
└── RECENT         (browsable)
    ├── Song X     (playable)
    └── Song Y     (playable)
```

- Set `isBrowsable = true` for folders, `isPlayable = true` for leaf items.
- Set `mediaType` on metadata for proper icon rendering in the Auto host.
- Limit browse tree depth and breadth per Auto content guidelines.

#### Playable Items

```kotlin
fun buildPlayableItem(id: String, title: String, artist: String, artworkUri: Uri): MediaItem {
    return MediaItem.Builder()
        .setMediaId(id)
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setTitle(title)
                .setArtist(artist)
                .setArtworkUri(artworkUri)
                .setIsBrowsable(false)
                .setIsPlayable(true)
                .setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC)
                .build()
        )
        .setRequestMetadata(
            MediaItem.RequestMetadata.Builder()
                .setMediaUri(Uri.parse("content://media/$id"))
                .build()
        )
        .build()
}
```

#### Voice Search

Handle voice-initiated playback via `onAddMediaItems`:

```kotlin
override fun onAddMediaItems(
    mediaSession: MediaSession,
    controller: MediaSession.ControllerInfo,
    mediaItems: List<MediaItem>
): ListenableFuture<List<MediaItem>> {
    // Media3 sends voice search queries as MediaItems with search RequestMetadata
    val resolvedItems = mediaItems.map { item ->
        val searchQuery = item.requestMetadata.searchQuery
        if (searchQuery != null) {
            // Resolve search query to actual playable items
            searchMediaCatalog(searchQuery).first()
        } else {
            // Resolve by mediaId
            resolveMediaItem(item.mediaId)
        }
    }
    return Futures.immediateFuture(resolvedItems)
}
```

#### Manifest Declaration

```xml
<service
    android:name=".AutoMediaService"
    android:exported="true"
    android:foregroundServiceType="mediaPlayback">
    <intent-filter>
        <action android:name="androidx.media3.session.MediaLibraryService" />
    </intent-filter>
</service>

<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />
```

For detailed ExoPlayer, audio focus, and MediaSession patterns, see `media-playback.md`.


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

Navigation apps use the `NavigationTemplate` and the `NavigationManager` API. For `SurfaceCallback` map rendering, see `car-app-library.md`.

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

POI and charging/EV apps use `MapWithContentTemplate` to display locations on the map alongside detail panes. For template details, see `car-app-library.md`.

#### MapWithContentTemplate for Charging/POI Detail

```kotlin
MapWithContentTemplate.Builder()
    .setMapController(
        MapController.Builder()
            .setMapActionStrip(
                ActionStrip.Builder()
                    .addAction(Action.PAN) // allow map panning
                    .build()
            )
            .build()
    )
    .setContentTemplate(
        PaneTemplate.Builder(
            Pane.Builder()
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
            .setTitle("Station A")
            .build()
    )
    .build()
```

Required categories:

```xml
<!-- POI apps -->
<category android:name="androidx.car.app.category.POI" />

<!-- EV charging apps -->
<category android:name="androidx.car.app.category.CHARGING" />
```


## Testing

### Desktop Head Unit (DHU)
---

The DHU simulates an Android Auto head unit on your development machine. For unit testing with `TestCarContext` and `SessionController`, see `car-app-library.md`.

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


## Distribution

### Play Store for Android Auto
---

#### Minimum Requirements

- Target API level 33+ for new submissions.
- Include both mobile and Auto experiences in the same APK/AAB (Auto is not a separate listing).
- Set `minCarAppApiLevel` in manifest (see `car-app-library.md`).

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
