# Swift Concurrency Reference (Apple Platforms)

## Contents
- async/await fundamentals, typed throws (Swift 6+), Result-based error handling for async
- Structured concurrency (`async let`, `TaskGroup`, cancellation)
- Actors (custom, `@MainActor`, global actors, isolation, `nonisolated`)
- Sendable (protocol, `@Sendable` closures, `sending` parameter)
- Task management (`Task`, `Task.detached`, priority, cancellation, `.task` modifier)
- `@MainActor` in practice (view models, UI updates, performance)
- AsyncSequence and AsyncStream (building, consuming, bridging)
- Migrating from GCD
- Migrating from Combine
- Common pitfalls (data races, reentrancy, deadlocks)
- Testing async code

## async/await Fundamentals

Any function marked `async` can suspend — yielding the thread while waiting for a result — then resume when the value is available.

```swift
func fetchUser(id: UUID) async throws -> User {
    let (data, response) = try await URLSession.shared.data(from: userURL(id))
    guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
        throw AppError.networkFailure
    }
    return try JSONDecoder().decode(User.self, from: data)
}

// Calling site
let user = try await fetchUser(id: userId)
```

### Typed throws (Swift 6+)

Swift 6 introduces typed throws so callers know exactly which error type to handle:

```swift
enum NetworkError: Error {
    case timeout
    case unauthorized
    case serverError(statusCode: Int)
}

func fetchData(from url: URL) async throws(NetworkError) -> Data {
    let (data, response) = try await {
        do {
            return try await URLSession.shared.data(from: url)
        } catch {
            throw NetworkError.timeout
        }
    }()
    guard let http = response as? HTTPURLResponse else {
        throw .serverError(statusCode: 0)
    }
    switch http.statusCode {
    case 200...299: return data
    case 401: throw .unauthorized
    default: throw .serverError(statusCode: http.statusCode)
    }
}

// Single typed-throws call — error type is inferred correctly
do {
    let data = try await fetchData(from: url)
} catch .timeout {
    showRetryPrompt()
} catch .unauthorized {
    navigateToLogin()
} catch .serverError(let code) {
    showServerError(code)
}
```

**Caveat — async inference gaps:** Typed throws has known compiler limitations in async contexts (as of Swift 6.1). Error type inference breaks with `async let` ([swift#76169](https://github.com/swiftlang/swift/issues/76169)), nested `do`-`catch` ([swift#75260](https://github.com/swiftlang/swift/issues/75260)), and generic error type parameters. Exhaustive pattern-matching in `catch` clauses is also not supported ([swift#74555](https://github.com/swiftlang/swift/issues/74555)) — you must use `catch { switch error { ... } }` instead.

### Result-based error handling for async

When combining multiple async calls with custom error types, prefer `Result<Success, Failure>`. Typed throws loses error type propagation when multiple `async throws(E)` calls appear in the same `do`-`catch` block — the compiler widens to `any Error`. `Result` preserves per-call error typing and allows callers to handle each error independently:

```swift
func fetchData(from url: URL) async -> Result<Data, NetworkError> {
    let data: Data
    let response: URLResponse
    do {
        (data, response) = try await URLSession.shared.data(from: url)
    } catch {
        return .failure(.timeout)
    }
    guard let http = response as? HTTPURLResponse else {
        return .failure(.serverError(statusCode: 0))
    }
    switch http.statusCode {
    case 200...299: return .success(data)
    case 401: return .failure(.unauthorized)
    default: return .failure(.serverError(statusCode: http.statusCode))
    }
}

// Each call preserves its error type — no compiler inference issues
let dataResult = await fetchData(from: url)
let configResult = await fetchConfig(from: configURL)

switch dataResult {
case .success(let data):
    process(data)
case .failure(.timeout):
    showRetryPrompt()
case .failure(.unauthorized):
    navigateToLogin()
case .failure(.serverError(let code)):
    showServerError(code)
}
```

Rules:
- Use typed throws for simple, single-call async contexts or synchronous code where callers benefit from exhaustive handling.
- Prefer `Result<Success, Failure>` when combining multiple async calls with custom error types — typed throws inference breaks in this scenario.
- Continue using untyped `throws` at module boundaries or when errors are heterogeneous.
- Typed throws compose — `throws(NetworkError)` inside `throws(AppError)` requires mapping.

## Structured Concurrency

Structured concurrency ties child tasks to a parent scope. When the parent is cancelled or throws, all children are automatically cancelled.

### `async let` — parallel bindings

```swift
func loadDashboard() async throws -> Dashboard {
    async let profile = fetchProfile()
    async let stats = fetchStats()
    async let notifications = fetchNotifications()
    return try await Dashboard(
        profile: profile,
        stats: stats,
        notifications: notifications
    )
}
```

All three requests run concurrently. If any throws, the others are cancelled. If the parent task is cancelled, all three are cancelled.

### TaskGroup

Use `TaskGroup` when the number of concurrent operations is dynamic:

```swift
func fetchAllUsers(ids: [UUID]) async throws -> [User] {
    try await withThrowingTaskGroup(of: User.self) { group in
        for id in ids {
            group.addTask { try await fetchUser(id: id) }
        }
        var users: [User] = []
        for try await user in group {
            users.append(user)
        }
        return users
    }
}
```

### Limiting concurrency in TaskGroup

```swift
func downloadImages(urls: [URL]) async throws -> [UIImage] {
    try await withThrowingTaskGroup(of: UIImage.self) { group in
        let maxConcurrent = 4
        var results: [UIImage] = []
        var index = 0

        // Seed initial batch
        for _ in 0..<min(maxConcurrent, urls.count) {
            let url = urls[index]; index += 1
            group.addTask { try await self.downloadImage(from: url) }
        }

        // As each completes, add next
        for try await image in group {
            results.append(image)
            if index < urls.count {
                let url = urls[index]; index += 1
                group.addTask { try await self.downloadImage(from: url) }
            }
        }
        return results
    }
}
```

### Cancellation checking

Cancellation is cooperative — your code must check for it.

```swift
func processItems(_ items: [Item]) async throws {
    for item in items {
        // Option 1: throws CancellationError if cancelled
        try Task.checkCancellation()

        // Option 2: check and handle gracefully
        guard !Task.isCancelled else {
            await saveProgress()
            return
        }

        await process(item)
    }
}
```

### `withTaskCancellationHandler`

Wraps a block with a handler that fires immediately when the task is cancelled — useful for cancelling underlying non-async work:

```swift
func download(url: URL) async throws -> Data {
    let delegate = DownloadDelegate()
    return try await withTaskCancellationHandler {
        try await delegate.download(url: url)
    } onCancel: {
        delegate.cancel() // Runs immediately on the cancelling thread
    }
}
```

The `onCancel` closure runs concurrently with the operation — it must be `Sendable` and thread-safe.

## Actors

Actors protect mutable state by serializing access. Only one task can execute on an actor at a time.

### Custom actors

```swift
actor ImageCache {
    private var cache: [URL: UIImage] = [:]

    func image(for url: URL) -> UIImage? {
        cache[url]
    }

    func store(_ image: UIImage, for url: URL) {
        cache[url] = image
    }

    func fetchOrLoad(url: URL) async throws -> UIImage {
        if let cached = cache[url] { return cached }
        let (data, _) = try await URLSession.shared.data(from: url)
        guard let image = UIImage(data: data) else {
            throw AppError.invalidImageData
        }
        cache[url] = image
        return image
    }
}

// Usage — all access goes through await
let cache = ImageCache()
let image = try await cache.fetchOrLoad(url: thumbnailURL)
```

### `@MainActor`

A global actor that ensures execution on the main thread. Essential for UI work.

```swift
@MainActor
@Observable
class SettingsViewModel {
    var settings: Settings?
    var errorMessage: String?

    func load() async {
        do {
            settings = try await settingsService.fetch()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
```

### Global actors

You can define custom global actors for subsystem-wide isolation:

```swift
@globalActor
actor DatabaseActor {
    static let shared = DatabaseActor()
}

@DatabaseActor
class PersistenceController {
    var items: [Item] = []

    func save(_ item: Item) {
        items.append(item)
        // All methods on this class are isolated to DatabaseActor
    }
}
```

### Actor isolation and `nonisolated`

By default, all stored properties and methods of an actor are isolated. Use `nonisolated` for properties/methods that don't touch mutable state:

```swift
actor UserSession {
    let userId: UUID              // let properties are implicitly nonisolated in Swift 6
    var token: String

    nonisolated var description: String {
        "Session for \(userId)"  // OK — userId is a let constant
    }

    func updateToken(_ newToken: String) {
        token = newToken          // Isolated — safe access to mutable state
    }
}
```

Rules:
- `nonisolated` methods cannot access mutable actor state.
- In Swift 6, `let` properties on actors are implicitly `nonisolated` and can be accessed synchronously.
- Use `nonisolated` to conform to protocols like `Hashable`, `CustomStringConvertible` without requiring async access.

## Sendable

`Sendable` marks types as safe to pass across concurrency domains (between actors, tasks, etc.). Swift 6 strict concurrency enforces this at compile time.

### Sendable protocol

```swift
// Value types with Sendable fields are automatically Sendable
struct UserDTO: Sendable {
    let id: UUID
    let name: String
    let email: String
}

// Enums with Sendable associated values are Sendable
enum LoadingState: Sendable {
    case idle
    case loading
    case loaded(UserDTO)
    case failed(String) // String is Sendable; Error is not
}

// Classes must be final and have only immutable Sendable stored properties
final class AppConfig: Sendable {
    let apiBaseURL: URL
    let maxRetries: Int

    init(apiBaseURL: URL, maxRetries: Int) {
        self.apiBaseURL = apiBaseURL
        self.maxRetries = maxRetries
    }
}
```

### `@Sendable` closures

Closures passed across isolation boundaries must be `@Sendable` — they cannot capture mutable local variables or non-Sendable references.

```swift
func processConcurrently(items: [Item]) async {
    await withTaskGroup(of: Void.self) { group in
        for item in items {
            group.addTask { // @Sendable inferred
                await process(item) // item must be Sendable
            }
        }
    }
}
```

### `sending` parameter (Swift 6+)

The `sending` keyword indicates a parameter that is transferred to a different isolation domain. The compiler ensures the caller does not use the value after passing it:

```swift
func enqueue(_ work: sending () async -> Void) {
    // The closure is transferred — caller cannot reference captured state after this call
    Task { await work() }
}

actor Processor {
    func submit(_ item: sending Item) {
        // item is now owned by the actor — no data race possible
        process(item)
    }
}
```

### Common patterns to satisfy strict concurrency

```swift
// 1. Use @MainActor isolation for UI-bound classes
@MainActor
@Observable
class HomeViewModel { // No Sendable needed — isolated to MainActor
    var items: [Item] = []
}

// 2. Use Sendable value types for data transfer
struct APIResponse: Sendable, Codable {
    let users: [UserDTO]
    let nextPage: Int?
}

// 3. Mark non-Sendable types with @unchecked Sendable when you manage thread safety yourself
final class ThreadSafeCache<Key: Hashable & Sendable, Value: Sendable>: @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [Key: Value] = [:]

    func value(for key: Key) -> Value? {
        lock.lock(); defer { lock.unlock() }
        return storage[key]
    }

    func setValue(_ value: Value, for key: Key) {
        lock.lock(); defer { lock.unlock() }
        storage[key] = value
    }
}

// 4. Use actors instead of locks when possible (preferred over @unchecked Sendable)
actor Cache<Key: Hashable & Sendable, Value: Sendable> {
    private var storage: [Key: Value] = [:]

    func value(for key: Key) -> Value? { storage[key] }
    func setValue(_ value: Value, for key: Key) { storage[key] = value }
}
```

Rules:
- Prefer value types (`struct`, `enum`) — they are automatically `Sendable` when all fields are `Sendable`.
- Use `@unchecked Sendable` sparingly and only when you have manual synchronization (locks, atomics).
- Actors are implicitly `Sendable`. Prefer actors over `@unchecked Sendable` classes.

## Task Management

### `Task { }`

Creates an unstructured task that inherits the current actor context and priority:

```swift
@MainActor
class SearchViewModel {
    private var searchTask: Task<Void, Never>?

    func search(query: String) {
        searchTask?.cancel() // Cancel previous search
        searchTask = Task {
            try? await Task.sleep(for: .milliseconds(300)) // Debounce
            guard !Task.isCancelled else { return }
            let results = try? await searchService.search(query)
            self.results = results ?? [] // Runs on MainActor — inherited
        }
    }
}
```

### `Task.detached`

Creates a task that does NOT inherit actor context or priority. Use sparingly.

```swift
// Detached — does NOT run on MainActor even if called from MainActor context
Task.detached(priority: .background) {
    await self.generateThumbnails(for: photos)
    // Must explicitly hop to MainActor for UI updates
    await MainActor.run {
        self.thumbnailsReady = true
    }
}
```

Prefer `Task { }` over `Task.detached` in most cases. Use `Task.detached` only when you explicitly want to escape the current actor context.

### Task priority

```swift
Task(priority: .userInitiated) { await loadVisibleContent() }
Task(priority: .utility) { await prefetchNextPage() }
Task(priority: .background) { await syncAnalytics() }
```

| Priority | Use case |
|---|---|
| `.userInitiated` | Direct response to user action |
| `.medium` | Default |
| `.utility` | Long-running work user is aware of |
| `.low` | Prefetching, non-urgent background work |
| `.background` | Maintenance, cleanup, analytics |

### `.task` view modifier lifecycle

The `.task` modifier creates a task tied to the view's lifecycle. The task is cancelled when the view disappears.

```swift
struct UserListView: View {
    @State private var users: [User] = []

    var body: some View {
        List(users) { user in
            UserRow(user: user)
        }
        // Starts when view appears, cancels when view disappears
        .task {
            users = (try? await userService.fetchAll()) ?? []
        }
        // Re-runs when id changes (previous task is cancelled)
        .task(id: selectedFilter) {
            users = (try? await userService.fetch(filter: selectedFilter)) ?? []
        }
    }
}
```

Rules:
- Prefer `.task` over `Task { }` in views — automatic cancellation prevents memory leaks and stale updates.
- Use `.task(id:)` to re-trigger work when a dependency changes.
- A `Task { }` created inside `onAppear` will NOT cancel on disappear — you must manage cancellation manually.

## @MainActor in Practice

### View models

Always annotate view models with `@MainActor`. They hold UI state and must update on the main thread.

```swift
@MainActor
@Observable
class OrderListViewModel {
    var orders: [Order] = []
    var isLoading = false
    var error: AppError?

    private let orderService: OrderService

    init(orderService: OrderService) {
        self.orderService = orderService
    }

    func loadOrders() async {
        isLoading = true
        defer { isLoading = false }
        do {
            orders = try await orderService.fetchAll()
        } catch let appError as AppError {
            error = appError
        } catch {
            self.error = .unknown(error.localizedDescription)
        }
    }

    func deleteOrder(_ order: Order) async {
        do {
            try await orderService.delete(order.id)
            orders.removeAll { $0.id == order.id }
        } catch {
            self.error = .deleteFailed
        }
    }
}
```

### Offloading expensive work from MainActor

When a `@MainActor`-isolated type needs to do heavy computation, push that work off the main thread explicitly:

```swift
@MainActor
@Observable
class ImageProcessingViewModel {
    var processedImage: UIImage?

    func processImage(_ input: UIImage) async {
        // Heavy work runs on a background thread
        let result = await Task.detached(priority: .userInitiated) {
            ImageProcessor.applyFilters(to: input) // CPU-intensive
        }.value

        // Back on MainActor automatically (we're in a @MainActor method)
        processedImage = result
    }
}
```

### When NOT to use @MainActor

```swift
// Services/repositories that only do network/disk work — no UI state
// Do NOT annotate with @MainActor
class APIClient {
    func fetch<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let (data, _) = try await URLSession.shared.data(for: endpoint.request)
        return try JSONDecoder().decode(T.self, from: data)
    }
}

// Actors for shared mutable state — use dedicated actor isolation, not MainActor
actor DownloadManager {
    private var activeDownloads: [URL: Task<Data, Error>] = [:]

    func download(url: URL) async throws -> Data {
        if let existing = activeDownloads[url] {
            return try await existing.value
        }
        let task = Task { try await URLSession.shared.data(from: url).0 }
        activeDownloads[url] = task
        defer { activeDownloads[url] = nil }
        return try await task.value
    }
}
```

Rules:
- `@MainActor` for view models and any type that directly drives UI.
- Do NOT put services, repositories, or network clients on `@MainActor`.
- Offload CPU work from `@MainActor` with `Task.detached` or a dedicated actor.
- `nonisolated` on individual methods when a `@MainActor` class has methods that do not touch UI state.

## AsyncSequence and AsyncStream

### Consuming async sequences

```swift
// URLSession bytes
func downloadLargeFile(url: URL) async throws {
    let (bytes, _) = try await URLSession.shared.bytes(from: url)
    var data = Data()
    for try await byte in bytes {
        data.append(byte)
        if data.count % (1024 * 1024) == 0 {
            await updateProgress(bytesReceived: data.count)
        }
    }
}

// Notifications as an async sequence
func observeKeyboardNotifications() async {
    for await notification in NotificationCenter.default.notifications(named: UIResponder.keyboardWillShowNotification) {
        guard let frame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect else { continue }
        await updateKeyboardHeight(frame.height)
    }
}
```

### Building with AsyncStream

Bridge callback-based or delegate-based APIs to async sequences:

```swift
// Bridging CLLocationManager
func locationUpdates() -> AsyncStream<CLLocation> {
    AsyncStream { continuation in
        let delegate = LocationDelegate(
            onUpdate: { location in
                continuation.yield(location)
            },
            onError: { _ in
                continuation.finish()
            }
        )
        continuation.onTermination = { _ in
            delegate.stopUpdating()
        }
        delegate.startUpdating()
    }
}

// Usage
for await location in locationUpdates() {
    await updateMap(with: location)
}
```

### AsyncThrowingStream for error-propagating sequences

```swift
func bluetoothUpdates() -> AsyncThrowingStream<BluetoothReading, Error> {
    AsyncThrowingStream { continuation in
        bluetoothManager.onReading = { reading in
            continuation.yield(reading)
        }
        bluetoothManager.onError = { error in
            continuation.finish(throwing: error)
        }
        bluetoothManager.onDisconnect = {
            continuation.finish()
        }
        continuation.onTermination = { _ in
            bluetoothManager.disconnect()
        }
        bluetoothManager.connect()
    }
}
```

### Transforming async sequences

```swift
let validReadings = bluetoothUpdates()
    .filter { $0.signalStrength > -80 }
    .map { Reading(value: $0.value, timestamp: Date()) }
    .prefix(100) // Take first 100

for try await reading in validReadings {
    process(reading)
}
```

## Migrating from GCD

### `DispatchQueue.main.async` -> `@MainActor`

```swift
// Before (GCD)
func updateUI(with data: Data) {
    DispatchQueue.main.async {
        self.label.text = String(data: data, encoding: .utf8)
    }
}

// After (Swift Concurrency)
@MainActor
func updateUI(with data: Data) {
    label.text = String(data: data, encoding: .utf8)
}

// Or, from a non-MainActor context:
await MainActor.run {
    label.text = String(data: data, encoding: .utf8)
}
```

### `DispatchGroup` -> `async let` or `TaskGroup`

```swift
// Before (GCD)
func loadAll(completion: @escaping (Profile?, [Order]?) -> Void) {
    let group = DispatchGroup()
    var profile: Profile?
    var orders: [Order]?

    group.enter()
    fetchProfile { result in profile = result; group.leave() }

    group.enter()
    fetchOrders { result in orders = result; group.leave() }

    group.notify(queue: .main) { completion(profile, orders) }
}

// After (Swift Concurrency)
func loadAll() async throws -> (Profile, [Order]) {
    async let profile = fetchProfile()
    async let orders = fetchOrders()
    return try await (profile, orders)
}
```

### Serial queue (state protection) -> Actor

```swift
// Before (GCD)
class TokenManager {
    private let queue = DispatchQueue(label: "token-manager")
    private var _token: String?

    func setToken(_ token: String) {
        queue.sync { _token = token }
    }

    func getToken() -> String? {
        queue.sync { _token }
    }
}

// After (Swift Concurrency)
actor TokenManager {
    private var token: String?

    func setToken(_ newToken: String) {
        token = newToken
    }

    func getToken() -> String? {
        token
    }
}
```

### `DispatchQueue.global()` -> `Task` or `Task.detached`

```swift
// Before (GCD)
DispatchQueue.global(qos: .userInitiated).async {
    let result = heavyComputation()
    DispatchQueue.main.async {
        self.updateUI(with: result)
    }
}

// After (Swift Concurrency)
Task {
    let result = await Task.detached(priority: .userInitiated) {
        heavyComputation()
    }.value
    await MainActor.run { updateUI(with: result) }
}
```

### Migration summary

| GCD Pattern | Swift Concurrency Replacement |
|---|---|
| `DispatchQueue.main.async` | `@MainActor`, `MainActor.run` |
| `DispatchQueue.global().async` | `Task { }`, `Task.detached` |
| `DispatchGroup` | `async let`, `TaskGroup` |
| Serial `DispatchQueue` (state) | `actor` |
| `DispatchSemaphore` | `AsyncStream`, actor-based throttling |
| `DispatchWorkItem` with cancel | `Task` with cancellation |
| `asyncAfter` | `Task.sleep(for:)` |

## Migrating from Combine

### When to keep Combine

Combine is not deprecated and remains the right tool for specific patterns. AsyncStream is **unicast** (single consumer), while Combine subjects are **multicast** (multiple subscribers with backpressure). They are complementary, not interchangeable.

- **Multi-subscriber reactive streams** — `CurrentValueSubject`, `PassthroughSubject` with multiple observers. AsyncStream cannot replicate this without manual fan-out.
- **Complex stream operators** — `debounce`, `throttle`, `combineLatest`, `merge`, `scan`, `switchToLatest` with backpressure. AsyncSequence operators are more limited.
- **SwiftUI `@Published` with `ObservableObject`** — if targeting iOS 16 or earlier.
- **KVO observation** — Combine's `publisher(for:)` is still convenient for observing UIKit properties.

### When to use async/await instead

- **Single-shot async work** — API calls, database queries. Use `async throws` instead of `Future`.
- **Single-consumer async sequences** — bridging a delegate/callback API for one consumer. Use `AsyncStream`.
- **iOS 17+ view model state** — `@Observable` replaces `ObservableObject`/`@Published` entirely, no Combine needed.

### Bridging: `values` property (AsyncPublisher)

Any Combine publisher can be consumed as an AsyncSequence:

```swift
import Combine

let subject = PassthroughSubject<String, Never>()

// Combine -> AsyncSequence
Task {
    for await value in subject.values {
        print("Received: \(value)")
    }
}

subject.send("Hello")
subject.send("World")
```

### Replacing common Combine patterns

```swift
// Before: Combine search with debounce
class SearchViewModel: ObservableObject {
    @Published var query = ""
    @Published var results: [Result] = []
    private var cancellables = Set<AnyCancellable>()

    init() {
        $query
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .removeDuplicates()
            .sink { [weak self] query in
                self?.performSearch(query)
            }
            .store(in: &cancellables)
    }
}

// After: async/await with manual debounce
@MainActor
@Observable
class SearchViewModel {
    var query = "" {
        didSet { handleQueryChanged() }
    }
    var results: [SearchResult] = []
    private var searchTask: Task<Void, Never>?

    private func handleQueryChanged() {
        searchTask?.cancel()
        searchTask = Task {
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            results = (try? await searchService.search(query)) ?? []
        }
    }
}
```

### Choosing the right tool

| Need | Recommended tool |
|---|---|
| SwiftUI view model state (iOS 17+) | `@Observable` |
| Single-shot async data fetching | `async/await` |
| Single-consumer async sequence | `AsyncStream` / `AsyncSequence` |
| Multi-subscriber reactive streams | Combine (`CurrentValueSubject`, `PassthroughSubject`) |
| Complex stream operators (`combineLatest`, `debounce`, etc.) | Combine |
| Cross-platform async sequences | `AsyncSequence` + Swift Async Algorithms |

## Common Pitfalls

### 1. Data races from non-Sendable types crossing isolation

```swift
// Bug: UIImage is not Sendable
@MainActor
class PhotoViewModel {
    func upload(_ image: UIImage) {
        Task.detached {
            await api.upload(image) // Warning: non-Sendable UIImage crosses isolation
        }
    }
}

// Fix: Convert to Sendable data before crossing boundaries
@MainActor
class PhotoViewModel {
    func upload(_ image: UIImage) {
        guard let data = image.pngData() else { return } // Data is Sendable
        Task.detached {
            await api.upload(data)
        }
    }
}
```

### 2. Actor reentrancy

Actors are reentrant — when an actor method hits an `await`, other callers can execute on the actor before the first call resumes. State may change across `await` boundaries.

```swift
actor BankAccount {
    var balance: Decimal

    // Bug: balance can change between read and write
    func withdraw(_ amount: Decimal) async throws {
        guard balance >= amount else { throw BankError.insufficientFunds }
        let newBalance = await processWithBank(amount) // Reentrancy: another withdraw can execute here
        balance = newBalance // May overdraw — another withdraw changed balance
    }

    // Fix: check state AFTER await, or restructure to avoid suspension between check and mutation
    func withdraw(_ amount: Decimal) async throws {
        let result = await processWithBank(amount)
        guard balance >= amount else { throw BankError.insufficientFunds } // Re-check after await
        balance -= amount
    }
}
```

Rules:
- Assume actor state may change across any `await` point.
- Re-validate conditions after `await` resumes.
- Minimize the number of `await` calls within actor methods when state consistency matters.

### 3. Deadlock: blocking the main thread on async work

```swift
// Bug: blocks main thread waiting for an async result
@MainActor
func loadSync() -> User {
    let semaphore = DispatchSemaphore(value: 0)
    var result: User?
    Task {
        result = try? await fetchUser()
        semaphore.signal()
    }
    semaphore.wait() // Deadlock — main thread is blocked, Task needs main thread
    return result!
}

// Fix: make the function async
@MainActor
func load() async -> User? {
    try? await fetchUser()
}
```

Never use `DispatchSemaphore`, `NSLock`, or any blocking primitive to wait for async work on the main thread.

### 4. Forgetting cancellation

```swift
// Bug: task keeps running after view disappears, writes to stale state
struct ChatView: View {
    @State private var messages: [Message] = []

    var body: some View {
        List(messages) { MessageRow(message: $0) }
            .onAppear {
                Task { // Not tied to view lifecycle!
                    for await msg in chatService.messageStream() {
                        messages.append(msg) // May update after view is gone
                    }
                }
            }
    }
}

// Fix: use .task modifier — automatically cancelled on disappear
struct ChatView: View {
    @State private var messages: [Message] = []

    var body: some View {
        List(messages) { MessageRow(message: $0) }
            .task {
                for await msg in chatService.messageStream() {
                    messages.append(msg) // Cancelled when view disappears
                }
            }
    }
}
```

### 5. `[weak self]` in Task closures

`Task { }` closures capture `self` strongly, but a strong capture alone is **not** a retain cycle. A cycle requires a mutual strong reference — `self` must also hold the `Task`. A fire-and-forget Task completes and releases `self` naturally.

Do not cargo-cult `[weak self]` from GCD/completion handlers into Task closures — it adds unnecessary optionality without solving a real problem.

```swift
// No cycle — Task holds self, but self does NOT hold Task
func start() {
    Task {
        await self.doWork() // Fine — released on Task completion
    }
}

// Cycle — self stores Task, Task captures self
class Poller {
    private var pollingTask: Task<Void, Never>?  // self -> Task

    func startPolling() {
        pollingTask = Task {                      // Task -> self
            while !Task.isCancelled {
                await self.fetchData()            // CYCLE: self -> pollingTask -> self
                try? await Task.sleep(for: .seconds(30))
            }
        }
    }

    // Fix: [weak self] because self stores the Task
    func startPollingFixed() {
        pollingTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.fetchData()
                try? await Task.sleep(for: .seconds(30))
            }
        }
    }
}
```

Use `[weak self]` only when:
- `self` stores the `Task` in a property (mutual strong reference — actual retain cycle).
- Long-running Task (e.g., async sequence iteration) where you want to stop work if the owning object is deallocated — a correctness choice, not a memory leak fix.

### 6. Using Task.detached when Task suffices

```swift
// Unnecessary — Task.detached loses actor isolation, priority, and task-local values
Task.detached {
    let data = try await self.fetchData()
    await MainActor.run { self.update(data) }
}

// Preferred — inherits current context, simpler
Task {
    let data = try await fetchData() // Already runs work off main thread at suspension
    update(data)                     // Resumes on MainActor if called from MainActor
}
```

### Pitfalls summary

| Pitfall | Fix |
|---|---|
| Non-Sendable type crosses isolation | Convert to Sendable form before crossing (e.g., `Data` instead of `UIImage`) |
| Actor reentrancy changes state | Re-check state after every `await` inside actors |
| Blocking main thread on async work | Make the function `async`, never use semaphores/locks to bridge |
| Task runs after view disappears | Use `.task` modifier instead of `Task { }` in `onAppear` |
| Retain cycle when self stores Task | Use `[weak self]` only when self holds the Task in a property |
| Unnecessary `Task.detached` | Prefer `Task { }` — it inherits context and is simpler |
| Silent cancellation (no checking) | Check `Task.isCancelled` or call `try Task.checkCancellation()` in loops |

## Testing Async Code

### Testing async functions

```swift
import Testing

@Test
func fetchUser_returnsValidUser() async throws {
    let repository = FakeUserRepository(stubbedUser: User(id: UUID(), name: "Alice"))
    let service = UserService(repository: repository)

    let user = try await service.fetchUser()

    #expect(user.name == "Alice")
}
```

With XCTest:

```swift
import XCTest

final class UserServiceTests: XCTestCase {
    func test_fetchUser_returnsValidUser() async throws {
        let repository = FakeUserRepository(stubbedUser: User(id: UUID(), name: "Alice"))
        let service = UserService(repository: repository)

        let user = try await service.fetchUser()

        XCTAssertEqual(user.name, "Alice")
    }
}
```

### Testing @MainActor view models

```swift
@Test @MainActor
func viewModel_load_setsOrders() async {
    let fakeService = FakeOrderService(stubbedOrders: [Order.sample])
    let viewModel = OrderListViewModel(orderService: fakeService)

    await viewModel.loadOrders()

    #expect(viewModel.orders.count == 1)
    #expect(viewModel.isLoading == false)
}
```

### Testing actors

```swift
@Test
func cache_storesAndRetrieves() async {
    let cache = ImageCache()
    let testImage = UIImage(systemName: "star")!
    let url = URL(string: "https://example.com/star.png")!

    await cache.store(testImage, for: url)
    let retrieved = await cache.image(for: url)

    #expect(retrieved != nil)
}
```

### Testing cancellation

```swift
@Test
func fetchUser_respectsCancellation() async {
    let service = SlowUserService(delay: .seconds(10))
    let task = Task {
        try await service.fetchUser()
    }

    task.cancel()

    do {
        _ = try await task.value
        Issue.record("Expected CancellationError")
    } catch is CancellationError {
        // Expected
    } catch {
        Issue.record("Unexpected error: \(error)")
    }
}
```

### Testing AsyncStream

```swift
@Test
func locationStream_yieldsUpdates() async {
    let fakeManager = FakeLocationManager()
    let stream = fakeManager.locationUpdates()

    var locations: [CLLocation] = []
    let task = Task {
        for await location in stream {
            locations.append(location)
            if locations.count == 2 { break }
        }
    }

    fakeManager.simulateUpdate(CLLocation(latitude: 37.7749, longitude: -122.4194))
    fakeManager.simulateUpdate(CLLocation(latitude: 34.0522, longitude: -118.2437))

    await task.value
    #expect(locations.count == 2)
}
```

### Testing tips

| Technique | When to use |
|---|---|
| `async` test method | Any test of async code |
| `@MainActor` on test | Testing `@MainActor`-isolated types |
| Fake with `AsyncStream` | Controlling emission timing |
| `Task` + cancel | Verifying cancellation behavior |
| `withTimeout` wrapper | Preventing hanging tests from async deadlocks |
| `confirmation()` (Swift Testing) | Waiting for expected async events |
