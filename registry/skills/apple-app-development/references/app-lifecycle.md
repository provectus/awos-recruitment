# App Lifecycle Reference

## Contents
- SwiftUI App lifecycle (`@main`, `App` protocol, scene types, scene phase)
- Scene phase transitions and state saving
- Background tasks (`BGTaskScheduler`)
- Push notifications (APNs, `UNUserNotificationCenter`, silent push)
- Deep links and Universal Links
- Handoff and `NSUserActivity`
- App Intents integration (brief — see `widgets-app-intents.md`)
- State restoration (`@SceneStorage`)
- Launch optimization
- UIKit App Delegate interop (`@UIApplicationDelegateAdaptor`)
- Memory management

## SwiftUI App Lifecycle

The `@main` attribute marks the app entry point. The `App` protocol replaces `UIApplicationDelegate` as the primary lifecycle owner.

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
```

### Scene Types

| Scene | Use Case |
|---|---|
| `WindowGroup` | Standard window, supports multiple instances on iPadOS/macOS |
| `DocumentGroup` | Document-based apps with open/save/create |
| `Settings` | macOS preferences window (opens via Cmd+,) |
| `Window` | macOS single-instance utility window (macOS 13+) |
| `ImmersiveSpace` | visionOS immersive content |

```swift
@main
struct MyDocApp: App {
    var body: some Scene {
        DocumentGroup(newDocument: TextDocument()) { file in
            TextEditorView(document: file.$document)
        }

        #if os(macOS)
        Settings {
            SettingsView()
        }

        Window("Activity Log", id: "activity-log") {
            ActivityLogView()
        }
        #endif
    }
}
```

### App-Level State and Dependencies

Inject shared dependencies at the `App` level so all scenes and views can access them:

```swift
@main
struct MyApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appState)
        }
    }
}
```

## Scene Phase

`scenePhase` tracks the current lifecycle state of the app's scenes. Use it to respond to foreground/background transitions.

| Phase | Meaning |
|---|---|
| `.active` | Scene is in the foreground and interactive |
| `.inactive` | Scene is visible but not interactive (e.g., incoming call, app switcher) |
| `.background` | Scene is not visible; limited execution time |

```swift
@main
struct MyApp: App {
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .onChange(of: scenePhase) { oldPhase, newPhase in
            switch newPhase {
            case .active:
                // Resume activity, refresh data
                break
            case .inactive:
                // Pause ongoing work, prepare for background
                break
            case .background:
                // Save state, release resources, schedule background tasks
                saveAppState()
                scheduleBackgroundRefresh()
            @unknown default:
                break
            }
        }
    }
}
```

You can also observe `scenePhase` from any view:

```swift
struct DashboardView: View {
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ContentView()
            .onChange(of: scenePhase) { _, newPhase in
                if newPhase == .active {
                    refreshDashboard()
                }
            }
    }
}
```

When observed at the `App` level, `scenePhase` reports the aggregate state across all scenes. When observed in a specific view, it reports that view's scene.

## Background Tasks

Use `BGTaskScheduler` to perform work when the app is in the background. Two task types are available:

| Type | Duration | Use Case |
|---|---|---|
| `BGAppRefreshTask` | ~30 seconds | Fetch latest data, update widgets |
| `BGProcessingTask` | Minutes (system-dependent) | Database maintenance, ML training, sync |

### Registration

Register task identifiers in `Info.plist` under `BGTaskSchedulerPermittedIdentifiers`:

```xml
<key>BGTaskSchedulerPermittedIdentifiers</key>
<array>
    <string>com.example.app.refresh</string>
    <string>com.example.app.sync</string>
</array>
```

Register handlers at app launch — before the end of the first `applicationDidFinishLaunching` equivalent:

```swift
@main
struct MyApp: App {
    @UIApplicationDelegateAdaptor private var appDelegate: AppDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        registerBackgroundTasks()
        return true
    }

    private func registerBackgroundTasks() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: "com.example.app.refresh",
            using: nil
        ) { task in
            guard let task = task as? BGAppRefreshTask else { return }
            self.handleAppRefresh(task)
        }

        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: "com.example.app.sync",
            using: nil
        ) { task in
            guard let task = task as? BGProcessingTask else { return }
            self.handleSync(task)
        }
    }

    private func handleAppRefresh(_ task: BGAppRefreshTask) {
        // Schedule the next refresh
        scheduleAppRefresh()

        let refreshTask = Task {
            do {
                let data = try await DataService.shared.fetchLatest()
                DataService.shared.update(with: data)
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }

        // Handle expiration — system can reclaim time at any point
        task.expirationHandler = {
            refreshTask.cancel()
        }
    }

    func scheduleAppRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: "com.example.app.refresh")
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60) // 15 min minimum
        try? BGTaskScheduler.shared.submit(request)
    }

    private func handleSync(_ task: BGProcessingTask) {
        let syncTask = Task {
            do {
                try await SyncService.shared.performFullSync()
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }

        task.expirationHandler = {
            syncTask.cancel()
        }
    }
}
```

### Scheduling

Schedule tasks when entering background:

```swift
.onChange(of: scenePhase) { _, newPhase in
    if newPhase == .background {
        appDelegate.scheduleAppRefresh()
    }
}
```

Test background tasks in the debugger with:

```
e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.example.app.refresh"]
```

## Push Notifications

### APNs Registration

```swift
class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        registerForPushNotifications()
        return true
    }

    private func registerForPushNotifications() {
        Task {
            let center = UNUserNotificationCenter.current()
            do {
                let granted = try await center.requestAuthorization(
                    options: [.alert, .sound, .badge]
                )
                if granted {
                    await MainActor.run {
                        UIApplication.shared.registerForRemoteNotifications()
                    }
                }
            } catch {
                print("Push authorization failed: \(error)")
            }
        }
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        // Send token to your server
        Task { try? await PushService.shared.register(token: token) }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        print("Failed to register for push: \(error)")
    }
}
```

### Handling Notifications

```swift
extension AppDelegate: UNUserNotificationCenterDelegate {
    // Called when notification arrives while app is in foreground
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        let userInfo = notification.request.content.userInfo
        // Process notification data
        handleNotificationPayload(userInfo)
        return [.banner, .sound, .badge]
    }

    // Called when user taps on notification
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let userInfo = response.notification.request.content.userInfo
        let actionIdentifier = response.actionIdentifier

        switch actionIdentifier {
        case UNNotificationDefaultActionIdentifier:
            // User tapped the notification itself
            handleNotificationTap(userInfo)
        case "REPLY_ACTION":
            if let textResponse = response as? UNTextInputNotificationResponse {
                handleReply(text: textResponse.userText, payload: userInfo)
            }
        default:
            handleCustomAction(actionIdentifier, payload: userInfo)
        }
    }
}
```

### Notification Categories and Actions

```swift
func registerNotificationCategories() {
    let replyAction = UNNotificationAction(
        identifier: "REPLY_ACTION",
        title: "Reply",
        options: [.authenticationRequired]
    )

    let archiveAction = UNNotificationAction(
        identifier: "ARCHIVE_ACTION",
        title: "Archive",
        options: [.destructive]
    )

    let messageCategory = UNNotificationCategory(
        identifier: "MESSAGE",
        actions: [replyAction, archiveAction],
        intentIdentifiers: [],
        options: [.customDismissAction]
    )

    UNUserNotificationCenter.current().setNotificationCategories([messageCategory])
}
```

### Silent Push Notifications

Silent push (`content-available: 1`) wakes the app in the background to fetch data. Requires the `Background Modes > Remote notifications` capability.

```swift
// AppDelegate — still the only way to receive silent push
func application(
    _ application: UIApplication,
    didReceiveRemoteNotification userInfo: [AnyHashable: Any]
) async -> UIBackgroundFetchResult {
    guard let type = userInfo["type"] as? String else {
        return .noData
    }

    do {
        switch type {
        case "content-update":
            try await ContentService.shared.syncLatest()
            return .newData
        case "badge-update":
            let count = userInfo["badge_count"] as? Int ?? 0
            await MainActor.run {
                UNUserNotificationCenter.current().setBadgeCount(count)
            }
            return .newData
        default:
            return .noData
        }
    } catch {
        return .failed
    }
}
```

APNs payload for silent push:

```json
{
    "aps": {
        "content-available": 1
    },
    "type": "content-update"
}
```

Note: Push notification delegate methods still require `UIApplicationDelegate` / `@UIApplicationDelegateAdaptor`. There is no pure SwiftUI equivalent.

## Deep Links and Universal Links

### Custom URL Schemes

Handle `myapp://path/to/content` URLs with `.onOpenURL`:

```swift
@main
struct MyApp: App {
    @State private var router = AppRouter()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(router)
                .onOpenURL { url in
                    router.handle(url)
                }
        }
    }
}

@Observable
class AppRouter {
    var selectedTab: Tab = .home
    var navigationPath = NavigationPath()

    func handle(_ url: URL) {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return
        }

        // myapp://product/123
        // myapp://settings/notifications
        let pathComponents = components.path.split(separator: "/").map(String.init)

        switch pathComponents.first {
        case "product":
            if let id = pathComponents.dropFirst().first {
                selectedTab = .shop
                navigationPath.append(ProductDestination(id: id))
            }
        case "settings":
            selectedTab = .settings
            if let section = pathComponents.dropFirst().first {
                navigationPath.append(SettingsDestination(section: section))
            }
        default:
            break
        }
    }
}
```

### Universal Links

Universal Links open HTTPS URLs directly in your app. Requires Associated Domains entitlement and a server-hosted `apple-app-site-association` file.

1. Add the Associated Domains capability in Xcode: `applinks:example.com`

2. Host `/.well-known/apple-app-site-association` on your domain:

```json
{
    "applinks": {
        "apps": [],
        "details": [
            {
                "appIDs": ["TEAMID.com.example.myapp"],
                "components": [
                    { "/": "/product/*", "comment": "Product pages" },
                    { "/": "/user/*", "comment": "User profiles" }
                ]
            }
        ]
    }
}
```

3. Handle in SwiftUI with the same `.onOpenURL`:

```swift
.onOpenURL { url in
    // Universal Links arrive as full HTTPS URLs
    // https://example.com/product/123
    router.handle(url)
}
```

Both custom URL schemes and Universal Links are delivered through `.onOpenURL`. Differentiate by scheme:

```swift
func handle(_ url: URL) {
    if url.scheme == "https" {
        handleUniversalLink(url)
    } else {
        handleDeepLink(url)
    }
}
```

## Handoff and NSUserActivity

Handoff lets users continue an activity across Apple devices signed into the same iCloud account.

```swift
struct ArticleView: View {
    let article: Article

    var body: some View {
        ScrollView {
            Text(article.body)
        }
        .userActivity("com.example.app.viewArticle") { activity in
            activity.title = article.title
            activity.isEligibleForHandoff = true
            activity.isEligibleForSearch = true  // Spotlight indexing
            activity.userInfo = ["articleID": article.id.uuidString]
            activity.webpageURL = URL(string: "https://example.com/article/\(article.id)")
        }
    }
}
```

Receive continued activities:

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onContinueUserActivity("com.example.app.viewArticle") { activity in
                    guard let articleID = activity.userInfo?["articleID"] as? String else {
                        return
                    }
                    router.navigate(to: .article(id: articleID))
                }
        }
    }
}
```

Register activity types in `Info.plist` under `NSUserActivityTypes`:

```xml
<key>NSUserActivityTypes</key>
<array>
    <string>com.example.app.viewArticle</string>
</array>
```

## App Intents Integration

Expose app functionality to Siri and Shortcuts via App Intents. This is a brief overview — see `widgets-app-intents.md` for full coverage.

```swift
import AppIntents

struct OpenArticleIntent: AppIntent {
    static var title: LocalizedStringResource = "Open Article"
    static var description: IntentDescription = "Opens a specific article in the app"
    static var openAppWhenRun = true

    @Parameter(title: "Article")
    var article: ArticleEntity

    @MainActor
    func perform() async throws -> some IntentResult {
        AppRouter.shared.navigate(to: .article(id: article.id))
        return .result()
    }
}

struct ArticleEntity: AppEntity {
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Article")
    static var defaultQuery = ArticleQuery()

    var id: String
    var title: String

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(title)")
    }
}
```

App Intents declared this way automatically appear in Shortcuts, Spotlight, and Siri without additional configuration.

## State Restoration

### @SceneStorage

`@SceneStorage` persists simple values per-scene, surviving app termination. Works like `@AppStorage` but scoped to the scene instance.

```swift
struct ContentView: View {
    @SceneStorage("selectedTab") private var selectedTab: String = "home"
    @SceneStorage("draftText") private var draftText: String = ""

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tag("home")
            ComposeView(text: $draftText)
                .tag("compose")
            SettingsView()
                .tag("settings")
        }
    }
}
```

Supported types: `Bool`, `Int`, `Double`, `String`, `URL`, `Data`, and `RawRepresentable` where `RawValue` is one of these.

### Restoring Navigation State

Combine `@SceneStorage` with `Codable` navigation paths:

```swift
struct ContentView: View {
    @SceneStorage("navigationPath") private var navigationData: Data?
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            HomeView()
                .navigationDestination(for: ProductDestination.self) { dest in
                    ProductDetailView(id: dest.id)
                }
                .navigationDestination(for: SettingsDestination.self) { dest in
                    SettingsDetailView(section: dest.section)
                }
        }
        .onChange(of: path) { _, newPath in
            // Persist on every navigation change
            navigationData = try? JSONEncoder().encode(newPath.codable)
        }
        .onAppear {
            // Restore on launch
            if let data = navigationData,
               let restored = try? JSONDecoder().decode(
                   NavigationPath.CodableRepresentation.self, from: data
               ) {
                path = NavigationPath(restored)
            }
        }
    }
}
```

All types used with `.navigationDestination` must conform to both `Hashable` and `Codable` for `NavigationPath.CodableRepresentation` to work.

## Launch Optimization

### Pre-main Optimization

Pre-main time (before `main()` executes) is affected by:

| Factor | Impact | Mitigation |
|---|---|---|
| Dynamic frameworks | Each adds load time | Merge frameworks, use static linking |
| `+load` / `__attribute__((constructor))` | Runs before main | Eliminate or defer to first use |
| Objective-C class registration | Proportional to class count | Reduce unused ObjC classes |
| Dylib count | Each adds linker overhead | Target < 6 non-system dylibs |

Measure with: `DYLD_PRINT_STATISTICS=1` environment variable in scheme settings.

### Post-main Optimization

```swift
@main
struct MyApp: App {
    // Lazy initialization — don't do heavy work at init
    @State private var dataStore = DataStore() // Keep init lightweight

    var body: some Scene {
        WindowGroup {
            ContentView()
                .task {
                    // Defer expensive setup to after first frame
                    await dataStore.loadInitialData()
                    await AnalyticsService.shared.initialize()
                }
        }
    }
}
```

Key principles:

- **Defer work** — do not initialize services, load databases, or make network calls during app init. Use `.task` or `.onAppear`.
- **Lazy properties** — use `lazy var` or `nonisolated(unsafe)` statics for heavy singletons.
- **Reduce storyboard/XIB usage** — each loaded at launch adds time. SwiftUI views are lightweight by comparison.
- **Profile with Instruments** — use the App Launch template to identify bottlenecks. Target < 400ms total launch time.
- **Avoid synchronous file I/O on launch** — `UserDefaults.standard` is fine, but loading large files or databases should be async.

### Warm Launch Optimization

```swift
// Cache critical data in memory, refresh in background
@Observable
class DataStore {
    private(set) var cachedItems: [Item] = []

    func loadInitialData() async {
        // Load from local cache first (fast)
        cachedItems = await LocalCache.shared.loadItems()

        // Then refresh from network (background)
        Task.detached(priority: .utility) {
            let fresh = try? await APIClient.shared.fetchItems()
            if let fresh {
                await MainActor.run { self.cachedItems = fresh }
                await LocalCache.shared.save(fresh)
            }
        }
    }
}
```

## UIKit App Delegate Interop

Use `@UIApplicationDelegateAdaptor` when you need `UIApplicationDelegate` callbacks that have no SwiftUI equivalent.

### When You Still Need an App Delegate

| Use Case | Why |
|---|---|
| Push notification token registration | `didRegisterForRemoteNotificationsWithDeviceToken` has no SwiftUI API |
| Silent push handling | `didReceiveRemoteNotification` has no SwiftUI API |
| Third-party SDK initialization | Many SDKs require setup in `didFinishLaunchingWithOptions` |
| Background task registration | `BGTaskScheduler.register` must be called early at launch |
| URL session background completion | `handleEventsForBackgroundURLSession` |
| Shortcut items (3D Touch / long press) | `performActionFor shortcutItem` |

```swift
@main
struct MyApp: App {
    @UIApplicationDelegateAdaptor private var appDelegate: AppDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // Third-party SDK setup
        FirebaseApp.configure()
        registerBackgroundTasks()
        registerNotificationCategories()
        return true
    }

    // Orientation lock (no SwiftUI equivalent)
    func application(
        _ application: UIApplication,
        supportedInterfaceOrientationsFor window: UIWindow?
    ) -> UIInterfaceOrientationMask {
        return OrientationManager.shared.allowedOrientations
    }
}
```

### Sharing State Between App Delegate and SwiftUI

Make the delegate observable so SwiftUI views can react to its state:

```swift
@Observable
class AppDelegate: NSObject, UIApplicationDelegate {
    var pushToken: String?

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        pushToken = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
    }
}

// Access in views
struct SettingsView: View {
    @Environment(AppDelegate.self) private var appDelegate

    var body: some View {
        if let token = appDelegate.pushToken {
            Text("Push registered: \(token.prefix(8))...")
        }
    }
}
```

For macOS, use `@NSApplicationDelegateAdaptor` with `NSApplicationDelegate`.

## Memory Management

### Handling Memory Warnings

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onReceive(
                    NotificationCenter.default.publisher(
                        for: UIApplication.didReceiveMemoryWarningNotification
                    )
                ) { _ in
                    ImageCacheManager.shared.clearCache()
                    DataStore.shared.purgeNonEssentialData()
                }
        }
    }
}
```

Or via the app delegate:

```swift
class AppDelegate: NSObject, UIApplicationDelegate {
    func applicationDidReceiveMemoryWarning(_ application: UIApplication) {
        URLCache.shared.removeAllCachedResponses()
        ImageCacheManager.shared.evictAll()
    }
}
```

### Image Caching Strategies

```swift
/// Simple NSCache-based image cache with memory pressure awareness
actor ImageCacheManager {
    static let shared = ImageCacheManager()

    private let cache = NSCache<NSString, UIImage>()
    private let costLimit: Int = 100 * 1024 * 1024 // 100 MB

    private init() {
        cache.totalCostLimit = costLimit
        // NSCache automatically evicts under memory pressure,
        // but explicit limits help prevent reaching that point.
    }

    func image(for key: String) -> UIImage? {
        cache.object(forKey: key as NSString)
    }

    func store(_ image: UIImage, for key: String) {
        let cost = Int(image.size.width * image.size.height * image.scale * 4)
        cache.setObject(image, forKey: key as NSString, cost: cost)
    }

    func clearCache() {
        cache.removeAllObjects()
    }
}
```

### Managing Large Resources

```swift
// Downscale images to display size — avoid holding full-resolution in memory
func downsampledImage(at url: URL, to pointSize: CGSize, scale: CGFloat) -> UIImage? {
    let maxDimension = max(pointSize.width, pointSize.height) * scale
    let options: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,
        kCGImageSourceShouldCacheImmediately: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceThumbnailMaxPixelSize: maxDimension
    ]

    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let cgImage = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
    else {
        return nil
    }

    return UIImage(cgImage: cgImage)
}
```

### Key Memory Management Practices

| Practice | Rationale |
|---|---|
| Use `NSCache` over `Dictionary` for caches | `NSCache` auto-evicts under memory pressure |
| Downscale images to display size | Full-res images waste memory (e.g., 12MP photo = ~48 MB uncompressed) |
| Release resources on `.background` | System may terminate background apps under pressure |
| Use `autoreleasepool` in tight loops | Prevents temporary object buildup in Obj-C bridged code |
| Avoid retain cycles in closures | Use `[weak self]` when closure outlives the capturing context |
| Profile with Instruments (Leaks, Allocations) | Detect leaks and unexpected growth early |

```swift
// Autoreleasepool for tight loops with bridged objects
func processLargeDataSet(_ items: [RawData]) -> [ProcessedItem] {
    var results: [ProcessedItem] = []
    results.reserveCapacity(items.count)

    for chunk in items.chunked(into: 1000) {
        autoreleasepool {
            let processed = chunk.map { transform($0) }
            results.append(contentsOf: processed)
        }
    }
    return results
}
```

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Heavy work in `App.init` | Defer to `.task` — keep init lightweight |
| Not handling scene phase `.background` | Save state and schedule background tasks |
| Forgetting `BGTaskSchedulerPermittedIdentifiers` in Info.plist | Tasks silently fail to register without it |
| Registering background tasks too late | Must register before `didFinishLaunchingWithOptions` returns |
| Not testing background tasks | Use debugger simulation command in Xcode |
| Missing Associated Domains entitlement | Universal Links fail silently |
| Not setting `UNUserNotificationCenter.delegate` early | Notifications received before delegate is set are lost |
| Using `@AppStorage` for scene-specific state | Use `@SceneStorage` — it scopes per scene instance |
| Force-loading all data at launch | Load cached/minimal data first, fetch fresh data async |
| Ignoring memory warnings | App will be terminated; clear caches proactively |
