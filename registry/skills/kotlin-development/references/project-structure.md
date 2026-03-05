# Kotlin Project Structure Reference

## Contents
- `build.gradle.kts` essentials (minimal setup, version catalog)
- Directory layout (single-module, conventions)
- Multi-module project organization (settings, shared config, module dependencies, guidelines)
- Compiler options (`-Xjsr305=strict`, explicit API mode, key flags)
- Testing setup (dependencies, kotlin.test, JUnit 5, coroutines testing, naming, organization)
- `.gitignore` for Gradle projects

## `build.gradle.kts` Essentials

### Minimal single-module setup

```kotlin
plugins {
    kotlin("jvm") version "2.1.0"
}

group = "com.example"
version = "1.0.0"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
}

kotlin {
    jvmToolchain(21)
}

tasks.test {
    useJUnitPlatform()
}
```

### Version catalog (`gradle/libs.versions.toml`)

```toml
[versions]
kotlin = "2.1.0"
coroutines = "1.9.0"
serialization = "1.7.3"
junit = "5.11.0"

[libraries]
coroutines-core = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-core", version.ref = "coroutines" }
coroutines-test = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-test", version.ref = "coroutines" }
serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "serialization" }
junit-jupiter = { module = "org.junit.jupiter:junit-jupiter", version.ref = "junit" }

[plugins]
kotlin-jvm = { id = "org.jetbrains.kotlin.jvm", version.ref = "kotlin" }
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
```

Reference in `build.gradle.kts`:

```kotlin
plugins {
    alias(libs.plugins.kotlin.jvm)
}

dependencies {
    implementation(libs.coroutines.core)
    testImplementation(libs.coroutines.test)
    testImplementation(libs.junit.jupiter)
}
```

## Directory Layout

### Single-module project

```
project-name/
├── build.gradle.kts
├── settings.gradle.kts
├── gradle.properties
├── gradle/
│   ├── libs.versions.toml
│   └── wrapper/
├── src/
│   ├── main/
│   │   ├── kotlin/
│   │   │   └── com/example/project/
│   │   │       ├── Application.kt
│   │   │       ├── model/
│   │   │       │   ├── User.kt
│   │   │       │   └── Order.kt
│   │   │       ├── service/
│   │   │       │   └── UserService.kt
│   │   │       └── util/
│   │   │           └── Extensions.kt
│   │   └── resources/
│   │       └── application.yml
│   └── test/
│       ├── kotlin/
│       │   └── com/example/project/
│       │       ├── model/
│       │       │   └── UserTest.kt
│       │       └── service/
│       │           └── UserServiceTest.kt
│       └── resources/
│           └── test-data.json
├── gradlew
└── gradlew.bat
```

### Key conventions

- **One class per file** — file name matches the primary class name (`UserService.kt`).
- **Extension files** — group related extensions in descriptive files (`StringExtensions.kt`, `CollectionExtensions.kt`).
- **Package = directory** — keep package declarations aligned with the directory structure.
- **Resources** — place in `src/main/resources` and `src/test/resources`; access with `ClassLoader.getResource()`.

## Multi-Module Project Organization

### `settings.gradle.kts`

```kotlin
rootProject.name = "my-project"

include(
    ":core",
    ":api",
    ":app",
)
```

### Typical module structure

```
my-project/
├── settings.gradle.kts
├── build.gradle.kts              # root — shared config
├── gradle/libs.versions.toml
├── core/
│   ├── build.gradle.kts
│   └── src/main/kotlin/...
├── api/
│   ├── build.gradle.kts
│   └── src/main/kotlin/...
└── app/
    ├── build.gradle.kts
    └── src/main/kotlin/...
```

### Shared configuration in root `build.gradle.kts`

```kotlin
subprojects {
    apply(plugin = "org.jetbrains.kotlin.jvm")

    repositories {
        mavenCentral()
    }

    kotlin {
        jvmToolchain(21)
    }

    tasks.test {
        useJUnitPlatform()
    }
}
```

### Module dependencies

```kotlin
// In app/build.gradle.kts
dependencies {
    implementation(project(":core"))
    implementation(project(":api"))
}
```

### Module organization guidelines

| Module | Purpose |
|---|---|
| `core` / `domain` | Domain models, business logic, no framework dependencies |
| `api` | API contracts, DTOs, interfaces |
| `app` | Application entry point, wiring, configuration |
| `infra` / `persistence` | Database, external service integrations |
| `common` / `shared` | Shared utilities (use sparingly) |

Keep the dependency graph acyclic. `core` should not depend on `app` or `infra`.

## Compiler Options

### Essential `build.gradle.kts` configuration

```kotlin
kotlin {
    jvmToolchain(21)

    compilerOptions {
        // Treat all warnings as errors
        allWarningsAsErrors.set(true)

        // Better Java interop for nullability annotations
        freeCompilerArgs.addAll(
            "-Xjsr305=strict",
        )
    }
}
```

### Key compiler options

| Option | DSL | Purpose |
|---|---|---|
| `-Xjsr305=strict` | `freeCompilerArgs.addAll("-Xjsr305=strict")` | Treat JSR-305 annotations (`@Nullable`, `@NonNull`) as strict — essential for Java interop |
| Explicit API | `explicitApi()` | Require explicit visibility and return types on public API — use for library modules |
| Progressive mode | `progressiveMode.set(true)` | Enable latest language improvements that may change behavior |
| Opt-in | `optIn.add("kotlin.RequiresOptIn")` | Allow use of `@OptIn` annotation |

### Explicit API mode

For library modules, enforce explicit visibility and types:

```kotlin
kotlin {
    explicitApi()
    // or: explicitApiWarning() for gradual adoption
}
```

With explicit API mode:
- All public declarations require explicit visibility modifier (`public`, `internal`, `private`)
- All public functions require explicit return type
- All public properties require explicit type

```kotlin
// Required with explicit API mode
public fun createUser(name: String): User { ... }

// Won't compile — missing visibility and return type
fun createUser(name: String) = User(name)
```

## Testing Setup

### Dependencies

```kotlin
dependencies {
    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
}

tasks.test {
    useJUnitPlatform()
}
```

### Basic test structure with `kotlin.test`

```kotlin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class UserServiceTest {

    @Test
    fun `creates user with valid data`() {
        val service = UserService()
        val user = service.create("Alice", "alice@example.com")

        assertEquals("Alice", user.name)
        assertNotNull(user.id)
    }

    @Test
    fun `rejects blank name`() {
        val service = UserService()

        assertFailsWith<ValidationException> {
            service.create("", "alice@example.com")
        }
    }
}
```

### JUnit 5 features

```kotlin
import org.junit.jupiter.api.Nested
import org.junit.jupiter.api.TestInstance
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.ValueSource

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class CalculatorTest {

    @Nested
    inner class Addition {
        @Test
        fun `adds positive numbers`() {
            assertEquals(3, Calculator.add(1, 2))
        }
    }

    @ParameterizedTest
    @ValueSource(ints = [1, 2, 3, 4, 5])
    fun `squares are positive`(n: Int) {
        assertTrue(Calculator.square(n) > 0)
    }
}
```

### Testing coroutines

```kotlin
import kotlinx.coroutines.test.runTest

class AsyncServiceTest {

    @Test
    fun `fetches user by id`() = runTest {
        val service = UserService(FakeRepository())
        val user = service.findById("123")

        assertEquals("Alice", user?.name)
    }
}
```

`runTest` from `kotlinx-coroutines-test` automatically advances virtual time and handles `delay` without waiting.

### Test naming

Use backtick-quoted names for readability:

```kotlin
@Test
fun `throws NotFoundException when user does not exist`() { ... }

@Test
fun `returns empty list when no orders match filter`() { ... }
```

### Test organization

Mirror the main source tree structure in tests:

```
src/
├── main/kotlin/com/example/
│   ├── model/User.kt
│   └── service/UserService.kt
└── test/kotlin/com/example/
    ├── model/UserTest.kt
    └── service/UserServiceTest.kt
```

### `.gitignore` for Gradle projects

```
# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# IDE
.idea/
*.iml
.kotlin/

# OS
.DS_Store
```
