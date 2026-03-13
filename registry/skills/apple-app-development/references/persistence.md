# Persistence Reference (Core Data & SwiftData)

Comprehensive guide to data persistence on Apple platforms. Covers Core Data (mature, full-featured) and SwiftData (iOS 17+, Swift-native). Use this reference for stack setup, CRUD, concurrency, migrations, performance, CloudKit sync, and testing.

## When to Use Which

| Criterion | SwiftData | Core Data |
|---|---|---|
| **Minimum target** | iOS 17+ | iOS 11+ |
| **Boilerplate** | Minimal (`@Model` macro) | Significant (`.xcdatamodeld`, codegen) |
| **SwiftUI integration** | Native (`@Query`, `.modelContainer`) | Workable (`@FetchRequest`) |
| **UIKit support** | Possible but awkward | First-class (`NSFetchedResultsController`) |
| **Undo/Redo** | Not built-in | Built-in (`NSUndoManager`) |
| **Complex predicates** | `#Predicate` (limited composition) | `NSCompoundPredicate` (flexible) |
| **Batch operations** | Limited | `NSBatchInsertRequest`, etc. |
| **CloudKit** | Supported (with constraints) | `NSPersistentCloudKitContainer` (mature) |
| **Performance at scale** | Good, slightly behind | Optimized over 15+ years |
| **Migrations** | `VersionedSchema` (still maturing) | Lightweight + heavyweight (battle-tested) |
| **Custom data stores** | iOS 18+ `DataStore` protocol | N/A |

**Guidance:**
- **New SwiftUI-only projects (iOS 17+):** Start with SwiftData unless you need batch operations, undo/redo, or complex predicate composition.
- **Existing Core Data apps:** Migrate strategically. SwiftData and Core Data can coexist — they share the same SQLite backing store.
- **Apps requiring UIKit + advanced features:** Core Data remains the stronger choice.
- **Widgets/extensions for Core Data apps:** Consider using SwiftData in the extension while the main app stays on Core Data, sharing the same store via App Groups.


## Core Data

### Stack Setup
---

```swift
import CoreData

final class PersistenceController: Sendable {
    static let shared = PersistenceController()

    let container: NSPersistentContainer

    init(inMemory: Bool = false) {
        container = NSPersistentContainer(name: "MyModel")

        if inMemory {
            container.persistentStoreDescriptions.first?.url = URL(fileURLWithPath: "/dev/null")
        }

        container.loadPersistentStores { _, error in
            if let error { fatalError("Core Data store failed: \(error.localizedDescription)") }
        }

        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
    }
}
```

Rules:
- Use `/dev/null` as the store URL for tests instead of `NSInMemoryStoreType` — it uses a real SQLite engine so cascade deletes and other SQLite-specific behaviors work correctly.
- Set `automaticallyMergesChangesFromParent = true` on `viewContext` so background saves propagate to the UI.
- Set a merge policy (typically `NSMergeByPropertyObjectTrumpMergePolicy`) to handle conflicts.

### NSManagedObject Codegen Modes
---

| Mode | When to use |
|---|---|
| **Class Definition** | Simple models, rapid prototyping. Xcode generates both class and properties. |
| **Category/Extension** | You write the class, Xcode generates a properties extension. Best for adding custom logic. |
| **Manual/None** | Full control. Required for transient properties, custom accessors. |

For production apps, **Category/Extension** is the most common — add computed properties, validation, and convenience methods while Xcode handles the `@NSManaged` boilerplate.

```swift
// With Category/Extension codegen, you write this:
@objc(Task)
public class Task: NSManagedObject {
    var isOverdue: Bool {
        guard let dueDate else { return false }
        return dueDate < Date.now
    }

    public override func validateForInsert() throws {
        try super.validateForInsert()
        guard let title, !title.isEmpty else {
            throw ValidationError.missingTitle
        }
    }
}
// Xcode generates the +CoreDataProperties extension with @NSManaged vars
```

### Context Concurrency
---

Core Data offers three context patterns. Critical rule: **never access a managed object or context on the wrong queue**.

#### viewContext (Main Queue)

```swift
let viewContext = container.viewContext
// Always tied to main queue. Safe from @MainActor code and SwiftUI views.
```

#### performBackgroundTask (Ephemeral)

```swift
container.performBackgroundTask { context in
    let request = NSFetchRequest<Task>(entityName: "Task")
    let tasks = try context.fetch(request)
    // ... mutate ...
    try context.save()
}
// Creates a new private-queue context each call. Avoid in tight loops — creates many threads.
```

#### newBackgroundContext (Reusable)

```swift
let backgroundContext = container.newBackgroundContext()
backgroundContext.automaticallyMergesChangesFromParent = true

backgroundContext.perform {
    // fetch, mutate, save
    try? backgroundContext.save()
}
```

#### Passing Objects Across Queues

Never pass `NSManagedObject` instances between queues. Use `NSManagedObjectID`:

```swift
// On background context
let objectID = backgroundTask.objectID

// On main context
await MainActor.run {
    let mainTask = viewContext.object(with: objectID) as! Task // Safe: objectID guarantees entity type
}
```

#### Swift 6 Strict Concurrency

Swift 6 flags `NSManagedObject` and `NSManagedObjectContext` as non-`Sendable`. Strategies:
- Use `@preconcurrency import CoreData` as a transitional measure.
- Pass only `NSManagedObjectID` (which is `Sendable`) across isolation boundaries.
- Wrap Core Data access behind an actor that owns a private-queue context.

### Fetch Requests & Predicates
---

```swift
let request = NSFetchRequest<Task>(entityName: "Task")
request.predicate = NSPredicate(format: "isCompleted == %@ AND dueDate < %@",
                                 NSNumber(value: false), Date.now as NSDate)
request.sortDescriptors = [
    NSSortDescriptor(keyPath: \Task.dueDate, ascending: true),
    NSSortDescriptor(keyPath: \Task.priority, ascending: false)
]
request.fetchBatchSize = 20
request.fetchLimit = 100
request.relationshipKeyPathsForPrefetching = ["assignee"]
```

#### NSFetchedResultsController (UIKit)

```swift
let frc = NSFetchedResultsController(
    fetchRequest: request,
    managedObjectContext: viewContext,
    sectionNameKeyPath: "category",
    cacheName: "TaskCache"
)
frc.delegate = self
try frc.performFetch()

// Modern delegate — integrates with diffable data sources
func controller(_ controller: NSFetchedResultsController<NSFetchRequestResult>,
                didChangeContentWith snapshot: NSDiffableDataSourceSnapshotReference) {
    let snapshot = snapshot as NSDiffableDataSourceSnapshot<String, NSManagedObjectID>
    dataSource.apply(snapshot, animatingDifferences: true)
}
```

### Relationships
---

| Type | Definition | Notes |
|---|---|---|
| **One-to-many** | Parent has `NSSet` of children; child has single parent ref | Always define inverse |
| **Many-to-many** | Both sides are `NSSet` | Core Data manages the join table |

**Always define inverse relationships.** Core Data uses inverses to maintain referential integrity. Omitting them causes Xcode warnings and can lead to data inconsistency.

#### Delete Rules

| Rule | Behavior |
|---|---|
| **Cascade** | Deleting the source deletes all related objects |
| **Nullify** | Sets the inverse relationship to nil |
| **Deny** | Prevents deletion if related objects exist |
| **No Action** | Does nothing (dangerous — can leave orphans) |

Best practice: **Cascade** from parent to children, **Nullify** from child to parent.

### Migrations
---

#### Lightweight (Preferred)

Core Data infers the mapping automatically. Supported changes (per Apple docs):

| Change | Supported |
|---|---|
| Add/remove an attribute | Yes |
| Non-optional → optional | Yes |
| Optional → non-optional (with default value) | Yes |
| Rename entity or property (with renaming identifier) | Yes |
| Add/remove/rename a relationship | Yes |
| To-one → to-many | Yes |
| Ordered ↔ unordered to-many | Yes |
| Add/remove/rename entities in a hierarchy | Yes |
| Move properties up/down entity hierarchy | Yes |
| Merge entity hierarchies | **No** |

Since iOS 17+, `NSPersistentContainer` attempts lightweight migration by default — no extra code needed. For explicit control:

```swift
let options = [
    NSMigratePersistentStoresAutomaticallyOption: true,
    NSInferMappingModelAutomaticallyOption: true
]
try coordinator.addPersistentStore(type: .sqlite, at: storeURL, options: options)
```

**Renaming identifiers** create a canonical name that works across multi-version migrations (V1→V3 works even if V2 renamed the property). Set them in the destination model's Data Model Inspector.

#### Staged Migrations

Staged lightweight migrations (iOS 17+) break incompatible changes into a series of compatible stages. Use when lightweight alone can't handle the change — e.g., making an optional attribute non-optional requires setting `nil` values to concrete values first.

Key components:
- **`NSStagedMigrationManager`** — orchestrates stages sequentially
- **`NSLightweightMigrationStage`** — a stage that Core Data can infer automatically
- **`NSCustomMigrationStage`** — a stage with custom pre/post-migration logic

```swift
let lightweightStage = NSLightweightMigrationStage(["ModelV1", "ModelV2"])

let customStage = NSCustomMigrationStage(
    migratingFrom: modelV2,
    to: modelV3
)
customStage.willMigrateHandler = { migrationManager, currentStage in
    let context = migrationManager.container.newBackgroundContext()
    try await context.perform {
        // Set nil values before non-optional constraint takes effect
        let request = NSFetchRequest<NSManagedObject>(entityName: "Task")
        request.predicate = NSPredicate(format: "priority == nil")
        let tasks = try context.fetch(request)
        for task in tasks { task.setValue(0, forKey: "priority") }
        try context.save()
    }
}

let manager = NSStagedMigrationManager([lightweightStage, customStage])
guard let description = container.persistentStoreDescriptions.first else { return }
description.setOption(manager, forKey: NSPersistentStoreStagedMigrationManagerOptionKey)
```

#### Manual (Heavyweight) Migrations

Required for elaborate changes beyond staged capabilities (splitting entities, complex data transformations):

```swift
guard let mapping = NSMappingModel(from: [Bundle.main],
                                    forSourceModel: sourceModel,
                                    destinationModel: destModel)
else { fatalError("No mapping model found for \(sourceModel) -> \(destModel)") }

let manager = NSMigrationManager(sourceModel: sourceModel,
                                  destinationModel: destModel)
try manager.migrateStore(from: sourceURL, type: .sqlite,
                          mapping: mapping, to: destURL, type: .sqlite)
```

**Best practice:** Test each migration step with real data. Use staged migrations when possible — they are simpler and less error-prone than manual.

### Batch Operations
---

Batch operations execute directly at the SQLite level, bypassing the managed object context. Dramatically faster for bulk work but require manual in-memory synchronization.

#### NSBatchInsertRequest

```swift
let request = NSBatchInsertRequest(entity: Task.entity(),
                                    managedObjectHandler: { obj in
    let task = obj as! Task // Safe: entity type matches NSBatchInsertRequest
    task.title = nextItem.title
    task.dueDate = nextItem.dueDate
    return false  // return true when done
})
request.resultType = .objectIDs

let result = try context.execute(request) as? NSBatchInsertResult
let objectIDs = result?.result as? [NSManagedObjectID] ?? []

NSManagedObjectContext.mergeChanges(
    fromRemoteContextSave: [NSInsertedObjectsKey: objectIDs],
    into: [container.viewContext]
)
```

#### NSBatchDeleteRequest

```swift
let fetchRequest: NSFetchRequest<NSFetchRequestResult> = Task.fetchRequest()
fetchRequest.predicate = NSPredicate(format: "isCompleted == YES")

let deleteRequest = NSBatchDeleteRequest(fetchRequest: fetchRequest)
deleteRequest.resultType = .resultTypeObjectIDs

let result = try context.execute(deleteRequest) as? NSBatchDeleteResult
let deletedIDs = result?.result as? [NSManagedObjectID] ?? []

NSManagedObjectContext.mergeChanges(
    fromRemoteContextSave: [NSDeletedObjectsKey: deletedIDs],
    into: [container.viewContext]
)
```

**Limitations:** Batch inserts cannot set relationships. Batch deletes don't fire cascade rules in the context — only at the SQLite level. Always merge changes back to keep in-memory state consistent.

#### Merging Batch Changes via Persistent History Tracking

`NSBatchInsertRequest` bypasses the context and doesn't trigger `NSManagedObjectContextDidSave` notifications. For large data feeds, use Persistent History Tracking instead of manual `mergeChanges`:

```swift
// 1. Enable on store description (required)
description.setOption(true as NSNumber, forKey: NSPersistentHistoryTrackingKey)
description.setOption(true as NSNumber,
                       forKey: NSPersistentStoreRemoteChangeNotificationPostOptionKey)

// 2. Observe remote change notifications
NotificationCenter.default.addObserver(
    self, selector: #selector(storeRemoteChange),
    name: .NSPersistentStoreRemoteChange, object: container.persistentStoreCoordinator
)

// 3. Fetch and merge history transactions
@objc func storeRemoteChange(_ notification: Notification) {
    let backgroundContext = container.newBackgroundContext()
    backgroundContext.perform {
        let request = NSPersistentHistoryChangeRequest.fetchHistory(after: self.lastToken)
        guard let result = try? backgroundContext.execute(request) as? NSPersistentHistoryResult,
              let transactions = result.result as? [NSPersistentHistoryTransaction]
        else { return }

        for transaction in transactions {
            self.container.viewContext.perform {
                self.container.viewContext.mergeChanges(
                    fromContextDidSave: transaction.objectIDNotification()
                )
            }
            self.lastToken = transaction.token
        }
    }
}
```

This pattern is essential for multi-process scenarios (app + widget sharing a store) and large data imports where `automaticallyMergesChangesFromParent` can cause excessive memory growth.

### Performance Tuning
---

| Parameter | Purpose | Recommendation |
|---|---|---|
| `fetchBatchSize` | Loads objects in batches (default 0 = all at once) | Set to 20–50 for large collections |
| `fetchLimit` | Caps total number of results | Use when you only need "top N" |
| `relationshipKeyPathsForPrefetching` | Eagerly loads specified relationships | Set for any relationship you'll access in a list |
| `includesPropertyValues` | If `false`, returns faults without pre-loading attributes | Use for existence checks or delete-only fetches |
| `returnsObjectsAsFaults` | If `false`, fully materializes objects immediately | Use when you know you need all attributes |
| `propertiesToFetch` | Fetch only specific attributes | Reduces I/O for partial reads |

Core Data lazily loads objects as "faults" — placeholders that trigger a database read only when a property is accessed. This keeps memory low but can cause N+1 query problems in large collections. Use `relationshipKeyPathsForPrefetching` and `fetchBatchSize` to mitigate.

### Core Data + CloudKit
---

```swift
let container = NSPersistentCloudKitContainer(name: "MyModel")

let description = container.persistentStoreDescriptions.first!
description.cloudKitContainerOptions = NSPersistentCloudKitContainerOptions(
    containerIdentifier: "iCloud.com.example.app"
)

// Required for CloudKit sync
description.setOption(true as NSNumber, forKey: NSPersistentHistoryTrackingKey)
description.setOption(true as NSNumber,
                       forKey: NSPersistentStoreRemoteChangeNotificationPostOptionKey)

container.loadPersistentStores { _, error in
    if let error { fatalError("CloudKit store failed: \(error)") }
}

#if DEBUG
try? container.initializeCloudKitSchema(options: [])
#endif
```

Requirements:
- All attributes must have default values or be optional.
- Unique constraints are not supported with CloudKit sync.
- Relationships must be optional.
- `initializeCloudKitSchema()` is expensive — run only in debug builds.
- Deploy the schema to production via the CloudKit Dashboard before shipping.

### Core Data + SwiftUI
---

```swift
// App entry point
@main
struct MyApp: App {
    let persistence = PersistenceController.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.managedObjectContext, persistence.container.viewContext)
        }
    }
}

// In a view
struct TaskListView: View {
    @Environment(\.managedObjectContext) private var viewContext

    @FetchRequest(
        sortDescriptors: [SortDescriptor(\.dueDate, order: .forward)],
        predicate: NSPredicate(format: "isCompleted == NO"),
        animation: .default
    )
    private var tasks: FetchedResults<Task>

    var body: some View {
        List(tasks) { task in
            TaskRow(task: task)
        }
    }
}
```

For **dynamic filtering**, wrap `@FetchRequest` in a child view whose initializer accepts filter parameters:

```swift
struct FilteredTaskList: View {
    @FetchRequest var tasks: FetchedResults<Task>

    init(category: String) {
        _tasks = FetchRequest(
            sortDescriptors: [SortDescriptor(\.dueDate)],
            predicate: NSPredicate(format: "category == %@", category)
        )
    }

    var body: some View {
        List(tasks) { task in TaskRow(task: task) }
    }
}
```


## SwiftData (iOS 17+)

### @Model, ModelContainer, ModelContext
---

```swift
import SwiftData

// @Model replaces NSManagedObject + .xcdatamodeld
@Model
final class Trip {
    var name: String
    var startDate: Date
    var endDate: Date
    var isCompleted: Bool = false

    @Relationship(deleteRule: .cascade, inverse: \Activity.trip)
    var activities: [Activity] = []

    init(name: String, startDate: Date, endDate: Date) {
        self.name = name
        self.startDate = startDate
        self.endDate = endDate
    }
}

@Model
final class Activity {
    var title: String
    var trip: Trip?

    init(title: String) {
        self.title = title
    }
}
```

```swift
// ModelContainer replaces NSPersistentContainer
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(for: [Trip.self, Activity.self])
    }
}
```

```swift
// ModelContext replaces NSManagedObjectContext
struct ContentView: View {
    @Environment(\.modelContext) private var modelContext

    func addTrip() {
        let trip = Trip(name: "Iceland", startDate: .now,
                        endDate: .now.addingTimeInterval(86400 * 7))
        modelContext.insert(trip)
        // SwiftData auto-saves; explicit save() is optional but available
    }
}
```

### @Query
---

`@Query` is SwiftData's equivalent of `@FetchRequest`:

```swift
struct TripListView: View {
    @Query(sort: \Trip.startDate, order: .reverse)
    private var trips: [Trip]

    var body: some View {
        List(trips) { trip in
            TripRow(trip: trip)
        }
    }
}
```

#### Filtering with #Predicate

```swift
@Query(filter: #Predicate<Trip> { trip in
    trip.isCompleted == false && trip.name.contains("Europe")
}, sort: \Trip.startDate)
private var upcomingTrips: [Trip]
```

#### Multiple Sort Descriptors

```swift
@Query(sort: [
    SortDescriptor(\Trip.startDate, order: .reverse),
    SortDescriptor(\Trip.name)
])
private var trips: [Trip]
```

#### Dynamic Queries

```swift
struct FilteredTrips: View {
    @Query private var trips: [Trip]

    init(searchText: String) {
        let predicate = #Predicate<Trip> { trip in
            searchText.isEmpty || trip.name.localizedStandardContains(searchText)
        }
        _trips = Query(filter: predicate, sort: \Trip.startDate)
    }

    var body: some View {
        List(trips) { trip in Text(trip.name) }
    }
}
```

**Limitation:** `#Predicate` does not support `NSCompoundPredicate`-style composition. Complex multi-step predicates require building the logic inline within the closure.

### Relationships and Delete Rules
---

```swift
@Model
final class Author {
    var name: String

    @Relationship(deleteRule: .cascade, inverse: \Book.author)
    var books: [Book] = []

    init(name: String) { self.name = name }
}

@Model
final class Book {
    var title: String
    var author: Author?

    init(title: String) { self.title = title }
}
```

Supported delete rules: `.cascade`, `.nullify`, `.deny`, `.noAction` — same semantics as Core Data.

For CloudKit sync, **all relationships must be optional** and `@Attribute(.unique)` is not allowed.

### Schema Migrations
---

```swift
// 1. Define schema versions
enum SchemaV1: VersionedSchema {
    static var versionIdentifier = Schema.Version(1, 0, 0)
    static var models: [any PersistentModel.Type] { [Trip.self] }

    @Model final class Trip {
        var name: String
        var startDate: Date
        init(name: String, startDate: Date) {
            self.name = name
            self.startDate = startDate
        }
    }
}

enum SchemaV2: VersionedSchema {
    static var versionIdentifier = Schema.Version(2, 0, 0)
    static var models: [any PersistentModel.Type] { [Trip.self] }

    @Model final class Trip {
        var name: String
        var startDate: Date
        var endDate: Date?  // New property
        init(name: String, startDate: Date, endDate: Date? = nil) {
            self.name = name
            self.startDate = startDate
            self.endDate = endDate
        }
    }
}

// 2. Define migration plan
enum TripMigrationPlan: SchemaMigrationPlan {
    static var schemas: [any VersionedSchema.Type] {
        [SchemaV1.self, SchemaV2.self]
    }

    static var stages: [MigrationStage] {
        [migrateV1toV2]
    }

    static let migrateV1toV2 = MigrationStage.lightweight(
        fromVersion: SchemaV1.self,
        toVersion: SchemaV2.self
    )
}

// 3. Use in container
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
            .modelContainer(for: SchemaV2.Trip.self,
                             migrationPlan: TripMigrationPlan.self)
    }
}
```

For **custom migrations** (when lightweight won't work):

```swift
static let migrateV1toV2 = MigrationStage.custom(
    fromVersion: SchemaV1.self,
    toVersion: SchemaV2.self,
    willMigrate: { context in
        let trips = try context.fetch(FetchDescriptor<SchemaV1.Trip>())
        // Custom logic: deduplicate, transform data
        try context.save()
    },
    didMigrate: nil
)
```

### ModelActor for Background Operations
---

`@ModelActor` creates a dedicated actor with its own `ModelContext`:

```swift
@ModelActor
actor TripDataHandler {
    func importTrips(from dtos: [TripDTO]) throws {
        for dto in dtos {
            let trip = Trip(name: dto.name, startDate: dto.startDate, endDate: dto.endDate)
            modelContext.insert(trip)
        }
        try modelContext.save()
    }

    func fetchTripIDs(matching name: String) throws -> [PersistentIdentifier] {
        let predicate = #Predicate<Trip> { $0.name.contains(name) }
        let descriptor = FetchDescriptor(predicate: predicate)
        return try modelContext.fetch(descriptor).map(\.persistentModelID)
    }
}
```

#### Passing Data Across Actor Boundaries

`PersistentModel` is not `Sendable`. Use `PersistentIdentifier` (which is `Sendable`) or DTOs:

```swift
struct TripDTO: Sendable {
    let name: String
    let startDate: Date
    let endDate: Date
}

// From @MainActor context
let handler = TripDataHandler(modelContainer: modelContainer)
let ids = try await handler.fetchTripIDs(matching: "Europe")

// Resolve on main context
for id in ids {
    if let trip = modelContext.model(for: id) as? Trip {
        print(trip.name)
    }
}
```

#### ModelActor Subscript

```swift
@ModelActor
actor BackgroundProcessor {
    func processTrip(id: PersistentIdentifier) throws {
        guard let trip = self[id, as: Trip.self] else { return }
        trip.isCompleted = true
        try modelContext.save()
    }
}
```

### SwiftData + CloudKit
---

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
            .modelContainer(for: Trip.self)
        // CloudKit sync is automatic when:
        // 1. iCloud capability with CloudKit is enabled
        // 2. Background Modes with Remote Notifications is enabled
        // 3. A CloudKit container identifier is configured
    }
}
```

To specify the CloudKit container explicitly:

```swift
let config = ModelConfiguration(
    cloudKitDatabase: .private("iCloud.com.example.app")
)
let container = try ModelContainer(for: Trip.self, configurations: config)
```

Constraints (same as Core Data + CloudKit):
- No `@Attribute(.unique)` — CloudKit does not support unique constraints.
- All properties must have default values or be optional.
- All relationships must be optional.
- Only the private CloudKit database is supported.

### iOS 18+ Features
---

#### #Unique — Composite Unique Constraints

```swift
@Model
final class Trip {
    #Unique<Trip>([\.name, \.startDate, \.endDate])

    var name: String
    var startDate: Date
    var endDate: Date

    init(name: String, startDate: Date, endDate: Date) {
        self.name = name
        self.startDate = startDate
        self.endDate = endDate
    }
}
// On collision, SwiftData performs an upsert rather than creating a duplicate.
```

#### #Index — Query Performance

```swift
@Model
final class Trip {
    #Index<Trip>([\.name], [\.startDate, \.endDate])

    var name: String
    var startDate: Date
    var endDate: Date
    // ...
}
// Creates indexes for fast lookups by name and by date range.
// Use #Index once per model — list all indexes in one call.
```

#### History Tracking

SwiftData History organizes changes as chronological transactions. Each transaction groups one or more inserts, updates, or deletes that occurred when `ModelContext` saved.

```swift
@Model
final class Trip {
    // Preserve key values in tombstone on deletion — enables identification across processes
    @Attribute(.preserveValueOnDeletion)
    var bookingRef: String

    var name: String
    var startDate: Date
    // ...
}
```

##### Fetching History

Use `HistoryDescriptor` with `DefaultToken` to fetch only transactions since the last sync:

```swift
func fetchTransactions(after tokenData: Data?) throws -> [DefaultHistoryTransaction] {
    let context = ModelContext(modelContainer)
    var descriptor = HistoryDescriptor<DefaultHistoryTransaction>()

    if let tokenData {
        let token = try JSONDecoder().decode(DefaultHistoryToken.self, from: tokenData)
        descriptor.predicate = #Predicate { $0.token > token }
    }

    return try context.fetchHistory(descriptor)
}
```

##### Processing Changes

Transactions contain heterogeneous changes across model types. Filter by type and inspect attributes:

```swift
for transaction in transactions {
    for change in transaction.changes {
        if let insert = change as? DefaultHistoryInsert<Trip> {
            let tripID = insert.changedModelID
            // Fetch and process new trip
        } else if let update = change as? DefaultHistoryUpdate<Trip> {
            let updatedKeys = update.updatedAttributes
            // React to specific attribute changes
        } else if let deletion = change as? DefaultHistoryDelete<Trip> {
            // Access preserved values via tombstone
            let bookingRef = deletion.tombstone[\.bookingRef]
        }
    }
}
```

##### Tagging Transactions with Authors

Set `ModelContext.author` to identify transaction origins (app vs widget vs background sync):

```swift
let context = ModelContext(modelContainer)
context.author = "widget"
// ... mutations ...
try context.save()

// Later, filter by author
descriptor.predicate = #Predicate { $0.author == "widget" }
```

##### Cleaning Up History

Delete stale transactions to prevent excessive storage. If you fetch with an expired token, SwiftData throws `SwiftDataError.historyTokenExpired`.

```swift
func deleteHistory(before token: DefaultHistoryToken) throws {
    let context = ModelContext(modelContainer)
    var descriptor = HistoryDescriptor<DefaultHistoryTransaction>()
    descriptor.predicate = #Predicate { $0.token < token }
    try context.deleteHistory(descriptor)
}
```

Use cases: remote server sync, out-of-process change handling (widget detects main app changes), audit logging.

##### Server Data Caching Pattern

For read-only caches of server data, combine `@Attribute(.unique)` with SwiftData's automatic upsert:

```swift
@Model
final class Quake {
    @Attribute(.unique) var code: String  // Server-side unique ID
    var magnitude: Double
    var time: Date

    init(code: String, magnitude: Double, time: Date) {
        self.code = code
        self.magnitude = magnitude
        self.time = time
    }
}

// Insert-or-update: SwiftData checks unique constraint automatically
for dto in serverResponse.items {
    let quake = Quake(code: dto.code, magnitude: dto.magnitude, time: dto.time)
    modelContext.insert(quake)  // Updates existing if code matches
}
// autosaveEnabled (default true) handles persistence
```

#### Custom Data Stores

The `DataStore` protocol lets you replace SQLite with any persistence backend:

```swift
struct JSONDataStore: DataStore {
    typealias Configuration = JSONStoreConfiguration
    typealias Snapshot = DefaultSnapshot

    func fetch<T>(_ request: DataStoreFetchRequest<T>) throws
        -> DataStoreFetchResult<T, DefaultSnapshot> {
        // Read from JSON file, create snapshots
    }

    func save(_ request: DataStoreSaveChangesRequest<DefaultSnapshot>) throws
        -> DataStoreSaveChangesResult<DefaultSnapshot> {
        // Write changes to JSON file
    }
}

struct JSONStoreConfiguration: DataStoreConfiguration {
    var name: String
    var schema: Schema?
    var fileURL: URL

    static func == (lhs: Self, rhs: Self) -> Bool { lhs.fileURL == rhs.fileURL }
    func hash(into hasher: inout Hasher) { hasher.combine(fileURL) }
}
```


## Shared Patterns

### App Groups (Sharing Data with Extensions/Widgets)
---

```swift
let appGroupID = "group.com.example.app"

// SwiftData
let config = ModelConfiguration(groupContainer: .identifier(appGroupID))
let container = try ModelContainer(for: Trip.self, configurations: config)

// Core Data
let storeURL = FileManager.default
    .containerURL(forSecurityApplicationGroupIdentifier: appGroupID)!
    .appendingPathComponent("Model.sqlite")
let description = NSPersistentStoreDescription(url: storeURL)
```

Enable **Persistent History Tracking** when sharing stores between processes — it ensures each process can detect and merge changes made by others.

### Data Validation
---

**Core Data** — override `validateForInsert()` and `validateForUpdate()`:

```swift
class Task: NSManagedObject {
    public override func validateForInsert() throws {
        try super.validateForInsert()
        guard let title, !title.isEmpty else {
            throw NSError(domain: "Validation", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Title cannot be empty"])
        }
    }
}
```

**SwiftData** — validate in `init` or use a repository layer:

```swift
@Model
final class Task {
    var title: String

    init(title: String) {
        precondition(!title.isEmpty, "Title must not be empty")
        self.title = title
    }
}
```

### Testing with In-Memory Stores
---

```swift
// SwiftData
@Test func tripCreation() async throws {
    let config = ModelConfiguration(isStoredInMemoryOnly: true)
    let container = try ModelContainer(for: Trip.self, configurations: config)
    let context = ModelContext(container)

    let trip = Trip(name: "Test", startDate: .now, endDate: .now)
    context.insert(trip)
    try context.save()

    let trips = try context.fetch(FetchDescriptor<Trip>())
    #expect(trips.count == 1)
    #expect(trips.first?.name == "Test")
}

// Core Data — use /dev/null for full SQLite behavior
func makeTestContainer() -> NSPersistentContainer {
    let container = NSPersistentContainer(name: "Model")
    let description = NSPersistentStoreDescription()
    description.url = URL(fileURLWithPath: "/dev/null")
    container.persistentStoreDescriptions = [description]
    container.loadPersistentStores { _, error in
        if let error { fatalError("Test store failed: \(error)") }
    }
    return container
}
```

Prefer `/dev/null` over `NSInMemoryStoreType` for Core Data tests — cascade delete rules and other SQLite-specific behaviors work identically to production.

### Repository Pattern
---

Abstract persistence behind a protocol to decouple business logic from Core Data/SwiftData:

```swift
protocol TripRepository: Sendable {
    func fetchAll() async throws -> [TripDTO]
    func fetch(id: String) async throws -> TripDTO?
    func save(_ dto: TripDTO) async throws
    func delete(id: String) async throws
}

// SwiftData implementation
@ModelActor
actor SwiftDataTripRepository: TripRepository {
    func fetchAll() async throws -> [TripDTO] {
        let descriptor = FetchDescriptor<Trip>(sortBy: [SortDescriptor(\.startDate)])
        return try modelContext.fetch(descriptor).map { $0.toDTO() }
    }

    func save(_ dto: TripDTO) async throws {
        let trip = Trip(name: dto.name, startDate: dto.startDate, endDate: dto.endDate)
        modelContext.insert(trip)
        try modelContext.save()
    }

    func fetch(id: String) async throws -> TripDTO? { /* ... */ }
    func delete(id: String) async throws { /* ... */ }
}

// In-memory implementation for tests and previews
actor InMemoryTripRepository: TripRepository {
    private var storage: [String: TripDTO] = [:]

    func fetchAll() async throws -> [TripDTO] {
        Array(storage.values).sorted { $0.startDate < $1.startDate }
    }

    func save(_ dto: TripDTO) async throws { storage[dto.id] = dto }
    func fetch(id: String) async throws -> TripDTO? { storage[id] }
    func delete(id: String) async throws { storage[id] = nil }
}
```

Benefits:
- Swap implementations for tests, previews, or future backend changes.
- Business logic never imports `SwiftData` or `CoreData`.
- Actor-based repositories prevent data races in Swift 6 strict concurrency.
- DTOs crossing actor boundaries are `Sendable` value types.


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Accessing `viewContext` from a background thread | Use `perform { }` or `performBackgroundTask`. Enable `-com.apple.CoreData.ConcurrencyDebug 1` to catch violations |
| Forgetting to call `save()` on background context | Changes are discarded. Always save after mutations |
| `performBackgroundTask` in a loop | Creates excessive threads. Use `newBackgroundContext()` instead |
| Not setting `automaticallyMergesChangesFromParent` | Background saves don't reflect in the UI |
| Batch operations without merge | In-memory state is stale. Always call `mergeChanges(fromRemoteContextSave:into:)` |
| N+1 faulting in lists | Set `relationshipKeyPathsForPrefetching` and `fetchBatchSize` |
| Passing `NSManagedObject` across queues | Use `NSManagedObjectID` instead |
| Passing `PersistentModel` across actors | Use `PersistentIdentifier` or DTOs instead |
| Missing inverse relationships (Core Data) | Always define inverses — prevents data inconsistency |
| `@Attribute(.unique)` with CloudKit | Not supported — CloudKit ignores unique constraints |
| SwiftData migration without `VersionedSchema` | Unversioned models break on schema changes in production |
| `automaticallyMergesChangesFromParent` with large batch imports | Can cause excessive memory growth. Use Persistent History Tracking instead |
| Fetching with expired `DefaultHistoryToken` | Throws `SwiftDataError.historyTokenExpired`. Delete stale history and reset token |
| Not enabling history tracking for shared stores | Multi-process stores (app + widget) miss each other's changes silently |
