# Code Quality Reference (Android Lint, Static Analysis)

Android platform-specific code quality tooling. Covers Android Lint configuration, built-in check categories, baseline management, suppression strategies, custom lint rules, Compose-specific checks, and CI integration. For project-level Gradle configuration and convention plugins, see `project-structure.md`. For Kotlin-level static analysis tools (Detekt, ktlint), see the `kotlin-development` skill's `references/static-analysis.md`.

## Contents
- Overview — what Android Lint is, how it integrates with AGP
- Configuration — `lint {}` block, severity levels, `lint.xml`, per-module config
- Baseline — generating and managing `lint-baseline.xml`, legacy project strategy
- Suppression — `@SuppressLint`, `tools:ignore`, `lint.xml` ignores, when to suppress vs fix
- Built-in Check Categories — correctness, security, performance, usability, accessibility, internationalization
- Compose Lint Checks — Compose compiler checks, stability warnings, common Compose issues
- Custom Lint Rules — `Detector`, `Issue`, `IssueRegistry`, lint module setup, testing
- CI Integration — running lint, report formats, failing builds on errors
- Multi-module Configuration — shared lint config, convention plugin approach
- Common Issues & Fixes — frequent warnings and resolutions


## Overview

Android Lint is the static analysis tool bundled with AGP (Android Gradle Plugin). It inspects Kotlin/Java source, XML resources, manifest, Gradle files, and ProGuard configs for correctness, performance, security, accessibility, and usability issues.

Lint runs automatically during build and can be invoked explicitly:

```bash
# Run lint on debug variant
./gradlew lintDebug

# Run lint on all variants
./gradlew lint
```

Reports are generated at `build/reports/lint-results-{variant}.html` (and `.xml`, `.sarif`).


## Configuration

### lint {} Block

```kotlin
// build.gradle.kts (app or library module)
android {
    lint {
        // Severity overrides
        error += "ObsoleteSdkInt"
        warning += "MissingTranslation"
        informational += "GradleDependency"
        disable += "UnusedResources" // suppress entirely

        // Treat all warnings as errors (strict mode)
        warningsAsErrors = true

        // Abort build on error
        abortOnError = true

        // Check only specific issue IDs (empty = check all)
        // checkOnly += "NewApi"

        // Generate reports
        htmlReport = true
        xmlReport = true
        sarifReport = true // SARIF for GitHub Code Scanning

        // Report output paths (optional)
        htmlOutput = file("${project.buildDir}/reports/lint/lint-results.html")

        // Check all dependencies, not just this module
        checkDependencies = true
    }
}
```

### Severity Levels

| Level | Meaning | Build effect |
|---|---|---|
| `fatal` | Critical issue | Always fails build |
| `error` | Serious issue | Fails build when `abortOnError = true` |
| `warning` | Potential issue | Shows warning, does not fail |
| `informational` | FYI | Shows in report only |
| `ignore` | Disabled | Skipped entirely |

### lint.xml Per-Module Override

Place `lint.xml` in the module root to override severity per module:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<lint>
    <!-- Disable for entire module -->
    <issue id="ObsoleteSdkInt" severity="ignore" />

    <!-- Downgrade to warning -->
    <issue id="HardcodedText" severity="warning" />

    <!-- Override for specific file paths -->
    <issue id="MagicNumber" severity="ignore">
        <option name="path" value="src/test/**" />
    </issue>
</lint>
```


## Baseline

Baselines capture existing issues so that only new violations fail the build. Essential for adopting lint in legacy projects.

### Generating a Baseline

```kotlin
// build.gradle.kts
android {
    lint {
        baseline = file("lint-baseline.xml")
    }
}
```

```bash
# First run generates the baseline file
./gradlew lintDebug
# lint-baseline.xml is created with all current issues
```

### Baseline Strategy for Legacy Projects

1. **Generate baseline** — captures all existing issues
2. **Commit baseline** — all current issues are suppressed
3. **Enforce on new code** — only new issues fail the build
4. **Periodically shrink** — delete baseline and regenerate to remove fixed issues

```bash
# Regenerate baseline (removes issues that no longer exist)
rm lint-baseline.xml
./gradlew lintDebug
# New baseline captures only remaining issues
```

> **Tip:** Schedule quarterly baseline refresh to track technical debt reduction.

### Baseline in CI

```bash
# CI will fail only on NEW issues not in baseline
./gradlew lintDebug --continue
```


## Suppression

### @SuppressLint (Kotlin/Java)

```kotlin
@SuppressLint("MissingPermission")
fun getLastLocation(): Location? {
    return locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
}

// Suppress multiple
@SuppressLint("ClickableViewAccessibility", "SetTextI18n")
fun setupView() { /* ... */ }

// Suppress all (avoid — too broad)
@SuppressLint("all")
```

### tools:ignore (XML)

```xml
<LinearLayout
    xmlns:tools="http://schemas.android.com/tools"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    tools:ignore="HardcodedText,ContentDescription">

    <TextView
        android:text="Debug only label"
        tools:ignore="HardcodedText" />
</LinearLayout>
```

### When to Suppress vs Fix

| Suppress when | Fix when |
|---|---|
| False positive for your use case | Real issue with clear fix |
| Third-party API constraint | Security or correctness warning |
| Test/debug code only | Production code |
| Intentional deviation (documented) | Unintentional oversight |

Always add a comment explaining why:

```kotlin
// Suppress: permission is checked in CallerActivity before launching this
@SuppressLint("MissingPermission")
fun startTracking() { /* ... */ }
```


## Built-in Check Categories

### Correctness

| Issue ID | Description |
|---|---|
| `NewApi` | Using API not available on `minSdk` |
| `ObsoleteSdkInt` | SDK version check that is always true |
| `MissingPermission` | Missing runtime permission |
| `WrongThread` | Calling UI method from background thread |
| `InvalidPackage` | Using JDK class not available on Android |
| `Recycle` | Not recycling `TypedArray`, `Cursor`, etc. |
| `PrivateApi` | Using non-SDK (hidden) API |

### Security

| Issue ID | Description |
|---|---|
| `ExportedContentProvider` | Content provider exported without permission |
| `HardcodedDebugMode` | `android:debuggable="true"` in manifest |
| `AllowBackup` | `android:allowBackup="true"` — data may leak |
| `SetJavaScriptEnabled` | WebView with JS enabled (XSS risk) |
| `TrustAllX509TrustManager` | Insecure trust manager |
| `UnprotectedSMSBroadcastReceiver` | SMS receiver without permission |

### Performance

| Issue ID | Description |
|---|---|
| `Wakelock` | Holding wakelock without releasing |
| `ViewHolder` | Not using ViewHolder pattern (ListView) |
| `DrawAllocation` | Allocating objects in `onDraw()` |
| `StaticFieldLeak` | Static field holds Context reference |
| `ObsoleteLayoutParam` | Layout param not used by parent |

### Usability & Accessibility

| Issue ID | Description |
|---|---|
| `HardcodedText` | Raw string instead of string resource |
| `ContentDescription` | Missing content description for accessibility |
| `LabelFor` | Form field without associated label |
| `TouchTargetSizeCheck` | Clickable element smaller than 48dp |
| `TextContrastCheck` | Insufficient contrast ratio |

### Internationalization

| Issue ID | Description |
|---|---|
| `MissingTranslation` | String resource missing in some locales |
| `ExtraTranslation` | Translation for non-existent string |
| `Typos` | Common typos in strings |
| `SetTextI18n` | Using string concatenation instead of format |


## Compose Lint Checks

### Built-in Compose Checks (AGP)

AGP includes Compose-specific lint checks when Compose is enabled:

| Issue ID | Description |
|---|---|
| `ComposableNaming` | Composable function should be PascalCase |
| `ComposableModifierFactory` | Modifier factory should be on `Modifier` |
| `RememberReturnType` | `remember` returning Unit (likely missing block body) |
| `FrequentlyChangedStateReadInComposition` | Reading frequently-changed state directly (use `derivedStateOf`) |
| `UnrememberedMutableState` | `mutableStateOf()` without `remember` in Composable |
| `UnrememberedGetBackStackEntry` | `getBackStackEntry()` without `remember` |
| `MutableCollectionMutableState` | Mutable collection inside `mutableStateOf` (won't trigger recomposition) |

### Compose Compiler Reports (Stability)

Not lint per se, but essential for identifying recomposition issues:

```kotlin
// build.gradle.kts
android {
    composeCompiler {
        reportsDestination = layout.buildDirectory.dir("compose_compiler")
        metricsDestination = layout.buildDirectory.dir("compose_compiler")
    }
}
```

```bash
./gradlew assembleRelease
# Check build/compose_compiler/{module}-classes.txt for stability info
```

Stability classes:
- **Stable** — safe to skip recomposition when equal
- **Unstable** — always recomposed (List, MutableState of non-stable type)
- **Runtime** — checked at runtime

```kotlin
// Mark class as stable if you know it's immutable
@Immutable
data class ChartData(val points: List<Point>) // List is unstable by default

// Or use @Stable for types with observable mutable state
@Stable
class ThemeState(initialDark: Boolean) {
    var isDark by mutableStateOf(initialDark)
}
```


## Custom Lint Rules

### Module Setup

```kotlin
// lint-checks/build.gradle.kts
plugins {
    kotlin("jvm")
}

dependencies {
    compileOnly("com.android.tools.lint:lint-api:<latest>")
    compileOnly("com.android.tools.lint:lint-checks:<latest>")
    testImplementation("com.android.tools.lint:lint-tests:<latest>")
    testImplementation("com.android.tools.lint:lint:<latest>")
}

// Register as lint plugin
tasks.jar {
    manifest {
        attributes("Lint-Registry-v2" to "com.example.lint.CustomIssueRegistry")
    }
}
```

```kotlin
// App module consumes lint checks
// build.gradle.kts (app)
dependencies {
    lintChecks(project(":lint-checks"))
}
```

### Defining an Issue

```kotlin
val ISSUE_HARDCODED_COROUTINE_DISPATCHER = Issue.create(
    id = "HardcodedCoroutineDispatcher",
    briefDescription = "Hardcoded coroutine dispatcher",
    explanation = """
        Inject dispatchers via constructor instead of using `Dispatchers.IO` directly.
        This makes the code testable — use `StandardTestDispatcher` in tests.
    """.trimIndent(),
    category = Category.CORRECTNESS,
    priority = 6,
    severity = Severity.WARNING,
    implementation = Implementation(
        HardcodedDispatcherDetector::class.java,
        Scope.JAVA_FILE_SCOPE,
    ),
)
```

### Writing a Detector

```kotlin
class HardcodedDispatcherDetector : Detector(), SourceCodeScanner {

    override fun getApplicableReferenceNames(): List<String> =
        listOf("IO", "Default", "Main")

    override fun visitReference(
        context: JavaContext,
        reference: UReferenceExpression,
        referenced: PsiElement,
    ) {
        val qualifiedName = (referenced as? PsiField)
            ?.containingClass?.qualifiedName ?: return

        if (qualifiedName == "kotlinx.coroutines.Dispatchers") {
            context.report(
                issue = ISSUE_HARDCODED_COROUTINE_DISPATCHER,
                scope = reference,
                location = context.getLocation(reference),
                message = "Inject `CoroutineDispatcher` instead of using `Dispatchers.${reference.resolvedName}` directly.",
            )
        }
    }
}
```

### Issue Registry

```kotlin
class CustomIssueRegistry : IssueRegistry() {

    override val issues: List<Issue> = listOf(
        ISSUE_HARDCODED_COROUTINE_DISPATCHER,
    )

    override val api: Int = CURRENT_API
    override val vendor: Vendor = Vendor(
        vendorName = "My Team",
        identifier = "com.example.lint",
    )
}
```

### Testing Custom Rules

```kotlin
class HardcodedDispatcherDetectorTest {

    @Test
    fun `detects direct Dispatchers_IO usage`() {
        lint()
            .files(
                kotlin(
                    """
                    import kotlinx.coroutines.Dispatchers
                    import kotlinx.coroutines.withContext

                    suspend fun loadData() {
                        withContext(Dispatchers.IO) { // should warn
                            // network call
                        }
                    }
                    """.trimIndent()
                ).indented(),
            )
            .issues(ISSUE_HARDCODED_COROUTINE_DISPATCHER)
            .run()
            .expect(
                """
                src/test.kt:5: Warning: Inject CoroutineDispatcher instead of using Dispatchers.IO directly. [HardcodedCoroutineDispatcher]
                    withContext(Dispatchers.IO) { // should warn
                                            ~~
                0 errors, 1 warnings
                """.trimIndent()
            )
    }

    @Test
    fun `clean code passes without warnings`() {
        lint()
            .files(
                kotlin(
                    """
                    import kotlinx.coroutines.CoroutineDispatcher
                    import kotlinx.coroutines.withContext

                    class Repository(private val ioDispatcher: CoroutineDispatcher) {
                        suspend fun loadData() {
                            withContext(ioDispatcher) { }
                        }
                    }
                    """.trimIndent()
                ).indented(),
            )
            .issues(ISSUE_HARDCODED_COROUTINE_DISPATCHER)
            .run()
            .expectClean()
    }
}
```


## CI Integration

### Running Lint in CI

```bash
# Run lint, generate all report formats
./gradlew lintDebug --continue

# Reports at:
# build/reports/lint-results-debug.html  (human-readable)
# build/reports/lint-results-debug.xml   (machine-readable)
# build/reports/lint-results-debug.sarif (GitHub Code Scanning)
```

### GitHub Actions Example

```yaml
- name: Run Android Lint
  run: ./gradlew lintDebug --continue

- name: Upload Lint SARIF
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: app/build/reports/lint-results-debug.sarif

- name: Upload Lint HTML Report
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: lint-report
    path: "**/build/reports/lint-results-*.html"
```

### Fail on New Issues Only

Combine baseline with `abortOnError`:

```kotlin
android {
    lint {
        baseline = file("lint-baseline.xml")
        abortOnError = true
        warningsAsErrors = true
    }
}
```


## Multi-module Configuration

### Convention Plugin Approach

Centralize lint configuration in a convention plugin. See `project-structure.md` for the build-logic module pattern.

```kotlin
// build-logic/convention/src/main/kotlin/AndroidLintConventionPlugin.kt
class AndroidLintConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.withPlugin("com.android.application") { configureLint() }
            pluginManager.withPlugin("com.android.library") { configureLint() }
        }
    }

    private fun Project.configureLint() {
        extensions.configure<CommonExtension<*, *, *, *, *, *>> {
            lint {
                abortOnError = true
                warningsAsErrors = true
                checkDependencies = false // each module checks itself
                htmlReport = true
                sarifReport = true
                baseline = file("lint-baseline.xml")

                // Team-wide severity overrides
                error += listOf("ObsoleteSdkInt", "NewApi")
                warning += listOf("MissingTranslation")
                disable += listOf("UnusedResources", "GradleDependency")
            }
        }
    }
}
```

```kotlin
// build-logic/convention/build.gradle.kts
gradlePlugin {
    plugins {
        register("androidLint") {
            id = "myapp.android.lint"
            implementationClass = "AndroidLintConventionPlugin"
        }
    }
}
```

```kotlin
// feature/build.gradle.kts
plugins {
    id("myapp.android.lint")
}
```

### Shared lint.xml

Place a `lint.xml` at the project root for defaults. Module-level `lint.xml` files merge with (and override) the root config.


## Common Issues & Fixes

### NewApi

```kotlin
// Problem: using API not available on minSdk
fun setStatusBarColor(color: Int) {
    window.statusBarColor = color // requires API 21
}

// Fix: version check
fun setStatusBarColor(color: Int) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
        window.statusBarColor = color
    }
}

// Better: use AndroidX compat
WindowCompat.setDecorFitsSystemWindows(window, false)
```

### HardcodedText

```xml
<!-- Problem -->
<TextView android:text="Submit" />

<!-- Fix: use string resource -->
<TextView android:text="@string/action_submit" />
```

### ContentDescription

```kotlin
// Problem: image without description
Image(painter = painterResource(R.drawable.logo), contentDescription = null)

// Fix: provide description (or null if purely decorative)
Image(
    painter = painterResource(R.drawable.logo),
    contentDescription = stringResource(R.string.app_logo_description),
)
```

### StaticFieldLeak

```kotlin
// Problem: static reference to Activity
companion object {
    var currentActivity: Activity? = null // leaks Activity
}

// Fix: use WeakReference or application-scoped dependency
companion object {
    var currentActivity: WeakReference<Activity>? = null
}

// Better: use dependency injection or Application context where appropriate
```

### MissingPermission

```kotlin
// Problem: calling permission-protected API without check
fun getLocation() {
    locationManager.getLastKnownLocation(GPS_PROVIDER)
}

// Fix: check or assert permission
fun getLocation() {
    if (ContextCompat.checkSelfPermission(context, ACCESS_FINE_LOCATION) ==
        PackageManager.PERMISSION_GRANTED
    ) {
        locationManager.getLastKnownLocation(GPS_PROVIDER)
    }
}
```
