# Media Playback Reference (AVFoundation & AVKit)

Comprehensive guide to media playback on Apple platforms. Covers AVPlayer, AVKit integration with SwiftUI and UIKit, audio session management, Picture-in-Picture, AirPlay, offline downloads, and performance. For tvOS-specific playback patterns see `tvos-patterns.md`.

## Architecture Overview

| Layer | Framework | Purpose |
|---|---|---|
| **UI** | AVKit | `VideoPlayer` (SwiftUI), `AVPlayerViewController` (UIKit) — standard transport controls, PiP, AirPlay |
| **Playback** | AVFoundation | `AVPlayer`, `AVPlayerItem`, `AVQueuePlayer` — playback engine, time observation, state management |
| **Rendering** | AVFoundation | `AVPlayerLayer` — Core Animation layer for custom player UI |
| **Audio** | AVFAudio | `AVAudioSession` — system audio configuration, categories, interruptions, route changes |
| **Assets** | AVFoundation | `AVAsset`, `AVURLAsset` — media metadata, tracks, duration, loading |

**Rule:** Use AVKit (`VideoPlayer` or `AVPlayerViewController`) for standard playback. Drop to AVFoundation only when you need a fully custom player UI.


## AVKit — Standard Playback

### VideoPlayer (SwiftUI)
---

The simplest way to add video playback. Provides native transport controls across all platforms.

```swift
import AVKit
import SwiftUI

struct PlayerView: View {
    @State private var player = AVPlayer(url: URL(string: "https://example.com/video.m3u8")!)

    var body: some View {
        VideoPlayer(player: player) {
            // Optional overlay — positioned above transport controls
            VStack {
                Spacer()
                Text("Live")
                    .font(.caption)
                    .padding(6)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .padding()
            }
        }
        .onAppear { player.play() }
        .onDisappear { player.pause() }
    }
}
```

`VideoPlayer` is suitable for inline playback. For fullscreen with rich metadata, use `AVPlayerViewController`.

### AVPlayerViewController (UIKit / UIViewControllerRepresentable)
---

Full-featured player with transport bar, subtitle selection, AirPlay, and PiP support.

```swift
struct FullscreenPlayerView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> AVPlayerViewController {
        let controller = AVPlayerViewController()
        let player = AVPlayer(url: url)
        controller.player = player
        controller.allowsPictureInPicturePlayback = true
        controller.canStartPictureInPictureAutomaticallyFromInline = true

        // Set metadata for display
        let item = player.currentItem!
        item.externalMetadata = makeMetadata()

        return controller
    }

    func updateUIViewController(_ controller: AVPlayerViewController, context: Context) {}

    private func makeMetadata() -> [AVMetadataItem] {
        let title = AVMutableMetadataItem()
        title.identifier = .commonIdentifierTitle
        title.value = "Episode Title" as NSString

        let subtitle = AVMutableMetadataItem()
        subtitle.identifier = .iTunesMetadataTrackSubTitle
        subtitle.value = "Season 1, Episode 3" as NSString

        return [title, subtitle]
    }
}
```

#### Presenting Fullscreen from SwiftUI

```swift
struct ContentView: View {
    @State private var showPlayer = false

    var body: some View {
        Button("Play Video") { showPlayer = true }
            .fullScreenCover(isPresented: $showPlayer) {
                FullscreenPlayerView(url: videoURL)
                    .ignoresSafeArea()
            }
    }
}
```


## AVFoundation — Playback Engine

### AVPlayer & AVPlayerItem
---

```swift
import AVFoundation

// Create player with a URL
let player = AVPlayer(url: mediaURL)

// Or with an AVPlayerItem for more control
let asset = AVURLAsset(url: mediaURL)
let item = AVPlayerItem(asset: asset)
let player = AVPlayer(playerItem: item)
```

#### Transport Controls

```swift
player.play()
player.pause()
player.rate = 2.0  // 2x speed
player.rate = 0.5  // half speed

// Seek to specific time
let target = CMTime(seconds: 30, preferredTimescale: 600)
await player.seek(to: target)

// Seek with tolerance (faster — allows nearest keyframe)
await player.seek(to: target, toleranceBefore: .zero, toleranceAfter: .zero)
```

#### Observing Playback State

Use `timeControlStatus` instead of `rate` for reliable play/pause detection:

```swift
// KVO observation
let observation = player.observe(\.timeControlStatus) { player, _ in
    switch player.timeControlStatus {
    case .playing:
        print("Playing")
    case .paused:
        print("Paused")
    case .waitingToPlayAtSpecifiedRate:
        print("Buffering — reason: \(player.reasonForWaitingToPlay?.rawValue ?? "unknown")")
    @unknown default:
        break
    }
}
```

#### AVPlayerItem Status

```swift
let statusObservation = item.observe(\.status) { item, _ in
    switch item.status {
    case .readyToPlay:
        // Safe to call play()
        break
    case .failed:
        print("Failed: \(item.error?.localizedDescription ?? "")")
    case .unknown:
        break
    @unknown default:
        break
    }
}
```

### Time Observation
---

#### Periodic Time Observer

Track playback progress for UI updates (scrubber, elapsed time):

```swift
let interval = CMTime(seconds: 0.5, preferredTimescale: 600)
let observer = player.addPeriodicTimeObserver(forInterval: interval, queue: .main) { time in
    let seconds = CMTimeGetSeconds(time)
    updateProgressUI(seconds: seconds)
}

// Remove when done — must store the observer token
player.removeTimeObserver(observer)
```

#### Boundary Time Observer

Trigger actions at specific times (chapter markers, ad cue points):

```swift
let times = [
    CMTime(seconds: 10, preferredTimescale: 600),
    CMTime(seconds: 60, preferredTimescale: 600),
].map { NSValue(time: $0) }

let observer = player.addBoundaryTimeObserver(forTimes: times, queue: .main) {
    showChapterTitle()
}
```

### AVQueuePlayer
---

Sequential playback of multiple items:

```swift
let items = urls.map { AVPlayerItem(url: $0) }
let queuePlayer = AVQueuePlayer(items: items)
queuePlayer.play()  // Automatically advances to next item

// Insert/remove items dynamically
queuePlayer.insert(newItem, after: nil)  // Append to end
queuePlayer.remove(items[0])

// Skip to next
queuePlayer.advanceToNextItem()
```

#### AVPlayerLooper

Seamless looping of a single item:

```swift
let item = AVPlayerItem(url: loopURL)
let queuePlayer = AVQueuePlayer()
let looper = AVPlayerLooper(player: queuePlayer, templateItem: item)
queuePlayer.play()

// Check loop state
print("Loop count: \(looper.loopCount)")
```

### Custom Player UI with AVPlayerLayer
---

When `VideoPlayer` and `AVPlayerViewController` don't fit your design, render video with `AVPlayerLayer`:

```swift
// UIKit
class CustomPlayerView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }

    var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }

    func configure(with player: AVPlayer) {
        playerLayer.player = player
        playerLayer.videoGravity = .resizeAspect
    }
}
```

```swift
// SwiftUI wrapper
struct CustomVideoView: UIViewRepresentable {
    let player: AVPlayer

    func makeUIView(context: Context) -> CustomPlayerView {
        let view = CustomPlayerView()
        view.configure(with: player)
        return view
    }

    func updateUIView(_ uiView: CustomPlayerView, context: Context) {}
}
```

**Video gravity options:**

| Value | Behavior |
|---|---|
| `.resizeAspect` | Fit within bounds, preserve aspect ratio (letterbox) |
| `.resizeAspectFill` | Fill bounds, preserve aspect ratio (crop) |
| `.resize` | Stretch to fill (distorts) |


## AVAudioSession
---

Configure how your app interacts with the system audio. **Must be set up before playback begins.**

### Categories

| Category | Behavior | Use Case |
|---|---|---|
| `.playback` | Silences other audio, plays with silent switch on | Video/music player |
| `.ambient` | Mixes with other audio, respects silent switch | Game background music |
| `.soloAmbient` | Default — silences other audio, respects silent switch | Casual audio |
| `.playAndRecord` | Input + output simultaneously | Voice/video calls |
| `.record` | Input only | Audio recording |

### Setup

```swift
func configureAudioSession() throws {
    let session = AVAudioSession.sharedInstance()
    try session.setCategory(.playback, mode: .moviePlayback, options: [])
    try session.setActive(true)
}
```

Common modes: `.default`, `.moviePlayback`, `.spokenAudio`, `.voiceChat`, `.videoChat`.

### Background Audio

To continue playback when the app is backgrounded:

1. Set category to `.playback`
2. Enable **Audio, AirPlay, and Picture in Picture** in target capabilities → Background Modes
3. Activate the session before playback

### Interruption Handling

```swift
NotificationCenter.default.addObserver(
    forName: AVAudioSession.interruptionNotification,
    object: AVAudioSession.sharedInstance(),
    queue: .main
) { notification in
    guard let info = notification.userInfo,
          let typeValue = info[AVAudioSessionInterruptionTypeKey] as? UInt,
          let type = AVAudioSession.InterruptionType(rawValue: typeValue)
    else { return }

    switch type {
    case .began:
        // Pause UI, save playback position
        break
    case .ended:
        let options = info[AVAudioSessionInterruptionOptionKey] as? UInt ?? 0
        if AVAudioSession.InterruptionOptions(rawValue: options).contains(.shouldResume) {
            player.play()
        }
    @unknown default:
        break
    }
}
```

### Route Change Handling

Detect headphone disconnect and pause playback (Apple HIG requirement):

```swift
NotificationCenter.default.addObserver(
    forName: AVAudioSession.routeChangeNotification,
    object: AVAudioSession.sharedInstance(),
    queue: .main
) { notification in
    guard let info = notification.userInfo,
          let reasonValue = info[AVAudioSessionRouteChangeReasonKey] as? UInt,
          let reason = AVAudioSession.RouteChangeReason(rawValue: reasonValue)
    else { return }

    if reason == .oldDeviceUnavailable {
        // Headphones unplugged — pause playback
        player.pause()
    }
}
```


## Picture-in-Picture (PiP)
---

### With AVPlayerViewController (Simplest)

```swift
let controller = AVPlayerViewController()
controller.player = player
controller.allowsPictureInPicturePlayback = true
controller.canStartPictureInPictureAutomaticallyFromInline = true
// PiP works automatically — no additional code needed
```

### With Custom Player (AVPictureInPictureController)

```swift
guard AVPictureInPictureController.isPictureInPictureSupported() else { return }

let pipController = AVPictureInPictureController(playerLayer: playerLayer)
pipController.delegate = self

// Start/stop
pipController.startPictureInPicture()
pipController.stopPictureInPicture()
```

#### Delegate

```swift
extension PlayerManager: AVPictureInPictureControllerDelegate {
    func pictureInPictureControllerWillStartPictureInPicture(
        _ controller: AVPictureInPictureController) {
        // Prepare UI — hide inline player controls
    }

    func pictureInPictureControllerDidStopPictureInPicture(
        _ controller: AVPictureInPictureController) {
        // Restore UI
    }

    func pictureInPictureController(
        _ controller: AVPictureInPictureController,
        restoreUserInterfaceForPictureInPictureStopWithCompletionHandler handler: @escaping (Bool) -> Void) {
        // Restore full player UI when user taps to return from PiP
        showFullscreenPlayer()
        handler(true)
    }
}
```

### PiP Requirements

- Audio session category `.playback` with Background Modes enabled
- Device must support PiP (`isPictureInPictureSupported()`)
- Player must be actively playing content


## AirPlay & External Display
---

### Enabling AirPlay

AirPlay is enabled by default with `AVPlayerViewController` and `VideoPlayer`. For custom players:

```swift
player.allowsExternalPlayback = true  // Default is true
player.usesExternalPlaybackWhileExternalScreenIsActive = true
```

### Route Detection

```swift
let routeDetector = AVRouteDetector()
routeDetector.isRouteDetectionEnabled = true

let observation = routeDetector.observe(\.multipleRoutesDetected) { detector, _ in
    showAirPlayButton = detector.multipleRoutesDetected
}
```

### Route Picker (Custom UI)

```swift
// UIKit — add AVRoutePickerView
let routePicker = AVRoutePickerView(frame: CGRect(x: 0, y: 0, width: 44, height: 44))
routePicker.tintColor = .white
view.addSubview(routePicker)
```


## Offline Downloads (HLS)
---

Download HTTP Live Streaming content for offline playback using `AVAssetDownloadURLSession`.

### Download Setup

```swift
let configuration = URLSessionConfiguration.background(
    withIdentifier: "com.example.app.asset-download"
)
let downloadSession = AVAssetDownloadURLSession(
    configuration: configuration,
    assetDownloadDelegate: self,
    delegateQueue: .main
)
```

### Starting a Download

```swift
let asset = AVURLAsset(url: hlsURL)
guard let task = downloadSession.makeAssetDownloadTask(
    asset: asset,
    assetTitle: "Episode 1",
    assetArtworkData: artworkData,
    options: [AVAssetDownloadTaskMinimumRequiredMediaBitrateKey: 2_000_000]
) else { return }

task.resume()
```

### Aggregate Download (Multiple Variants)

Download specific media selections (subtitles, audio tracks):

```swift
guard let task = downloadSession.aggregateAssetDownloadTask(
    with: asset,
    mediaSelections: [audioSelection, subtitleSelection],
    assetTitle: "Episode 1",
    assetArtworkData: artworkData,
    options: nil
) else { return }

task.resume()
```

### Delegate Callbacks

```swift
extension DownloadManager: AVAssetDownloadDelegate {
    func urlSession(_ session: URLSession, assetDownloadTask: AVAssetDownloadTask,
                    didFinishDownloadingTo location: URL) {
        // Save location for offline playback
        UserDefaults.standard.set(location.relativePath, forKey: assetDownloadTask.taskDescription!)
    }

    func urlSession(_ session: URLSession,
                    assetDownloadTask: AVAssetDownloadTask,
                    didLoad timeRange: CMTimeRange,
                    totalTimeRangesLoaded: [NSValue],
                    timeRangeExpectedToLoad: CMTimeRange) {
        var percentComplete = 0.0
        for value in totalTimeRangesLoaded {
            let loaded = value.timeRangeValue
            percentComplete += CMTimeGetSeconds(loaded.duration) /
                               CMTimeGetSeconds(timeRangeExpectedToLoad.duration)
        }
        updateDownloadProgress(percentComplete)
    }
}
```

### Playing Downloaded Content

```swift
// Retrieve saved location
guard let relativePath = UserDefaults.standard.string(forKey: assetID) else { return }
let localURL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(relativePath)
let asset = AVURLAsset(url: localURL)
let item = AVPlayerItem(asset: asset)
player.replaceCurrentItem(with: item)
player.play()
```

### Storage Management

```swift
let manager = AVAssetDownloadStorageManager.shared()
let policy = AVMutableAssetDownloadStorageManagementPolicy()
policy.expirationDate = Date().addingTimeInterval(30 * 24 * 60 * 60)  // 30 days
policy.priority = .important

let localURL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(relativePath)
manager.setStorageManagementPolicy(policy, for: localURL)
```


## Media Selection (Subtitles & Audio Tracks)
---

```swift
// Discover available options
guard let asset = player.currentItem?.asset else { return }
let mediaCharacteristics: [AVMediaCharacteristic] = [.audible, .legible]

for characteristic in mediaCharacteristics {
    if let group = try? await asset.loadMediaSelectionGroup(for: characteristic) {
        for option in group.options {
            print("\(characteristic): \(option.displayName) [\(option.locale?.identifier ?? "")]")
        }
    }
}

// Select a specific subtitle track
if let subtitleGroup = try? await asset.loadMediaSelectionGroup(for: .legible) {
    let french = subtitleGroup.options.first { $0.locale?.languageCode == "fr" }
    if let french {
        player.currentItem?.select(french, in: subtitleGroup)
    }
}

// Set preferred language criteria (automatic selection)
player.appliesMediaSelectionCriteriaAutomatically = true
let criteria = AVPlayerMediaSelectionCriteria(
    preferredLanguages: ["en", "fr"],
    preferredMediaCharacteristics: [.legible]
)
player.setMediaSelectionCriteria(criteria, forMediaCharacteristic: .legible)
```


## Now Playing & Remote Controls
---

Enable lock screen and Control Center controls for media apps.

### MPNowPlayingInfoCenter

```swift
import MediaPlayer

func updateNowPlayingInfo(title: String, artist: String, duration: TimeInterval, elapsed: TimeInterval) {
    var info: [String: Any] = [
        MPMediaItemPropertyTitle: title,
        MPMediaItemPropertyArtist: artist,
        MPMediaItemPropertyPlaybackDuration: duration,
        MPNowPlayingInfoPropertyElapsedPlaybackTime: elapsed,
        MPNowPlayingInfoPropertyPlaybackRate: player.rate
    ]

    if let artwork = loadArtwork() {
        info[MPMediaItemPropertyArtwork] = MPMediaItemArtwork(
            boundsSize: artwork.size
        ) { _ in artwork }
    }

    MPNowPlayingInfoCenter.default().nowPlayingInfo = info
}
```

### MPRemoteCommandCenter

```swift
func setupRemoteCommands() {
    let commandCenter = MPRemoteCommandCenter.shared()

    commandCenter.playCommand.addTarget { [weak self] _ in
        self?.player.play()
        return .success
    }

    commandCenter.pauseCommand.addTarget { [weak self] _ in
        self?.player.pause()
        return .success
    }

    commandCenter.skipForwardCommand.preferredIntervals = [15]
    commandCenter.skipForwardCommand.addTarget { [weak self] event in
        guard let self, let event = event as? MPSkipIntervalCommandEvent else { return .commandFailed }
        let target = CMTimeAdd(player.currentTime(), CMTime(seconds: event.interval, preferredTimescale: 600))
        Task { await self.player.seek(to: target) }
        return .success
    }

    commandCenter.skipBackwardCommand.preferredIntervals = [15]
    commandCenter.skipBackwardCommand.addTarget { [weak self] event in
        guard let self, let event = event as? MPSkipIntervalCommandEvent else { return .commandFailed }
        let target = CMTimeSubtract(player.currentTime(), CMTime(seconds: event.interval, preferredTimescale: 600))
        Task { await self.player.seek(to: target) }
        return .success
    }
}
```


## Asset Loading
---

Load asset properties asynchronously before playback:

```swift
let asset = AVURLAsset(url: mediaURL)

// Modern async API (iOS 15+)
let duration = try await asset.load(.duration)
let tracks = try await asset.load(.tracks)
let isPlayable = try await asset.load(.isPlayable)

// Load multiple properties at once
let (dur, playable) = try await asset.load(.duration, .isPlayable)

// Check if a specific track type exists
let videoTracks = try await asset.loadTracks(withMediaType: .video)
let hasVideo = !videoTracks.isEmpty
```

**Rule:** Always check `isPlayable` before attempting playback. Never access asset properties synchronously — use `load(_:)`.


## Performance & Best Practices

### Memory Management

```swift
// Release player resources when not visible
func cleanup() {
    player.pause()
    player.replaceCurrentItem(with: nil)  // Releases buffers
}
```

### Preloading

```swift
// Preload next item in queue for gapless playback
let nextItem = AVPlayerItem(url: nextURL)
nextItem.preferredForwardBufferDuration = 5  // Buffer 5 seconds ahead
```

### Error Handling

```swift
// Observe player item failures
NotificationCenter.default.addObserver(
    forName: .AVPlayerItemFailedToPlayToEndTime,
    object: player.currentItem,
    queue: .main
) { notification in
    let error = notification.userInfo?[AVPlayerItemFailedToPlayToEndTimeErrorKey] as? Error
    handlePlaybackError(error)
}

// Observe end of playback
NotificationCenter.default.addObserver(
    forName: .AVPlayerItemDidPlayToEndTime,
    object: player.currentItem,
    queue: .main
) { _ in
    showReplayButton()
    // Or loop: player.seek(to: .zero); player.play()
}
```


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| No audio — silent switch is on | Set audio session category to `.playback` |
| No background audio | Enable Background Modes capability + `.playback` category |
| PiP doesn't work | Requires `.playback` audio session + Background Modes + active playback |
| Video doesn't render in custom player | Ensure `AVPlayerLayer` is properly sized and added to view hierarchy |
| Playback starts with delay | Use `automaticallyWaitsToMinimizeStalling` and preload with `preferredForwardBufferDuration` |
| Not pausing on headphone disconnect | Observe `AVAudioSession.routeChangeNotification` and check `.oldDeviceUnavailable` |
| Time observers not removed | Store observer token and call `removeTimeObserver(_:)` — leaks otherwise |
| Accessing asset properties synchronously | Use `asset.load(.duration)` — synchronous access is deprecated and can block |
| App Transport Security blocks HTTP streams | Add exception in Info.plist or use HTTPS |
| Player item reused after failure | Create a new `AVPlayerItem` — failed items cannot be reused |
| AirPlay not showing | Check `allowsExternalPlayback` (default true) and ensure route detection is enabled |
