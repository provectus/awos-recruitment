# Code Quality Reference (Xcode Analysis, Sanitizers, Dead Code)

Apple platform-specific quality tools that complement language-level linting. For SwiftLint and SwiftFormat configuration, rules, and CI setup, see the `swift-development` skill's `references/static-analysis.md`. This reference covers Xcode-specific tooling: static analyzer, runtime sanitizers, dead code detection, Danger-Swift, and build settings.

## Contents
- When to use which tool (decision table)
- Xcode Static Analyzer (Analyze, build settings)
- Sanitizers (Address, Thread, Undefined Behavior)
- Periphery — dead code detection
- Danger-Swift for PR automation
- Xcode build settings for quality
- Xcode configuration files (`.xcconfig`)
- Common pitfalls

## When to Use Which

| Tool | Purpose | Runs On |
|---|---|---|
| Xcode Static Analyzer | Memory leaks, null dereferences, logic errors | Xcode Analyze (Cmd+Shift+B) |
| Address Sanitizer | Runtime memory bug detection | Xcode scheme, test plans |
| Thread Sanitizer | Data race detection | Xcode scheme, test plans |
| Undefined Behavior Sanitizer | Integer overflow, misaligned pointers | Xcode scheme, test plans |
| Periphery | Dead code detection | CLI, CI |
| Danger-Swift | Automated PR checks and conventions | CI |

**Rule:** Run Xcode Analyze before releases. Enable sanitizers in dedicated test plan configurations. Run Periphery after major refactors. For linting and formatting (SwiftLint, SwiftFormat), see `swift-development` skill's `references/static-analysis.md`.


## Xcode Static Analyzer

### When to Use
---

The Xcode Static Analyzer performs deep analysis of control flow and memory management. Run it via Product > Analyze (Cmd+Shift+B) or enable it in build settings.

#### What It Catches

- Memory leaks in Objective-C and bridged code
- Null pointer dereferences
- Use-after-free
- Logic errors (dead code branches, unreachable code)
- Division by zero
- API misuse (CoreFoundation reference counting)

#### Build Settings

```
// Enable static analysis during builds (slows build — use selectively)
RUN_CLANG_STATIC_ANALYZER = YES              // Analyze During 'Build'
CLANG_STATIC_ANALYZER_MODE = deep            // shallow (faster) or deep (thorough)
CLANG_STATIC_ANALYZER_MODE_ON_ANALYZE_ACTION = deep
```

## Sanitizers

Sanitizers are runtime tools that detect bugs during test execution. Enable them in your scheme or test plan.

#### Address Sanitizer (ASan)

Detects memory corruption: buffer overflows, use-after-free, stack overflow, heap overflow.

```
// Scheme > Test > Diagnostics > Address Sanitizer
ENABLE_ADDRESS_SANITIZER = YES

// Also enable:
CLANG_ADDRESS_SANITIZER_CONTAINER_OVERFLOW = YES
```

#### Thread Sanitizer (TSan)

Detects data races — concurrent access to shared mutable state without synchronization.

```
// Scheme > Test > Diagnostics > Thread Sanitizer
ENABLE_THREAD_SANITIZER = YES
```

Rules:
- Thread Sanitizer and Address Sanitizer cannot be enabled simultaneously.
- Thread Sanitizer adds ~5-15x slowdown — run in CI on a dedicated test plan.
- Thread Sanitizer is especially valuable when migrating to Swift 6 strict concurrency.

#### Undefined Behavior Sanitizer (UBSan)

Detects undefined behavior: integer overflow, misaligned pointers, null reference.

```
// Scheme > Test > Diagnostics > Undefined Behavior Sanitizer
ENABLE_UNDEFINED_BEHAVIOR_SANITIZER = YES
CLANG_UNDEFINED_BEHAVIOR_SANITIZER_INTEGER = YES
CLANG_UNDEFINED_BEHAVIOR_SANITIZER_NULLABILITY = YES
```

### Enabling Sanitizers in Test Plans
---

```json
{
    "configurations": [
        {
            "name": "Default",
            "options": {
                "addressSanitizer": {
                    "enabled": false
                },
                "threadSanitizer": {
                    "enabled": false
                }
            }
        },
        {
            "name": "Thread Safety",
            "options": {
                "threadSanitizer": {
                    "enabled": true
                }
            }
        },
        {
            "name": "Memory Safety",
            "options": {
                "addressSanitizer": {
                    "enabled": true,
                    "detectStackUseAfterReturn": true
                },
                "undefinedBehaviorSanitizer": {
                    "enabled": true
                }
            }
        }
    ]
}
```

Run separate test plan configurations in CI for sanitizer checks — they incur significant overhead and should not run in the default test suite.


## Periphery — Dead Code Detection

Periphery scans your Xcode project for unused declarations: classes, structs, enums, protocols, functions, properties, and more. It requires an Xcode project or SPM package to perform indexing.

### Installation and Basic Usage
---

```bash
# Install
brew install periphery

# Scan an Xcode project
periphery scan --project MyApp.xcodeproj --schemes MyApp --targets MyApp

# Scan an SPM package
periphery scan --spm
```

### Configuration (`.periphery.yml`)
---

```yaml
# .periphery.yml
project: MyApp.xcodeproj
schemes:
  - MyApp
targets:
  - MyApp
  - MyAppKit

# Retain declarations matching these patterns (avoid false positives)
retain_public: false        # Set true for frameworks/libraries
retain_objc_accessible: true

# Exclude files from scanning
index_exclude:
  - "Sources/Generated/**"
  - "Sources/Resources/**"

# Additional retain patterns
retain_unused_protocol_func_params: false
```

### Handling False Positives
---

Periphery may flag code that is actually used through dynamic dispatch or runtime features:

```swift
// @objc methods called from Objective-C or Interface Builder
// periphery:ignore
@objc func buttonTapped(_ sender: UIButton) {
    // ...
}

// Codable synthesized conformance — properties appear unused
// periphery:ignore
struct APIResponse: Codable {
    let id: String
    let name: String
}

// IBOutlet/IBAction connected in storyboards
// periphery:ignore
@IBOutlet weak var titleLabel: UILabel!

// Protocol conformance required by framework
// periphery:ignore
func application(_ application: UIApplication,
                 didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    return true
}
```

Rules:
- Run Periphery after major refactors to find leftover dead code.
- Use `// periphery:ignore` sparingly — investigate whether the code is truly needed first.
- Set `retain_public: true` for library/framework targets where public API is consumed externally.
- Set `retain_objc_accessible: true` to avoid false positives with `@objc` declarations.


## Danger-Swift for PR Automation

Danger-Swift runs during CI and automates PR review conventions: size warnings, missing tests, lint integration.

### Setup
---

```swift
// Dangerfile.swift
import Danger

let danger = Danger()

// Warn if PR is too large
let bigPRThreshold = 500
if danger.github.pullRequest.additions + danger.github.pullRequest.deletions > bigPRThreshold {
    warn("This PR is quite large. Consider breaking it into smaller PRs.")
}

// Check for SwiftLint violations
SwiftLint.lint(inline: true, configFile: ".swiftlint.yml")

// Ensure tests are updated when source changes
let sourceChanges = danger.git.modifiedFiles.filter { $0.hasPrefix("Sources/") }
let testChanges = danger.git.modifiedFiles.filter { $0.hasPrefix("Tests/") }
if !sourceChanges.isEmpty && testChanges.isEmpty {
    warn("Source files were modified but no tests were updated. Please add or update tests.")
}

// Check for TODO/FIXME in added lines
for file in danger.git.modifiedFiles.filter({ $0.hasSuffix(".swift") }) {
    for line in danger.utils.diff(for: file)?.hunks.flatMap(\.lines) ?? [] where line.type == .addition {
        if line.text.contains("TODO") || line.text.contains("FIXME") {
            message("New TODO/FIXME found in \(file). Consider resolving before merge.")
            break
        }
    }
}
```


## CI/CD Integration

### Periphery in GitHub Actions
---

```yaml
# .github/workflows/code-quality.yml (add to existing workflow)
  periphery:
    name: Dead Code Detection
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Periphery
        run: brew install periphery

      - name: Scan for unused code
        run: |
          periphery scan \
            --project MyApp.xcodeproj \
            --schemes MyApp \
            --targets MyApp \
            --format github-actions
```

### Sanitizer CI Job
---

```yaml
  sanitizers:
    name: Sanitizer Checks
    runs-on: macos-latest
    strategy:
      matrix:
        sanitizer: [thread, address]
    steps:
      - uses: actions/checkout@v4

      - name: Run tests with ${{ matrix.sanitizer }} sanitizer
        run: |
          xcodebuild test \
            -project MyApp.xcodeproj \
            -scheme MyApp \
            -destination 'platform=iOS Simulator,name=iPhone 16' \
            -enableAddressSanitizer ${{ matrix.sanitizer == 'address' && 'YES' || 'NO' }} \
            -enableThreadSanitizer ${{ matrix.sanitizer == 'thread' && 'YES' || 'NO' }}
```

Rules:
- Run sanitizer jobs on a schedule (nightly) or on merge to main — not on every PR push due to overhead.
- Use matrix strategy to run ASan and TSan in parallel (they cannot run simultaneously in one build).


## Xcode Build Settings for Quality

### Strict Concurrency Checking
---

```
// Build Settings > Swift Compiler - Upcoming Features
SWIFT_STRICT_CONCURRENCY = complete       // Full Swift 6 concurrency checking
```

This enables compile-time data race safety. Set to `targeted` for gradual migration, `complete` for full enforcement.

### Treat Warnings as Errors
---

```
// For release builds — prevents shipping code with warnings
SWIFT_TREAT_WARNINGS_AS_ERRORS = YES      // Swift warnings
GCC_TREAT_WARNINGS_AS_ERRORS = YES        // C/ObjC warnings

// Apply only to release configuration in xcconfig:
// Release.xcconfig
SWIFT_TREAT_WARNINGS_AS_ERRORS = YES
GCC_TREAT_WARNINGS_AS_ERRORS = YES
```

Rules:
- Enable treat-warnings-as-errors for Release configurations only.
- In Debug, keep as warnings to avoid blocking development.
- Fix all warnings before merging to main — enforce via CI.

### Other Recommended Build Settings
---

```
// Enable testability for test targets
ENABLE_TESTABILITY = YES                  // On test targets only

// Enable module stability for frameworks
BUILD_LIBRARY_FOR_DISTRIBUTION = YES      // For distributed frameworks only

// Optimization
SWIFT_COMPILATION_MODE = wholemodule      // Release — better optimization
SWIFT_COMPILATION_MODE = incremental       // Debug — faster incremental builds

// Warnings
CLANG_WARN_DOCUMENTATION_COMMENTS = YES
CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES
CLANG_WARN_SUSPICIOUS_MOVE = YES
CLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE
```

### Xcode Configuration Files (`.xcconfig`)
---

```
// Shared.xcconfig — common settings across all configurations
SWIFT_VERSION = 6.0
IPHONEOS_DEPLOYMENT_TARGET = 17.0
SWIFT_STRICT_CONCURRENCY = complete

// Debug.xcconfig
#include "Shared.xcconfig"
SWIFT_COMPILATION_MODE = incremental
SWIFT_TREAT_WARNINGS_AS_ERRORS = NO
ENABLE_TESTABILITY = YES

// Release.xcconfig
#include "Shared.xcconfig"
SWIFT_COMPILATION_MODE = wholemodule
SWIFT_TREAT_WARNINGS_AS_ERRORS = YES
GCC_TREAT_WARNINGS_AS_ERRORS = YES
SWIFT_OPTIMIZATION_LEVEL = -O
```


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Ignoring Periphery false positives without investigation | Always verify whether flagged code is truly unused before adding `// periphery:ignore` |
| Enabling all sanitizers simultaneously | Address Sanitizer and Thread Sanitizer cannot coexist. Use separate test plan configurations |
| Running sanitizers in every CI build | Sanitizers add 5-15x overhead. Run in a scheduled nightly job or a separate CI stage |
| Treat-warnings-as-errors in Debug | Blocks development. Enable only for Release builds |
| Skipping static analysis entirely | Run Xcode Analyze at least before releases. Catches memory bugs that compiler warnings miss |

## Related References

- **`swift-development` skill's `references/static-analysis.md`** — SwiftLint, SwiftFormat configuration, rules, combined setup, pre-commit hooks, CI integration.
- **`references/testing.md`** — Test plans, test configurations, and CI/CD test commands. Sanitizers configured here are enabled in test plans described there.
- **`references/project-structure.md`** — Build configurations, schemes, and xcconfig setup referenced in the build settings section above.
