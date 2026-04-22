---
name: apple-app-development
description: "This skill should be used when the user asks to \"create a SwiftUI view\", \"build an iOS app\", \"set up an Xcode project\", \"review Apple platform code\", \"add a widget\", \"create a watchOS app\", \"build for visionOS\", \"fix SwiftUI layout\", or when generating any Swift code targeting Apple platforms (iOS, iPadOS, macOS, tvOS, watchOS, visionOS). Provides modern SwiftUI-first best practices covering UI patterns, app lifecycle, navigation, project structure, and platform-specific guidance. Use together with `swift-development` for Swift language fundamentals. Always generates Swift unless the project explicitly requires Objective-C."
version: 0.1.0
---

# Apple App Development (Swift 6+ / SwiftUI)

Modern best practices for building apps across Apple platforms. Targets Swift 6+ with SwiftUI as the primary UI framework. Covers iOS, iPadOS, macOS, tvOS, watchOS, and visionOS.

For Swift language fundamentals (type system, optionals, error handling, concurrency, protocols, generics, idiomatic patterns), see the `swift-development` skill. This skill focuses on platform and framework patterns.

## Important Rules

- **Always generate Swift.** Only write Objective-C when the project explicitly requires it (legacy codebase, Obj-C-only API). See `references/objc-interop.md` for bridging patterns.
- **SwiftUI-first.** Use UIKit/AppKit only when SwiftUI lacks the capability. See `references/uikit-interop.md` for interop patterns.
- **Respect the existing UI framework.** In legacy UIKit codebases, do not mix SwiftUI and UIKit **lifecycle or navigation** within the same screen (e.g., nesting `UINavigationController` inside `NavigationStack`). Using `UIViewRepresentable` to embed individual UIKit views (maps, web views, text editors) within a SwiftUI screen is expected and supported. New **isolated flows** (full screens or self-contained features) may use SwiftUI, but existing UIKit screens should not be partially rewritten without explicit request. For greenfield projects, use SwiftUI exclusively.
- **Check the project context.** Before applying patterns, check the deployment target, Swift version, and existing architecture. Adapt recommendations accordingly.
- **No `#if` / compiler directives for multi-target branching.** Do not use `#if TARGET_NAME` or custom build flags to branch behavior between app targets. Instead, use dependency injection (protocol + per-target conformance) or separate file implementations (one per target, added to the correct target membership in Xcode). `#if` directives are reserved for excluding code from compilation entirely (e.g., `#if DEBUG`, `#if os(iOS)`, `#if canImport(UIKit)`) — not for runtime or build-time polymorphism between targets in the same project.
- **Always localize user-facing text.** Never use explicit string literals for user-facing text (e.g., `"Welcome back"`, `Text("Sign in")`). Always use whichever localization solution is already in use in the project (e.g., String Catalogs, `.strings` files, a custom localization layer). Do not migrate to a different solution unless explicitly asked. When you encounter an existing explicit string that should be localized, flag it and suggest the appropriate key name and parameter names, but do not migrate it unless asked. See `references/localization.md` for String Catalog patterns and named parameter format.

## Reference Files

- **`references/swiftui-patterns.md`** — View composition, property wrappers (`@State`, `@Binding`, `@Observable`), navigation, state management, lists, forms, custom modifiers
- **`references/concurrency.md`** — `@MainActor` for UI, `.task` modifier, `@Observable` lifecycle, Combine interop in SwiftUI context
- **`references/uikit-interop.md`** — `UIViewRepresentable`, `UIViewControllerRepresentable`, hosting SwiftUI in UIKit, migration strategies
- **`references/project-structure.md`** — Xcode project organization, SPM packages, multi-module architecture, build configurations, targets, schemes
- **`references/persistence.md`** — Core Data (NSPersistentContainer, contexts, migrations, batch ops, CloudKit) and SwiftData (@Model, @Query, ModelActor, VersionedSchema, #Unique, #Index)
- **`references/networking.md`** — URLSession (async/await, uploads, downloads, background sessions, WebSocket, auth challenges, caching), Alamofire (interceptors, retry, certificate pinning, multipart)
- **`references/storekit.md`** — StoreKit 2 (Product, Transaction, subscriptions, entitlements, verification), StoreKit SwiftUI views (SubscriptionStoreView, StoreView), testing, refunds
- **`references/media-playback.md`** — AVPlayer, AVKit (VideoPlayer, AVPlayerViewController), AVAudioSession, Picture-in-Picture, AirPlay, offline HLS downloads, Now Playing, remote controls
- **`references/app-lifecycle.md`** — App/Scene lifecycle, background tasks, push notifications, deep links, Universal Links
- **`references/ipados-patterns.md`** — Multitasking (Split View, Slide Over, Stage Manager), pointer/keyboard support, drag & drop, Mac Catalyst
- **`references/macos-patterns.md`** — AppKit interop, menus, toolbar, windows, settings/preferences, sandboxing
- **`references/tvos-patterns.md`** — Focus engine, Top Shelf, TVMLKit, remote navigation, media playback
- **`references/watchos-patterns.md`** — WatchKit, complications, workout sessions, background refresh, watch connectivity
- **`references/visionos-patterns.md`** — RealityKit, immersive spaces, volumes, ornaments, spatial gestures, entity-component system
- **`references/widgets-app-intents.md`** — WidgetKit (timeline, configuration), App Intents, Shortcuts, Live Activities
- **`references/carplay-patterns.md`** — CarPlay app lifecycle, CPTemplate API, navigation, media, EV charging, communication apps
- **`references/objc-interop.md`** — Bridging headers, `@objc`, `NS_SWIFT_NAME`, nullability annotations, incremental migration
- **`references/testing.md`** — Swift Testing (@Test, #expect, traits, parameterized), XCTest (unit tests, async, performance), XCUITest (UI automation, page objects), test doubles, snapshot testing, test plans, CI/CD
- **`references/localization.md`** — String Catalogs (.xcstrings), code-generated accessors, named parameter format (`%(name)@`, `%1$(name)@`), custom table namespacing, localization best practices
- **`references/code-quality.md`** — Xcode Static Analyzer, sanitizers (ASan, TSan, UBSan), Periphery (dead code), Danger-Swift, Xcode build settings, xcconfig. For SwiftLint/SwiftFormat, see `swift-development` skill's `references/static-analysis.md`

## Code Style

For general Swift code style (short functions, imports, access control), follow the `swift-development` skill. Below are Apple/SwiftUI-specific conventions.

- **Define a custom app style system and apply it at the root.** Every app should have a centralized design system defining colors, typography, spacing, and shapes. Apply it at the top level and reference tokens everywhere — never raw values.

```swift
// 1. Define design tokens (once, in a shared UI module or Core/)
enum AppSpacing {
    static let small: CGFloat = 8
    static let medium: CGFloat = 16
    static let large: CGFloat = 24
}

enum AppCornerRadius {
    static let standard: CGFloat = 8
    static let large: CGFloat = 16
}

enum AppTypography {
    static let body: Font = .system(size: 16, weight: .regular)
    static let headline: Font = .system(size: 24, weight: .bold)
    static let caption: Font = .system(size: 12, weight: .regular)
}

enum AppColors {
    static let primary = Color("PrimaryColor")         // from Asset Catalog
    static let background = Color("BackgroundColor")
    static let onPrimary = Color("OnPrimaryColor")
}

// 2. Use tokens everywhere — never raw values
Text("Hello")
    .font(AppTypography.body)                           // not .font(.system(size: 16))
    .foregroundStyle(AppColors.primary)                 // not .foregroundStyle(Color.blue)
    .padding(AppSpacing.medium)                         // not .padding(16)
    .clipShape(RoundedRectangle(cornerRadius: AppCornerRadius.standard))
```

For more advanced theming, use `@Environment` with a custom theme object to support runtime switching (dark mode, brand themes):

```swift
struct AppTheme {
    let colors: AppColorScheme
    let spacing: AppSpacingScheme
    let typography: AppTypographyScheme
}

private struct AppThemeKey: EnvironmentKey {
    static let defaultValue = AppTheme.default
}

extension EnvironmentValues {
    var appTheme: AppTheme {
        get { self[AppThemeKey.self] }
        set { self[AppThemeKey.self] = newValue }
    }
}

// Apply at root
ContentView()
    .environment(\.appTheme, .default)

// Use in views
@Environment(\.appTheme) private var theme
Text("Hello").font(theme.typography.body)
```

**No magic numbers in UI code.** If a numeric value appears in UI, it must be an app-defined design token. For SwiftUI theming patterns see `references/swiftui-patterns.md`.

## Naming Conventions (Apple-Specific)

| Element | Convention | Example |
|---|---|---|
| SwiftUI View | Suffix `View` | `SettingsView`, `UserCardView` |
| View Model | Suffix `ViewModel` | `SettingsViewModel` |
| Screen composable | Suffix `View` | `HomeView`, `ProfileView` |
| UI State | Suffix `ViewState` or `State` | `HomeViewState` |
| Preview | Prefix `#Preview` | `#Preview { SettingsView() }` |

For general Swift naming conventions (types, functions, properties, booleans, files), follow the `swift-development` skill.

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
- Use `@State` for view-local state, `@Binding` for parent-child communication, `@Bindable` for bindings to `@Observable` properties, and `@Environment` for shared/injected state.
- **`@State` + `@Observable` caveat:** Unlike `@StateObject`, `@State` re-evaluates the initializer expression on every view struct recreation (SwiftUI discards the new instance but `init()` still runs). Avoid side effects in `@Observable` class initializers — use `.task` for deferred setup.

For navigation, lists, forms, custom modifiers, and advanced patterns see `references/swiftui-patterns.md`.

## Apple Concurrency Patterns

For Swift concurrency fundamentals (async/await, actors, TaskGroup, Sendable), see the `swift-development` skill. Below are Apple platform-specific patterns.

```swift
// @MainActor for UI-updating code
@MainActor
@Observable
class SettingsViewModel {
    var settings: Settings?

    func load() async {
        settings = await settingsService.fetch()
    }
}
```

Rules:
- **`@MainActor`** for any code that updates UI state (ViewModels, UI-bound services).
- **`.task` modifier** for async work tied to view lifecycle — cancels on disappear.
- **Never block the main thread.** Offload heavy work with `Task` or actors.

For actors, task groups, Sendable patterns, GCD migration, and Combine interop see `references/concurrency.md`.

## Architecture

**Recommended: MVVM with unidirectional data flow** for new SwiftUI projects. The ViewModel owns the state, the View renders it and sends user actions back. This is the natural pattern for SwiftUI with `@Observable`.

For projects that want stricter unidirectional architecture (similar to MVI on Android), **TCA (The Composable Architecture)** is a well-established alternative — see below.

If the project already uses MVC, MVP, or another architecture — adapt to the existing pattern.

### MVVM Pattern (Recommended)

```swift
// 1. State — single struct per screen
struct HomeViewState {
    var items: [Item] = []
    var isLoading = false
    var error: String?
}

// 2. ViewModel — owns state, exposes actions
@Observable
class HomeViewModel {
    private(set) var state = HomeViewState()
    private let repository: ItemRepository

    init(repository: ItemRepository) {
        self.repository = repository
    }

    func loadItems() async {
        state.isLoading = true
        state.error = nil
        do {
            state.items = try await repository.getItems()
        } catch {
            state.error = error.localizedDescription
        }
        state.isLoading = false
    }

    func deleteItem(id: UUID) async {
        try? await repository.delete(id: id)
        state.items.removeAll { $0.id == id }
    }
}

// 3. View — renders state, calls ViewModel actions
struct HomeView: View {
    @State private var viewModel: HomeViewModel

    init(repository: ItemRepository) {
        _viewModel = State(initialValue: HomeViewModel(repository: repository))
    }

    var body: some View {
        Group {
            if viewModel.state.isLoading {
                ProgressView()
            } else if let error = viewModel.state.error {
                ErrorView(message: error, onRetry: { Task { await viewModel.loadItems() } })
            } else {
                ItemListView(
                    items: viewModel.state.items,
                    onDelete: { id in Task { await viewModel.deleteItem(id: id) } }
                )
            }
        }
        .task { await viewModel.loadItems() }
    }
}
```

### Rules

- **ViewModel per screen** — each screen has its own `@Observable` ViewModel.
- **Single state object** — prefer one `ViewState` struct over scattered `@Published` properties. Easier to test and reason about.
- **View doesn't mutate state directly** — it calls ViewModel methods which update state.
- **Inject dependencies** — ViewModel receives protocols via `init`, not concrete types.
- **Adapt to existing architecture.** If the project uses MVC/MVP/VIPER, follow the established pattern. Propose MVVM for new screens or new projects.

### TCA (The Composable Architecture) — Alternative

For teams that prefer a stricter unidirectional architecture (similar to MVI on Android), TCA provides `State` + `Action` + `Reducer` + `Store` with built-in dependency injection, side effect management, and exhaustive testing. It is a third-party framework (Point-Free), well-established and actively maintained in the iOS community.

```swift
// TCA pattern (requires swift-composable-architecture package)
@Reducer
struct HomeFeature {
    @ObservableState
    struct State {
        var items: [Item] = []
        var isLoading = false
    }

    enum Action {
        case loadItems
        case itemsLoaded(Result<[Item], Error>)
        case deleteItem(id: UUID)
    }

    // Inject dependencies via @Dependency (uses swift-dependencies package)
    @Dependency(\.itemRepository) var repository

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .loadItems:
                state.isLoading = true
                return .run { [repository] send in
                    await send(.itemsLoaded(Result { try await repository.getItems() }))
                }
            case .itemsLoaded(.success(let items)):
                state.items = items
                state.isLoading = false
                return .none
            case .itemsLoaded(.failure):
                state.isLoading = false
                return .none
            case .deleteItem(let id):
                state.items.removeAll { $0.id == id }
                return .none
            }
        }
    }
}
```

Use TCA when: the project needs highly testable, composable feature modules with explicit side effect management. Don't adopt TCA mid-project without team buy-in — it has a learning curve.

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
- Prefer one primary type per file, file name matches type name. Small closely-related helper types may co-locate.

For SPM multi-module setup, build configurations, targets, schemes see `references/project-structure.md`.

## Testable Design

For general testable design patterns (DI, fakes over mocks, protocol-based injection), see the `swift-development` skill. For comprehensive testing guidance, see `references/testing.md` (Swift Testing, XCTest, XCUITest, test doubles, test plans, CI/CD) and `references/code-quality.md` (linting, static analysis, sanitizers).

Key principles:
- **`@Environment` injection** — use SwiftUI environment for injecting dependencies in the view layer.
- **Protocol-based DI** — inject dependencies via init for testability. Inject `Clock` for time-dependent code.
- **Snapshot tests** — verify UI appearance with swift-snapshot-testing.
- **XCUITest** — for end-to-end flows on device/simulator with Page Object pattern.

## Platform-Specific Guidance

The core skill covers iOS/iPhone by default. For other platforms, consult the corresponding reference:

| Platform | Reference | Key Topics |
|---|---|---|
| iPadOS | `references/ipados-patterns.md` | Multitasking, pointer, drag & drop, Mac Catalyst |
| macOS | `references/macos-patterns.md` | AppKit interop, menus, windows, toolbar, sandboxing |
| tvOS | `references/tvos-patterns.md` | Focus engine, Top Shelf, remote navigation |
| watchOS | `references/watchos-patterns.md` | Complications, workouts, watch connectivity |
| visionOS | `references/visionos-patterns.md` | RealityKit, immersive spaces, volumes, spatial gestures |
| CarPlay | `references/carplay-patterns.md` | CPTemplate API, navigation, media, EV charging |

Cross-platform features:

| Feature | Reference |
|---|---|
| Widgets, Live Activities, App Intents | `references/widgets-app-intents.md` |
| Objective-C interop & migration | `references/objc-interop.md` |
| UIKit/AppKit interop | `references/uikit-interop.md` |

## Quick Reference: Common Mistakes

| Mistake | Fix |
|---|---|
| Massive view `body` (>30 lines) | Extract subviews and modifiers |
| `ObservableObject` on iOS 17+ | Use `@Observable` macro |
| Blocking main thread with sync I/O | Use `async/await`, move to background actor |
| `Task { }` without cancellation handling | Use `.task` modifier or check `Task.isCancelled` |
| God view model (500+ lines) | Split by responsibility, extract services |
| Hard-coded dependencies | Protocol-based DI via init or `@Environment` |
| `@State` for shared state | Use `@Observable` model or `@Environment` |
| String-based navigation | Use `NavigationPath` with typed destinations |
| Magic numbers in UI (`padding(16)`, `.cornerRadius(8)`) | Define design tokens (`AppSpacing.medium`, `AppCornerRadius.standard`) |
| `#if TARGET_NAME` for multi-target branching | Use DI (protocol + per-target conformance) or separate files per target |
| Mixing SwiftUI and UIKit lifecycle/navigation in one screen | Don't nest `UINavigationController` inside `NavigationStack`; `UIViewRepresentable` for individual views is fine |
| Hard-coded user-facing strings (`"Welcome back"`, `Text("Sign in")`) | Use localized strings — reference the project's localization solution (String Catalogs, `.strings`, etc.) |
