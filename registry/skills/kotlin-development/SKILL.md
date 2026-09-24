---
name: kotlin-development
description: "This skill should be used when the user asks to \"write Kotlin code\", \"create a Kotlin class\", \"set up a Kotlin project\", \"review Kotlin code\", \"refactor Kotlin\", \"use Kotlin coroutines\", \"fix Kotlin style\", \"set up Detekt\", \"configure ktlint\", \"add static analysis to a Kotlin project\", \"set up Kotlin linting (Detekt, ktlint)\", or when generating any Kotlin source code. Provides modern Kotlin 2.1+ best practices covering null safety, coroutines, data modeling, error handling, idiomatic patterns, and static analysis (Detekt, ktlint). Covers the language and stdlib only; the one framework-specific part is an optional Android/Compose lint section."
version: 0.1.0
---

# Kotlin Development (2.1+)

Modern Kotlin best practices for writing concise, safe, and idiomatic code. Targets Kotlin 2.1+ on the JVM — language and stdlib only, no frameworks or libraries. The lint configuration is target-neutral; Android/Compose settings live in one clearly marked section of `references/static-analysis.md` and apply only when the project uses them.

## Reference Files

- **`references/type-system.md`** — Generics, variance, smart casts, inline/value classes, `Nothing`, SAM conversions
- **`references/patterns.md`** — Scope functions, sealed hierarchies, delegation, extensions, DSL builders, domain modeling, error handling guide
- **`references/coroutines.md`** — Flow, StateFlow/SharedFlow, Channels, exception handling, cancellation, testing
- **`references/project-structure.md`** — `build.gradle.kts`, multi-module, compiler options, testing setup
- **`references/static-analysis.md`** — Detekt (setup, `detekt.yml`, rule sets, custom rules, baseline), ktlint (setup, `.editorconfig`, standard rules, Spotless), Detekt vs ktlint comparison, multi-module convention plugin, pre-commit hooks, Android/Compose additions (optional)

## Code Style

- **Short functions** — keep each function readable without scrolling. If a block needs a comment to explain it, extract it into a well-named function. The Detekt config in `references/static-analysis.md` enforces `LongMethod` at 60 lines as the hard ceiling; aim well below it.
- **Imports at the top** — never use inline fully-qualified types (`java.time.LocalDateTime`) in the code body. Use import aliases for naming conflicts. No wildcard imports.

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Package | `lowercase` | `com.example.userdata` |
| Class / Object | `PascalCase` | `UserAccount`, `JsonParser` |
| Function / Property | `camelCase` | `getUserById()`, `isActive` |
| Constant (`const val`) | `UPPER_SNAKE` | `MAX_RETRIES` |
| Type parameter | Single uppercase | `T`, `K`, `V` |
| Enum entry | `UPPER_SNAKE` | `Status.ACTIVE` |
| Backing property | `_prefixed` | `private val _items` |
| File name | `PascalCase.kt` | `UserService.kt` |
| Boolean | Prefix `is`, `has`, `can`, `should` | `isValid`, `hasPermission` |

## Null Safety

```kotlin
val name: String? = findUser()?.name   // safe call
val length = name?.length ?: 0          // elvis — default for null
```

Never use `!!` to silence the compiler — it crashes at runtime. Acceptable only with a provable invariant and a comment explaining why.

### Safe patterns

```kotlin
user?.let { sendEmail(it) }                              // nullable transform
requireNotNull(id) { "id must not be null" }             // precondition + smart cast
val names: List<String> = users.mapNotNull { it.name }   // filter nulls
```

## Type System

Kotlin infers types aggressively. Annotate explicitly for public API, when the inferred type is too broad, or when readability benefits.

```kotlin
// Inferred — fine for locals
val count = items.size

// Explicit — public API
fun findUser(id: String): User? { ... }
```

For generics (`in`/`out` variance, star projection, reified types), type aliases, smart casts, and value classes, see `references/type-system.md`.

## Data Modeling

### `data class` — value containers

```kotlin
data class User(val id: String, val name: String, val email: String)
```

Use `val` properties — change state with `copy()`. Prefer data classes over `Map<String, Any>`; maps lose type safety, autocompletion, and refactoring support.

### `sealed class` / `sealed interface` — restricted hierarchies

```kotlin
sealed interface Result<out T> {
    data class Success<T>(val value: T) : Result<T>
    data class Failure(val error: Throwable) : Result<Nothing>
}
```

Enables exhaustive `when`. Prefer `sealed interface` when subtypes don't share state.

### `value class` — zero-cost wrappers

```kotlin
@JvmInline
value class UserId(val value: String)

@JvmInline
value class Email(val value: String) {
    init { require(value.contains("@")) { "Invalid email: $value" } }
}
```

Use to prevent primitive obsession — the compiler catches swapped parameters.

### Precision arithmetic

Never use `Double`/`Float` for monetary values. Use `BigDecimal` (construct from `String`, never `Double`) with explicit `MathContext`, or `Long` (cents) with a `value class` wrapper. See `references/patterns.md` for full patterns.

## Error Handling

```kotlin
// Custom hierarchy
open class AppException(message: String, cause: Throwable? = null) : RuntimeException(message, cause)
class ValidationException(message: String) : AppException(message)
class NotFoundException(message: String) : AppException(message)

// runCatching — non-suspending code only (see the coroutines rule below)
val port = runCatching { config.getValue("port").toInt() }.getOrDefault(8080)

// Sealed result for expected business outcomes
sealed interface FetchResult {
    data class Found(val user: User) : FetchResult
    data object NotFound : FetchResult
    data class Error(val reason: String) : FetchResult
}
```

Rules:
- Use `require()` for argument validation, `check()` for state validation.
- Catch the narrowest exception that you can handle. Don't catch `Throwable` unless re-throwing — it hides `OutOfMemoryError` and cancellation.
- Prefer sealed hierarchies over exceptions for expected outcomes.
- In `suspend` functions use `try/catch` and rethrow `CancellationException` first; `runCatching` catches `Throwable`, so it swallows cancellation too. Keep it for non-suspending code.
- See `references/patterns.md` for the full error handling decision guide.

## Coroutines Essentials

```kotlin
suspend fun fetchUser(id: String): User = httpClient.get("users/$id")

suspend fun loadDashboard(): Dashboard = coroutineScope {
    val user = async { fetchUser(userId) }
    val orders = async { fetchOrders(userId) }
    Dashboard(user.await(), orders.await())
}
```

Rules:
- Use structured concurrency; don't use `GlobalScope` — it leaks coroutines that nothing cancels.
- `coroutineScope` when all must succeed; `supervisorScope` when partial failure is OK.
- `launch` for fire-and-forget; `async` when you need the result.
- Rethrow `CancellationException` from every catch block — swallowing it breaks structured concurrency (worked example in `references/coroutines.md`).
- Use `withContext(Dispatchers.IO)` for blocking I/O; `Dispatchers.Default` for CPU work.

For Flow, Channels, exception handling, cancellation patterns, timeouts, and testing, see `references/coroutines.md`.

## Project Structure

```
project-name/
├── build.gradle.kts
├── settings.gradle.kts
├── gradle/libs.versions.toml
├── src/
│   ├── main/kotlin/com/example/project/
│   └── test/kotlin/com/example/project/
└── gradlew
```

- Use Gradle Kotlin DSL and version catalog (`libs.versions.toml`).
- Organize by domain, not by technical role.
- One class per file; file name matches class name.

For `build.gradle.kts` config, multi-module setup, compiler options, and testing, see `references/project-structure.md`.

## Idiomatic Patterns

- `buildList` / `buildMap` / `buildString` for constructing collections and strings.
- `groupBy`, `associateBy`, `partition`, `flatMap` for collection transformations.
- `Sequence` for lazy evaluation of large collections.
- `use` for auto-closeable resource management.
- Collection operations over loops: `users.filter { it.age >= 18 }.map { it.name }`
- Scope functions (`let`, `run`, `with`, `apply`, `also`): pick by what the lambda should return and whether the object is `this` or `it`; don't nest them. Decision table in `references/patterns.md`.

## Testable Design

- **Constructor injection** — accept dependencies as constructor parameters, never instantiate internally.
- **Depend on interfaces** at module boundaries.
- **Fakes over mocks** — write simple in-memory implementations.
- **Pure core logic** — push I/O to the edges, keep business logic in pure functions.

For full patterns, see `references/patterns.md`.

## Quick Reference: Common Mistakes

| Mistake | Fix |
|---|---|
| Using `!!` to silence nullability | Use `?.`, `?:`, `let`, or redesign to be non-null |
| Platform types without annotation | Add explicit nullability at Java boundaries |
| `var` in data classes | Use `val` — copy with `copy()` |
| Catching `Throwable` | Catch specific exceptions |
| Mutable collections in public API | Expose `List`, not `MutableList`; backing property pattern |
| Inline fully-qualified types | Import at top; use aliases for conflicts |
| `Map<String, Any>` as data holder | Define a `data class` |
| `Double` for money | `BigDecimal` with `MathContext`, or `Long` (cents) |
| Long functions (Detekt `LongMethod` fires at 60 lines) | Extract named private functions |
| Hard-coded dependencies | Constructor injection; depend on interfaces |
| `when` without exhaustive check | Use sealed types or add `else` branch |

