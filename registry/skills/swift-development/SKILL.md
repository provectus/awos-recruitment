---
name: swift-development
description: "This skill should be used when the user asks to \"write Swift code\", \"create a Swift type\", \"set up a Swift package\", \"review Swift code\", \"refactor Swift\", \"use async/await in Swift\", \"fix Swift style\", \"set up SwiftLint\", \"configure SwiftFormat\", or when generating any Swift source code regardless of target platform. Provides modern Swift 6+ best practices covering type system, optionals, concurrency, error handling, protocols, generics, idiomatic patterns, and SwiftLint/SwiftFormat setup. Covers the language, standard library, and Foundation only — no platform UI frameworks; pair with `apple-app-development` for Apple app work."
version: 0.1.0
---

# Swift Development (6+)

Modern Swift best practices for writing safe, expressive, and idiomatic code. Targets Swift 6+ — the language, standard library, and Foundation. Platform frameworks are out of scope, with one deliberate exception: `references/concurrency.md` ends with brief notes on migrating Combine pipelines to `AsyncSequence`, because that refactor lands in language-level code.

Applicable to all Swift targets: Apple platforms, server-side (Vapor, Hummingbird), CLI tools, cross-platform (Linux, Windows). For Apple platform and UI work (SwiftUI, app lifecycle, Xcode projects, widgets) use this skill together with `apple-app-development`, which owns the framework guidance.

## Reference Files

- **`references/type-system.md`** — Generics, protocols with associated types, opaque types (`some`), existentials (`any`), metatypes, `@dynamicMemberLookup`, `@dynamicCallable`
- **`references/concurrency.md`** — Actors, task groups, async sequences, Sendable, isolation, continuations, GCD migration, Combine-to-`AsyncSequence` migration notes (Apple targets)
- **`references/patterns.md`** — Property wrappers, result builders, key paths, Codable, extensions, copy-on-write, DSL design
- **`references/project-structure.md`** — Swift Package Manager setup, multi-target packages, build configurations, plugins, testing setup
- **`references/static-analysis.md`** — SwiftLint (configuration, rules, custom rules, auto-correct), SwiftFormat (configuration, formatting rules), combined setup, CI/CD integration, pre-commit hooks

## Code Style

- **Short functions** — extract well-named helpers when a block needs a comment. The bundled SwiftLint config (`references/static-analysis.md`) sets the ceiling: `function_body_length` warns at 50 lines and errors at 100.
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

Use `struct` by default. Use `class` when you need identity, inheritance, or reference semantics. Use `actor` when you need thread-safe mutable state.

## Optionals

```swift
guard let user = fetchUser(id) else { return }              // early exit — preferred
let displayName = user.nickname ?? user.name                // nil coalescing
let uppercased = user.nickname.map { $0.uppercased() }      // String?
let config = try optionalConfig ?? { throw AppError.notFound(resource: "Config") }()
```

Rules:
- Use shorthand binding whenever the bound name matches the variable — `if let value`, `guard let value`, `while let value`, `guard let foo, let bar` — and write `if let renamed = original` only when intentionally binding to a different name.
- Never force-unwrap (`!`) to silence the compiler; it trades a compile-time diagnostic for a runtime crash. The one acceptable use is a provable invariant, stated in a comment beside it.

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

For actors, task groups, async sequences, Sendable patterns, continuations, GCD migration, and Combine-to-`AsyncSequence` migration notes see `references/concurrency.md`.

## Collections and Closures

- Prefer higher-order functions (`filter`, `map(\.keyPath)`, `reduce`, `Dictionary(grouping:by:)`) over manual loops; use `.lazy` when chaining over large collections.
- Use `$0`, `$1` only in short single-expression closures; name the parameters when the body is multi-line.
- Prefer `async` functions over completion-handler closures in new code; mark closures `@Sendable` when they cross concurrency boundaries.

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
- **Test naming** — Swift Testing: a descriptive `@Test("...")` display name plus a short function name (`fetchUser`). XCTest: `test_methodName_whenCondition_expectedResult`, because XCTest discovers tests by the `test` prefix.

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
