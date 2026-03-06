# Widgets & App Intents Reference

## Contents
- WidgetKit fundamentals (`Widget`, `TimelineProvider`, `TimelineEntry`, `WidgetFamily`)
- Static vs configurable widgets (`StaticConfiguration`, `AppIntentConfiguration`)
- Timeline management (`TimelineReloadPolicy`, `WidgetCenter`)
- Interactive widgets (iOS 17+ — `Button`, `Toggle`, `AppIntent` in widgets)
- Live Activities (`ActivityKit`, `ActivityAttributes`, Dynamic Island, Lock Screen)
- App Intents framework (`AppIntent`, `@Parameter`, `IntentDialog`, `IntentResult`)
- App Shortcuts (`AppShortcutsProvider`, phrases, Spotlight/Siri integration)
- Shortcuts integration (parameterized intents, custom UI)
- Widgets across platforms (iOS, iPadOS, macOS, watchOS, StandBy, Smart Stack)
- Data sharing (App Groups, shared `UserDefaults`, shared CoreData/SwiftData)
- Best practices (performance, timeline strategy, snapshots, placeholders)

## WidgetKit Fundamentals

A widget is a SwiftUI view driven by a timeline of entries. The system requests entries from your `TimelineProvider` and renders them at scheduled times.

### Widget Protocol

```swift
@main
struct MyWidget: Widget {
    let kind: String = "MyWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: MyTimelineProvider()) { entry in
            MyWidgetEntryView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("My Widget")
        .description("Shows important information at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .systemExtraLarge])
    }
}
```

### TimelineEntry and TimelineProvider

```swift
struct MyEntry: TimelineEntry {
    let date: Date
    let title: String
    let value: Int
}

struct MyTimelineProvider: TimelineProvider {
    // Shown while the widget is loading for the first time
    func placeholder(in context: Context) -> MyEntry {
        MyEntry(date: .now, title: "Placeholder", value: 0)
    }

    // Used for the widget gallery preview and transient displays
    func getSnapshot(in context: Context, completion: @escaping (MyEntry) -> Void) {
        let entry = MyEntry(date: .now, title: "Snapshot", value: 42)
        completion(entry)
    }

    // Provides the actual timeline of entries
    func getTimeline(in context: Context, completion: @escaping (Timeline<MyEntry>) -> Void) {
        var entries: [MyEntry] = []
        let now = Date.now
        for offset in 0..<5 {
            let entryDate = Calendar.current.date(byAdding: .hour, value: offset, to: now)!
            entries.append(MyEntry(date: entryDate, title: "Update", value: offset * 10))
        }
        let timeline = Timeline(entries: entries, policy: .atEnd)
        completion(timeline)
    }
}
```

### Async TimelineProvider (preferred for iOS 17+)

```swift
struct MyAsyncProvider: TimelineProvider {
    func placeholder(in context: Context) -> MyEntry {
        MyEntry(date: .now, title: "Placeholder", value: 0)
    }

    func getSnapshot(in context: Context) async -> MyEntry {
        let data = await fetchLatestData()
        return MyEntry(date: .now, title: data.title, value: data.value)
    }

    func getTimeline(in context: Context) async -> Timeline<MyEntry> {
        let data = await fetchLatestData()
        let entry = MyEntry(date: .now, title: data.title, value: data.value)
        return Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(3600)))
    }
}
```

### WidgetFamily Sizes

| Family | Size | Platform |
|---|---|---|
| `.systemSmall` | Square, tap-only | iOS, iPadOS, macOS |
| `.systemMedium` | Wide rectangle | iOS, iPadOS, macOS |
| `.systemLarge` | Tall rectangle | iOS, iPadOS, macOS |
| `.systemExtraLarge` | Full width (iPad) | iPadOS |
| `.accessoryCircular` | Circular (Lock Screen) | iOS, watchOS |
| `.accessoryRectangular` | Rectangular (Lock Screen) | iOS, watchOS |
| `.accessoryInline` | Single line of text | iOS, watchOS |

Use `@Environment(\.widgetFamily)` to adapt layout per size:

```swift
struct MyWidgetEntryView: View {
    var entry: MyEntry
    @Environment(\.widgetFamily) var family

    var body: some View {
        switch family {
        case .systemSmall:
            CompactView(entry: entry)
        case .systemMedium:
            MediumView(entry: entry)
        case .systemLarge, .systemExtraLarge:
            DetailedView(entry: entry)
        case .accessoryCircular:
            GaugeView(entry: entry)
        case .accessoryRectangular:
            RectangularView(entry: entry)
        case .accessoryInline:
            Text("\(entry.title): \(entry.value)")
        @unknown default:
            Text(entry.title)
        }
    }
}
```

### Widget Bundle

When providing multiple widgets from one extension:

```swift
@main
struct MyWidgetBundle: WidgetBundle {
    var body: some Widget {
        StatusWidget()
        StatsWidget()
        QuickActionWidget()
    }
}
```

## Static vs Configurable Widgets

### StaticConfiguration

No user-configurable options. Content is determined entirely by the app:

```swift
StaticConfiguration(kind: "StatusWidget", provider: StatusProvider()) { entry in
    StatusWidgetView(entry: entry)
        .containerBackground(.fill.tertiary, for: .widget)
}
```

### AppIntentConfiguration (iOS 17+)

Allows the user to configure the widget using an App Intent:

```swift
struct SelectCategoryIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Select Category"
    static var description: IntentDescription = "Choose which category to display."

    @Parameter(title: "Category")
    var category: CategoryEntity

    @Parameter(title: "Show Details", default: true)
    var showDetails: Bool
}

struct ConfigurableWidget: Widget {
    let kind = "ConfigurableWidget"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(
            kind: kind,
            intent: SelectCategoryIntent.self,
            provider: CategoryTimelineProvider()
        ) { entry in
            CategoryWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Category Widget")
        .description("Displays items from a chosen category.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
```

### AppIntentTimelineProvider

Used with `AppIntentConfiguration` to receive the user's configuration:

```swift
struct CategoryTimelineProvider: AppIntentTimelineProvider {
    typealias Intent = SelectCategoryIntent
    typealias Entry = CategoryEntry

    func placeholder(in context: Context) -> CategoryEntry {
        CategoryEntry(date: .now, categoryName: "Category", items: [])
    }

    func snapshot(for configuration: SelectCategoryIntent, in context: Context) async -> CategoryEntry {
        let items = await fetchItems(for: configuration.category.id)
        return CategoryEntry(date: .now, categoryName: configuration.category.name, items: items)
    }

    func timeline(for configuration: SelectCategoryIntent, in context: Context) async -> Timeline<CategoryEntry> {
        let items = await fetchItems(for: configuration.category.id)
        let entry = CategoryEntry(date: .now, categoryName: configuration.category.name, items: items)
        return Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(1800)))
    }
}
```

### Custom Entity for Parameters

```swift
struct CategoryEntity: AppEntity {
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Category")
    static var defaultQuery = CategoryQuery()

    var id: String
    var name: String

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(name)")
    }
}

struct CategoryQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [CategoryEntity] {
        await DataStore.shared.categories(for: identifiers)
    }

    func suggestedEntities() async throws -> [CategoryEntity] {
        await DataStore.shared.allCategories()
    }

    func defaultResult() async -> CategoryEntity? {
        try? await suggestedEntities().first
    }
}
```

## Timeline Management

### TimelineReloadPolicy

| Policy | Behavior |
|---|---|
| `.atEnd` | System requests a new timeline after the last entry's date passes |
| `.after(Date)` | System requests a new timeline after the specified date |
| `.never` | Timeline is only refreshed when the app explicitly requests it |

```swift
// Refresh after the last entry expires
Timeline(entries: entries, policy: .atEnd)

// Refresh after 30 minutes
Timeline(entries: entries, policy: .after(.now.addingTimeInterval(1800)))

// Only refresh on explicit app request
Timeline(entries: entries, policy: .never)
```

### Programmatic Reloads

```swift
import WidgetKit

// Reload a specific widget by kind
WidgetCenter.shared.reloadTimelines(ofKind: "StatusWidget")

// Reload all widgets belonging to the app
WidgetCenter.shared.reloadAllTimelines()

// Get current widget configurations
WidgetCenter.shared.getCurrentConfigurations { result in
    if case .success(let configs) = result {
        for config in configs {
            print("Widget: \(config.kind), family: \(config.family)")
        }
    }
}
```

The system imposes a daily budget on timeline reloads. Avoid calling `reloadTimelines` excessively.

### Relevance

Influence widget placement in the Smart Stack:

```swift
struct MyEntry: TimelineEntry {
    let date: Date
    let title: String
    let relevance: TimelineEntryRelevance?
}

// Higher score = more likely to appear on top of Smart Stack
let entry = MyEntry(
    date: .now,
    title: "Important Update",
    relevance: TimelineEntryRelevance(score: 100)
)
```

## Interactive Widgets (iOS 17+)

Starting with iOS 17, widgets support `Button` and `Toggle` that execute `AppIntent` actions directly from the widget — no app launch required.

### Button in Widget

```swift
struct TaskToggleIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle Task"

    @Parameter(title: "Task ID")
    var taskID: String

    init() {}
    init(taskID: String) { self.taskID = taskID }

    func perform() async throws -> some IntentResult {
        let store = TaskStore.shared
        await store.toggleCompletion(for: taskID)
        return .result()
    }
}

struct TaskWidgetView: View {
    var entry: TaskEntry

    var body: some View {
        VStack(alignment: .leading) {
            ForEach(entry.tasks) { task in
                HStack {
                    Button(intent: TaskToggleIntent(taskID: task.id)) {
                        Image(systemName: task.isCompleted ? "checkmark.circle.fill" : "circle")
                    }
                    .tint(task.isCompleted ? .green : .gray)
                    Text(task.title)
                }
            }
        }
    }
}
```

### Toggle in Widget

```swift
struct ToggleFeatureIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle Feature"

    @Parameter(title: "Feature ID")
    var featureID: String

    init() {}
    init(featureID: String) { self.featureID = featureID }

    func perform() async throws -> some IntentResult {
        let store = SettingsStore.shared
        await store.toggleFeature(featureID)
        return .result()
    }
}

struct SettingsWidgetView: View {
    var entry: SettingsEntry

    var body: some View {
        VStack {
            Toggle(isOn: entry.isFeatureEnabled,
                   intent: ToggleFeatureIntent(featureID: "dark_mode")) {
                Label("Dark Mode", systemImage: "moon.fill")
            }
        }
    }
}
```

### Invalidating After Interaction

After an interactive intent performs, the system automatically reloads the widget's timeline. You can also manually trigger a reload inside `perform()`:

```swift
func perform() async throws -> some IntentResult {
    await store.toggleCompletion(for: taskID)
    // Explicit reload if needed for related widgets
    WidgetCenter.shared.reloadTimelines(ofKind: "SummaryWidget")
    return .result()
}
```

## Live Activities

Live Activities display real-time, glanceable information on the Lock Screen and in the Dynamic Island.

### ActivityAttributes

Define the static and dynamic data for a Live Activity:

```swift
import ActivityKit

struct DeliveryAttributes: ActivityAttributes {
    // Fixed data — does not change during the activity
    struct ContentState: Codable, Hashable {
        // Dynamic data — updated throughout the activity
        var status: String
        var estimatedArrival: Date
        var driverName: String
    }

    let orderNumber: String
    let restaurantName: String
}
```

### Starting a Live Activity

```swift
func startDeliveryTracking(order: Order) throws -> Activity<DeliveryAttributes> {
    let attributes = DeliveryAttributes(
        orderNumber: order.id,
        restaurantName: order.restaurant
    )
    let initialState = DeliveryAttributes.ContentState(
        status: "Preparing",
        estimatedArrival: order.estimatedArrival,
        driverName: "Assigning..."
    )
    let content = ActivityContent(state: initialState, staleDate: nil)

    return try Activity.request(
        attributes: attributes,
        content: content,
        pushType: .token  // enables push-based updates
    )
}
```

### Updating and Ending

```swift
// Update
func updateDelivery(activity: Activity<DeliveryAttributes>, newState: DeliveryAttributes.ContentState) async {
    let content = ActivityContent(state: newState, staleDate: nil)
    await activity.update(content)
}

// End
func endDelivery(activity: Activity<DeliveryAttributes>, finalState: DeliveryAttributes.ContentState) async {
    let content = ActivityContent(state: finalState, staleDate: nil)
    await activity.end(content, dismissalPolicy: .after(.now.addingTimeInterval(3600)))
}

// End all activities of a type
for activity in Activity<DeliveryAttributes>.activities {
    await activity.end(nil, dismissalPolicy: .immediate)
}
```

### Live Activity UI — Lock Screen and Dynamic Island

```swift
struct DeliveryLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: DeliveryAttributes.self) { context in
            // Lock Screen / StandBy / banner presentation
            VStack(alignment: .leading) {
                HStack {
                    Text(context.attributes.restaurantName)
                        .font(.headline)
                    Spacer()
                    Text(context.state.status)
                        .foregroundStyle(.secondary)
                }
                HStack {
                    Label(context.state.driverName, systemImage: "car.fill")
                    Spacer()
                    Text(context.state.estimatedArrival, style: .timer)
                }
            }
            .padding()
            .activityBackgroundTint(.cyan.opacity(0.2))

        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded regions (long press on Dynamic Island)
                DynamicIslandExpandedRegion(.leading) {
                    Label(context.state.driverName, systemImage: "car.fill")
                        .font(.caption)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.estimatedArrival, style: .timer)
                        .font(.caption)
                        .foregroundStyle(.cyan)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text("Order #\(context.attributes.orderNumber) — \(context.state.status)")
                }
                DynamicIslandExpandedRegion(.center) {
                    Text(context.attributes.restaurantName)
                        .font(.headline)
                }
            } compactLeading: {
                // Compact leading (left side of Dynamic Island pill)
                Image(systemName: "bag.fill")
                    .foregroundStyle(.cyan)
            } compactTrailing: {
                // Compact trailing (right side of Dynamic Island pill)
                Text(context.state.estimatedArrival, style: .timer)
                    .foregroundStyle(.cyan)
                    .frame(maxWidth: 64)
            } minimal: {
                // Minimal (when multiple Live Activities are active)
                Image(systemName: "bag.fill")
                    .foregroundStyle(.cyan)
            }
        }
    }
}
```

### Push Token Updates

```swift
func observePushToken(for activity: Activity<DeliveryAttributes>) {
    Task {
        for await pushToken in activity.pushTokenUpdates {
            let tokenString = pushToken.map { String(format: "%02x", $0) }.joined()
            await sendTokenToServer(token: tokenString, activityID: activity.id)
        }
    }
}
```

## App Intents Framework

The App Intents framework lets you expose app actions to Siri, Shortcuts, Spotlight, and interactive widgets through a single Swift-native API.

### AppIntent Protocol

```swift
import AppIntents

struct CreateTaskIntent: AppIntent {
    static var title: LocalizedStringResource = "Create Task"
    static var description: IntentDescription = "Creates a new task in the app."

    @Parameter(title: "Title")
    var title: String

    @Parameter(title: "Priority", default: .medium)
    var priority: TaskPriority

    @Parameter(title: "Due Date")
    var dueDate: Date?

    static var parameterSummary: some ParameterSummary {
        Summary("Create \(\.$title) with \(\.$priority) priority") {
            \.$dueDate
        }
    }

    func perform() async throws -> some IntentResult & ReturnsValue<TaskEntity> & ProvidesDialog {
        let task = await TaskStore.shared.create(title: title, priority: priority, dueDate: dueDate)
        return .result(
            value: TaskEntity(task: task),
            dialog: "Created task: \(title)"
        )
    }
}
```

### Custom Enums as Parameters

```swift
enum TaskPriority: String, AppEnum {
    case low, medium, high, urgent

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Priority")

    static var caseDisplayRepresentations: [TaskPriority: DisplayRepresentation] = [
        .low: "Low",
        .medium: "Medium",
        .high: "High",
        .urgent: "Urgent"
    ]
}
```

### Opening the App from an Intent

```swift
struct OpenTaskIntent: AppIntent {
    static var title: LocalizedStringResource = "Open Task"
    static var openAppWhenRun = true

    @Parameter(title: "Task")
    var task: TaskEntity

    func perform() async throws -> some IntentResult {
        await NavigationManager.shared.navigate(to: .task(task.id))
        return .result()
    }
}
```

### IntentResult Variations

```swift
// Simple completion
func perform() async throws -> some IntentResult {
    return .result()
}

// Return a value
func perform() async throws -> some IntentResult & ReturnsValue<String> {
    return .result(value: "Done")
}

// Return a dialog (spoken by Siri)
func perform() async throws -> some IntentResult & ProvidesDialog {
    return .result(dialog: "Task completed successfully.")
}

// Return a snippet view (shown in Shortcuts/Siri)
func perform() async throws -> some IntentResult & ShowsSnippetView {
    return .result {
        TaskCompletionView(task: task)
    }
}
```

## App Shortcuts

App Shortcuts make your App Intents discoverable without user setup. They appear in Spotlight, Siri suggestions, and the Shortcuts app automatically.

### AppShortcutsProvider

```swift
struct MyAppShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: CreateTaskIntent(),
            phrases: [
                "Create a task in \(.applicationName)",
                "Add a new task in \(.applicationName)",
                "New \(.applicationName) task"
            ],
            shortTitle: "Create Task",
            systemImageName: "plus.circle"
        )

        AppShortcut(
            intent: ShowStatsIntent(),
            phrases: [
                "Show my \(.applicationName) stats",
                "How am I doing in \(.applicationName)"
            ],
            shortTitle: "Show Stats",
            systemImageName: "chart.bar"
        )
    }
}
```

Rules:
- Every phrase must include `\(.applicationName)` so Siri can associate it with your app.
- Keep phrases natural and conversational.
- Provide at least 2-3 phrase variations per shortcut.
- Maximum 10 App Shortcuts per app.

### Spotlight and Siri Integration

App Shortcuts are automatically indexed by Spotlight. Users can also invoke them via Siri using the defined phrases. No additional code is required beyond the `AppShortcutsProvider` conformance.

Update shortcuts when app data changes:

```swift
// Call when relevant data changes (e.g., new categories added)
AppShortcutsProvider.updateAppShortcutParameters()
```

## Shortcuts Integration

### Parameterized Intents with Dynamic Options

```swift
struct LogWorkoutIntent: AppIntent {
    static var title: LocalizedStringResource = "Log Workout"

    @Parameter(title: "Workout Type")
    var workoutType: WorkoutTypeEntity

    @Parameter(title: "Duration (minutes)", inclusiveRange: (1, 480))
    var duration: Int

    @Parameter(title: "Notes")
    var notes: String?

    static var parameterSummary: some ParameterSummary {
        Summary("Log \(\.$duration) min \(\.$workoutType)") {
            \.$notes
        }
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let workout = await WorkoutStore.shared.log(
            type: workoutType.id,
            duration: duration,
            notes: notes
        )
        return .result(dialog: "Logged \(duration) minute \(workoutType.name) workout.")
    }
}
```

### Custom Snippet UI in Shortcuts

Provide a custom SwiftUI view that appears in the Shortcuts app and Siri results:

```swift
struct ShowStatsIntent: AppIntent {
    static var title: LocalizedStringResource = "Show Stats"

    func perform() async throws -> some IntentResult & ShowsSnippetView {
        let stats = await StatsService.shared.fetchWeekly()
        return .result {
            VStack(alignment: .leading, spacing: 8) {
                Text("This Week")
                    .font(.headline)
                HStack(spacing: 16) {
                    StatBadge(label: "Tasks", value: "\(stats.tasksCompleted)")
                    StatBadge(label: "Streak", value: "\(stats.streak) days")
                    StatBadge(label: "Points", value: "\(stats.points)")
                }
            }
            .padding()
        }
    }
}
```

### Requesting Confirmation

```swift
struct DeleteAllTasksIntent: AppIntent {
    static var title: LocalizedStringResource = "Delete All Tasks"

    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await requestConfirmation(
            result: .result(dialog: "This will delete all tasks. Are you sure?"),
            confirmationActionName: .destructive
        )
        await TaskStore.shared.deleteAll()
        return .result(dialog: "All tasks deleted.")
    }
}
```

## Widgets Across Platforms

### Platform Availability

| Platform | Widget Types | Notes |
|---|---|---|
| iOS | Home Screen, Lock Screen, StandBy | Full WidgetKit support |
| iPadOS | Home Screen, Lock Screen | Includes `.systemExtraLarge` |
| macOS | Notification Center, Desktop | Shared with iOS via Catalyst or native |
| watchOS | Smart Stack, Watch Face | Accessory families, complications |

### StandBy Mode (iOS 17+, iPhone)

Widgets in StandBy mode display in a large, clock-like layout when the iPhone is charging in landscape. No additional code is needed — system and large family widgets automatically appear. Optimize by:

- Supporting `.systemLarge` and `.systemMedium` families.
- Using high-contrast colors and large text for readability at a distance.
- Providing a night-mode variant via `@Environment(\.isLuminanceReduced)`.

```swift
struct StandByAwareView: View {
    var entry: MyEntry
    @Environment(\.isLuminanceReduced) var isLuminanceReduced

    var body: some View {
        Text(entry.title)
            .font(.largeTitle)
            .foregroundStyle(isLuminanceReduced ? .red : .primary)
    }
}
```

### watchOS — Smart Stack and Complications

On watchOS, widgets appear in the Smart Stack (scrollable list on the watch face) and as watch face complications using accessory families.

```swift
struct WatchWidget: Widget {
    let kind = "WatchWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: WatchProvider()) { entry in
            WatchWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .supportedFamilies([
            .accessoryCircular,
            .accessoryRectangular,
            .accessoryInline,
            .accessoryCorner    // watchOS only
        ])
    }
}
```

### Sharing Code Across Platforms

Use conditional compilation and shared widget targets:

```swift
struct CrossPlatformWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "CrossPlatform", provider: SharedProvider()) { entry in
            SharedWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .supportedFamilies(supportedFamilies)
    }

    private var supportedFamilies: [WidgetFamily] {
        #if os(watchOS)
        [.accessoryCircular, .accessoryRectangular, .accessoryInline]
        #elseif os(iOS)
        [.systemSmall, .systemMedium, .systemLarge, .accessoryCircular, .accessoryRectangular]
        #else
        [.systemSmall, .systemMedium, .systemLarge]
        #endif
    }
}
```

## Data Sharing

Widgets run in a separate process from the main app. Use App Groups to share data.

### App Groups Setup

1. Enable "App Groups" capability in both the app target and widget extension target.
2. Use the same group identifier (e.g., `group.com.example.myapp`).

### Shared UserDefaults

```swift
// Shared container — use in both app and widget
let sharedDefaults = UserDefaults(suiteName: "group.com.example.myapp")!

// Write from the app
sharedDefaults.set(42, forKey: "taskCount")
sharedDefaults.set(Date.now, forKey: "lastUpdated")

// Read from the widget provider
func getTimeline(in context: Context) async -> Timeline<MyEntry> {
    let defaults = UserDefaults(suiteName: "group.com.example.myapp")!
    let count = defaults.integer(forKey: "taskCount")
    let lastUpdated = defaults.object(forKey: "lastUpdated") as? Date ?? .now

    let entry = MyEntry(date: .now, taskCount: count, lastUpdated: lastUpdated)
    return Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(900)))
}
```

### Shared File Container

```swift
let containerURL = FileManager.default.containerURL(
    forSecurityApplicationGroupIdentifier: "group.com.example.myapp"
)!

let dataURL = containerURL.appendingPathComponent("shared_data.json")

// Write from app
let data = try JSONEncoder().encode(model)
try data.write(to: dataURL)

// Notify widget to refresh
WidgetCenter.shared.reloadTimelines(ofKind: "MyWidget")
```

### Shared SwiftData / CoreData

```swift
// SwiftData — shared model container
let sharedContainer: ModelContainer = {
    let schema = Schema([Task.self, Category.self])
    let config = ModelConfiguration(
        "SharedStore",
        schema: schema,
        url: FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: "group.com.example.myapp"
        )!.appendingPathComponent("shared.store"),
        cloudKitDatabase: .none
    )
    return try! ModelContainer(for: schema, configurations: [config])
}()

// CoreData — shared persistent container
let container: NSPersistentContainer = {
    let container = NSPersistentContainer(name: "Model")
    let storeURL = FileManager.default.containerURL(
        forSecurityApplicationGroupIdentifier: "group.com.example.myapp"
    )!.appendingPathComponent("Model.sqlite")
    container.persistentStoreDescriptions = [NSPersistentStoreDescription(url: storeURL)]
    container.loadPersistentStores { _, error in
        if let error { fatalError("Core Data failed: \(error)") }
    }
    return container
}()
```

## Best Practices

### Keep Widgets Lightweight

- Widget extensions have limited memory (~30 MB). Avoid loading large images or datasets.
- Perform network calls in `getTimeline`, not in the view.
- Use `URLSession` shared or background sessions — widgets cannot run long background tasks.

### Timeline Strategy

| Scenario | Strategy |
|---|---|
| Data changes rarely | `.never` + explicit `reloadTimelines` from app |
| Periodic updates (weather, stocks) | `.after(Date)` with 15-60 min intervals |
| Time-based content (countdowns) | Multiple entries with future dates, `.atEnd` |
| User-triggered changes | `.never` + `reloadTimelines` on data write |

Avoid generating more than ~50 timeline entries at once. The system may throttle excessive entries.

### Snapshot vs Timeline Entry

- **Snapshot** (`getSnapshot`): Must return quickly (under 5 seconds). Used for widget gallery previews. Provide representative sample data — not a loading state.
- **Timeline** (`getTimeline`): Can perform async work (network, database). Provides the actual entries the user sees.
- **Placeholder**: A redacted version of the widget with no real data. The system applies a redaction effect automatically. Use `.redacted(reason: .placeholder)` or return generic shapes.

```swift
func placeholder(in context: Context) -> MyEntry {
    // Return "shape" data — the system redacts it visually
    MyEntry(date: .now, title: "Task Name", value: 42)
}
```

### Link Handling

Widgets do not support general navigation. Use `widgetURL` for small widgets and `Link` for medium/large:

```swift
struct MyWidgetView: View {
    var entry: MyEntry

    var body: some View {
        VStack {
            // For .systemSmall — only widgetURL works (taps the whole widget)
            Text(entry.title)
        }
        .widgetURL(URL(string: "myapp://task/\(entry.id)")!)
    }
}

// For .systemMedium and .systemLarge — use Link for specific areas
struct MediumWidgetView: View {
    var entry: TaskListEntry

    var body: some View {
        VStack {
            ForEach(entry.tasks) { task in
                Link(destination: URL(string: "myapp://task/\(task.id)")!) {
                    TaskRow(task: task)
                }
            }
        }
    }
}
```

### Common Pitfalls

| Pitfall | Fix |
|---|---|
| Widget shows stale data | Reload timelines when app writes shared data |
| Snapshot shows loading spinner | Return sample data, never a loading state |
| Widget exceeds memory limit | Reduce image sizes, limit data fetched |
| Interactive buttons not working | Ensure `AppIntent` is in the widget extension target |
| Live Activity not appearing | Check `NSSupportsLiveActivities` is `true` in Info.plist |
| Shared data not accessible | Verify both targets have the same App Group capability |
| Timeline entries not updating | Check reload policy; system throttles excessive reloads |
| Widget appears blank on watchOS | Use accessory families, not system families |
