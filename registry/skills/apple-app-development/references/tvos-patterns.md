# tvOS Patterns

Patterns and guidance for building tvOS apps with SwiftUI. Targets tvOS 17+ and Swift 6+.

## Focus Engine

tvOS has no touch screen or pointer. The **focus engine** determines which element is focused and handles directional navigation from the Siri Remote.

### `@FocusState` and `focusable()`

```swift
struct MenuView: View {
    enum MenuItem: Hashable {
        case movies, shows, settings
    }

    @FocusState private var focusedItem: MenuItem?

    var body: some View {
        HStack(spacing: 40) {
            MenuButton(title: "Movies")
                .focused($focusedItem, equals: .movies)

            MenuButton(title: "Shows")
                .focused($focusedItem, equals: .shows)

            MenuButton(title: "Settings")
                .focused($focusedItem, equals: .settings)
        }
        .onAppear {
            focusedItem = .movies  // set initial focus
        }
    }
}
```

Any view can opt in to focus with `.focusable()`:

```swift
Text("Focusable label")
    .focusable()
    .onFocusChange { isFocused in
        // react to focus gain/loss
    }
```

### Custom Focus Behavior

Use `.focusSection()` to group related views so the focus engine treats them as a unit. This prevents focus from escaping a logical section unexpectedly:

```swift
VStack {
    // Top shelf row
    ScrollView(.horizontal) {
        LazyHStack { /* cards */ }
    }
    .focusSection()

    // Bottom row
    ScrollView(.horizontal) {
        LazyHStack { /* cards */ }
    }
    .focusSection()
}
```

### Focus Guides

When the default focus movement skips a view because it is not geometrically aligned, use a focus guide to redirect:

```swift
// UIKit approach (still needed for complex layouts)
let guide = UIFocusGuide()
view.addLayoutGuide(guide)
guide.preferredFocusEnvironments = [targetView]
```

In SwiftUI, prefer `.focusSection()` and layout adjustments over manual focus guides. For edge cases requiring UIKit-level control, wrap in a `UIViewRepresentable`.

### `onMoveCommand`

Intercept directional input before the focus engine processes it:

```swift
struct GridView: View {
    @State private var selectedIndex = 0

    var body: some View {
        CardView(item: items[selectedIndex])
            .onMoveCommand { direction in
                switch direction {
                case .left:  selectedIndex = max(0, selectedIndex - 1)
                case .right: selectedIndex = min(items.count - 1, selectedIndex + 1)
                case .up, .down: break
                @unknown default: break
                }
            }
    }
}
```

## Top Shelf

The Top Shelf is the banner area shown when the user hovers over your app on the home screen. It requires a **Top Shelf Extension** target.

### Setting Up

1. Add a new target: **TV Top Shelf Extension** in Xcode.
2. Implement `TopShelfProvider`:

```swift
import TVServices

struct MyTopShelfProvider: TopShelfProvider {
    var topShelfStyle: TopShelfContentStyle { .sectioned }

    var topShelfItems: [TopShelfSectionedContent] {
        get async {
            let items = await ContentService.shared.fetchFeatured()

            let section = TopShelfItemCollection(
                items: items.map { content in
                    let item = TopShelfSectionedItem(identifier: content.id)
                    item.title = content.title
                    item.setImageURL(content.imageURL, for: .screenScale1x)
                    item.setImageURL(content.imageURL2x, for: .screenScale2x)
                    item.displayAction = .init(url: content.deepLink)
                    return item
                }
            )
            section.title = "Featured"

            return [TopShelfSectionedContent(sections: [section])]
        }
    }
}
```

### Content Styles

| Style | Description | Use Case |
|---|---|---|
| `.sectioned` | Multiple labeled rows of items | Browseable catalogs, multiple categories |
| `.inset` | Single row of large, full-bleed images | Hero content, featured movies/shows |

## Remote Navigation

The Siri Remote is the primary input device. It provides a clickpad (touch surface), directional swipes, and physical buttons.

### Swipe and Press Handling

```swift
struct PlayerControlsView: View {
    var body: some View {
        VideoContentView()
            // Play/Pause button on remote
            .onPlayPauseCommand {
                playerManager.togglePlayback()
            }
            // Menu/Back button on remote
            .onExitCommand {
                dismiss()
            }
    }
}
```

### Gesture Recognition

SwiftUI gesture recognizers work with the Siri Remote clickpad:

```swift
struct SwipeableCardView: View {
    @State private var offset: CGFloat = 0

    var body: some View {
        CardView()
            .offset(x: offset)
            .gesture(
                DragGesture()
                    .onChanged { value in
                        offset = value.translation.width
                    }
                    .onEnded { value in
                        withAnimation {
                            if value.translation.width > 100 {
                                // swiped right — advance
                            }
                            offset = 0
                        }
                    }
            )
    }
}
```

### Button Presses

Handle specific remote buttons with press commands:

```swift
ContentView()
    .onMoveCommand { direction in
        // D-pad / clickpad edge presses
    }
    .onPlayPauseCommand {
        // Play/Pause physical button
    }
    .onExitCommand {
        // Menu / Back button
    }
```

> Avoid overriding `.onExitCommand` unless you need custom back navigation. Users expect it to go back or exit.

## Media Playback

tvOS is a media-centric platform. AVKit provides the standard playback experience users expect.

### VideoPlayer (SwiftUI)

```swift
import AVKit

struct MoviePlayerView: View {
    @State private var player = AVPlayer(
        url: URL(string: "https://example.com/movie.m3u8")!
    )

    var body: some View {
        VideoPlayer(player: player) {
            // Optional overlay content
            VStack {
                Spacer()
                Text("Now Playing: Movie Title")
                    .font(.caption)
                    .padding()
            }
        }
        .ignoresSafeArea()
        .onAppear { player.play() }
        .onDisappear { player.pause() }
    }
}
```

### AVPlayerViewController for Full Control

For transport bar customization, info tabs, and interstitial handling, use `AVPlayerViewController` via UIKit interop:

```swift
struct FullPlayerView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> AVPlayerViewController {
        let controller = AVPlayerViewController()
        controller.player = AVPlayer(url: url)
        controller.allowsPictureInPicturePlayback = true

        // Custom info view controllers (tabs in transport bar)
        let infoVC = UIHostingController(rootView: MovieInfoView())
        controller.customInfoViewControllers = [infoVC]

        return controller
    }

    func updateUIViewController(_ controller: AVPlayerViewController, context: Context) {}
}
```

### Background Audio

To continue audio playback when the app is backgrounded, configure the audio session and enable the background mode:

```swift
import AVFoundation

func configureAudioSession() throws {
    let session = AVAudioSession.sharedInstance()
    try session.setCategory(.playback, mode: .moviePlayback)
    try session.setActive(true)
}
```

Also enable **Audio, AirPlay, and Picture in Picture** in your target's capabilities under Background Modes.

### Picture-in-Picture

PiP is available on tvOS. Use `AVPlayerViewController` with `allowsPictureInPicturePlayback = true`. The system handles the PiP window automatically when the user presses the home button during playback.

## Layout Differences

tvOS apps render on large screens. Design for the living room viewing distance.

### Screen Resolutions

| Resolution | When Used |
|---|---|
| 1920x1080 (1080p) | Apple TV HD |
| 3840x2160 (4K) | Apple TV 4K |

SwiftUI uses points, so the coordinate space is always **1920x1080** regardless of device. The system handles pixel doubling for 4K.

### Safe Areas and Overscan

TVs may crop edges of the signal (overscan). tvOS provides built-in safe area insets (~60pt on all sides) to keep content visible:

```swift
struct ContentView: View {
    var body: some View {
        VStack {
            Text("This respects safe areas by default")
        }
        // Only ignore safe areas for full-bleed backgrounds/video
        // .ignoresSafeArea()
    }
}
```

Rules:
- Keep all interactive and readable content **within safe areas** (the default).
- Use `.ignoresSafeArea()` only for background images, video players, and decorative elements.
- Never place buttons or text near the screen edges.

### Text Sizing

Users sit far from the TV. Use larger font sizes than you would on iOS:

```swift
Text("Section Title")
    .font(.title)       // ~76pt on tvOS vs ~28pt on iOS

Text("Description")
    .font(.body)        // ~29pt on tvOS vs ~17pt on iOS

Text("Caption")
    .font(.caption)     // ~25pt on tvOS vs ~12pt on iOS
```

Prefer system Dynamic Type styles. They are already scaled for the TV viewing distance.

## UI Patterns

### Horizontally Scrolling Shelves

The most common tvOS pattern. Each row is a horizontally scrollable collection:

```swift
struct ShelfRow: View {
    let title: String
    let items: [MediaItem]

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(title)
                .font(.headline)

            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 40) {
                    ForEach(items) { item in
                        Button {
                            // navigate to detail
                        } label: {
                            CardView(item: item)
                        }
                        .buttonStyle(.card)  // tvOS card lift effect
                    }
                }
                .padding(.horizontal, 50)
            }
            .focusSection()
        }
    }
}
```

### Card-Based Layouts and Lock-Up Views

Cards are the primary interactive element. Use `.buttonStyle(.card)` for the standard tvOS focus lift animation:

```swift
struct CardView: View {
    let item: MediaItem

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            AsyncImage(url: item.posterURL) { image in
                image
                    .resizable()
                    .aspectRatio(16/9, contentMode: .fill)
            } placeholder: {
                Rectangle()
                    .fill(.quaternary)
            }
            .frame(width: 400, height: 225)
            .clipShape(RoundedRectangle(cornerRadius: 12))

            Text(item.title)
                .font(.callout)
                .lineLimit(1)
        }
    }
}
```

> "Lock-up view" is Apple's term for a card that combines an image with a text label below it, behaving as a single focusable unit. SwiftUI `Button` with `.buttonStyle(.card)` achieves this.

### Full-Screen Content

For immersive views (hero banners, video backgrounds):

```swift
struct HeroBannerView: View {
    let featured: MediaItem

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            AsyncImage(url: featured.backdropURL) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                Color.black
            }
            .ignoresSafeArea()

            VStack(alignment: .leading, spacing: 16) {
                Text(featured.title)
                    .font(.largeTitle)
                    .bold()

                Text(featured.synopsis)
                    .font(.body)
                    .lineLimit(3)
                    .frame(maxWidth: 800, alignment: .leading)

                Button("Play") {
                    // start playback
                }
            }
            .padding(80)
        }
    }
}
```

### Tabbed Navigation

Use `TabView` for top-level navigation. tvOS renders tabs as a translucent bar at the top:

```swift
@main
struct MyTVApp: App {
    var body: some Scene {
        WindowGroup {
            TabView {
                HomeView()
                    .tabItem { Label("Home", systemImage: "house") }

                SearchView()
                    .tabItem { Label("Search", systemImage: "magnifyingglass") }

                SettingsView()
                    .tabItem { Label("Settings", systemImage: "gear") }
            }
        }
    }
}
```

## TVMLKit

TVMLKit is the JavaScript/XML-based framework for building tvOS UIs using TVML templates. It is a legacy approach.

### When to Use

| Criteria | Use SwiftUI | Use TVMLKit |
|---|---|---|
| New apps | Yes | No |
| Server-driven UI needed | SwiftUI + JSON config | Maybe (but consider alternatives) |
| Existing TVMLKit codebase | Migrate when practical | Maintain if stable |
| Complex custom interactions | Yes | Limited |

TVMLKit was useful when tvOS first launched (tvOS 9) for quickly building catalog-style apps with server-driven templates. For new development, SwiftUI is the clear choice. Apple has not significantly updated TVMLKit in recent years.

### Basic Setup (Legacy Reference)

```swift
import TVMLKit

class AppDelegate: UIResponder, UIApplicationDelegate, TVApplicationControllerDelegate {
    var appController: TVApplicationController?

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        let context = TVApplicationControllerContext()
        context.javaScriptApplicationURL = URL(string: "https://example.com/app.js")!

        appController = TVApplicationController(
            context: context,
            window: window,
            delegate: self
        )
        return true
    }
}
```

## Multiuser Support

Apple TV supports multiple users. Each user has their own Apple ID, preferences, and data.

### Detecting the Current User

```swift
import TVServices

func loadCurrentUserProfile() async {
    let userManager = TVUserManager()
    let currentUser = userManager.currentUser

    // Use the user identifier to key per-user data
    if let userID = currentUser?.identifier {
        await loadProfile(for: userID)
    }
}
```

### Per-User Data

```swift
import TVServices

@Observable
class UserProfileManager {
    var currentProfile: UserProfile?

    private let userManager = TVUserManager()

    func observeUserChanges() {
        NotificationCenter.default.addObserver(
            forName: .TVUserManagerCurrentUserDidChange,
            object: userManager,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                await self?.reloadProfile()
            }
        }
    }

    private func reloadProfile() async {
        guard let userID = userManager.currentUser?.identifier else {
            currentProfile = nil
            return
        }
        currentProfile = await ProfileStore.shared.load(for: userID)
    }
}
```

Rules:
- Always handle user switching. The active user can change at any time.
- Key all user-specific data (watch history, favorites, preferences) by the user identifier.
- Listen for `.TVUserManagerCurrentUserDidChange` to react to user switches.

## Limitations

tvOS has significant restrictions compared to iOS. Be aware of these when designing your app.

| Limitation | Detail |
|---|---|
| **No web views** | `WKWebView` is not available. You cannot display web content. Fetch data via APIs and render natively. |
| **Limited text input** | No keyboard attached. Text input uses an on-screen keyboard navigated by remote, or dictation. Minimize text entry in your UI. |
| **No pointer support** | No mouse, trackpad, or cursor. All navigation is focus-based via the Siri Remote. |
| **No file system access** | No `UIDocumentPickerViewController`, no Files app. Local storage is limited and purgeable. |
| **Limited local storage** | Apps get ~500 KB of persistent storage (`UserDefaults`). Use CloudKit or a remote backend for larger data. |
| **No background execution** | Apps are suspended immediately when the user leaves. Background modes are limited to audio playback and downloads. |
| **No Camera/Location** | Hardware not available. `CoreLocation` and `AVCaptureSession` are absent. |
| **Restricted frameworks** | No `WebKit`, `MessageUI`, `HealthKit`, `ARKit`, `CallKit`, `StoreKit` in-app purchases work differently (no direct purchase flow on older tvOS). |
| **App size** | The main app bundle is capped at 4 GB. Use On-Demand Resources for additional assets. |

### Working Around Limitations

```swift
// Instead of web views, fetch and render content natively
struct ArticleView: View {
    let article: Article  // parsed from API, not loaded via web view

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text(article.title).font(.title)
                Text(article.body).font(.body)
            }
            .padding(80)
        }
    }
}

// Minimize text input — use search with dictation or predefined filters
struct SearchView: View {
    @State private var query = ""

    var body: some View {
        NavigationStack {
            VStack {
                // The system searchable modifier provides the
                // best on-screen keyboard experience on tvOS
                List(filteredResults) { item in
                    NavigationLink(item.title, value: item)
                }
                .searchable(text: $query, prompt: "Search movies")
            }
        }
    }
}
```
