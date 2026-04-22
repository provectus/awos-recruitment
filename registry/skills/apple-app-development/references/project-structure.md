# Project Structure Reference

## Contents
- Xcode project organization (groups vs folders, target structure, shared frameworks)
- SPM multi-module architecture (local packages, Package.swift, module boundaries, dependency graph)
- Feature module pattern (isolation, shared core, API/implementation split)
- Build configurations (Debug/Release, Staging, xcconfig files, Info.plist)
- Targets and schemes (app, test, extension targets, scheme management)
- Asset management (Asset Catalogs, color sets, image sets, SF Symbols, String Catalogs)
- Code generation (SwiftGen, SPM build plugins)
- CI/CD considerations (xcodebuild, fastlane, signing, TestFlight)
- Multi-platform targets (iOS/macOS/watchOS/tvOS/visionOS, platform conditionals)
- Dependency management (SPM preferred, CocoaPods legacy, version pinning)

## Xcode Project Organization

### Groups vs folders
---

Xcode 16+ uses **filesystem-backed folders** by default. Every group in the Project Navigator corresponds to a real directory on disk. This replaced the legacy "virtual groups" behavior where Xcode groups could diverge from the filesystem.

**Rules:**
- Always use filesystem-backed folders (the default in Xcode 16+). Never create virtual groups in new projects.
- If inheriting a legacy project with virtual groups, migrate incrementally: right-click a group and select "Convert to Folder" when touching that area of code.
- Keep the navigator hierarchy shallow — 3-4 levels deep maximum.

### Recommended app target structure

```
MyApp/
├── MyApp.xcodeproj
├── MyApp/                          # Main app target
│   ├── App/
│   │   ├── MyAppApp.swift          # @main entry point
│   │   ├── AppDelegate.swift       # Only if needed (push notifications, etc.)
│   │   └── DependencyContainer.swift
│   ├── Features/
│   │   ├── Auth/
│   │   │   ├── AuthView.swift
│   │   │   ├── AuthViewModel.swift
│   │   │   └── AuthService.swift
│   │   ├── Home/
│   │   └── Settings/
│   ├── Core/
│   │   ├── Models/
│   │   ├── Networking/
│   │   ├── Persistence/
│   │   └── Extensions/
│   ├── UI/                         # Shared UI components
│   │   ├── Components/
│   │   ├── Modifiers/
│   │   └── Styles/
│   └── Resources/
│       ├── Assets.xcassets
│       ├── Localizable.xcstrings   # String Catalog (Xcode 15+)
│       ├── Info.plist
│       └── Fonts/
├── MyAppTests/
├── MyAppUITests/
└── Packages/                       # Local SPM packages
```

### Shared frameworks (embedded)

For monorepo setups where SPM local packages are not feasible, use embedded frameworks:

```
MyApp/
├── MyApp/                          # App target
├── SharedKit/                      # Embedded framework target
│   ├── Sources/
│   └── SharedKit.h                 # Umbrella header (Swift-only: leave empty)
└── MyApp.xcodeproj
```

In the Xcode project, the framework target is added under "Frameworks, Libraries, and Embedded Content" with **Embed & Sign**. Prefer SPM local packages over embedded frameworks for new projects — they are simpler to configure and test.

## SPM Multi-Module Architecture

### Why local packages

Local SPM packages provide:
- **Faster incremental builds** — unchanged modules are not recompiled.
- **Enforced access control** — `internal` is scoped to the module, not the entire app.
- **Independent testability** — each package has its own test target.
- **Clear dependency graph** — imports declare what a module depends on.

### Directory layout

```
MyApp/
├── MyApp.xcodeproj
├── MyApp/                          # Thin app target (wiring only)
│   ├── App/
│   │   └── MyAppApp.swift
│   └── Resources/
├── Packages/
│   ├── Core/
│   │   ├── Package.swift
│   │   ├── Sources/
│   │   │   └── Core/
│   │   │       ├── Models/
│   │   │       ├── Networking/
│   │   │       └── Extensions/
│   │   └── Tests/
│   │       └── CoreTests/
│   ├── FeatureAuth/
│   │   ├── Package.swift
│   │   ├── Sources/
│   │   │   └── FeatureAuth/
│   │   └── Tests/
│   │       └── FeatureAuthTests/
│   ├── FeatureHome/
│   │   ├── Package.swift
│   │   ├── Sources/
│   │   │   └── FeatureHome/
│   │   └── Tests/
│   │       └── FeatureHomeTests/
│   └── UIComponents/
│       ├── Package.swift
│       ├── Sources/
│       │   └── UIComponents/
│       └── Tests/
│           └── UIComponentsTests/
├── MyAppTests/
└── MyAppUITests/
```

### Package.swift for a feature module

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "FeatureAuth",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "FeatureAuth", targets: ["FeatureAuth"]),
    ],
    dependencies: [
        .package(path: "../Core"),
        .package(path: "../UIComponents"),
    ],
    targets: [
        .target(
            name: "FeatureAuth",
            dependencies: [
                .product(name: "Core", package: "Core"),
                .product(name: "UIComponents", package: "UIComponents"),
            ]
        ),
        .testTarget(
            name: "FeatureAuthTests",
            dependencies: ["FeatureAuth"]
        ),
    ]
)
```

### Package.swift for a core module with external dependencies

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Core",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "Core", targets: ["Core"]),
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-algorithms.git", from: "<latest-stable>"),
    ],
    targets: [
        .target(
            name: "Core",
            dependencies: [
                .product(name: "Algorithms", package: "swift-algorithms"),
            ]
        ),
        .testTarget(
            name: "CoreTests",
            dependencies: ["Core"]
        ),
    ]
)
```

### Monorepo Package.swift (single package, multiple targets)

An alternative to per-module Package.swift files — a single package with multiple library targets:

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AppModules",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "Core", targets: ["Core"]),
        .library(name: "Networking", targets: ["Networking"]),
        .library(name: "FeatureAuth", targets: ["FeatureAuth"]),
        .library(name: "FeatureHome", targets: ["FeatureHome"]),
        .library(name: "UIComponents", targets: ["UIComponents"]),
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-algorithms.git", from: "<latest-stable>"),
    ],
    targets: [
        .target(name: "Core"),
        .target(name: "Networking", dependencies: ["Core"]),
        .target(name: "UIComponents", dependencies: ["Core"]),
        .target(name: "FeatureAuth", dependencies: ["Core", "Networking", "UIComponents"]),
        .target(name: "FeatureHome", dependencies: ["Core", "Networking", "UIComponents"]),

        .testTarget(name: "CoreTests", dependencies: ["Core"]),
        .testTarget(name: "NetworkingTests", dependencies: ["Networking"]),
        .testTarget(name: "FeatureAuthTests", dependencies: ["FeatureAuth"]),
        .testTarget(name: "FeatureHomeTests", dependencies: ["FeatureHome"]),
    ]
)
```

### Dependency graph rules

```
FeatureAuth ──┐
FeatureHome ──┼──> Core
FeatureSettings─┘    │
      │              ▼
      └──────> UIComponents
```

- **Acyclic** — features never depend on each other. Features depend on `Core` and `UIComponents`.
- **Core has zero feature dependencies** — it contains models, protocols, networking, persistence.
- **UIComponents has zero business logic** — pure view components and modifiers.
- **App target is the composition root** — it imports all feature modules and wires them together.

### When to create a new module

| Signal | Action |
|---|---|
| Component is a self-contained logical unit (player, auth, networking, analytics) | Extract to its own module — even with a single consumer. Benefits: incremental compilation (unchanged module is not recompiled), enforced access boundaries (`internal` scoped to module), isolated testability, ready for reuse without refactoring. |
| Code is used by 2+ feature modules | Extract to a `Core` or shared package |
| Feature has its own team or release cycle | Own SPM package under `Packages/` |
| Build time is growing — large target causes frequent recompilation | Split into smaller SPM targets with narrower dependencies |
| You need different platform support for a subset of code | Separate target with its own platform requirements |

### When NOT to create a module

- **Tiny scope** — a single extension or utility function doesn't justify a module. Put it in `Core`.
- **No clear boundary** — if you can't define a clean public API for the module, it's not ready to be extracted.
- **Over-splitting** — each SPM target adds build graph complexity and Package.swift maintenance. A well-organized project with 8-12 targets is better than 40 micro-targets with 2 files each.

### Adding local packages to the Xcode project

1. Drag the `Packages/` directory (or individual package folders) into the Xcode project navigator.
2. Xcode automatically resolves local `.package(path:)` references.
3. In the app target's "Frameworks, Libraries, and Embedded Content", add each library product.

## Feature Module Pattern

### Structure of a feature package

```
FeatureAuth/
├── Package.swift
├── Sources/
│   └── FeatureAuth/
│       ├── AuthFeature.swift       # Public entry point (view or coordinator)
│       ├── Views/
│       │   ├── LoginView.swift
│       │   ├── SignUpView.swift
│       │   └── Components/
│       │       └── AuthTextField.swift
│       ├── ViewModels/
│       │   ├── LoginViewModel.swift
│       │   └── SignUpViewModel.swift
│       ├── Models/
│       │   └── AuthCredentials.swift
│       └── Services/
│           └── AuthService.swift
└── Tests/
    └── FeatureAuthTests/
        ├── LoginViewModelTests.swift
        └── AuthServiceTests.swift
```

### Public API surface

Each feature module exposes a minimal public interface. Everything else stays `internal` (the default) or `private`:

```swift
// AuthFeature.swift — the single public entry point
public struct AuthFeature {
    public static func loginView(onSuccess: @escaping () -> Void) -> some View {
        LoginView(onSuccess: onSuccess)
    }

    public static func signUpView(onSuccess: @escaping () -> Void) -> some View {
        SignUpView(onSuccess: onSuccess)
    }
}
```

### API / Implementation split

For larger projects, split a feature into an API module and an implementation module. The API module contains protocols and models; the implementation module contains concrete types. This prevents transitive compilation dependencies.

```swift
// Package.swift
products: [
    .library(name: "FeatureAuthAPI", targets: ["FeatureAuthAPI"]),
    .library(name: "FeatureAuth", targets: ["FeatureAuth"]),
],
targets: [
    .target(name: "FeatureAuthAPI", dependencies: ["Core"]),
    .target(name: "FeatureAuth", dependencies: ["FeatureAuthAPI", "Core", "Networking"]),
]
```

```swift
// In FeatureAuthAPI module
public protocol AuthServiceProtocol: Sendable {
    func login(email: String, password: String) async throws -> User
    func logout() async
}

// In FeatureAuth module
struct RemoteAuthService: AuthServiceProtocol {
    func login(email: String, password: String) async throws -> User { ... }
    func logout() async { ... }
}
```

Other feature modules depend on `FeatureAuthAPI` only — they never import `FeatureAuth` directly. The app target wires the concrete implementation at the composition root.

### Shared Core module

```
Core/
├── Sources/
│   └── Core/
│       ├── Models/
│       │   ├── User.swift
│       │   └── AppError.swift
│       ├── Protocols/
│       │   ├── Repository.swift
│       │   └── UseCase.swift
│       ├── Networking/
│       │   ├── HTTPClient.swift
│       │   ├── Endpoint.swift
│       │   └── NetworkError.swift
│       ├── Persistence/
│       │   └── StorageService.swift
│       └── Extensions/
│           ├── Date+Formatting.swift
│           └── String+Validation.swift
└── Tests/
    └── CoreTests/
```

Rules for Core:
- Contains only types that at least two feature modules need.
- If a type is used by only one feature, it belongs in that feature module.
- Core must not import any feature module.

## Build Configurations

### Default configurations

Xcode projects start with **Debug** and **Release**. Add a **Staging** configuration for environments that differ from production but need optimizations:

| Configuration | Optimization | Assertions | Typical Use |
|---|---|---|---|
| Debug | `-Onone` | Enabled | Local development |
| Staging | `-O` | Enabled | QA / TestFlight |
| Release | `-O` | Disabled | App Store |

### Adding a Staging configuration

In Xcode: Project > Info > Configurations > click `+` > Duplicate "Release". Rename to "Staging".

### xcconfig files

Use `.xcconfig` files to manage build settings outside the Xcode project file. This reduces merge conflicts and makes settings reviewable in PRs.

```
MyApp/
├── Configuration/
│   ├── Base.xcconfig
│   ├── Debug.xcconfig
│   ├── Staging.xcconfig
│   └── Release.xcconfig
├── MyApp/
└── MyApp.xcodeproj
```

**Base.xcconfig:**
```
// Shared across all configurations
PRODUCT_BUNDLE_IDENTIFIER = com.example.myapp
SWIFT_VERSION = 6.0
IPHONEOS_DEPLOYMENT_TARGET = 17.0
MARKETING_VERSION = 1.0.0
CURRENT_PROJECT_VERSION = 1
CODE_SIGN_STYLE = Automatic
DEVELOPMENT_TEAM = XXXXXXXXXX
```

**Debug.xcconfig:**
```
#include "Base.xcconfig"

SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG
PRODUCT_BUNDLE_IDENTIFIER = $(inherited).debug
ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon-Debug
API_BASE_URL = https://api-dev.example.com
```

**Staging.xcconfig:**
```
#include "Base.xcconfig"

SWIFT_ACTIVE_COMPILATION_CONDITIONS = STAGING
PRODUCT_BUNDLE_IDENTIFIER = $(inherited).staging
ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon-Staging
API_BASE_URL = https://api-staging.example.com
SWIFT_OPTIMIZATION_LEVEL = -O
```

**Release.xcconfig:**
```
#include "Base.xcconfig"

SWIFT_ACTIVE_COMPILATION_CONDITIONS = RELEASE
API_BASE_URL = https://api.example.com
SWIFT_OPTIMIZATION_LEVEL = -O
```

Assign xcconfig files in Xcode: Project > Info > Configurations > set the config file for each configuration/target combination.

### Accessing build settings in code

Expose xcconfig values through `Info.plist` and read them at runtime:

**Info.plist entry:**
```xml
<key>APIBaseURL</key>
<string>$(API_BASE_URL)</string>
```

**Swift code:**
```swift
enum BuildConfig {
    static let apiBaseURL: URL = {
        guard let string = Bundle.main.infoDictionary?["APIBaseURL"] as? String,
              let url = URL(string: string) else {
            fatalError("APIBaseURL not configured in Info.plist")
        }
        return url
    }()

    static var isDebug: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }
}
```

### Info.plist management

Xcode 16+ generates a default `Info.plist` for new projects. Add custom keys in the target's "Info" tab or via a physical `Info.plist` file. When using xcconfig, prefer injecting values via `$(VARIABLE_NAME)` substitution rather than hardcoding values in the plist.

For SPM packages, `Info.plist` is not used. Configure package-level metadata in `Package.swift`.

## Targets and Schemes

### Target types

| Target | Purpose | Example |
|---|---|---|
| App | Main application | `MyApp` |
| Unit Test | XCTest bundle for logic tests | `MyAppTests` |
| UI Test | XCUITest bundle for UI automation | `MyAppUITests` |
| Widget Extension | WidgetKit widgets | `MyAppWidget` |
| Watch App | watchOS companion app | `MyApp Watch App` |
| Intents Extension | App Intents / Siri | `MyAppIntents` |
| Notification Service | Push notification modification | `NotificationService` |
| Notification Content | Custom push UI | `NotificationContent` |
| Share Extension | Share sheet integration | `ShareExtension` |
| App Clip | Lightweight app experience | `MyAppClip` |

### Extension target structure

```
MyApp/
├── MyApp/                          # Main app target
├── MyAppWidget/
│   ├── MyAppWidget.swift           # @main WidgetBundle
│   ├── SimpleWidget.swift
│   ├── Assets.xcassets
│   └── Info.plist
├── MyApp Watch App/
│   ├── MyWatchApp.swift
│   ├── ContentView.swift
│   └── Assets.xcassets
└── NotificationService/
    ├── NotificationService.swift
    └── Info.plist
```

### Sharing code between app and extensions

Extensions and the main app are separate processes. Share code via:

1. **SPM local packages** (preferred) — both targets import the same package.
2. **App Groups** — for sharing data (UserDefaults, files) between app and extensions.
3. **Shared framework target** — embed in both app and extension.

```swift
// In both app target and widget target, import the shared package
import Core
import Networking
```

For App Groups (shared UserDefaults):
```swift
// Configure in both app and extension entitlements
// com.example.myapp.shared

let sharedDefaults = UserDefaults(suiteName: "group.com.example.myapp.shared")
```

### Scheme management

- **One scheme per runnable target** — `MyApp`, `MyApp Watch App`, `MyAppWidget`.
- **Shared schemes** — check "Shared" in Manage Schemes so they are committed to version control (stored in `.xcodeproj/xcshareddata/xcschemes/`).
- **Scheme per configuration** — create `MyApp (Staging)` scheme that uses the Staging build configuration for Run and Archive actions.

Scheme configuration:

| Action | Configuration | Typical Setting |
|---|---|---|
| Run | Debug | Debugger attached, assertions on |
| Test | Debug | Code coverage enabled |
| Profile | Release | Instruments profiling |
| Analyze | Debug | Static analysis |
| Archive | Release (or Staging) | Distribution build |

### Creating a scheme for Staging

1. Duplicate the main app scheme.
2. Rename to `MyApp (Staging)`.
3. Set Run action build configuration to "Staging".
4. Set Archive action build configuration to "Staging".
5. Mark as Shared.

## Asset Management

### Asset Catalogs

```
Resources/
├── Assets.xcassets/
│   ├── AccentColor.colorset/       # App-wide accent color
│   ├── AppIcon.appiconset/         # App icon (single 1024x1024 in Xcode 16+)
│   ├── Colors/                     # Organized in folders
│   │   ├── Primary.colorset/
│   │   ├── Secondary.colorset/
│   │   └── Background.colorset/
│   ├── Images/
│   │   ├── Logo.imageset/
│   │   ├── Onboarding/
│   │   │   ├── Step1.imageset/
│   │   │   └── Step2.imageset/
│   │   └── Placeholder.imageset/
│   └── Symbols/                    # Custom SF Symbols
│       └── custom.heart.symbolset/
```

### Color sets

Define colors with light/dark appearances in the Asset Catalog. Reference in code:

```swift
// SwiftUI
Color("Primary")                    // String-based (fragile)
Color(.primary)                     // Type-safe via asset symbol generation (Xcode 15+)

// UIKit
UIColor(named: "Primary")
UIColor(resource: .primary)         // Type-safe (Xcode 15+)
```

Xcode 15+ generates type-safe asset symbols automatically. Prefer `.primary` over `"Primary"` for compile-time safety.

### Image sets

Provide images at 1x, 2x, 3x scales or use a single PDF/SVG with "Preserve Vector Data" enabled (preferred for resolution independence).

```swift
// SwiftUI
Image(.logo)                        // Type-safe asset symbol
Image("Logo")                       // String-based (avoid)

// Rendering modes
Image(.logo)
    .renderingMode(.template)       // Tintable
    .resizable()
    .scaledToFit()
```

### SF Symbols

Use SF Symbols as the primary icon system. Custom symbols can be created in the SF Symbols app and exported as `.symbolset` assets.

```swift
// System symbols
Image(systemName: "heart.fill")
Label("Favorites", systemImage: "heart.fill")

// With symbol rendering
Image(systemName: "heart.fill")
    .symbolRenderingMode(.hierarchical)
    .foregroundStyle(.red)

// Symbol effects (iOS 17+)
Image(systemName: "heart.fill")
    .symbolEffect(.bounce, value: isFavorited)
```

### String Catalogs (Xcode 15+)

String Catalogs (`.xcstrings`) replace `Localizable.strings` and `Localizable.stringsdict`. Xcode automatically discovers localizable strings from `String(localized:)`, `Text()`, and `LocalizedStringKey`.

```swift
// These are automatically extracted into the String Catalog
Text("Welcome back!")
Text("Hello, \(username)")         // Interpolation supported

// Explicit localization with comment
Text("settings_title", comment: "Navigation title for Settings screen")

// Programmatic
let message = String(localized: "upload_complete",
                     defaultValue: "Upload complete",
                     comment: "Shown after successful file upload")
```

**String Catalog workflow:**
1. Create `Localizable.xcstrings` in the Resources folder.
2. Build the project — Xcode extracts all localizable strings.
3. Add languages in the String Catalog editor.
4. Translate strings in the editor or export as XLIFF for translators.

### Asset organization rules

- Group related assets in Asset Catalog folders (Colors, Images, Icons).
- Use type-safe asset symbols (Xcode 15+ auto-generated) instead of string literals.
- Provide dark mode variants for all custom colors.
- Use SF Symbols over custom icons when a suitable symbol exists.
- Keep image assets in the Asset Catalog, not loose files in the bundle.

## Code Generation

### SwiftGen

SwiftGen generates type-safe Swift code for resources (colors, images, strings, fonts). It is less critical with Xcode 15+ asset symbol generation, but remains useful for strings with complex interpolation and custom fonts.

Install via SPM plugin or Homebrew:

```bash
brew install swiftgen
```

**swiftgen.yml:**
```yaml
strings:
  inputs:
    - MyApp/Resources/Localizable.xcstrings
  outputs:
    - templateName: structured-swift5
      output: MyApp/Generated/Strings.swift

fonts:
  inputs:
    - MyApp/Resources/Fonts
  outputs:
    - templateName: swift5
      output: MyApp/Generated/Fonts.swift
```

### SPM build plugins

SPM supports build tool plugins that run during compilation. Use them for code generation that must stay in sync with source files.

```swift
// In Package.swift
targets: [
    .target(
        name: "MyFeature",
        dependencies: [],
        plugins: [
            .plugin(name: "SwiftGenPlugin", package: "SwiftGenPlugin"),
        ]
    ),
    .plugin(
        name: "MyCodeGenPlugin",
        capability: .buildTool()
    ),
]
```

### Custom SPM build plugin example

```swift
// Plugins/MyCodeGenPlugin/MyCodeGenPlugin.swift
import PackagePlugin

@main
struct MyCodeGenPlugin: BuildToolPlugin {
    func createBuildCommands(
        context: PluginContext,
        target: Target
    ) async throws -> [Command] {
        let tool = try context.tool(named: "my-generator")
        let outputDir = context.pluginWorkDirectoryURL

        return [
            .buildCommand(
                displayName: "Generate code",
                executable: tool.url,
                arguments: [
                    "--input", target.directoryURL.path(),
                    "--output", outputDir.path(),
                ],
                outputFiles: [outputDir.appending(path: "Generated.swift")]
            )
        ]
    }
}
```

### When to use code generation

| Scenario | Tool | Notes |
|---|---|---|
| Asset references (colors, images) | Xcode 15+ built-in | Asset symbols generated automatically |
| Strings with complex interpolation | SwiftGen | Better type safety than raw String Catalogs |
| Custom fonts | SwiftGen | Type-safe font references |
| API models from OpenAPI spec | swift-openapi-generator | Apple's official OpenAPI plugin |
| Mock generation | Sourcery or manual fakes | Prefer hand-written fakes for small projects |
| gRPC / Protobuf | grpc-swift plugin | SPM plugin for proto compilation |

## CI/CD Considerations

### Options

| Tool | Type | Best For |
|------|------|----------|
| **Xcode Cloud** | Apple's first-party CI/CD (25 free compute hours/month) | Simple pipelines, tight Xcode integration, TestFlight distribution |
| **Fastlane** | Open-source automation | Complex workflows, multi-lane builds, custom signing |
| **GitHub Actions** | GitHub-native CI | Teams already on GitHub, matrix testing, custom runners |

### xcodebuild commands

```bash
# Build
xcodebuild build \
    -project MyApp.xcodeproj \
    -scheme "MyApp" \
    -configuration Debug \
    -destination "platform=iOS Simulator,name=iPhone 16,OS=18.0" \
    | xcbeautify

# Build with workspace (when using SPM or CocoaPods)
xcodebuild build \
    -workspace MyApp.xcworkspace \
    -scheme "MyApp" \
    -configuration Debug \
    -destination "platform=iOS Simulator,name=iPhone 16,OS=18.0"

# Run tests
xcodebuild test \
    -scheme "MyApp" \
    -destination "platform=iOS Simulator,name=iPhone 16,OS=18.0" \
    -resultBundlePath TestResults.xcresult

# Archive for distribution
xcodebuild archive \
    -scheme "MyApp" \
    -configuration Release \
    -archivePath build/MyApp.xcarchive \
    -allowProvisioningUpdates

# Export IPA from archive
xcodebuild -exportArchive \
    -archivePath build/MyApp.xcarchive \
    -exportPath build/export \
    -exportOptionsPlist ExportOptions.plist
```

**ExportOptions.plist for TestFlight:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store-connect</string>
    <key>destination</key>
    <string>upload</string>
    <key>signingStyle</key>
    <string>automatic</string>
    <key>teamID</key>
    <string>XXXXXXXXXX</string>
</dict>
</plist>
```

### Fastlane basics

```ruby
# fastlane/Fastfile
default_platform(:ios)

platform :ios do
  desc "Run tests"
  lane :test do
    run_tests(
      scheme: "MyApp",
      devices: ["iPhone 16"],
      clean: true,
      code_coverage: true
    )
  end

  desc "Build and upload to TestFlight"
  lane :beta do
    increment_build_number(
      build_number: ENV["CI_BUILD_NUMBER"] || latest_testflight_build_number + 1
    )
    build_app(
      scheme: "MyApp",
      configuration: "Release",
      export_method: "app-store-connect"
    )
    upload_to_testflight(
      skip_waiting_for_build_processing: true
    )
  end

  desc "Build and upload to App Store"
  lane :release do
    build_app(
      scheme: "MyApp",
      configuration: "Release",
      export_method: "app-store-connect"
    )
    upload_to_app_store(
      skip_metadata: false,
      skip_screenshots: true,
      precheck_include_in_app_purchases: false
    )
  end
end
```

### Code signing

**Automatic signing (recommended for small teams):**
- Set `CODE_SIGN_STYLE = Automatic` in build settings or xcconfig.
- Xcode / xcodebuild manages provisioning profiles via your Apple Developer account.
- On CI, use `xcodebuild -allowProvisioningUpdates` and install the Apple Developer certificate in the CI keychain.

**Manual signing (recommended for large teams / enterprise):**
- Use fastlane `match` to manage certificates and profiles in a shared Git repo or cloud storage.
- Set `CODE_SIGN_STYLE = Manual` and specify `PROVISIONING_PROFILE_SPECIFIER`.

```ruby
# fastlane/Matchfile
git_url("https://github.com/your-org/certificates.git")
storage_mode("git")
type("appstore")
app_identifier(["com.example.myapp"])
```

```bash
# Sync certificates
fastlane match appstore
fastlane match development
```

### TestFlight distribution

```bash
# Using altool (still works for App Store Connect uploads, but deprecated for notarization)
xcrun altool --upload-app \
    --type ios \
    --file build/export/MyApp.ipa \
    --apiKey YOUR_KEY_ID \
    --apiIssuer YOUR_ISSUER_ID

# Using Apple Transporter (modern, recommended for CI)
xcrun iTMSTransporter -m upload \
    -assetFile build/export/MyApp.ipa \
    -apiKey ~/.private_keys/AuthKey_XXXX.p8 \
    -apiIssuer YOUR_ISSUER_ID
```

> **Note:** `notarytool` is for **macOS app notarization only** — do not use it for iOS/tvOS/watchOS TestFlight uploads. For iOS uploads, use `altool`, Apple Transporter (`iTMSTransporter`), Fastlane, or Xcode Cloud.

Prefer the App Store Connect API key (`.p8` file) over Apple ID credentials for CI authentication.

## Multi-Platform Targets

### Platform conditionals

```swift
// Compile-time platform checks
#if os(iOS)
import UIKit
#elseif os(macOS)
import AppKit
#elseif os(watchOS)
import WatchKit
#elseif os(tvOS)
import TVUIKit
#elseif os(visionOS)
import RealityKit
#endif

// Target environment (simulator vs device)
#if targetEnvironment(simulator)
let isSimulator = true
#else
let isSimulator = false
#endif

// Availability checks at runtime
if #available(iOS 18, macOS 15, *) {
    // Use new API
}
```

### Shared code with platform-specific views

```swift
// Shared view model — works on all platforms
@Observable
class SettingsViewModel {
    var notifications: Bool = true
    var theme: Theme = .system

    func save() async throws {
        try await settingsService.save(notifications: notifications, theme: theme)
    }
}

// Platform-specific views
struct SettingsView: View {
    @State private var viewModel = SettingsViewModel()

    var body: some View {
        Form {
            Toggle("Notifications", isOn: $viewModel.notifications)

            #if os(iOS)
            // iOS-specific haptic feedback toggle
            Toggle("Haptics", isOn: $viewModel.haptics)
            #endif

            #if os(macOS)
            // macOS-specific menu bar toggle
            Toggle("Show in Menu Bar", isOn: $viewModel.showInMenuBar)
            #endif
        }
    }
}
```

### Multi-platform Package.swift

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Core",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
        .watchOS(.v10),
        .tvOS(.v17),
        .visionOS(.v1),
    ],
    products: [
        .library(name: "Core", targets: ["Core"]),
    ],
    targets: [
        .target(
            name: "Core",
            swiftSettings: [
                .define("ENABLE_HAPTICS", .when(platforms: [.iOS])),
            ]
        ),
        .testTarget(name: "CoreTests", dependencies: ["Core"]),
    ]
)
```

### Conditional dependencies in SPM

```swift
.target(
    name: "PlatformKit",
    dependencies: [
        .target(name: "Core"),
        .target(name: "IOSSupport", condition: .when(platforms: [.iOS])),
        .target(name: "MacSupport", condition: .when(platforms: [.macOS])),
    ]
),
```

### Multi-platform project organization

```
MyApp/
├── MyApp/                          # iOS app target
├── MyApp-macOS/                    # macOS app target (if separate)
├── MyApp Watch App/                # watchOS target
├── Packages/
│   ├── Core/                       # Platform-agnostic logic
│   ├── PlatformKit/                # Platform abstractions
│   │   ├── Sources/
│   │   │   └── PlatformKit/
│   │   │       ├── Shared/         # Cross-platform code
│   │   │       ├── iOS/            # iOS-specific implementations
│   │   │       └── macOS/          # macOS-specific implementations
│   └── Features/                   # Feature modules (mostly shared)
└── MyApp.xcodeproj
```

Rules for multi-platform:
- Keep business logic platform-agnostic in `Core`.
- Isolate platform-specific UI in platform-named directories.
- Use `#if os()` sparingly and only in leaf views. Extract platform differences into dedicated types when the conditional logic grows beyond a few lines.
- Test shared logic on one platform; test platform-specific code on its target platform.

### Multi-target apps (same platform, different brands/products)

When a project has multiple app targets (e.g., different branded apps sharing a codebase), **never use `#if` compiler directives or custom build flags to branch behavior between targets.** `#if` is designed to exclude code from compilation entirely (e.g., `#if DEBUG`, `#if os(iOS)`), not to implement polymorphism between app variants.

Instead, use one of these approaches:

**1. Dependency injection (preferred)** — define a protocol for the varying behavior, provide a per-target conformance, and inject at the composition root:

```swift
// Shared protocol
protocol AppConfiguration {
    var appName: String { get }
    var primaryColor: Color { get }
    var featureFlags: FeatureFlags { get }
}

// Target A implementation (in Target A's file membership)
struct TargetAConfiguration: AppConfiguration {
    let appName = "App A"
    let primaryColor = Color.blue
    let featureFlags = FeatureFlags(showPremium: true)
}

// Target B implementation (in Target B's file membership)
struct TargetBConfiguration: AppConfiguration {
    let appName = "App B"
    let primaryColor = Color.green
    let featureFlags = FeatureFlags(showPremium: false)
}

// Inject at app entry point
@main
struct MyApp: App {
    let config: AppConfiguration = TargetAConfiguration() // per-target

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.appConfig, config)
        }
    }
}
```

**2. Separate files per target** — create one file per target with the same type name, and assign each file to the correct target membership in Xcode. The linker resolves the right implementation at build time.

```
MyApp/
├── Config/
│   ├── AppConfig+TargetA.swift    # target membership: Target A only
│   └── AppConfig+TargetB.swift    # target membership: Target B only
```

This keeps code clean, testable, and avoids the maintenance burden of scattered `#if` blocks that are hard to audit and easy to break.

## Dependency Management

### SPM (preferred for new projects)

Dependencies are declared in `Package.swift` (for packages) or added via Xcode > File > Add Package Dependencies (for app targets).

**Version pinning strategies:**

```swift
// Exact version — maximum stability, minimum flexibility
.package(url: "https://github.com/pointfreeco/swift-composable-architecture.git", exact: "1.17.0")

// Minor version range (recommended) — allows patch updates
.package(url: "https://github.com/pointfreeco/swift-composable-architecture.git", from: "1.17.0")

// Version range — when you need to cap the upper bound
.package(url: "https://github.com/pointfreeco/swift-composable-architecture.git", "1.15.0"..<"2.0.0")

// Branch (development only, never for release)
.package(url: "https://github.com/some/package.git", branch: "main")
```

**Package.resolved:** Commit `Package.resolved` to version control. This locks the full dependency graph to specific versions, ensuring reproducible builds across the team and CI.

### Evaluating third-party dependencies

Before adding a dependency, consider:

| Criterion | Check |
|---|---|
| Maintenance | Recent commits, responsive to issues, multiple contributors |
| License | Compatible with your distribution (MIT, Apache 2.0 preferred) |
| Size | Does it pull in a large transitive dependency graph? |
| Platform support | Does it support all your target platforms? |
| Alternatives | Can you write this in 50-100 lines instead of adding a dependency? |

### CocoaPods (legacy)

Use CocoaPods only when a dependency does not support SPM or when maintaining an existing project that already uses it.

```ruby
# Podfile
platform :ios, '17.0'
use_frameworks!

target 'MyApp' do
  pod 'FirebaseAnalytics', '~> 11.0'
  pod 'GoogleMaps', '~> 9.0'

  target 'MyAppTests' do
    inherit! :search_paths
  end
end

post_install do |installer|
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '17.0'
    end
  end
end
```

```bash
# Install / update
pod install
pod update FirebaseAnalytics

# Always open the workspace, not the project
open MyApp.xcworkspace
```

**Migration path from CocoaPods to SPM:**
1. Check if each pod has an SPM-compatible release.
2. Add the SPM package, remove the pod, verify the build.
3. Migrate one dependency at a time. Run tests after each migration.
4. Once all pods are removed, delete `Podfile`, `Podfile.lock`, `Pods/`, and the `.xcworkspace` if it was created by CocoaPods.

### Dependency management rules

- **SPM by default** for all new dependencies.
- **Commit lock files** — `Package.resolved` for SPM, `Podfile.lock` for CocoaPods.
- **Pin to minor versions** (`from: "1.17.0"`) — allows patches, blocks breaking changes.
- **Audit regularly** — review dependency updates monthly. Apply security patches immediately.
- **Minimize dependencies** — every external dependency is a maintenance and security liability. Prefer Apple frameworks and standard library when feasible.
- **Never use branch-based dependencies in release builds.**

### .gitignore for Xcode projects

```
# Xcode
*.xcodeproj/project.xcworkspace/xcuserdata/
*.xcodeproj/xcuserdata/
*.xcworkspace/xcuserdata/
*.xcworkspace/xcshareddata/swiftpm/configuration/

# Build
build/
DerivedData/

# CocoaPods (if used)
Pods/

# Fastlane
fastlane/report.xml
fastlane/Preview.html
fastlane/screenshots/
fastlane/test_output/

# OS
.DS_Store
*.swp

# SPM — DO commit Package.resolved
# !/Package.resolved
```
