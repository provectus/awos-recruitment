# Swift Project Structure Reference

## Contents
- `Package.swift` essentials (swift-tools-version, targets, dependencies, traits)
- Multi-target package organization (API separation, internal modules, split criteria)
- Build configurations (conditional compilation, optimization, custom flags)
- Plugins (build tool, command, permissions, common plugins)
- Testing setup (Swift Testing, XCTest, organization, parameterized tests)
- Dependency management (version resolution, best practices, diamond dependencies)
- CI/CD considerations (Linux, Docker, coverage, linting)
- Module decision guide (when to split, criteria)

## Package.swift

### Minimal package manifest

```swift
// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "MyLibrary",
    products: [
        .library(name: "MyLibrary", targets: ["MyLibrary"]),
    ],
    targets: [
        .target(name: "MyLibrary"),
        .testTarget(
            name: "MyLibraryTests",
            dependencies: ["MyLibrary"]
        ),
    ]
)
```

The `swift-tools-version` comment must be the very first line. It determines the minimum Swift version and which Package API features are available.

### Target types

| Target type | Factory method | Purpose |
|---|---|---|
| Library | `.target(name:)` | Compiled module importable by other targets |
| Executable | `.executableTarget(name:)` | Produces a runnable binary |
| Plugin | `.plugin(name:capability:)` | Build tool or command plugin |
| Macro | `.macro(name:)` | Swift macro implementation |
| Test | `.testTarget(name:)` | Test bundle |
| System library | `.systemLibrary(name:)` | Wraps a system-installed C library |

### Dependencies

```swift
let package = Package(
    name: "MyApp",
    dependencies: [
        // Remote — version range (up to next major)
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.3.0"),

        // Remote — exact version
        .package(url: "https://github.com/apple/swift-log.git", exact: "1.5.4"),

        // Remote — branch
        .package(url: "https://github.com/apple/swift-nio.git", branch: "main"),

        // Remote — revision
        .package(url: "https://github.com/apple/swift-collections.git",
                 revision: "a1b2c3d4e5f6"),

        // Local package
        .package(path: "../SharedUtils"),
    ],
    targets: [
        .executableTarget(
            name: "MyApp",
            dependencies: [
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
                .product(name: "Logging", package: "swift-log"),
                "SharedUtils",
            ]
        ),
    ]
)
```

### Version requirement summary

| Requirement | Syntax | Resolves to |
|---|---|---|
| Up to next major | `from: "1.3.0"` | `>= 1.3.0, < 2.0.0` |
| Up to next minor | `.upToNextMinor(from: "1.3.0")` | `>= 1.3.0, < 1.4.0` |
| Exact | `exact: "1.3.0"` | `== 1.3.0` |
| Range | `"1.2.0"..<"1.5.0"` | `>= 1.2.0, < 1.5.0` |
| Branch | `branch: "main"` | Latest commit on branch |
| Revision | `revision: "abc123"` | Specific commit |

### Platform constraints

Only specify platforms when your code actually requires platform-specific APIs. Omit entirely for pure Swift code that runs everywhere.

```swift
let package = Package(
    name: "PlatformSpecificLib",
    platforms: [
        .macOS(.v14),
    ],
    // ...
)
```

### Package traits and conditional compilation

Swift 6.0+ supports package traits for compile-time feature selection:

```swift
let package = Package(
    name: "MyLibrary",
    traits: [
        .trait(name: "Logging", description: "Enable structured logging support"),
        .trait(name: "Metrics", description: "Enable metrics collection"),
    ],
    targets: [
        .target(
            name: "MyLibrary",
            dependencies: [
                .product(name: "Logging", package: "swift-log",
                         condition: .when(traits: ["Logging"])),
            ],
            swiftSettings: [
                .define("LOGGING_ENABLED", .when(traits: ["Logging"])),
                .define("METRICS_ENABLED", .when(traits: ["Metrics"])),
            ]
        ),
    ]
)
```

Consumers enable traits in their dependency declaration:

```swift
.package(url: "https://github.com/example/MyLibrary.git", from: "1.0.0",
         traits: ["Logging"]),
```

## Multi-Target Packages

### Separating public API from implementation

```
Sources/
├── MyLibrary/            # Public API surface
│   ├── PublicTypes.swift
│   └── Client.swift
├── MyLibraryCore/        # Internal implementation
│   ├── Engine.swift
│   └── Parser.swift
└── my-cli/               # Executable consuming the library
    └── main.swift
```

```swift
let package = Package(
    name: "MyLibrary",
    products: [
        .library(name: "MyLibrary", targets: ["MyLibrary"]),
        .executable(name: "my-cli", targets: ["my-cli"]),
    ],
    targets: [
        .target(name: "MyLibraryCore"),
        .target(name: "MyLibrary", dependencies: ["MyLibraryCore"]),
        .executableTarget(name: "my-cli", dependencies: ["MyLibrary"]),
        .testTarget(name: "MyLibraryTests", dependencies: ["MyLibrary"]),
        .testTarget(name: "MyLibraryCoreTests", dependencies: ["MyLibraryCore"]),
    ]
)
```

### Access control across modules

| Modifier | Same module | Other modules |
|---|---|---|
| `open` | Yes | Yes (subclass + override) |
| `public` | Yes | Yes (no subclass) |
| `package` | Yes | Yes (same package only) |
| `internal` (default) | Yes | No |
| `fileprivate` | Same file | No |
| `private` | Same scope | No |

The `package` access level (Swift 5.9+) is useful for sharing implementation details across targets within the same SwiftPM package without exposing them to external consumers.

```swift
// In MyLibraryCore target
package func internalHelper() -> String {
    "available to other targets in this package, but not to external consumers"
}
```

### When to split into separate targets

- The code has a distinct, well-defined API boundary.
- You want different access control (public API vs internal engine).
- Faster incremental builds — unchanged targets are not recompiled.
- Independent testability — test internal logic without going through the public API.
- Reuse across multiple executables or libraries within the same package.
- Self-contained logical units deserve their own module even with a single consumer.

### When to use a single target

- Small project with under ~20 source files.
- No meaningful internal boundary to draw.
- The overhead of managing multiple targets outweighs the benefit.
- Prototyping or early development where boundaries are not yet clear.

## Build Configurations

### Conditional compilation

```swift
#if DEBUG
let apiURL = "https://staging.example.com"
#else
let apiURL = "https://api.example.com"
#endif

#if os(Linux)
import Glibc
#elseif os(macOS)
import Darwin
#elseif os(Windows)
import WinSDK
#endif

#if canImport(FoundationNetworking)
import FoundationNetworking  // Required on Linux for URLSession
#endif

#if swift(>=6.0)
// Use Swift 6 features
#endif

#if compiler(>=6.0)
// Compiler-version check (different from language version)
#endif
```

### Common compilation conditions

| Condition | Values |
|---|---|
| `os()` | `macOS`, `Linux`, `Windows`, `iOS`, `watchOS`, `tvOS`, `visionOS` |
| `arch()` | `x86_64`, `arm64`, `i386`, `arm` |
| `canImport()` | Any module name |
| `swift()` | Version check (e.g., `>=6.0`) |
| `compiler()` | Compiler version check |
| `DEBUG` | Set in debug builds |
| `SWIFT_PACKAGE` | Always set when building with SwiftPM |

### Custom build settings in Package.swift

```swift
.target(
    name: "MyLibrary",
    swiftSettings: [
        // Custom defines
        .define("FEATURE_FLAG_NEW_PARSER"),
        .define("VERBOSE_LOGGING", .when(configuration: .debug)),

        // Upcoming language features
        .enableUpcomingFeature("StrictConcurrency"),
        .enableExperimentalFeature("BodyMacros"),

        // Unsafe flags (avoid if possible — breaks package consumers)
        .unsafeFlags(["-Xfrontend", "-warn-long-function-bodies=100"],
                     .when(configuration: .debug)),
    ],
    linkerSettings: [
        .linkedLibrary("sqlite3"),
        .linkedLibrary("z", .when(platforms: [.linux])),
    ]
)
```

### Optimization levels

| Flag | Configuration | Effect |
|---|---|---|
| `-Onone` | Debug (default) | No optimization, fastest compile |
| `-O` | Release (default) | Standard optimization |
| `-Osize` | — | Optimize for binary size |
| `-Ounchecked` | — | Remove runtime safety checks (dangerous) |
| `-wmo` | — | Whole module optimization |

Build with a specific configuration:

```bash
swift build -c debug    # -Onone
swift build -c release  # -O -wmo
```

## Plugins

### Build tool plugins

Run automatically during the build process (e.g., code generation):

```swift
.plugin(
    name: "GenerateResources",
    capability: .buildTool()
)
```

Plugin implementation in `Plugins/GenerateResources/plugin.swift`:

```swift
import PackagePlugin

@main
struct GenerateResources: BuildToolPlugin {
    func createBuildCommands(context: PluginContext, target: Target) throws -> [Command] {
        let outputPath = context.pluginWorkDirectoryURL
            .appending(path: "GeneratedResources.swift")

        return [
            .buildCommand(
                displayName: "Generate resource accessors",
                executable: try context.tool(named: "resource-generator").url,
                arguments: [target.directoryURL.path(), outputPath.path()],
                outputFiles: [outputPath]
            )
        ]
    }
}
```

### Command plugins

Run on demand via `swift package <command>`:

```swift
.plugin(
    name: "FormatCode",
    capability: .command(
        intent: .sourceCodeFormatting(),
        permissions: [.writeToPackageDirectory(reason: "Format source files")]
    )
)
```

### Plugin permissions

| Permission | Purpose |
|---|---|
| `.writeToPackageDirectory(reason:)` | Modify source files in-place |
| `.allowNetworkConnections(scope:reason:)` | Network access (e.g., download tools) |

Plugins run in a sandbox by default. They cannot write to the package directory or access the network unless permissions are explicitly declared and the user approves.

### Common plugins

| Plugin | Purpose | Integration |
|---|---|---|
| [SwiftLint](https://github.com/realm/SwiftLint) | Linting | Build tool or command plugin |
| [swift-format](https://github.com/swiftlang/swift-format) | Formatting | Command plugin |
| [SwiftGen](https://github.com/SwiftGen/SwiftGen) | Resource code generation | Build tool plugin |
| [swift-openapi-generator](https://github.com/apple/swift-openapi-generator) | OpenAPI client/server codegen | Build tool plugin |

## Testing Setup

### Directory layout

```
Sources/
└── MyLibrary/
    └── Calculator.swift
Tests/
├── MyLibraryTests/
│   ├── CalculatorTests.swift
│   └── ParserTests.swift
└── MyLibraryIntegrationTests/
    └── EndToEndTests.swift
```

```swift
targets: [
    .target(name: "MyLibrary"),
    .testTarget(name: "MyLibraryTests", dependencies: ["MyLibrary"]),
    .testTarget(name: "MyLibraryIntegrationTests", dependencies: ["MyLibrary"]),
]
```

### Swift Testing framework (Swift 6.0+)

The modern testing framework — preferred for new code:

```swift
import Testing
@testable import MyLibrary

@Suite("Calculator")
struct CalculatorTests {

    let calculator = Calculator()

    @Test("adds two integers")
    func addition() {
        #expect(calculator.add(2, 3) == 5)
    }

    @Test("throws on division by zero")
    func divisionByZero() {
        #expect(throws: MathError.divisionByZero) {
            try calculator.divide(10, by: 0)
        }
    }

    @Test("rejects negative input")
    func negativeInput() throws {
        #expect(calculator.isValid(-1) == false)
    }
}
```

### Parameterized tests

```swift
@Test("square roots of perfect squares", arguments: [
    (input: 4, expected: 2),
    (input: 9, expected: 3),
    (input: 16, expected: 4),
    (input: 25, expected: 5),
])
func squareRoot(input: Int, expected: Int) {
    #expect(Calculator.sqrt(input) == expected)
}

// Multiple argument sources — tests all combinations
@Test(arguments: ["USD", "EUR", "GBP"], [100, 200, 500])
func formatCurrency(code: String, amount: Int) {
    let result = Formatter.currency(amount, code: code)
    #expect(!result.isEmpty)
}
```

### Test tags for filtering

```swift
extension Tag {
    @Tag static var slow: Self
    @Tag static var network: Self
}

@Test(.tags(.slow))
func performanceHeavyTest() { ... }

@Test(.tags(.network))
func apiIntegrationTest() { ... }
```

Run filtered tests:

```bash
swift test --filter MyLibraryTests.CalculatorTests
```

### XCTest (for compatibility)

Still supported and needed for older codebases or when Swift Testing is unavailable:

```swift
import XCTest
@testable import MyLibrary

final class CalculatorXCTests: XCTestCase {

    func testAddition() {
        let calc = Calculator()
        XCTAssertEqual(calc.add(2, 3), 5)
    }

    func testAsyncFetch() async throws {
        let result = try await service.fetch()
        XCTAssertFalse(result.isEmpty)
    }
}
```

Swift Testing and XCTest can coexist in the same test target. Migrate incrementally.

### Test resources and fixtures

Place test fixtures in the test target directory and declare them as resources:

```swift
.testTarget(
    name: "MyLibraryTests",
    dependencies: ["MyLibrary"],
    resources: [
        .copy("Fixtures"),           // Copy entire directory as-is
        .process("Resources"),       // Process resources (optimize images, etc.)
    ]
)
```

Access in tests:

```swift
let fixtureURL = Bundle.module.url(forResource: "sample", withExtension: "json",
                                    subdirectory: "Fixtures")!
let data = try Data(contentsOf: fixtureURL)
```

### Test organization

| Category | Location | What to test |
|---|---|---|
| Unit tests | `Tests/MyLibraryTests/` | Individual functions, types, logic in isolation |
| Integration tests | `Tests/MyLibraryIntegrationTests/` | Multiple components working together, I/O |

Naming convention: test target name = source target name + `Tests` suffix.

## Dependency Management

### Version resolution and Package.resolved

- `Package.resolved` is auto-generated and locks exact dependency versions.
- **Libraries**: do not commit `Package.resolved` — let consumers resolve versions.
- **Executables/apps**: commit `Package.resolved` — ensures reproducible builds.

```bash
swift package resolve          # Resolve and update Package.resolved
swift package update           # Update all dependencies to latest allowed versions
swift package update Logging   # Update a single dependency
swift package show-dependencies --format json  # Inspect dependency graph
```

### Dependency best practices

- Prefer `from:` version requirements — allows patch and minor updates.
- Avoid `branch:` in production code — builds are not reproducible.
- Minimize direct dependencies — each one is a maintenance and security surface.
- Pin major versions to avoid surprise breaking changes.
- Audit transitive dependencies with `swift package show-dependencies`.

### When to vendor vs depend

**Vendor** (copy source into your repo) when:
- The dependency is tiny (single file or small utility).
- The upstream project is unmaintained or unstable.
- You need modifications that diverge from upstream.

**Depend** (use SwiftPM dependency) when:
- The library is actively maintained with semantic versioning.
- You want automatic security and bug-fix updates.
- The dependency graph is already manageable.

### Handling diamond dependency problems

When two dependencies require different versions of the same package, SwiftPM attempts to find a version that satisfies all constraints. If it fails:

1. Check if updating your direct dependencies resolves the conflict.
2. Use `swift package show-dependencies` to visualize the conflict.
3. Open issues with the conflicting packages requesting broader version ranges.
4. As a last resort, consider vendoring one of the conflicting dependencies.

## CI/CD Considerations

### Building on Linux vs macOS

Key differences:
- **Foundation**: On Linux, `FoundationNetworking` must be imported separately for `URLSession`.
- **No Objective-C runtime**: `@objc`, `NSObject` subclassing, and dynamic dispatch are unavailable.
- **`Bundle.module`**: Works the same on both platforms for SwiftPM resources.
- **XCTest on Linux**: Requires explicit test manifests (not needed with Swift 5.4+, `--enable-test-discovery` is default).

### Docker images

```dockerfile
FROM swift:6.0 AS builder
WORKDIR /app
COPY . .
RUN swift build -c release

FROM swift:6.0-slim
COPY --from=builder /app/.build/release/my-cli /usr/local/bin/
ENTRYPOINT ["my-cli"]
```

Available base images:
- `swift:6.0` — full development image (Ubuntu-based)
- `swift:6.0-slim` — minimal runtime image
- `swift:6.0-noble` — Ubuntu 24.04 based
- `swift:6.0-amazonlinux2` — Amazon Linux 2 based

### Build and test commands

```bash
# Build
swift build                          # Debug build
swift build -c release               # Release build
swift build --verbose                # Verbose output

# Test
swift test                           # Run all tests
swift test --parallel                # Run tests in parallel
swift test --filter MyLibraryTests   # Run specific test target
swift test --enable-code-coverage    # Enable coverage collection

# Coverage report
swift test --enable-code-coverage
llvm-cov report \
    .build/debug/MyLibraryPackageTests.xctest \
    -instr-profile .build/debug/codecov/default.profdata
llvm-cov export \
    .build/debug/MyLibraryPackageTests.xctest \
    -instr-profile .build/debug/codecov/default.profdata \
    -format lcov > coverage.lcov
```

### Linting and formatting

**SwiftLint** — rule-based linting:

```bash
# Install
brew install swiftlint        # macOS
# Or use via Docker: ghcr.io/realm/swiftlint

# Run
swiftlint lint --strict
swiftlint lint --reporter json > lint-report.json
```

**swift-format** — official Swift formatter:

```bash
# Install
brew install swift-format     # macOS
# Or build from source on Linux

# Run
swift-format lint --strict --recursive Sources/ Tests/
swift-format format --in-place --recursive Sources/ Tests/
```

Both tools support configuration files (`.swiftlint.yml`, `.swift-format`) at the project root.

## Module Decision Guide

### When to create a new module/target

- The code defines a clear API boundary (set of public types/functions with a cohesive purpose).
- Multiple targets or external consumers will import it.
- You want to enforce access control — hide implementation behind `internal`/`package`.
- The module is a self-contained logical unit, even with a single consumer.
- Build times benefit from parallelism — independent targets compile concurrently.
- The code has a distinct set of dependencies that other targets should not transitively inherit.

### When to keep code in the existing module

- The code is tightly coupled to existing types with no clear seam.
- The project is small and the overhead of managing multiple targets is not justified.
- Boundaries are still evolving — premature splitting leads to churn.
- The new module would contain only one or two files with no meaningful API surface.

### Decision criteria summary

| Criterion | Favors new module | Favors existing module |
|---|---|---|
| API boundary | Well-defined, stable | Fuzzy, evolving |
| Build time | Large target, slow incremental builds | Small target, fast builds |
| Testability | Need to test internals independently | Tests through public API are sufficient |
| Reuse | Used by multiple consumers | Single consumer |
| Dependencies | Distinct dependency set | Shares all dependencies with parent |
| Logical cohesion | Self-contained domain concept | Tightly coupled to existing code |
| Team boundaries | Different teams own different modules | Single team, single module |
