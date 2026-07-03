---
name: swift-development
description: "This skill should be used when the user asks to \"write Swift code\", \"create a Swift type\", \"set up a Swift package\", \"review Swift code\", \"refactor Swift\", \"use async/await in Swift\", \"fix Swift style\", or when generating any Swift source code regardless of target platform. Provides modern Swift 6+ best practices covering type system, optionals, concurrency, error handling, protocols, generics, and idiomatic patterns. Does not cover any specific platform or framework."
version: 0.1.0
---

# Swift Development (6+)

Modern Swift best practices for writing safe, expressive, and idiomatic code. Targets Swift 6+ — language and standard library only, no platform frameworks.

Applicable to all Swift targets: Apple platforms, server-side (Vapor, Hummingbird), CLI tools, cross-platform (Linux, Windows).

## Reference Files

- **`references/type-system.md`** — Generics, protocols with associated types, opaque types (`some`), existentials (`any`), metatypes, `@dynamicMemberLookup`, `@dynamicCallable`
- **`references/concurrency.md`** — Actors, task groups, async sequences, Sendable, isolation, GCD migration, Combine interop
- **`references/patterns.md`** — Property wrappers, result builders, key paths, Codable, extensions, copy-on-write, DSL design
- **`references/project-structure.md`** — Swift Package Manager setup, multi-target packages, build configurations, plugins, testing setup
- **`references/static-analysis.md`** — SwiftLint (configuration, rules, custom rules, auto-correct), SwiftFormat (configuration, formatting rules), combined setup, CI/CD integration, pre-commit hooks

## Code Style

- **Short functions** — target under 20 lines. Extract well-named helpers when a block needs a comment.
- **Imports at the top** — group by module. No `@_exported` unless building a module facade.
- **Access control** — default to `private` or `internal`. Use `public` only at module boundaries.

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Type / Protocol | `PascalCase` | `UserProfile`, `Fetchable` |
| Function / Property | `camelCase` | `fetchUser()`, `isActive` |
| Constant (`let` at module scope) | `camelCase` | `defaultTimeout` |
| Enum case | `camelCase` | `case loading`, `case success(Data)` |
| Boolean | Prefix `is`, `has`, `can`, `should` | `isValid`, `hasPermission` |
| File name | `PascalCase.swift` | `UserProfile.swift` |
| Protocol | Adjective or `-able`/`-ible` suffix | `Loadable`, `Configurable` |
| Generic parameter | Descriptive or single uppercase | `Element`, `T`, `Key`, `Value` |

Follow the [Swift API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/):
- Name functions and methods according to their side effects: noun for non-mutating (`distance(to:)`), verb for mutating (`sort()`), `-ed`/`-ing` for non-mutating variant (`sorted()`, `removing()`).
- Prefer clarity over brevity. A name should read naturally at the call site.
- Label closure parameters and tuple members.

## Value Types vs Reference Types

```swift
struct User {                          // Value type — prefer by default
    let id: UUID
    var name: String
}

class UserStore {                      // Reference type — when identity matters
    private var users: [User] = []
}
```

Use `struct` by default. Use `class` when you need identity, inheritance, or reference semantics. Actors when you need thread-safe mutable state.

## Optionals

```swift
let name: String? = user?.name         // safe chaining
let displayName = name ?? "Anonymous"  // nil coalescing

// NEVER force-unwrap unless you have a provable invariant with a comment
guard let user = fetchUser(id) else { return }  // early exit — preferred
```

### Safe patterns

```swift
// Shorthand optional binding (Swift 5.7+) — use when binding name matches the variable
if let name {
    print(name)
}

guard let user else { return }

// Explicit binding — only when intentionally binding to a different name
if let email = user.email {
    sendConfirmation(to: email)
}

// map / flatMap
let uppercased = name.map { $0.uppercased() }           // String?
let nested = fetchUser(id).flatMap { $0.address }        // Address?

// Coalescing with throwing
let user = try optionalUser ?? { throw AppError.notFound }()
```

Always use shorthand optional binding when the binding name matches the original variable name. Write `if let value { }` instead of `if let value = value { }`. This applies to all optional binding contexts: `if let`, `guard let`, `while let`, and multi-condition bindings (e.g., `guard let foo, let bar else { }`). Only use the explicit `if let renamed = original` form when intentionally binding to a different name.

NEVER use `!` to silence the compiler. Acceptable only with a provable invariant and a comment explaining why.

## Enums with Associated Values

```swift
enum LoadingState<T> {
    case idle
    case loading
    case loaded(T)
    case failed(Error)
}
```

Prefer enums over boolean flags for state modeling. Enables exhaustive `switch`.

## Protocols and Extensions

```swift
protocol Repository {
    associatedtype Entity
    func fetch(id: UUID) async throws -> Entity
    func save(_ entity: Entity) async throws
}

extension Array where Element: Identifiable {
    func element(withID id: Element.ID) -> Element? {
        first { $0.id == id }
    }
}
```

Rules:
- Prefer protocol composition (`Fetchable & Cacheable`) over large monolithic protocols.
- Use extensions to organize conformances — one extension per protocol conformance.
- Default implementations in protocol extensions for shared behavior.

For generics, opaque types, existentials, and advanced protocol patterns see `references/type-system.md`.

## Error Handling

```swift
// Define domain errors
enum AppError: LocalizedError {
    case networkUnavailable
    case unauthorized
    case notFound(resource: String)

    var errorDescription: String? {
        switch self {
        case .networkUnavailable: "Network is unavailable"
        case .unauthorized: "Authentication required"
        case .notFound(let resource): "\(resource) not found"
        }
    }
}

// Use typed throws (Swift 6+)
func fetchUser(id: UUID) async throws(AppError) -> User { ... }

// Use Result for expected outcomes in callbacks
func validate(_ input: String) -> Result<ValidatedInput, ValidationError> { ... }
```

Rules:
- Use `guard` for preconditions with early exit.
- Catch the narrowest error type. Never catch `Error` broadly unless at a top-level boundary.
- Prefer `async throws` over `Result` for async operations.
- Use `LocalizedError` for user-facing error messages.
- Typed throws (Swift 6+) for functions with a single known error type.

## Concurrency Essentials

```swift
// async/await
func fetchUser(id: UUID) async throws -> User {
    let data = try await networkClient.get("users/\(id)")
    return try decode(data)
}

// Structured concurrency — parallel execution
func loadDashboard() async throws -> Dashboard {
    async let profile = fetchProfile()
    async let notifications = fetchNotifications()
    return Dashboard(profile: try await profile, notifications: try await notifications)
}

// Actor — thread-safe mutable state
actor Cache<Key: Hashable, Value> {
    private var storage: [Key: Value] = [:]

    func get(_ key: Key) -> Value? { storage[key] }
    func set(_ key: Key, value: Value) { storage[key] = value }
}
```

Rules:
- **Use structured concurrency** — `async let`, `TaskGroup`. Avoid `Task.detached` unless truly needed.
- **Never block the calling thread.** Offload heavy work with `Task` or actors.
- **Sendable compliance** — Swift 6 strict concurrency requires types crossing isolation boundaries to be `Sendable`.
- **Use `Task.isCancelled` or `try Task.checkCancellation()`** to respond to cancellation.
- Mark `nonisolated` explicitly when actor methods don't need isolation.

For actors, task groups, async sequences, Sendable patterns, GCD migration, and Combine interop see `references/concurrency.md`.

## Collections

```swift
// Prefer higher-order functions over manual loops
let activeUsers = users.filter { $0.isActive }
let names = users.map(\.name)
let totalAge = users.reduce(0) { $0 + $1.age }

// Lazy for large collections
let firstMatch = users.lazy.filter { $0.isActive }.first

// Dictionary grouping
let byDepartment = Dictionary(grouping: employees, by: \.department)
```

## Closures

```swift
// Trailing closure syntax
let sorted = users.sorted { $0.name < $1.name }

// Multi-line closures — use named parameters
let transformed = items.map { item in
    Item(
        id: item.id,
        name: item.name.uppercased()
    )
}

// @escaping — when closure outlives the function
func fetch(completion: @escaping (Result<User, Error>) -> Void) { ... }

// @Sendable — when closure crosses concurrency boundaries
func execute(_ work: @Sendable () async -> Void) { ... }
```

Rules:
- Use `$0`, `$1` only for short, single-expression closures.
- Name parameters explicitly when the closure body is multi-line.
- Prefer `async` functions over completion handler closures in new code.

## Project Structure

```
MyPackage/
├── Package.swift
├── Sources/
│   ├── MyLibrary/
│   │   ├── Models/
│   │   ├── Services/
│   │   └── Extensions/
│   └── MyExecutable/
│       └── main.swift
├── Tests/
│   └── MyLibraryTests/
└── Plugins/
```

Rules:
- Use Swift Package Manager for dependency management.
- Organize by domain, not by technical role.
- One type per file, file name matches type name.
- Separate targets for libraries and executables.

For SPM setup, multi-target packages, build configurations, plugins, and testing see `references/project-structure.md`.

## Testable Design

- **Dependency injection** — inject protocols, not concrete types. Use init injection.
- **Pure logic** — keep business logic free of framework and I/O dependencies.
- **Fakes over mocks** — write simple in-memory protocol conformances.
- **Test naming** — `test_methodName_whenCondition_expectedResult`.

```swift
protocol UserRepository {
    func fetch(id: UUID) async throws -> User
}

// Production
struct RemoteUserRepository: UserRepository {
    let client: HTTPClient
    func fetch(id: UUID) async throws -> User { ... }
}

// Test
struct FakeUserRepository: UserRepository {
    var stubbedUser: User?
    func fetch(id: UUID) async throws -> User {
        guard let user = stubbedUser else { throw AppError.notFound(resource: "User") }
        return user
    }
}
```

### Swift Testing (Swift 6+)

```swift
import Testing

@Test("Fetches user by ID")
func fetchUser() async throws {
    let repo = FakeUserRepository(stubbedUser: User(id: testID, name: "Alice"))
    let user = try await repo.fetch(id: testID)
    #expect(user.name == "Alice")
}

@Test("Throws when user not found")
func fetchUserNotFound() async {
    let repo = FakeUserRepository(stubbedUser: nil)
    await #expect(throws: AppError.self) {
        try await repo.fetch(id: testID)
    }
}
```

Prefer Swift Testing (`@Test`, `#expect`) over XCTest for new code. Use XCTest when the project requires it or for UI/integration tests on Apple platforms.

## Quick Reference: Common Mistakes

| Mistake | Fix |
|---|---|
| Force-unwrapping (`!`) without invariant | Use `guard let`, `if let`, `??`, or optional chaining |
| `if let value = value { }` when names match | Use shorthand: `if let value { }` (Swift 5.7+) |
| Catching `Error` broadly | Catch specific error types at appropriate boundaries |
| `Task { }` without cancellation handling | Check `Task.isCancelled` or use `Task.checkCancellation()` |
| Using GCD (`DispatchQueue`) in new code | Use Swift Concurrency (`async/await`, actors) |
| Mutable `var` in struct properties without need | Default to `let`; use `var` only when mutation is required |
| Large protocols (>5 requirements) | Break into focused protocols; use composition |
| Ignoring `Sendable` warnings | Conform value types or use actor isolation |
| Completion handlers in new code | Use `async/await`; wrap legacy APIs with `withCheckedContinuation` |
| Stringly-typed APIs | Use enums, phantom types, or value types for type safety |
| `Any` / `AnyObject` without reason | Use generics or existentials with constraints |
| `Double` for money | Use `Decimal` with explicit rounding |
| Hard-coded dependencies | Protocol-based DI via init injection |
| `#if` directives for multi-target polymorphism | Use DI or separate file implementations per target; reserve `#if` for `DEBUG`, `os()`, `canImport()` |
