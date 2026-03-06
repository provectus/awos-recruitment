---
name: apple-app-development
description: "This skill should be used when the user asks to \"write Swift code\", \"create a SwiftUI view\", \"build an iOS app\", \"set up an Xcode project\", \"review Swift code\", \"refactor Swift\", \"add a widget\", \"create a watchOS app\", \"build for visionOS\", \"fix Swift style\", or when generating any Swift source code targeting Apple platforms (iOS, iPadOS, macOS, tvOS, watchOS, visionOS). Provides modern Swift 6+ and SwiftUI-first best practices covering concurrency, UI patterns, app lifecycle, project structure, and platform-specific guidance. Always generates Swift unless the project explicitly requires Objective-C."
version: 0.1.0
---

# Apple App Development (Swift 6+ / SwiftUI)

Modern best practices for building apps across Apple platforms. Targets Swift 6+ with SwiftUI as the primary UI framework. Covers iOS, iPadOS, macOS, tvOS, watchOS, and visionOS.

## Important Rules

- **Always generate Swift.** Only write Objective-C when the project explicitly requires it (legacy codebase, Obj-C-only API). See `references/objc-interop.md` for bridging patterns.
- **SwiftUI-first.** Use UIKit/AppKit only when SwiftUI lacks the capability. See `references/uikit-interop.md` for interop patterns.
- **Check the project context.** Before applying patterns, check the deployment target, Swift version, and existing architecture. Adapt recommendations accordingly.

## Reference Files

- **`references/swiftui-patterns.md`** — View composition, property wrappers (`@State`, `@Binding`, `@Observable`), navigation, state management, lists, forms, custom modifiers
- **`references/concurrency.md`** — async/await, actors, `@MainActor`, structured concurrency, Task groups, Sendable, migrating from GCD/Combine
- **`references/uikit-interop.md`** — `UIViewRepresentable`, `UIViewControllerRepresentable`, hosting SwiftUI in UIKit, migration strategies
- **`references/project-structure.md`** — Xcode project organization, SPM packages, multi-module architecture, build configurations, targets, schemes
- **`references/app-lifecycle.md`** — App/Scene lifecycle, background tasks, push notifications, deep links, Universal Links
- **`references/ipados-patterns.md`** — Multitasking (Split View, Slide Over, Stage Manager), pointer/keyboard support, drag & drop, Mac Catalyst
- **`references/macos-patterns.md`** — AppKit interop, menus, toolbar, windows, settings/preferences, sandboxing
- **`references/tvos-patterns.md`** — Focus engine, Top Shelf, TVMLKit, remote navigation, media playback
- **`references/watchos-patterns.md`** — WatchKit, complications, workout sessions, background refresh, watch connectivity
- **`references/visionos-patterns.md`** — RealityKit, immersive spaces, volumes, ornaments, spatial gestures, entity-component system
- **`references/widgets-app-intents.md`** — WidgetKit (timeline, configuration), App Intents, Shortcuts, Live Activities
- **`references/objc-interop.md`** — Bridging headers, `@objc`, `NS_SWIFT_NAME`, nullability annotations, incremental migration

## Code Style

- **Short functions** — target under 20 lines. Extract well-named helpers when a block needs a comment.
- **Imports at the top** — group by framework. No `@_exported` unless building a module facade.
- **Access control** — default to `private` or `internal`. Use `public` only at module boundaries.

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Type / Protocol | `PascalCase` | `UserProfile`, `Fetchable` |
| Function / Property | `camelCase` | `fetchUser()`, `isActive` |
| Constant (`let` at module scope) | `camelCase` | `defaultTimeout` |
| Enum case | `camelCase` | `case loading`, `case success(Data)` |
| Boolean | Prefix `is`, `has`, `can`, `should` | `isValid`, `hasPermission` |
| File name | `PascalCase.swift` | `UserProfileView.swift` |
| SwiftUI View | Suffix `View` | `SettingsView`, `UserCardView` |
| View Model | Suffix `ViewModel` | `SettingsViewModel` |
| Protocol | Adjective or `-able`/`-ible` suffix | `Loadable`, `Configurable` |

## Swift Type System Essentials

### Value types vs Reference types

```swift
struct User {                          // Value type — prefer by default
    let id: UUID
    var name: String
}

class UserStore: ObservableObject {    // Reference type — when identity matters
    @Published var users: [User] = []
}
```

Use `struct` by default. Use `class` when you need identity, inheritance, or reference semantics (e.g., `ObservableObject`).

### Optionals

```swift
let name: String? = user?.name         // safe chaining
let displayName = name ?? "Anonymous"  // nil coalescing

// NEVER force-unwrap unless you have a provable invariant with a comment
guard let user = fetchUser(id) else { return }  // early exit — preferred
```

### Enums with associated values

```swift
enum LoadingState<T> {
    case idle
    case loading
    case loaded(T)
    case failed(Error)
}
```

Prefer enums over boolean flags for state modeling. Enables exhaustive `switch`.

### Protocols and extensions

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
- Catch the narrowest error type. Never catch `Error` broadly unless at a top-level boundary (e.g., view model).
- Prefer `async throws` over `Result` for async operations.
- Use `LocalizedError` for user-facing error messages.

## SwiftUI Essentials

```swift
// Observable model (Swift 5.9+ / iOS 17+)
@Observable
class UserViewModel {
    var user: User?
    var isLoading = false

    func load() async {
        isLoading = true
        defer { isLoading = false }
        user = try? await userService.fetch()
    }
}

// View
struct UserView: View {
    @State private var viewModel = UserViewModel()

    var body: some View {
        Group {
            if viewModel.isLoading {
                ProgressView()
            } else if let user = viewModel.user {
                Text(user.name)
            }
        }
        .task { await viewModel.load() }
    }
}
```

Rules:
- Use `@Observable` (iOS 17+) over `ObservableObject`/`@Published` for new code.
- Use `.task` for async work tied to view lifecycle — it cancels automatically.
- Keep views small. Extract subviews when `body` exceeds ~30 lines.
- Use `@State` for view-local state, `@Binding` for parent-child communication.

For navigation, lists, forms, custom modifiers, and advanced patterns see `references/swiftui-patterns.md`.

## Concurrency Essentials

```swift
// Mark UI-updating code with @MainActor
@MainActor
class SettingsViewModel: ObservableObject {
    @Published var settings: Settings?

    func load() async {
        settings = await settingsService.fetch()
    }
}

// Use structured concurrency
func loadDashboard() async throws -> Dashboard {
    async let profile = fetchProfile()
    async let notifications = fetchNotifications()
    return Dashboard(profile: try await profile, notifications: try await notifications)
}
```

Rules:
- **Use structured concurrency** — `async let`, `TaskGroup`. Avoid `Task.detached` unless truly needed.
- **`@MainActor`** for any code that updates UI state.
- **Never block the main thread.** Offload heavy work with `Task` or actors.
- **Sendable compliance** — Swift 6 strict concurrency requires types crossing isolation boundaries to be `Sendable`.

For actors, task groups, Sendable patterns, GCD migration, and Combine interop see `references/concurrency.md`.

## Project Structure

```
MyApp/
├── MyApp/                         # Main app target
│   ├── App/                       # App entry point, configuration
│   │   └── MyAppApp.swift
│   ├── Features/                  # Feature modules
│   │   ├── Auth/
│   │   ├── Home/
│   │   └── Settings/
│   ├── Core/                      # Shared business logic
│   │   ├── Models/
│   │   ├── Services/
│   │   └── Extensions/
│   └── Resources/                 # Assets, Localizable, Info.plist
├── Packages/                      # Local SPM packages (multi-module)
├── MyAppTests/
├── MyAppUITests/
└── MyApp.xcodeproj
```

Rules:
- Organize by feature, not by technical role.
- Extract shared logic into local SPM packages for build time and testability.
- One type per file, file name matches type name.

For SPM multi-module setup, build configurations, targets, schemes see `references/project-structure.md`.

## Testable Design

- **Dependency injection** — inject protocols, not concrete types. Use environment or init injection.
- **Pure logic** — keep business logic free of UI and framework dependencies.
- **Fakes over mocks** — write simple in-memory protocol conformances.
- **Test naming** — `test_methodName_whenCondition_expectedResult`.

```swift
protocol UserRepository {
    func fetch(id: UUID) async throws -> User
}

// Production
struct RemoteUserRepository: UserRepository { ... }

// Test
struct FakeUserRepository: UserRepository {
    var stubbedUser: User?
    func fetch(id: UUID) async throws -> User {
        guard let user = stubbedUser else { throw AppError.notFound(resource: "User") }
        return user
    }
}
```

## Platform-Specific Guidance

The core skill covers iOS/iPhone by default. For other platforms, consult the corresponding reference:

| Platform | Reference | Key Topics |
|---|---|---|
| iPadOS | `references/ipados-patterns.md` | Multitasking, pointer, drag & drop, Mac Catalyst |
| macOS | `references/macos-patterns.md` | AppKit interop, menus, windows, toolbar, sandboxing |
| tvOS | `references/tvos-patterns.md` | Focus engine, Top Shelf, remote navigation |
| watchOS | `references/watchos-patterns.md` | Complications, workouts, watch connectivity |
| visionOS | `references/visionos-patterns.md` | RealityKit, immersive spaces, volumes, spatial gestures |

Cross-platform features:

| Feature | Reference |
|---|---|
| Widgets, Live Activities, App Intents | `references/widgets-app-intents.md` |
| Objective-C interop & migration | `references/objc-interop.md` |
| UIKit/AppKit interop | `references/uikit-interop.md` |

## Quick Reference: Common Mistakes

| Mistake | Fix |
|---|---|
| Force-unwrapping (`!`) without invariant | Use `guard let`, `if let`, `??`, or optional chaining |
| Massive view `body` (>30 lines) | Extract subviews and modifiers |
| `ObservableObject` on iOS 17+ | Use `@Observable` macro |
| Blocking main thread with sync I/O | Use `async/await`, move to background actor |
| `Task { }` without cancellation handling | Use `.task` modifier or check `Task.isCancelled` |
| God view model (500+ lines) | Split by responsibility, extract services |
| Hard-coded dependencies | Protocol-based DI via init or `@Environment` |
| Catching `Error` broadly | Catch specific error types at appropriate boundaries |
| `@State` for shared state | Use `@Observable` model or `@Environment` |
| String-based navigation | Use `NavigationPath` with typed destinations |
| Ignoring `Sendable` warnings | Conform value types or use `@MainActor` isolation |
| Using GCD (`DispatchQueue`) in new code | Use Swift Concurrency (`async/await`, actors) |
