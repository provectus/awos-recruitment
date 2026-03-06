# watchOS Patterns Reference

## Contents
- App structure (standalone vs companion, `@main` entry point, `NavigationStack`)
- Complications (WidgetKit-based, widget families, timeline providers)
- Workout sessions (`HKWorkoutSession`, `HKLiveWorkoutBuilder`, real-time metrics)
- Digital Crown (`.digitalCrownRotation()`, custom scrolling)
- Notifications (custom views, actionable notifications, categories)
- Watch Connectivity (`WCSession`, data transfer, background transfers)
- Background refresh (`WKApplicationRefreshBackgroundTask`, scheduling)
- Health and sensors (HealthKit, heart rate, accelerometer, gyroscope)
- UI patterns (list navigation, `TabView`, compact layouts, `.containerBackground`)
- Smart Stack (widget recommendations)
- Limitations (memory, background time, screen sizes)

## App Structure

### Standalone vs companion

watchOS 10+ apps are standalone by default. A companion iPhone app is optional. The watch app has its own bundle identifier, lifecycle, and App Store presence.

```swift
// Standalone watchOS app entry point
import SwiftUI

@main
struct MyWatchApp: App {
    @WKApplicationDelegateAdaptor(AppDelegate.self) var delegate

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                ContentView()
            }
        }
    }
}

final class AppDelegate: NSObject, WKApplicationDelegate {
    func applicationDidFinishLaunching() {
        // Setup on launch
    }
}
```

### NavigationStack on watch

watchOS 10+ uses `NavigationStack` with value-based navigation, replacing the deprecated `NavigationLink(destination:)` pattern.

```swift
struct ContentView: View {
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            List {
                NavigationLink("Workout", value: Route.workout)
                NavigationLink("Settings", value: Route.settings)
            }
            .navigationDestination(for: Route.self) { route in
                switch route {
                case .workout: WorkoutView()
                case .settings: SettingsView()
                }
            }
        }
    }
}

enum Route: Hashable {
    case workout
    case settings
}
```

## Complications

### WidgetKit-based complications (watchOS 10+)

watchOS 10 migrated complications to WidgetKit. ClockKit is deprecated.

```swift
import WidgetKit
import SwiftUI

struct StepsComplication: Widget {
    let kind: String = "StepsComplication"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: StepsProvider()) { entry in
            StepsComplicationView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Steps")
        .description("Shows your daily step count.")
        .supportedFamilies([
            .accessoryCircular,
            .accessoryRectangular,
            .accessoryInline,
            .accessoryCorner
        ])
    }
}
```

### Widget families for watch

| Family | Shape | Typical content |
|---|---|---|
| `.accessoryCircular` | Small circle | Gauge, icon with number |
| `.accessoryRectangular` | Wide rectangle | Multi-line text, small chart |
| `.accessoryInline` | Single text line | Short status text |
| `.accessoryCorner` | Corner arc (watchOS) | Gauge along bezel edge |

### Timeline providers

```swift
struct StepsProvider: TimelineProvider {
    func placeholder(in context: Context) -> StepsEntry {
        StepsEntry(date: .now, steps: 5000)
    }

    func getSnapshot(in context: Context, completion: @escaping (StepsEntry) -> Void) {
        completion(StepsEntry(date: .now, steps: 5000))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<StepsEntry>) -> Void) {
        let currentSteps = fetchCurrentSteps()
        let entry = StepsEntry(date: .now, steps: currentSteps)
        // Refresh in 15 minutes
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: .now)!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }
}

struct StepsEntry: TimelineEntry {
    let date: Date
    let steps: Int
}
```

## Workout Sessions

### HKWorkoutSession and HKLiveWorkoutBuilder

```swift
import HealthKit

final class WorkoutManager: NSObject, ObservableObject {
    let healthStore = HKHealthStore()
    var session: HKWorkoutSession?
    var builder: HKLiveWorkoutBuilder?

    @Published var heartRate: Double = 0
    @Published var activeCalories: Double = 0
    @Published var elapsedTime: TimeInterval = 0

    func startWorkout(type: HKWorkoutActivityType) async throws {
        let config = HKWorkoutConfiguration()
        config.activityType = type
        config.locationType = .outdoor

        session = try HKWorkoutSession(healthStore: healthStore, configuration: config)
        builder = session?.associatedWorkoutBuilder()

        session?.delegate = self
        builder?.delegate = self
        builder?.dataSource = HKLiveWorkoutDataSource(
            healthStore: healthStore,
            workoutConfiguration: config
        )

        let start = Date()
        session?.startActivity(with: start)
        try await builder?.beginCollection(at: start)
    }

    func pauseWorkout() {
        session?.pause()
    }

    func resumeWorkout() {
        session?.resume()
    }

    func endWorkout() async throws {
        session?.end()
        try await builder?.endCollection(at: .now)
        try await builder?.finishWorkout()
    }
}

extension WorkoutManager: HKWorkoutSessionDelegate {
    func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didChangeTo toState: HKWorkoutSessionState,
        from fromState: HKWorkoutSessionState,
        date: Date
    ) {
        // Handle state transitions
    }

    func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didFailWithError error: Error
    ) {
        // Handle failure
    }
}

extension WorkoutManager: HKLiveWorkoutBuilderDelegate {
    func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) { }

    func workoutBuilder(
        _ workoutBuilder: HKLiveWorkoutBuilder,
        didCollectDataOf collectedTypes: Set<HKSampleType>
    ) {
        for type in collectedTypes {
            guard let quantityType = type as? HKQuantityType else { continue }
            let statistics = workoutBuilder.statistics(for: quantityType)

            DispatchQueue.main.async {
                switch quantityType {
                case HKQuantityType(.heartRate):
                    let bpm = statistics?.mostRecentQuantity()?
                        .doubleValue(for: .count().unitDivided(by: .minute()))
                    self.heartRate = bpm ?? 0
                case HKQuantityType(.activeEnergyBurned):
                    let kcal = statistics?.sumQuantity()?
                        .doubleValue(for: .kilocalorie())
                    self.activeCalories = kcal ?? 0
                default:
                    break
                }
            }
        }
    }
}
```

### Common workout types

| Activity | `HKWorkoutActivityType` |
|---|---|
| Running | `.running` |
| Cycling | `.cycling` |
| Swimming | `.swimming` |
| HIIT | `.highIntensityIntervalTraining` |
| Yoga | `.yoga` |
| Walking | `.walking` |
| Strength | `.traditionalStrengthTraining` |

## Digital Crown

### `.digitalCrownRotation()`

```swift
struct CrownScrollView: View {
    @State private var crownValue: Double = 0.0
    @State private var isCrownIdle: Bool = true

    var body: some View {
        ZStack {
            Circle()
                .fill(.blue.opacity(0.3))
                .scaleEffect(1.0 + crownValue / 10.0)

            Text("\(Int(crownValue))")
                .font(.title2)
        }
        .focusable()
        .digitalCrownRotation(
            $crownValue,
            from: 0.0,
            through: 100.0,
            by: 1.0,
            sensitivity: .medium,
            isContinuous: false,
            isHapticFeedbackEnabled: true
        )
    }
}
```

### Custom scrolling with detents

```swift
struct DetentCrownView: View {
    @State private var selectedIndex: Double = 0.0
    let items = ["Low", "Medium", "High", "Max"]

    var body: some View {
        VStack {
            Text(items[Int(selectedIndex)])
                .font(.headline)
            Text("Rotate crown to select")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .focusable()
        .digitalCrownRotation(
            $selectedIndex,
            from: 0,
            through: Double(items.count - 1),
            by: 1.0,
            sensitivity: .low,
            isContinuous: false,
            isHapticFeedbackEnabled: true
        )
    }
}
```

## Notifications

### Custom notification view

```swift
struct NotificationView: View {
    let title: String
    let message: String
    let date: Date

    var body: some View {
        VStack(alignment: .leading) {
            Text(title)
                .font(.headline)
            Text(message)
                .font(.body)
            Text(date, style: .time)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}
```

### Actionable notifications

Register categories with actions in the app delegate:

```swift
import UserNotifications

final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    func registerCategories() {
        let replyAction = UNNotificationAction(
            identifier: "REPLY",
            title: "Reply",
            options: .foreground
        )
        let dismissAction = UNNotificationAction(
            identifier: "DISMISS",
            title: "Dismiss",
            options: .destructive
        )

        let messageCategory = UNNotificationCategory(
            identifier: "MESSAGE",
            actions: [replyAction, dismissAction],
            intentIdentifiers: [],
            options: .customDismissAction
        )

        UNUserNotificationCenter.current().setNotificationCategories([messageCategory])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        switch response.actionIdentifier {
        case "REPLY":
            // Handle reply
            break
        case "DISMISS":
            // Handle dismiss
            break
        default:
            break
        }
    }
}
```

### Scheduling a local notification

```swift
func scheduleReminder() {
    let content = UNMutableNotificationContent()
    content.title = "Workout Reminder"
    content.body = "Time for your afternoon run."
    content.categoryIdentifier = "MESSAGE"
    content.sound = .default

    let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 3600, repeats: false)
    let request = UNNotificationRequest(identifier: "workout-reminder", content: content, trigger: trigger)

    UNUserNotificationCenter.current().add(request)
}
```

## Watch Connectivity

### WCSession setup

```swift
import WatchConnectivity

final class ConnectivityManager: NSObject, ObservableObject, WCSessionDelegate {
    static let shared = ConnectivityManager()

    override init() {
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    // Required delegate methods
    func session(
        _ session: WCSession,
        activationDidCompleteWith activationState: WCSessionActivationState,
        error: Error?
    ) { }

    #if os(iOS)
    func sessionDidBecomeInactive(_ session: WCSession) { }
    func sessionDidDeactivate(_ session: WCSession) {
        WCSession.default.activate()
    }
    #endif
}
```

### Data transfer methods

| Method | Delivery | Use case |
|---|---|---|
| `sendMessage(_:replyHandler:)` | Immediate (both apps active) | Real-time interaction |
| `updateApplicationContext(_:)` | Latest-only, queued | App state sync (only newest value kept) |
| `transferUserInfo(_:)` | Queued FIFO | All messages must arrive |
| `transferFile(_:metadata:)` | Background file transfer | Large data, images |
| `transferCurrentComplicationUserInfo(_:)` | High priority, limited budget | Complication updates from phone |

```swift
// Send a message (requires counterpart to be reachable)
func sendHeartRate(_ bpm: Double) {
    guard WCSession.default.isReachable else { return }
    WCSession.default.sendMessage(
        ["heartRate": bpm],
        replyHandler: nil,
        errorHandler: { error in
            print("Send failed: \(error.localizedDescription)")
        }
    )
}

// Update application context (latest-wins)
func syncSettings(_ settings: [String: Any]) {
    try? WCSession.default.updateApplicationContext(settings)
}

// Receive on counterpart
func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {
    if let bpm = message["heartRate"] as? Double {
        DispatchQueue.main.async { self.latestHeartRate = bpm }
    }
}

func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {
    // Process updated settings
}
```

### Complication updates from phone

```swift
// On iPhone — push data to watch complication (limited to 50/day)
func pushComplicationUpdate(steps: Int) {
    guard WCSession.default.isComplicationEnabled else { return }
    WCSession.default.transferCurrentComplicationUserInfo(["steps": steps])
}
```

## Background Refresh

### WKApplicationRefreshBackgroundTask

```swift
final class AppDelegate: NSObject, WKApplicationDelegate {
    func handle(_ backgroundTasks: Set<WKRefreshBackgroundTask>) {
        for task in backgroundTasks {
            switch task {
            case let refreshTask as WKApplicationRefreshBackgroundTask:
                // Fetch new data
                fetchLatestData { success in
                    // Schedule next refresh
                    self.scheduleNextRefresh()
                    refreshTask.setTaskCompletedWithSnapshot(success)
                }

            case let urlTask as WKURLSessionRefreshBackgroundTask:
                // Handle background URL session completion
                urlTask.setTaskCompletedWithSnapshot(false)

            case let snapshotTask as WKSnapshotRefreshBackgroundTask:
                snapshotTask.setTaskCompleted(
                    restoredDefaultState: true,
                    estimatedSnapshotExpiration: .distantFuture,
                    userInfo: nil
                )

            default:
                task.setTaskCompletedWithSnapshot(false)
            }
        }
    }

    func scheduleNextRefresh() {
        let fireDate = Date(timeIntervalSinceNow: 15 * 60) // 15 minutes
        WKApplication.shared().scheduleBackgroundRefresh(
            withPreferredDate: fireDate,
            userInfo: nil
        ) { error in
            if let error {
                print("Schedule failed: \(error.localizedDescription)")
            }
        }
    }
}
```

### Background URLSession

```swift
func startBackgroundDownload(url: URL) {
    let config = URLSessionConfiguration.background(
        withIdentifier: "com.example.watchapp.background"
    )
    config.isDiscretionary = false
    config.sessionSendsLaunchEvents = true

    let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    let task = session.downloadTask(with: url)
    task.resume()
}
```

The system wakes your app via `WKURLSessionRefreshBackgroundTask` when the download completes.

## Health and Sensors

### HealthKit authorization

```swift
func requestAuthorization() async throws {
    let typesToRead: Set<HKObjectType> = [
        HKQuantityType(.heartRate),
        HKQuantityType(.stepCount),
        HKQuantityType(.activeEnergyBurned),
        HKQuantityType(.oxygenSaturation)
    ]

    let typesToWrite: Set<HKSampleType> = [
        HKQuantityType(.activeEnergyBurned)
    ]

    try await healthStore.requestAuthorization(toShare: typesToWrite, read: typesToRead)
}
```

### Querying heart rate

```swift
func fetchLatestHeartRate() async throws -> Double? {
    let heartRateType = HKQuantityType(.heartRate)
    let sortDescriptor = SortDescriptor(\HKQuantitySample.startDate, order: .reverse)
    let descriptor = HKSampleQueryDescriptor(
        predicates: [.quantitySample(type: heartRateType)],
        sortDescriptors: [sortDescriptor],
        limit: 1
    )

    let results = try await descriptor.result(for: healthStore)
    let bpmUnit = HKUnit.count().unitDivided(by: .minute())
    return results.first?.quantity.doubleValue(for: bpmUnit)
}
```

### CoreMotion — accelerometer and gyroscope

```swift
import CoreMotion

final class MotionManager: ObservableObject {
    private let manager = CMMotionManager()

    @Published var acceleration: CMAcceleration = .init()
    @Published var rotationRate: CMRotationRate = .init()

    func startAccelerometer() {
        guard manager.isAccelerometerAvailable else { return }
        manager.accelerometerUpdateInterval = 0.1
        manager.startAccelerometerUpdates(to: .main) { [weak self] data, _ in
            guard let data else { return }
            self?.acceleration = data.acceleration
        }
    }

    func startGyroscope() {
        guard manager.isGyroAvailable else { return }
        manager.gyroUpdateInterval = 0.1
        manager.startGyroUpdates(to: .main) { [weak self] data, _ in
            guard let data else { return }
            self?.rotationRate = data.rotationRate
        }
    }

    func stopAll() {
        manager.stopAccelerometerUpdates()
        manager.stopGyroUpdates()
    }
}
```

Always stop sensor updates when no longer needed to preserve battery.

## UI Patterns

### List-based navigation

Lists are the primary navigation pattern on watchOS. Keep rows compact.

```swift
struct ActivityListView: View {
    var body: some View {
        List {
            Section("Recent") {
                ForEach(recentActivities) { activity in
                    NavigationLink(value: activity) {
                        HStack {
                            Image(systemName: activity.icon)
                                .foregroundStyle(activity.color)
                            VStack(alignment: .leading) {
                                Text(activity.name)
                                    .font(.headline)
                                Text(activity.duration, format: .units(allowed: [.hours, .minutes]))
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
        }
    }
}
```

### TabView with page style

```swift
struct MainView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            MetricsView()
                .tag(0)
            NowPlayingView()
                .tag(1)
            ControlsView()
                .tag(2)
        }
        .tabViewStyle(.verticalPage)  // watchOS 10+: vertical paging
    }
}
```

watchOS 10 introduced `.verticalPage` style. Use `.verticalPage(transitionStyle: .blur)` for a blur transition between pages.

### Compact layouts

```swift
struct CompactMetricView: View {
    let value: String
    let unit: String
    let label: String

    var body: some View {
        VStack(spacing: 2) {
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(value)
                    .font(.title2.monospacedDigit())
                Text(unit)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}
```

### `.containerBackground`

watchOS 10+ requires `.containerBackground` for full-screen background styling in `NavigationStack` and `TabView` content.

```swift
struct WorkoutActiveView: View {
    var body: some View {
        VStack {
            Text("Running")
                .font(.title3)
            Text("5:32")
                .font(.system(size: 48, weight: .bold, design: .rounded).monospacedDigit())
        }
        .containerBackground(
            Color.green.gradient,
            for: .navigation
        )
    }
}

// For TabView pages
struct MetricsPage: View {
    var body: some View {
        Text("150 BPM")
            .containerBackground(
                .red.gradient.opacity(0.3),
                for: .tabView
            )
    }
}
```

## Smart Stack

### Widget recommendations

Widgets can suggest when they should appear in the Smart Stack using relevance values.

```swift
struct StepsProvider: AppIntentTimelineProvider {
    // ... other methods ...

    func timeline(for configuration: StepsIntent, in context: Context) async -> Timeline<StepsEntry> {
        let entry = StepsEntry(date: .now, steps: currentSteps)

        // Higher relevance = more likely to appear at the top of Smart Stack
        let relevance: TimelineEntryRelevance? = if currentSteps < 2000 {
            // Morning with low steps — remind user
            TimelineEntryRelevance(score: 80)
        } else {
            TimelineEntryRelevance(score: 20)
        }

        var entryWithRelevance = entry
        entryWithRelevance.relevance = relevance

        let timeline = Timeline(entries: [entryWithRelevance], policy: .after(.now.addingTimeInterval(900)))
        return timeline
    }
}

struct StepsEntry: TimelineEntry {
    let date: Date
    let steps: Int
    var relevance: TimelineEntryRelevance?
}
```

Key points:
- Score ranges from `0` (low) to `100` (high).
- The system uses relevance alongside user behavior to rank widgets.
- Widgets can also provide a `duration` to indicate how long the relevance score applies.

## Limitations

### Memory budget

watchOS apps typically have 30-50 MB of usable memory depending on the device. The system terminates apps that exceed the limit without warning.

- Avoid loading large images or datasets into memory at once.
- Use pagination and streaming for large data sets.
- Profile with Instruments on a real device — the simulator does not enforce memory limits.

### Background execution

- Background tasks get approximately **30 seconds** of execution time.
- `WKApplicationRefreshBackgroundTask` is budgeted by the system — scheduling more frequently than every 15 minutes is not guaranteed.
- Extended runtime sessions (for workouts, mindfulness, physical therapy) are the only way to get long-running background time.

### No web views

`WKWebView` and `SFSafariViewController` are not available on watchOS. Render content natively. If you need to display rich text, use `AttributedString` and SwiftUI `Text`.

### Screen sizes

| Device | Screen width | Resolution |
|---|---|---|
| Apple Watch SE (40mm) | 162pt | 324 x 394 |
| Apple Watch SE (44mm) | 176pt | 352 x 430 |
| Apple Watch Series 9/10 (41mm) | 170pt | 352 x 430 |
| Apple Watch Series 9/10 (45mm) | 185pt | 396 x 484 |
| Apple Watch Ultra 2 (49mm) | 205pt | 410 x 502 |

- Always use dynamic type and scalable layouts.
- Test with the smallest and largest screen sizes.
- Avoid hardcoded dimensions — use `.frame(maxWidth: .infinity)` and relative sizing.

### Other constraints

- **No third-party web browsers or web views** — content must be native.
- **No background audio recording** — microphone access is foreground only.
- **Limited networking** — prefer the paired iPhone for heavy network tasks when the phone is nearby. The watch uses Wi-Fi or LTE when the phone is unavailable.
- **No MapKit interactivity** — `Map` view is available but limited compared to iOS.
- **Storage** — keep local data minimal. watchOS devices have limited disk space shared across all apps.
