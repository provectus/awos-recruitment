# Android Project Structure Reference

Covers Android-specific project organization, Gradle configuration, build variants, and CI/CD. For generic Kotlin/Gradle project structure (single-module layout, version catalog basics, compiler options, testing setup), see the `kotlin-development` skill's `references/project-structure.md`.

Targets latest stable **AGP** and **Kotlin 2.x**.

## Multi-Module Architecture

### Module types

| Module | Purpose | Example |
|---|---|---|
| `:app` | Application shell — `MainActivity`, navigation graph, DI wiring | `app/` |
| `:feature:<name>` | Single feature — screen(s), ViewModel, UI state | `:feature:auth`, `:feature:home` |
| `:core:ui` | Shared composables, theme, design system | `:core:ui` |
| `:core:network` | HTTP client, API definitions, interceptors | `:core:network` |
| `:core:data` | Repositories, data sources, caching | `:core:data` |
| `:core:database` | Room database, DAOs, migrations | `:core:database` |
| `:core:domain` | Use cases, domain models (pure Kotlin, no Android deps) | `:core:domain` |
| `:core:common` | Shared utilities, extensions (use sparingly) | `:core:common` |
| `:core:testing` | Shared test utilities, fakes, test rules | `:core:testing` |

### Typical directory layout

```
my-app/
├── app/
│   ├── build.gradle.kts
│   └── src/main/kotlin/com/example/app/
│       ├── MainActivity.kt
│       ├── MainApplication.kt
│       └── navigation/AppNavGraph.kt
├── feature/
│   ├── auth/
│   │   ├── build.gradle.kts
│   │   └── src/main/kotlin/com/example/feature/auth/
│   │       ├── AuthScreen.kt
│   │       ├── AuthViewModel.kt
│   │       └── AuthUiState.kt
│   └── home/
│       └── ...
├── core/
│   ├── ui/
│   ├── network/
│   ├── data/
│   ├── database/
│   ├── domain/
│   └── common/
├── build-logic/
│   └── convention/
│       ├── build.gradle.kts
│       └── src/main/kotlin/
├── gradle/
│   └── libs.versions.toml
├── build.gradle.kts
├── settings.gradle.kts
└── gradle.properties
```

### Dependency graph rules

```
app --> feature:* --> core:domain
                  --> core:ui
                  --> core:data --> core:network
                               --> core:database
                  --> core:common
```

- **`:app`** depends on all `:feature:*` modules.
- **`:feature:*`** modules depend on `:core:*` but never on each other.
- **`:core:domain`** is pure Kotlin — no Android framework dependencies.
- **`:core:data`** depends on `:core:network` and `:core:database`, exposes repository interfaces.
- Keep the graph **acyclic**. If two features need to communicate, use navigation arguments or a shared `:core:` module.

### API/impl split

For larger projects, split core modules into API and implementation:

```
core/
├── network-api/       # Interfaces, models — lightweight
│   └── build.gradle.kts   (kotlin("jvm") or Android library)
├── network-impl/      # Retrofit/Ktor implementation
│   └── build.gradle.kts   (depends on :core:network-api)
```

Feature modules depend on `-api` modules only. The `:app` module wires `-impl` via DI. This reduces rebuild scope and enforces clear contracts.

### When to create a new module

| Signal | Action |
|---|---|
| Component is a self-contained logical unit (player, auth, networking, analytics) | Extract to its own module — even with a single consumer. Benefits: incremental compilation (unchanged module is not recompiled), enforced access boundaries (`internal` scoped to module), isolated testability, ready for reuse without refactoring. |
| Code is used by 2+ feature modules | Extract to `:core:<name>` |
| Feature has its own team or release cycle | Own `:feature:<name>` module |
| Build time is growing — large module causes frequent recompilation | Split into smaller modules with narrower dependencies |
| You need different `minSdk` or dependencies for a subset of code | Separate module with its own `build.gradle.kts` |

### When NOT to create a module

- **Tiny scope** — a single utility function or extension doesn't justify a module. Put it in `:core:common`.
- **No clear boundary** — if you can't define a clean public API for the module, it's not ready to be extracted.
- **Over-splitting** — each module adds Gradle configuration overhead and sync time. A well-organized project with 10-15 modules is better than 50+ micro-modules with 2 files each.

```kotlin
// feature/auth/build.gradle.kts
dependencies {
    implementation(project(":core:network-api"))
    // NOT :core:network-impl
}

// app/build.gradle.kts
dependencies {
    implementation(project(":core:network-impl"))
}
```


## Gradle Setup

### `build.gradle.kts` android block

```kotlin
// app/build.gradle.kts
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt.android)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.example.myapp"
    compileSdk = <latest-stable-api>  // use latest stable Android API level

    defaultConfig {
        applicationId = "com.example.myapp"
        minSdk = 26
        targetSdk = <latest-stable-api>  // must match Play Store requirements
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }

    kotlinOptions {
        jvmTarget = "21"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}
```

### Library module

```kotlin
// core/network/build.gradle.kts
plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.example.core.network"
    compileSdk = <latest-stable-api>

    defaultConfig {
        minSdk = 26
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
}
```

### SDK version guidelines

| Property | Recommendation | Notes |
|---|---|---|
| `compileSdk` | Latest stable API level | Access newest APIs at compile time |
| `targetSdk` | Latest stable API level | Required by Play Store annually; opt into latest platform behavior |
| `minSdk` | 90%+ device coverage (currently 26+) | Adapt to project requirements; if the project already defines a minSdk, confirm before changing |
| `jvmTarget` | `"21"` (recommended), `"17"` (minimum) | JDK 21 LTS preferred for new projects; JDK 17 is the AGP minimum |

### Compose compiler (Kotlin 2.x)

Starting with Kotlin 2.0, the Compose compiler is a Kotlin compiler plugin — no separate version tracking needed:

```kotlin
// build.gradle.kts
plugins {
    alias(libs.plugins.kotlin.compose) // org.jetbrains.kotlin.plugin.compose
}

// Optional: configure compiler reports for recomposition debugging
composeCompiler {
    reportsDestination = layout.buildDirectory.dir("compose_reports")
    metricsDestination = layout.buildDirectory.dir("compose_metrics")
    stabilityConfigurationFile = rootProject.layout.projectDirectory.file("stability_config.conf")
}
```

### `settings.gradle.kts`

```kotlin
pluginManagement {
    includeBuild("build-logic")
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "MyApp"

include(":app")
include(":feature:auth")
include(":feature:home")
include(":core:ui")
include(":core:network")
include(":core:data")
include(":core:database")
include(":core:domain")
include(":core:common")
```

### `gradle.properties`

```properties
# Performance
org.gradle.jvmargs=-Xmx4g -XX:+UseParallelGC
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true

# Android
android.useAndroidX=true
android.nonTransitiveRClass=true
```


## Version Catalog

### `gradle/libs.versions.toml`

```toml
[versions]
agp = "<latest>"
kotlin = "<latest>"
ksp = "<latest>"

# AndroidX
core-ktx = "<latest>"
lifecycle = "<latest>"
activity-compose = "<latest>"
navigation-compose = "<latest>"
compose-bom = "<latest>"
room = "<latest>"
hilt = "<latest>"
hilt-navigation-compose = "<latest>"
datastore = "<latest>"

# Networking
retrofit = "<latest>"
okhttp = "<latest>"
ktor = "<latest>"
serialization = "<latest>"

# Image loading
coil = "<latest>"

# Testing
junit = "<latest>"
junit5 = "<latest>"
truth = "<latest>"
mockk = "<latest>"
turbine = "<latest>"
coroutines = "<latest>"
espresso = "<latest>"
test-runner = "<latest>"

[libraries]
# AndroidX Core
androidx-core-ktx = { module = "androidx.core:core-ktx", version.ref = "core-ktx" }
androidx-lifecycle-runtime-compose = { module = "androidx.lifecycle:lifecycle-runtime-compose", version.ref = "lifecycle" }
androidx-lifecycle-viewmodel-compose = { module = "androidx.lifecycle:lifecycle-viewmodel-compose", version.ref = "lifecycle" }
androidx-activity-compose = { module = "androidx.activity:activity-compose", version.ref = "activity-compose" }
androidx-navigation-compose = { module = "androidx.navigation:navigation-compose", version.ref = "navigation-compose" }

# Compose (BOM-managed)
compose-bom = { module = "androidx.compose:compose-bom", version.ref = "compose-bom" }
compose-ui = { module = "androidx.compose.ui:ui" }
compose-ui-graphics = { module = "androidx.compose.ui:ui-graphics" }
compose-ui-tooling = { module = "androidx.compose.ui:ui-tooling" }
compose-ui-tooling-preview = { module = "androidx.compose.ui:ui-tooling-preview" }
compose-material3 = { module = "androidx.compose.material3:material3" }
compose-ui-test-manifest = { module = "androidx.compose.ui:ui-test-manifest" }
compose-ui-test-junit4 = { module = "androidx.compose.ui:ui-test-junit4" }

# Room
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }
room-ktx = { module = "androidx.room:room-ktx", version.ref = "room" }

# Hilt
hilt-android = { module = "com.google.dagger:hilt-android", version.ref = "hilt" }
hilt-compiler = { module = "com.google.dagger:hilt-compiler", version.ref = "hilt" }
hilt-navigation-compose = { module = "androidx.hilt:hilt-navigation-compose", version.ref = "hilt-navigation-compose" }

# Networking
retrofit = { module = "com.squareup.retrofit2:retrofit", version.ref = "retrofit" }
retrofit-serialization = { module = "com.squareup.retrofit2:converter-kotlinx-serialization", version.ref = "retrofit" }
okhttp-logging = { module = "com.squareup.okhttp3:logging-interceptor", version.ref = "okhttp" }
ktor-client-core = { module = "io.ktor:ktor-client-core", version.ref = "ktor" }
ktor-client-okhttp = { module = "io.ktor:ktor-client-okhttp", version.ref = "ktor" }
ktor-client-content-negotiation = { module = "io.ktor:ktor-client-content-negotiation", version.ref = "ktor" }
ktor-serialization-json = { module = "io.ktor:ktor-serialization-kotlinx-json", version.ref = "ktor" }
serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "serialization" }

# Image loading
coil-compose = { module = "io.coil-kt.coil3:coil-compose", version.ref = "coil" }
coil-network-okhttp = { module = "io.coil-kt.coil3:coil-network-okhttp", version.ref = "coil" }

# DataStore
datastore-preferences = { module = "androidx.datastore:datastore-preferences", version.ref = "datastore" }

# Testing
junit = { module = "junit:junit", version.ref = "junit" }
junit5 = { module = "org.junit.jupiter:junit-jupiter", version.ref = "junit5" }
truth = { module = "com.google.truth:truth", version.ref = "truth" }
mockk = { module = "io.mockk:mockk", version.ref = "mockk" }
turbine = { module = "app.cash.turbine:turbine", version.ref = "turbine" }
coroutines-test = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-test", version.ref = "coroutines" }
espresso-core = { module = "androidx.test.espresso:espresso-core", version.ref = "espresso" }
test-runner = { module = "androidx.test:runner", version.ref = "test-runner" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
android-library = { id = "com.android.library", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
hilt-android = { id = "com.google.dagger.hilt.android", version.ref = "hilt" }
room = { id = "androidx.room", version.ref = "room" }
```

### BOM management

The Compose BOM controls versions for all `androidx.compose` artifacts. Declare it once, omit versions on individual Compose libraries:

```kotlin
dependencies {
    val composeBom = platform(libs.compose.bom)
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)
}
```

Prefer BOM-managed versions for consistency. Individual library versions can be overridden when needed, but be aware that alpha/beta overrides may pull in alpha transitive dependencies.


## Convention Plugins

Convention plugins centralize shared Gradle configuration. Place them in a `build-logic` included build.

### Structure

```
build-logic/
└── convention/
    ├── build.gradle.kts
    └── src/main/kotlin/
        ├── AndroidApplicationConventionPlugin.kt
        ├── AndroidLibraryConventionPlugin.kt
        ├── AndroidComposeConventionPlugin.kt
        └── AndroidHiltConventionPlugin.kt
```

### `build-logic/convention/build.gradle.kts`

```kotlin
plugins {
    `kotlin-dsl`
}

dependencies {
    compileOnly(libs.android.gradlePlugin)
    compileOnly(libs.kotlin.gradlePlugin)
    compileOnly(libs.compose.gradlePlugin)
    compileOnly(libs.ksp.gradlePlugin)
}
```

Add to `libs.versions.toml`:

```toml
[libraries]
android-gradlePlugin = { module = "com.android.tools.build:gradle", version.ref = "agp" }
kotlin-gradlePlugin = { module = "org.jetbrains.kotlin:kotlin-gradle-plugin", version.ref = "kotlin" }
compose-gradlePlugin = { module = "org.jetbrains.kotlin:compose-compiler-gradle-plugin", version.ref = "kotlin" }
ksp-gradlePlugin = { module = "com.google.devtools.ksp:com.google.devtools.ksp.gradle.plugin", version.ref = "ksp" }
```

### Example: Android library convention plugin

```kotlin
// AndroidLibraryConventionPlugin.kt
import com.android.build.gradle.LibraryExtension
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure

class AndroidLibraryConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("com.android.library")
            pluginManager.apply("org.jetbrains.kotlin.android")

            extensions.configure<LibraryExtension> {
                compileSdk = <latest-stable-api>

                defaultConfig {
                    minSdk = 26
                    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
                }

                compileOptions {
                    sourceCompatibility = JavaVersion.VERSION_21
                    targetCompatibility = JavaVersion.VERSION_21
                }
            }
        }
    }
}
```

Register in `build-logic/convention/build.gradle.kts`:

```kotlin
gradlePlugin {
    plugins {
        register("androidLibrary") {
            id = "myapp.android.library"
            implementationClass = "AndroidLibraryConventionPlugin"
        }
        register("androidApplication") {
            id = "myapp.android.application"
            implementationClass = "AndroidApplicationConventionPlugin"
        }
        register("androidCompose") {
            id = "myapp.android.compose"
            implementationClass = "AndroidComposeConventionPlugin"
        }
        register("androidHilt") {
            id = "myapp.android.hilt"
            implementationClass = "AndroidHiltConventionPlugin"
        }
    }
}
```

### Usage in feature modules

```kotlin
// feature/auth/build.gradle.kts
plugins {
    id("myapp.android.library")
    id("myapp.android.compose")
    id("myapp.android.hilt")
}

android {
    namespace = "com.example.feature.auth"
}

dependencies {
    implementation(project(":core:domain"))
    implementation(project(":core:ui"))
}
```

This replaces 30+ lines of boilerplate per module with 3 plugin applications.


## Build Variants

### Build types

```kotlin
android {
    buildTypes {
        debug {
            isDebuggable = true
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
        create("staging") {
            initWith(getByName("release"))
            applicationIdSuffix = ".staging"
            versionNameSuffix = "-staging"
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}
```

### Product flavors

```kotlin
android {
    flavorDimensions += listOf("environment", "store")

    productFlavors {
        create("dev") {
            dimension = "environment"
            buildConfigField("String", "API_BASE_URL", "\"https://api-dev.example.com\"")
        }
        create("prod") {
            dimension = "environment"
            buildConfigField("String", "API_BASE_URL", "\"https://api.example.com\"")
        }
        create("googlePlay") {
            dimension = "store"
        }
        create("huawei") {
            dimension = "store"
        }
    }
}
```

Resulting variants: `devGooglePlayDebug`, `devGooglePlayRelease`, `prodHuaweiRelease`, etc.

### Flavor-specific source sets

```
app/src/
├── main/           # Shared code
├── debug/          # Debug-only code/resources
├── release/        # Release-only code/resources
├── dev/            # Dev flavor code
├── prod/           # Prod flavor code
├── googlePlay/     # Google Play flavor code
└── huawei/         # Huawei flavor code
```

### Build config fields and res values

```kotlin
defaultConfig {
    buildConfigField("Boolean", "ENABLE_LOGGING", "false")
    resValue("string", "app_name", "My App")
}

buildTypes {
    debug {
        buildConfigField("Boolean", "ENABLE_LOGGING", "true")
        resValue("string", "app_name", "My App (Debug)")
    }
}
```


## Signing Configurations

### Debug signing

Debug builds use a default keystore automatically. For team-consistent debug signing:

```kotlin
android {
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }
}
```

### Release signing

Never hardcode release credentials. Load from environment variables or a local properties file:

```kotlin
android {
    signingConfigs {
        create("release") {
            val keystorePropertiesFile = rootProject.file("keystore.properties")
            if (keystorePropertiesFile.exists()) {
                val props = java.util.Properties().apply {
                    load(keystorePropertiesFile.inputStream())
                }
                storeFile = file(props["storeFile"] as String)
                storePassword = props["storePassword"] as String
                keyAlias = props["keyAlias"] as String
                keyPassword = props["keyPassword"] as String
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

`keystore.properties` (git-ignored):

```properties
storeFile=release.keystore
storePassword=your_store_password_here
keyAlias=your_key_alias_here
keyPassword=your_key_password_here
```

For CI, use environment variables:

```kotlin
create("release") {
    storeFile = file(System.getenv("KEYSTORE_PATH") ?: "release.keystore")
    storePassword = System.getenv("KEYSTORE_PASSWORD") ?: ""
    keyAlias = System.getenv("KEY_ALIAS") ?: ""
    keyPassword = System.getenv("KEY_PASSWORD") ?: ""
}
```


## ProGuard / R8

AGP 8.x uses R8 by default (drop-in replacement for ProGuard with the same rule format).

### `proguard-rules.pro` (app module)

```proguard
# --- Obfuscation ---
-flattenpackagehierarchy
-renamesourcefileattribute SourceFile

# --- Attributes to preserve ---
-keepattributes LineNumberTable, SourceFile, Signature, *Annotation*, InnerClasses, EnclosingMethod

# --- Crashlytics: readable stack traces for exceptions ---
-keep public class * extends java.lang.Exception

# --- Enums: prevent removal of values()/valueOf() ---
-keepclassmembers enum * { *; }

# --- Strip Kotlin intrinsics (parameter names, null-check messages) from release ---
-assumenosideeffects class kotlin.jvm.internal.Intrinsics {
    public static void checkNotNullParameter(...);
    public static void checkNotNullExpressionValue(...);
    public static void checkReturnedValueIsNotNull(...);
    public static void checkFieldIsNotNull(...);
    public static void checkParameterIsNotNull(...);
    public static void throwUninitializedPropertyAccessException(...);
}

# --- Reflection: keep classes accessed via reflection (add as needed) ---
# -keep class com.example.myapp.SomeReflectedClass { *; }

# --- Kotlin serialization ---
-dontnote kotlinx.serialization.**
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class com.example.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# --- Retrofit ---
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

# --- Room ---
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *

# --- Hilt ---
-keep class dagger.hilt.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper { *; }

# --- Compose — R8 full mode compatibility ---
-dontwarn androidx.compose.**
```

> **Tip:** If shrinking causes issues during investigation, use `-dontshrink` temporarily to isolate whether the problem is shrinking vs obfuscation. Do not ship with `-dontshrink`.

### Consumer ProGuard rules (library modules)

Library modules ship rules to consumers via `consumerProguardFiles`:

```kotlin
// core/network/build.gradle.kts
android {
    defaultConfig {
        consumerProguardFiles("consumer-rules.pro")
    }
}
```

```proguard
# consumer-rules.pro — applied automatically to any app depending on this library
-keep class com.example.core.network.model.** { *; }
```

### R8 full mode

AGP 8.x enables R8 full mode by default. Key differences from compatibility mode:
- More aggressive optimizations and tree shaking.
- Default rules are stricter — classes are removed unless explicitly kept.
- Add `-keep` rules for anything accessed via reflection.

### Debugging R8 issues

```bash
# Generate mapping file for crash deobfuscation
./gradlew assembleRelease
# Output: app/build/outputs/mapping/release/mapping.txt

# Check which rules apply
./gradlew :app:printConfigurationRelease
```

Upload `mapping.txt` to Play Console and Firebase Crashlytics for readable stack traces.


## Common Gradle Commands

```bash
# Build
./gradlew assembleDebug            # Debug APK
./gradlew assembleRelease          # Release APK
./gradlew bundleRelease            # Release AAB (Play Store)

# Test & lint
./gradlew testDebugUnitTest        # Unit tests
./gradlew connectedDebugAndroidTest # Instrumented tests
./gradlew lintDebug                # Lint check
./gradlew check                    # Full check (lint + tests)

# Utilities
./gradlew clean assembleRelease    # Clean build
./gradlew tasks --group=build      # List build tasks
./gradlew :app:dependencies --configuration releaseRuntimeClasspath  # Dependency tree
```

| Format | Use case |
|---|---|
| APK (`.apk`) | Direct install, testing, sideloading, Firebase App Distribution |
| AAB (`.aab`) | Play Store upload (required since 2021), Google generates optimized APKs per device |


## Asset and Resource Management

### Resource directory structure

```
app/src/main/res/
├── drawable/              # Vector drawables, XML shapes
├── drawable-night/        # Dark mode overrides
├── mipmap-mdpi/           # Launcher icons (48x48)
├── mipmap-hdpi/           # Launcher icons (72x72)
├── mipmap-xhdpi/          # Launcher icons (96x96)
├── mipmap-xxhdpi/         # Launcher icons (144x144)
├── mipmap-xxxhdpi/        # Launcher icons (192x192)
├── values/
│   ├── strings.xml
│   ├── colors.xml
│   ├── dimens.xml
│   ├── themes.xml
│   └── arrays.xml
├── values-night/          # Dark theme colors/styles
├── values-es/             # Spanish translations
├── values-sw600dp/        # Tablet dimensions
├── values-land/           # Landscape overrides
├── font/                  # Custom fonts (.ttf, .otf)
├── raw/                   # Raw files (audio, JSON)
├── xml/                   # XML configs (network security, backup rules)
└── anim/                  # View animations (XML)
```

### Common resource qualifiers

| Qualifier | Example | Purpose |
|---|---|---|
| `-night` | `values-night/colors.xml` | Dark theme |
| `-<lang>` | `values-es/strings.xml` | Localization |
| `-sw<N>dp` | `values-sw600dp/dimens.xml` | Smallest width (tablets) |
| `-land` | `layout-land/` | Landscape orientation |
| `-v<N>` | `values-v31/themes.xml` | API level gating |
| `-<dpi>` | `drawable-xxhdpi/` | Screen density |

### Vector drawables

Prefer vector drawables over raster images for icons and simple graphics:

```xml
<!-- res/drawable/ic_search.xml -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="@color/icon_tint"
        android:pathData="M15.5,14h-0.79l-0.28,-0.27 ..." />
</vector>
```

In Compose, load with `painterResource(R.drawable.ic_search)`.

### Accessing resources in Compose

```kotlin
// Strings
Text(text = stringResource(R.string.welcome_message, userName))

// Dimensions
val padding = dimensionResource(R.dimen.screen_padding)

// Drawables
Icon(painter = painterResource(R.drawable.ic_search), contentDescription = "Search")

// Colors (prefer MaterialTheme.colorScheme over direct resource colors)
val color = colorResource(R.color.brand_primary)
```


## Dependencies

### Common Android dependency sets

```kotlin
// build.gradle.kts — typical app module dependencies
dependencies {
    // Compose (BOM-managed)
    val composeBom = platform(libs.compose.bom)
    implementation(composeBom)
    androidTestImplementation(composeBom)
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)

    // AndroidX
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)

    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)

    // Networking (Retrofit)
    implementation(libs.retrofit)
    implementation(libs.retrofit.serialization)
    implementation(libs.okhttp.logging)
    implementation(libs.serialization.json)

    // OR Networking (Ktor)
    // implementation(libs.ktor.client.core)
    // implementation(libs.ktor.client.okhttp)
    // implementation(libs.ktor.client.content.negotiation)
    // implementation(libs.ktor.serialization.json)

    // Room
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)

    // Image loading
    implementation(libs.coil.compose)
    implementation(libs.coil.network.okhttp)

    // DataStore
    implementation(libs.datastore.preferences)

    // Testing
    testImplementation(libs.junit)
    testImplementation(libs.truth)
    testImplementation(libs.mockk)
    testImplementation(libs.turbine)
    testImplementation(libs.coroutines.test)
    androidTestImplementation(libs.espresso.core)
    androidTestImplementation(libs.test.runner)
    androidTestImplementation(libs.compose.ui.test.junit4)
    debugImplementation(libs.compose.ui.test.manifest)
}
```

### Choosing between alternatives

| Category | Option A | Option B | Recommendation |
|---|---|---|---|
| HTTP client | Retrofit + OkHttp | Ktor Client | Retrofit for Android-only; Ktor for KMP projects |
| Serialization | kotlinx-serialization | Gson/Moshi | kotlinx-serialization (Kotlin-native, multiplatform) |
| Image loading | Coil 3 | Glide | Coil (Kotlin-first, Compose-native, lighter) |
| DI | Hilt | Koin | Hilt for apps (compile-time safety); Koin for KMP or simplicity |
| Local DB | Room | SQLDelight | Room for Android-only; SQLDelight for KMP |
| Key-value storage | DataStore | SharedPreferences | DataStore (async, type-safe, coroutines) |
| Testing assertions | Truth | kotlin.test assertions | Truth for Android; kotlin.test for multiplatform |
| Mocking | MockK | Mockito-Kotlin | MockK (Kotlin-native, better coroutine support) |
| Flow testing | Turbine | Manual collection | Turbine (concise API for testing Flow emissions) |
