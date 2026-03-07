# Swift Concurrency Reference

Comprehensive reference for Swift 6+ concurrency features. All patterns here are platform-agnostic — applicable to server-side Swift, CLI tools, and Apple platforms alike.

## Actors

### Actor Definition and Isolation

Actors provide data-race safety by isolating their mutable state. Only one task can execute on an actor at a time.

```swift
actor BankAccount {
    let accountID: String
    private var balance: Decimal

    init(accountID: String, initialBalance: Decimal) {
        self.accountID = accountID
        self.balance = initialBalance
    }

    func deposit(_ amount: Decimal) {
        balance += amount
    }

    func withdraw(_ amount: Decimal) throws -> Decimal {
        guard balance >= amount else {
            throw BankError.insufficientFunds
        }
        balance -= amount
        return amount
    }

    func currentBalance() -> Decimal {
        balance
    }
}

// External callers must await actor-isolated methods
let account = BankAccount(accountID: "A1", initialBalance: 100)
try await account.withdraw(50)
let balance = await account.currentBalance()
```

All stored properties of an actor are isolated by default. Access from outside the actor requires `await` because the call may suspend while waiting for the actor to become available.

### Actor Reentrancy

Actor methods are reentrant: when an actor suspends at an `await`, other tasks can execute on that actor. This means state may change across suspension points.

```swift
actor ImageCache {
    private var cache: [String: Data] = [:]
    private var inProgress: [String: Task<Data, Error>] = [:]

    func image(for url: String) async throws -> Data {
        // Check cache before suspension — good
        if let cached = cache[url] {
            return cached
        }

        // Coalesce duplicate requests
        if let existing = inProgress[url] {
            return try await existing.value
        }

        let task = Task {
            try await downloadImage(from: url)
        }
        inProgress[url] = task

        let data: Data
        do {
            data = try await task.value   // suspension point — state may change!
        } catch {
            inProgress[url] = nil
            throw error
        }

        // Re-check/update state after suspension
        cache[url] = data
        inProgress[url] = nil
        return data
    }
}
```

Rules for reentrancy:
- Never assume state is unchanged after an `await` inside an actor.
- Perform state checks both before and after suspension points.
- Use in-progress tracking (as above) to coalesce duplicate work.

### nonisolated Methods and Properties

Methods and computed properties that don't access mutable state can be marked `nonisolated`, making them callable synchronously from outside the actor.

```swift
actor UserSession {
    let userID: String                    // let properties are implicitly nonisolated
    private var token: String?

    init(userID: String) {
        self.userID = userID
    }

    nonisolated var description: String { // no access to mutable state
        "Session for user \(userID)"
    }

    nonisolated func hashableID() -> String {
        userID                            // only accesses a let property
    }

    func currentToken() -> String? {
        token                             // accesses mutable state — must be isolated
    }
}

// No await needed for nonisolated members
let session = UserSession(userID: "u123")
print(session.description)                // synchronous
let token = await session.currentToken()  // requires await
```

### Actor Protocols

Actors can conform to protocols. If the protocol is marked with `Actor`, only actor types can conform.

```swift
protocol DataStore: Actor {
    func save(_ data: Data, forKey key: String) async throws
    func load(forKey key: String) async throws -> Data?
}

actor FileDataStore: DataStore {
    private var storage: [String: Data] = [:]

    func save(_ data: Data, forKey key: String) async throws {
        storage[key] = data
    }

    func load(forKey key: String) async throws -> Data? {
        storage[key]
    }
}

// Generic function constrained to any actor-based data store
func backup<S: DataStore>(store: S, key: String, data: Data) async throws {
    try await store.save(data, forKey: key)
}
```


## Global Actors

### Defining Custom Global Actors

A global actor provides a single shared actor instance accessible via an attribute. Useful for serializing access to a subsystem.

```swift
@globalActor
actor DatabaseActor {
    static let shared = DatabaseActor()
}

@DatabaseActor
final class DatabaseService {
    private var connections: [String: Connection] = [:]

    func connect(to url: String) throws -> Connection {
        if let existing = connections[url] {
            return existing
        }
        let conn = try Connection(url: url)
        connections[url] = conn
        return conn
    }

    func disconnect(from url: String) {
        connections[url]?.close()
        connections[url] = nil
    }
}

// Any function can be isolated to the global actor
@DatabaseActor
func performMigration() async throws {
    let service = DatabaseService()
    let conn = try service.connect(to: "db://localhost")
    try conn.migrate()
}
```

### @MainActor as a Built-in Global Actor

`@MainActor` is a built-in global actor that isolates code to the main actor's serial executor. It guarantees serial execution on a single, well-known context.

```swift
@MainActor
final class AppState {
    var currentUser: User?
    var isLoading = false

    func updateUser(_ user: User) {
        isLoading = false
        currentUser = user
    }
}

// Isolate individual functions
@MainActor
func processResult(_ result: Result<User, Error>) {
    switch result {
    case .success(let user):
        print("Processed: \(user.name)")
    case .failure(let error):
        print("Error: \(error)")
    }
}
```

### Global Actor Inference Rules

Global actor isolation propagates in specific cases:
- A subclass inherits the global actor of its superclass.
- A type annotated with a global actor isolates all its stored properties and methods.
- A closure passed to a global-actor-isolated context may inherit that isolation.
- Protocol conformance does NOT infer global actor isolation — you must annotate explicitly.

```swift
@MainActor
class BaseController {
    var state: String = "idle"       // isolated to @MainActor
}

class DerivedController: BaseController {
    // Also @MainActor via inheritance
    func updateState() {
        state = "active"             // no await needed — same isolation
    }
}
```

### Opting Out with nonisolated

Use `nonisolated` to remove global actor isolation from specific members.

```swift
@MainActor
final class ViewModel {
    var title: String = ""
    let id: String

    nonisolated func computeHash() -> Int {
        // Can only access nonisolated/let properties
        id.hashValue
    }

    nonisolated func formatID() -> String {
        "VM-\(id)"
    }
}

// computeHash() and formatID() can be called without await
let vm = await ViewModel()
let hash = vm.computeHash()  // synchronous, no await
```


## Task Groups

### withTaskGroup / withThrowingTaskGroup

Task groups provide structured concurrency for dynamic numbers of concurrent operations.

```swift
func fetchAllUsers(ids: [UUID]) async throws -> [User] {
    try await withThrowingTaskGroup(of: User.self) { group in
        for id in ids {
            group.addTask {
                try await fetchUser(id: id)
            }
        }

        var users: [User] = []
        for try await user in group {
            users.append(user)
        }
        return users
    }
}
```

Non-throwing variant for operations that cannot fail:

```swift
func generateHashes(for inputs: [String]) async -> [String: Int] {
    await withTaskGroup(of: (String, Int).self) { group in
        for input in inputs {
            group.addTask {
                (input, input.hashValue)
            }
        }

        var results: [String: Int] = [:]
        for await (input, hash) in group {
            results[input] = hash
        }
        return results
    }
}
```

### Collecting Results

Order of results from a task group is nondeterministic. To preserve ordering, include an index:

```swift
func fetchPages(urls: [String]) async throws -> [String] {
    let indexed = try await withThrowingTaskGroup(
        of: (Int, String).self
    ) { group in
        for (index, url) in urls.enumerated() {
            group.addTask {
                let content = try await download(url)
                return (index, content)
            }
        }

        var results: [(Int, String)] = []
        for try await pair in group {
            results.append(pair)
        }
        return results
    }

    return indexed.sorted(by: { $0.0 < $1.0 }).map(\.1)
}
```

### Limiting Concurrency Manually

Task groups launch all child tasks eagerly. To limit concurrency, control the number of in-flight tasks:

```swift
func processItems(_ items: [WorkItem], maxConcurrency: Int) async throws -> [Result] {
    try await withThrowingTaskGroup(of: Result.self) { group in
        var results: [Result] = []
        var iterator = items.makeIterator()

        // Seed initial batch
        for _ in 0..<min(maxConcurrency, items.count) {
            if let item = iterator.next() {
                group.addTask { try await process(item) }
            }
        }

        // As each task completes, add the next
        for try await result in group {
            results.append(result)
            if let item = iterator.next() {
                group.addTask { try await process(item) }
            }
        }

        return results
    }
}
```

### withDiscardingTaskGroup (Swift 5.9+)

When you don't need to collect results, `withDiscardingTaskGroup` is more efficient — it discards child task results immediately and avoids accumulating them in memory.

```swift
func sendNotifications(to recipients: [Recipient]) async throws {
    try await withThrowingDiscardingTaskGroup { group in
        for recipient in recipients {
            group.addTask {
                try await sendNotification(to: recipient)
            }
        }
        // No need to iterate results — they are discarded automatically
    }
}
```

Use discarding task groups for fire-and-process workloads like event handlers, notification dispatching, or background cleanup tasks.


## Async Sequences

### AsyncSequence Protocol

`AsyncSequence` is the async counterpart of `Sequence`. Each element is produced asynchronously.

```swift
struct Counter: AsyncSequence {
    typealias Element = Int
    let limit: Int

    struct AsyncIterator: AsyncIteratorProtocol {
        var current = 0
        let limit: Int

        mutating func next() async -> Int? {
            guard current < limit else { return nil }
            defer { current += 1 }
            try? await Task.sleep(for: .milliseconds(100))
            return current
        }
    }

    func makeAsyncIterator() -> AsyncIterator {
        AsyncIterator(limit: limit)
    }
}

// Usage
for await number in Counter(limit: 5) {
    print(number)  // 0, 1, 2, 3, 4
}
```

### AsyncStream and AsyncThrowingStream

`AsyncStream` bridges imperative code (callbacks, delegates, timers) into an async sequence.

```swift
// Non-throwing stream
func heartbeat(interval: Duration) -> AsyncStream<Date> {
    AsyncStream { continuation in
        let task = Task {
            while !Task.isCancelled {
                continuation.yield(Date())
                try? await Task.sleep(for: interval)
            }
            continuation.finish()
        }

        continuation.onTermination = { _ in
            task.cancel()
        }
    }
}

// Usage
for await timestamp in heartbeat(interval: .seconds(1)) {
    print("Heartbeat: \(timestamp)")
}
```

Throwing variant for error-producing sources:

```swift
func events(from source: EventSource) -> AsyncThrowingStream<Event, Error> {
    AsyncThrowingStream { continuation in
        source.onEvent = { event in
            continuation.yield(event)
        }
        source.onError = { error in
            continuation.finish(throwing: error)
        }
        source.onComplete = {
            continuation.finish()
        }
    }
}
```

### for await Loops

`for await` consumes an async sequence element by element. The loop suspends between elements.

```swift
func processEvents(_ stream: AsyncThrowingStream<Event, Error>) async throws {
    for try await event in stream {
        switch event.type {
        case .message:
            try await handleMessage(event)
        case .disconnect:
            break  // exits the for-await loop
        default:
            continue
        }
    }
    // Reached when stream finishes
    print("Stream completed")
}
```

### Combining and Transforming Async Sequences

Use built-in operators (available on all `AsyncSequence` types):

```swift
// map
let names = users.map { $0.name }

// filter
let activeUsers = users.filter { $0.isActive }

// compactMap
let validIDs = rawIDs.compactMap { UUID(uuidString: $0) }

// prefix — take first N elements
let firstThree = events.prefix(3)

// drop — skip while condition is true
let afterWarmup = readings.drop(while: { $0.value < threshold })

// Chaining
for try await name in fetchUserStream()
    .filter { $0.isActive }
    .map { $0.name }
    .prefix(10)
{
    print(name)
}
```

For merging multiple async sequences, use a task group:

```swift
func merge<S1: AsyncSequence, S2: AsyncSequence>(
    _ s1: S1, _ s2: S2
) -> AsyncStream<S1.Element> where S1.Element == S2.Element, S1: Sendable, S2: Sendable, S1.Element: Sendable {
    AsyncStream { continuation in
        let task = Task {
            await withTaskGroup(of: Void.self) { group in
                group.addTask {
                    do {
                        for try await element in s1 {
                            continuation.yield(element)
                        }
                    } catch {}
                }
                group.addTask {
                    do {
                        for try await element in s2 {
                            continuation.yield(element)
                        }
                    } catch {}
                }
            }
            continuation.finish()
        }
        continuation.onTermination = { _ in task.cancel() }
    }
}
```


## Sendable

### Sendable Protocol and What It Means

`Sendable` marks a type as safe to pass across concurrency domains (between actors, tasks, isolation boundaries). The compiler enforces that `Sendable` types contain no shared mutable state.

```swift
// Value types with Sendable fields are safe
struct Point: Sendable {
    let x: Double
    let y: Double
}

// Enums with Sendable associated values are safe
enum Status: Sendable {
    case pending
    case completed(Point)
    case failed(String)
}
```

### @Sendable Closures

Closures that cross isolation boundaries must be `@Sendable`. They can only capture `Sendable` values and cannot capture mutable variables.

```swift
func executeInBackground(_ work: @Sendable () async -> Void) {
    Task {
        await work()
    }
}

let value = 42                          // Int is Sendable — OK
executeInBackground {
    print("Value: \(value)")            // captures Sendable value — OK
}

// This would NOT compile:
// var mutableCount = 0
// executeInBackground {
//     mutableCount += 1               // error: cannot capture mutable variable
// }
```

### Implicit Sendable Conformance

The compiler automatically infers `Sendable` for:
- Structs where all stored properties are `Sendable`
- Enums where all associated values are `Sendable`
- Actors (always implicitly `Sendable`)
- Tuples of `Sendable` types

```swift
struct Config {
    let host: String          // String is Sendable
    let port: Int             // Int is Sendable
    let retryCount: Int       // Int is Sendable
}
// Config is implicitly Sendable (all fields are Sendable and it's a struct)

// Classes are NOT implicitly Sendable — they require explicit conformance
// and must be final with only let properties
final class Endpoint: Sendable {
    let url: String
    let method: String

    init(url: String, method: String) {
        self.url = url
        self.method = method
    }
}
```

### @unchecked Sendable

Use `@unchecked Sendable` when you know a type is safe to send across boundaries but the compiler cannot verify it. This disables compiler checking — you take full responsibility.

```swift
// Thread-safe via internal locking — compiler can't verify this
final class AtomicCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var _value: Int = 0

    var value: Int {
        lock.withLock { _value }
    }

    func increment() {
        lock.withLock { _value += 1 }
    }
}
```

**When to use `@unchecked Sendable`:**
- Types protected by locks, atomics, or other synchronization primitives
- Wrapping C/C++ thread-safe types
- Immutable reference types the compiler cannot prove immutable

**Warnings:**
- Misuse leads to data races that the compiler will not catch.
- Prefer actors or `Sendable` value types first. Use `@unchecked Sendable` as a last resort.
- Document why the type is safe in a comment.

### Swift 6 Strict Concurrency Checking

Swift 6 enables strict concurrency checking by default. All cross-isolation-boundary transfers are checked at compile time.

```swift
// In Package.swift — enable strict concurrency for Swift 6
// swiftSettings: [.swiftLanguageMode(.v6)]

// Or enable incrementally with Swift 5.x:
// swiftSettings: [.enableExperimentalFeature("StrictConcurrency")]
```

Common fixes for strict concurrency warnings:
- Make types `Sendable` (prefer value types).
- Use actors to protect mutable state.
- Mark closures as `@Sendable` when they cross boundaries.
- Use `nonisolated` for properties/methods that don't touch actor state.


## Task Management

### Task Creation and Cancellation

`Task` creates a unit of asynchronous work that inherits the current actor context and priority.

```swift
// Task inherits current isolation context
@MainActor
func startLoading() {
    let task = Task {
        // Inherits @MainActor isolation
        let data = try await fetchData()
        processResult(data)
    }

    // Cancel later if needed
    task.cancel()
}
```

### Task.detached — Rare Use Cases

`Task.detached` creates a task that does NOT inherit the current actor context or priority. Use sparingly.

```swift
// Legitimate use: CPU-heavy work that must not block the current actor
@MainActor
func handleUpload(data: Data) {
    Task.detached(priority: .utility) {
        // Runs outside @MainActor — no isolation inherited
        let compressed = await compress(data)
        let hash = computeHash(compressed)

        // Explicitly hop back if needed
        await MainActor.run {
            self.uploadComplete(hash: hash)
        }
    }
}
```

Prefer `Task` over `Task.detached` in nearly all cases. Detached tasks don't participate in structured concurrency and don't propagate cancellation automatically.

### TaskLocal Values

`TaskLocal` provides task-scoped values that propagate to child tasks automatically. Useful for request IDs, logging contexts, or tracing.

```swift
enum RequestContext {
    @TaskLocal static var requestID: String = "unknown"
    @TaskLocal static var traceLevel: Int = 0
}

func handleRequest() async {
    await RequestContext.$requestID.withValue("req-\(UUID())") {
        await RequestContext.$traceLevel.withValue(1) {
            // All child tasks see these values
            await processRequest()
        }
    }
}

func processRequest() async {
    print("Processing \(RequestContext.requestID)")  // "req-..."
    print("Trace level: \(RequestContext.traceLevel)")  // 1

    // Child tasks inherit TaskLocal values
    async let sub = subtask()
    await sub
}

func subtask() async {
    print("Subtask for \(RequestContext.requestID)")  // same "req-..."
}
```

### Task Priorities

```swift
Task(priority: .high) { await urgentWork() }
Task(priority: .medium) { await normalWork() }
Task(priority: .low) { await backgroundWork() }
Task(priority: .utility) { await maintenanceWork() }
Task(priority: .background) { await cleanupWork() }

// Priority escalation: if a high-priority task awaits a low-priority task,
// the low-priority task is escalated automatically.
```

### Cancellation Propagation and Cooperative Cancellation

Cancellation in Swift is cooperative — tasks must check for cancellation explicitly. Cancellation propagates from parent to child tasks automatically in structured concurrency.

```swift
func fetchAllPages() async throws -> [Page] {
    try await withThrowingTaskGroup(of: Page.self) { group in
        for i in 0..<100 {
            group.addTask {
                // Check cancellation before expensive work
                try Task.checkCancellation()
                return try await fetchPage(i)
            }
        }

        var pages: [Page] = []
        for try await page in group {
            pages.append(page)

            // Cancel remaining tasks if we have enough
            if pages.count >= 10 {
                group.cancelAll()
                break
            }
        }
        return pages
    }
}

// Manual cancellation checking
func longRunningProcess() async throws {
    for chunk in dataChunks {
        // Option 1: Throws CancellationError
        try Task.checkCancellation()

        // Option 2: Check and handle gracefully
        if Task.isCancelled {
            await cleanup()
            return
        }

        await process(chunk)
    }
}
```


## Isolation

### Isolation Domains

An isolation domain is a region of code where mutable state can be safely accessed without data races. Swift has three kinds of isolation domains:

1. **Actor isolation** — each actor instance is its own domain.
2. **Global actor isolation** — all code annotated with the same global actor shares one domain.
3. **nonisolated** — no isolation; can only access `Sendable` data or immutable state.

```swift
actor OrderProcessor {
    // This method is in the OrderProcessor's isolation domain
    func process(_ order: Order) async throws -> Receipt {
        validate(order)                    // same isolation — no await
        return try await charge(order)     // if charge() is on another actor — await
    }

    private func validate(_ order: Order) {
        // Same actor — synchronous access to actor state is fine
    }
}

@MainActor
func displayReceipt(_ receipt: Receipt) {
    // In the @MainActor isolation domain
    print("Receipt: \(receipt.id)")
}
```

### Transferring Values Between Isolation Domains

Values crossing isolation boundaries must be `Sendable`. Swift 6 enforces this strictly.

```swift
actor Processor {
    func process() async -> ProcessedResult {
        let result = ProcessedResult(data: computeData())
        return result  // result must be Sendable to leave the actor
    }
}

// Sendable struct — safe to transfer
struct ProcessedResult: Sendable {
    let data: [UInt8]
}
```

### `sending` Parameter Modifier (Swift 6)

The `sending` keyword indicates that a value is being transferred into a different isolation domain. The caller gives up access to the value.

```swift
actor Worker {
    func accept(_ item: sending WorkItem) {
        // Worker now owns `item` exclusively
        // Caller cannot use `item` after passing it
    }
}

struct WorkItem: ~Copyable {
    var data: [UInt8]
}

func submit() async {
    let item = WorkItem(data: [1, 2, 3])
    let worker = Worker()
    await worker.accept(item)
    // item is consumed — cannot be used here
}
```

The `sending` modifier enables transferring non-Sendable types safely by proving the caller no longer retains a reference.

### nonisolated(unsafe)

`nonisolated(unsafe)` is an escape hatch that suppresses isolation checking for a specific property. The compiler trusts you that concurrent access is safe.

```swift
@MainActor
final class Logger {
    // This property is accessed only during init and is effectively immutable,
    // but the compiler can't prove it. nonisolated(unsafe) silences the warning.
    nonisolated(unsafe) let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return f
    }()
}
```

**Use only when:**
- The property is effectively immutable after initialization.
- Access patterns are safe but unprovable by the compiler.
- You have exhausted `nonisolated`, `Sendable`, and actor-based solutions.

**Never use as a blanket fix** for concurrency warnings. Each usage should have a comment explaining why it is safe.


## Continuations

### withCheckedContinuation / withCheckedThrowingContinuation

Continuations bridge callback-based APIs into `async/await`. The "checked" variants include runtime validation that `resume` is called exactly once.

```swift
func fetchData(from url: String) async throws -> Data {
    try await withCheckedThrowingContinuation { continuation in
        performLegacyFetch(url: url) { result in
            switch result {
            case .success(let data):
                continuation.resume(returning: data)
            case .failure(let error):
                continuation.resume(throwing: error)
            }
        }
    }
}

// Non-throwing variant
func currentLocation() async -> Coordinate {
    await withCheckedContinuation { continuation in
        locationProvider.requestLocation { coordinate in
            continuation.resume(returning: coordinate)
        }
    }
}
```

### Wrapping Callback-Based APIs

Common pattern for wrapping delegate-based APIs:

```swift
class ConnectionWrapper {
    private var connection: LegacyConnection

    init(connection: LegacyConnection) {
        self.connection = connection
    }

    func connect() async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            connection.connect(
                onSuccess: {
                    continuation.resume()
                },
                onFailure: { error in
                    continuation.resume(throwing: error)
                }
            )
        }
    }

    func receive() async throws -> Message {
        try await withCheckedThrowingContinuation { continuation in
            connection.onNextMessage = { message in
                continuation.resume(returning: message)
            }
            connection.onError = { error in
                continuation.resume(throwing: error)
            }
        }
    }
}
```

### withUnsafeContinuation — Performance-Critical Cases

`withUnsafeContinuation` omits runtime checks. Use only in performance-critical paths where you are certain `resume` is called exactly once.

```swift
func fastLookup(key: String) async -> Value? {
    await withUnsafeContinuation { continuation in
        cache.asyncGet(key) { value in
            continuation.resume(returning: value)
        }
    }
}
```

Prefer `withCheckedContinuation` in development and testing. Switch to `withUnsafeContinuation` only after profiling shows the check is a bottleneck (rare).

### Rules: Resume Exactly Once

A continuation must be resumed exactly once. Violating this rule leads to:
- **Zero resumes**: the calling task hangs forever (leak). Checked variant traps in debug.
- **Multiple resumes**: undefined behavior. Checked variant traps immediately.

```swift
// WRONG — may resume twice if timeout fires after success
func badExample() async throws -> Data {
    try await withCheckedThrowingContinuation { continuation in
        fetchWithTimeout(
            onSuccess: { data in
                continuation.resume(returning: data)     // first resume
            },
            onTimeout: {
                continuation.resume(throwing: TimeoutError())  // potential second resume!
            }
        )
    }
}

// CORRECT — guard against multiple resumes
func safeExample() async throws -> Data {
    try await withCheckedThrowingContinuation { continuation in
        let resumed = AtomicFlag()

        fetchWithTimeout(
            onSuccess: { data in
                if resumed.setIfFirst() {
                    continuation.resume(returning: data)
                }
            },
            onTimeout: {
                if resumed.setIfFirst() {
                    continuation.resume(throwing: TimeoutError())
                }
            }
        )
    }
}
```


## Migrating from GCD

### DispatchQueue.main to @MainActor

```swift
// Before (GCD)
DispatchQueue.main.async {
    self.updateState(newValue)
}

// After (Swift Concurrency)
@MainActor
func updateState(_ value: Value) {
    state = value
}

// Or hop to main actor explicitly
await MainActor.run {
    updateState(newValue)
}
```

### DispatchQueue.global() to Task / Actors

```swift
// Before (GCD)
DispatchQueue.global(qos: .userInitiated).async {
    let result = heavyComputation()
    DispatchQueue.main.async {
        self.handleResult(result)
    }
}

// After (Swift Concurrency)
Task(priority: .userInitiated) {
    let result = await heavyComputation()
    await MainActor.run {
        handleResult(result)
    }
}
```

### DispatchGroup to TaskGroup

```swift
// Before (GCD)
let group = DispatchGroup()
var results: [Data] = []
let lock = NSLock()

for url in urls {
    group.enter()
    fetchData(url) { data in
        lock.withLock { results.append(data) }
        group.leave()
    }
}
group.notify(queue: .main) {
    processAll(results)
}

// After (Swift Concurrency)
func fetchAll(urls: [String]) async throws -> [Data] {
    try await withThrowingTaskGroup(of: Data.self) { group in
        for url in urls {
            group.addTask { try await fetchData(url) }
        }
        var results: [Data] = []
        for try await data in group {
            results.append(data)
        }
        return results
    }
}
```

### DispatchSemaphore to AsyncStream or Actors

Semaphores block threads and must never be used in async contexts (risk of deadlock). Replace with structured alternatives.

```swift
// Before (GCD) — producer/consumer with semaphore
let semaphore = DispatchSemaphore(value: 0)
var sharedItem: Item?

// Producer
queue.async {
    sharedItem = produceItem()
    semaphore.signal()
}

// Consumer
semaphore.wait()
consume(sharedItem!)

// After (Swift Concurrency) — use AsyncStream
let (stream, continuation) = AsyncStream.makeStream(of: Item.self)

// Producer
Task {
    let item = await produceItem()
    continuation.yield(item)
    continuation.finish()
}

// Consumer
for await item in stream {
    consume(item)
}
```

For bounded concurrency (semaphore as a limiter):

```swift
// Before: DispatchSemaphore(value: 4) to limit concurrency
// After: use the task group throttling pattern (see Task Groups section)
func processWithLimit(_ items: [Item], limit: Int) async throws {
    try await withThrowingTaskGroup(of: Void.self) { group in
        var iterator = items.makeIterator()
        for _ in 0..<min(limit, items.count) {
            if let item = iterator.next() {
                group.addTask { try await process(item) }
            }
        }
        for try await _ in group {
            if let item = iterator.next() {
                group.addTask { try await process(item) }
            }
        }
    }
}
```

### Common Migration Patterns Summary

| GCD Pattern | Swift Concurrency Replacement |
|---|---|
| `DispatchQueue.main.async` | `@MainActor` or `MainActor.run` |
| `DispatchQueue.global().async` | `Task { }` or actors |
| `DispatchGroup` | `TaskGroup` or `async let` |
| `DispatchSemaphore` | `AsyncStream`, actors, or task group throttling |
| `DispatchWorkItem` | `Task` (supports cancellation) |
| `DispatchQueue` (serial) | `actor` |
| `DispatchQueue` (concurrent + barrier) | `actor` or custom serial executor |
| `DispatchSource.makeTimerSource` | `Task.sleep(for:)` + loop, or `AsyncStream` |


## Migrating from Combine (Brief, Platform-Agnostic)

### Publisher to AsyncSequence

Combine publishers and `AsyncSequence` serve similar roles — producing values over time. `AsyncSequence` is built into the language and works everywhere Swift runs.

```swift
// Combine-style thinking
// publisher.map { transform($0) }.filter { $0.isValid }

// AsyncSequence equivalent
for try await value in source.map({ transform($0) }).filter({ $0.isValid }) {
    handle(value)
}
```

For custom value production, replace `PassthroughSubject` / `CurrentValueSubject` with `AsyncStream`:

```swift
// Combine: PassthroughSubject<Event, Never>()
// AsyncSequence equivalent:
let (stream, continuation) = AsyncStream.makeStream(of: Event.self)

// Produce
continuation.yield(.userLoggedIn)

// Consume
for await event in stream {
    handleEvent(event)
}

// Finish
continuation.finish()
```

### sink to for await

```swift
// Combine
// cancellable = publisher.sink { value in handleValue(value) }

// AsyncSequence
let task = Task {
    for await value in asyncSequence {
        handleValue(value)
    }
}
// Cancel when done
task.cancel()
```

### When Combine (or Reactive Frameworks) Are Still Useful

`AsyncSequence` does not natively support all reactive operators. Reactive frameworks remain useful for:

- **Complex operator chains** — `combineLatest`, `merge`, `debounce`, `throttle`, `zip` with backpressure semantics are mature in reactive frameworks but require manual implementation with `AsyncSequence`.
- **Backpressure** — `AsyncStream` has a buffering policy but lacks the fine-grained demand system of reactive streams.
- **Multi-subscriber broadcasting** — `AsyncStream` is single-consumer. Broadcasting to multiple consumers requires custom infrastructure.
- **Time-based operators** — `debounce`, `throttle`, `delay`, `timeout` require manual implementation with async sequences.

For new code with simple data flows, prefer `AsyncSequence`. For complex event processing pipelines, evaluate whether the reactive framework's operator library justifies the dependency.
