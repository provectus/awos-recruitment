# Kotlin Patterns Reference

## Contents
- Scope functions decision guide (`let`, `run`, `with`, `apply`, `also`)
- Sealed class hierarchies (state modeling, nested hierarchies, sealed vs boolean flags)
- Delegation (`by`, `by lazy`, observables, map delegation)
- Extension functions and properties
- DSL builders (`@DslMarker`, stdlib builders)
- Sequences vs collections
- Operator overloading
- Precision arithmetic (BigDecimal, Long-based storage)
- Domain modeling (data classes over maps, value classes for primitive obsession)
- Testable design (constructor injection, fakes over mocks, pure functions)
- Error handling decision guide (sealed vs Result vs exceptions)

## Scope Functions Decision Guide

| Function | Object ref | Returns | Use when |
|---|---|---|---|
| `let` | `it` | Lambda result | Null checks, transformations, scoping |
| `run` | `this` | Lambda result | Computing a value using object's methods |
| `with` | `this` | Lambda result | Grouping calls on an object (non-null) |
| `apply` | `this` | Object itself | Configuring / initializing an object |
| `also` | `it` | Object itself | Side effects (logging, validation) |

```kotlin
// let — null-safe transform
user?.let { sendNotification(it) }

// run — compute using receiver
val greeting = user.run { "Hello, $name! You have $unreadCount messages." }

// with — group calls on non-null object
val result = with(StringBuilder()) { append("Hello"); append(", World"); toString() }

// apply — configure and return
val config = DatabaseConfig().apply { url = "jdbc:postgresql://localhost/mydb"; maxPoolSize = 10 }

// also — side effects in a chain
val users = fetchUsers()
    .also { logger.debug("Fetched ${it.size} users") }
    .filter { it.isActive }
```

### Anti-patterns

- **Nested scope functions** — hard to read. Extract to named functions instead.
- **`let` on non-null values** — unnecessary; just use the value directly.
- **`apply` for computation** — use `run` if you need the lambda result, not the receiver.

## Sealed Class Hierarchies

```kotlin
// State modeling
sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data class Success<T>(val data: T) : UiState<T>
    data class Error(val message: String) : UiState<Nothing>
}

fun <T> render(state: UiState<T>) = when (state) {
    is UiState.Loading -> showSpinner()
    is UiState.Success -> showData(state.data)
    is UiState.Error -> showError(state.message)
    // No else needed — exhaustive
}
```

### Nested sealed hierarchies

```kotlin
sealed interface PaymentResult {
    data class Success(val transactionId: String) : PaymentResult

    sealed interface Failure : PaymentResult {
        data class Declined(val reason: String) : Failure
        data class NetworkError(val cause: Throwable) : Failure
        data object InsufficientFunds : Failure
    }
}
```

### Sealed types over boolean flags

```kotlin
// Bad — unclear which combinations are valid
data class Payment(
    val status: String,          // "pending", "completed", "failed" — no enforcement
    val transactionId: String?,  // null when pending? or failed?
    val errorMessage: String?,   // null when successful? always?
)

// Good — each state carries exactly the data it needs
sealed interface PaymentState {
    data object Pending : PaymentState
    data class Completed(val transactionId: String) : PaymentState
    data class Failed(val errorMessage: String) : PaymentState
}
```

## Delegation

### Interface delegation (`by`)

```kotlin
class LoggingList<T>(
    private val inner: MutableList<T> = mutableListOf(),
) : MutableList<T> by inner {
    override fun add(element: T): Boolean {
        println("Adding: $element")
        return inner.add(element)
    }
}
```

### Lazy and observable properties

```kotlin
val heavyObject: HeavyObject by lazy { HeavyObject() }
// Thread-safe by default (LazyThreadSafetyMode.SYNCHRONIZED)

var name: String by Delegates.observable("initial") { _, old, new ->
    println("Changed from $old to $new")
}
```

### Map delegation

```kotlin
class User(map: Map<String, Any?>) {
    val name: String by map
    val age: Int by map
}

val user = User(mapOf("name" to "Alice", "age" to 30))
```

## Extension Functions and Properties

```kotlin
fun String.words(): List<String> = split("\\s+".toRegex())

fun <T> MutableList<T>.swap(i: Int, j: Int) {
    val temp = this[i]; this[i] = this[j]; this[j] = temp
}

val String.lastChar: Char get() = this[length - 1]
```

Best practices:
- Extensions are dispatched statically — not virtual. A `Base` extension won't be overridden by a `Derived` extension.
- Scope extensions to the smallest appropriate visibility (`private`, `internal`).
- Avoid extending `Any` — it pollutes every type's autocomplete.

## DSL Builders

```kotlin
@DslMarker
annotation class HtmlDsl

@HtmlDsl
class HTML {
    private val children = mutableListOf<Element>()
    fun head(init: Head.() -> Unit) { children += Head().apply(init) }
    fun body(init: Body.() -> Unit) { children += Body().apply(init) }
}

fun html(init: HTML.() -> Unit): HTML = HTML().apply(init)
```

`@DslMarker` prevents accidentally using outer receivers in nested lambdas.

### Stdlib builders

```kotlin
val csv = buildString {
    appendLine("name,age")
    for (user in users) appendLine("${user.name},${user.age}")
}

val lookup = buildMap<String, User> {
    for (user in users) put(user.id, user)
}
```

## Sequences vs Collections

```kotlin
// Eager — creates intermediate lists at each step
val result = (1..1_000_000).map { it * 2 }.filter { it % 3 == 0 }.take(10)

// Lazy — no intermediate collections, stops after finding 10
val result = (1..1_000_000).asSequence()
    .map { it * 2 }.filter { it % 3 == 0 }.take(10).toList()
```

Use sequences for large collections with chained operations. Stick with collections for small data or operations needing the whole collection (`sorted`, `groupBy`).

## Operator Overloading

| Operator | Function | Example |
|---|---|---|
| `+` / `-` / `*` | `plus` / `minus` / `times` | `a + b` |
| `[]` | `get` / `set` | `a[i]` |
| `in` | `contains` | `item in collection` |
| `()` | `invoke` | `action()` |
| `==` | `equals` | `a == b` |
| `<`, `>` | `compareTo` | `a > b` |

```kotlin
data class Point(val x: Double, val y: Double) {
    operator fun plus(other: Point) = Point(x + other.x, y + other.y)
    operator fun times(scale: Double) = Point(x * scale, y * scale)
}
```

Only overload operators when the semantics are obvious. `+` on `Point` makes sense; `+` on `User` doesn't.

## Precision Arithmetic

Never use `Double` or `Float` for monetary values or quantities where rounding matters.

```kotlin
// Always construct from String, never from Double
val price = BigDecimal("19.99")              // correct
val wrong = BigDecimal(19.99)                // wrong — inherits imprecision

// Arithmetic with explicit context
val tax = price.multiply(BigDecimal("0.08"), MathContext.DECIMAL64)
val total = price.add(tax).setScale(2, RoundingMode.HALF_UP)

// Comparison — never use == on BigDecimal
BigDecimal("1.0") == BigDecimal("1.00")       // false (different scale)
BigDecimal("1.0").compareTo(BigDecimal("1.00")) // 0 (numerically equal)
```

### Long-based storage for monetary values

```kotlin
@JvmInline
value class Cents(val value: Long) {
    operator fun plus(other: Cents) = Cents(value + other.value)
    operator fun minus(other: Cents) = Cents(value - other.value)
    fun toBigDecimal(): BigDecimal = BigDecimal(value).movePointLeft(2)
}
```

| Approach | Use for |
|---|---|
| `BigDecimal` | Calculations, display, API boundaries |
| `Long` (cents) | Database storage, wire format, high-performance paths |
| `Double` | Scientific computation, graphics, non-financial approximation |

## Domain Modeling

### Data classes over maps

Never use `Map<String, Any>` as a data container. Maps lose type safety, autocompletion, and refactoring support.

```kotlin
// Bad
fun createUser(data: Map<String, Any>): User {
    val name = data["name"] as String  // ClassCastException risk
    ...
}

// Good
data class CreateUserRequest(val name: String, val age: Int, val email: String)
```

### Value classes for primitive obsession

```kotlin
// Bad — easy to mix up
fun transferMoney(from: String, to: String, amount: Long) { ... }

// Good — compiler catches mistakes
@JvmInline value class AccountId(val value: String)
fun transferMoney(from: AccountId, to: AccountId, amount: Cents) { ... }
```

## Testable Design

### Constructor injection

```kotlin
// Bad — impossible to test without real implementations
class UserService {
    private val repository = PostgresUserRepository()
    private val emailSender = SmtpEmailSender()
    fun register(name: String, email: String): User { ... }
}

// Good — inject interfaces
class UserService(
    private val repository: UserRepository,
    private val emailSender: EmailSender,
) {
    fun register(name: String, email: String): User { ... }
}
```

### Fakes over mocks

```kotlin
class InMemoryUserRepository : UserRepository {
    private val users = mutableMapOf<String, User>()
    override suspend fun save(user: User) { users[user.id] = user }
    override suspend fun findById(id: String): User? = users[id]
}

@Test
fun `sends welcome email on registration`() = runTest {
    val fakeEmail = FakeEmailSender()
    val service = UserService(InMemoryUserRepository(), fakeEmail)
    service.register("Alice", "alice@example.com")
    assertEquals(1, fakeEmail.sent.size)
}
```

### Pure functions for core logic

Push I/O to the edges. Keep business logic in pure functions.

```kotlin
// Pure — easy to unit test
fun calculateDiscount(order: Order): Discount = when {
    order.total > Cents(10000) -> Discount.percentage(10)
    order.items.size >= 5 -> Discount.percentage(5)
    else -> Discount.none()
}

// Thin orchestration — integration tested
suspend fun processDiscount(orderId: String) {
    val order = repository.findOrder(orderId)
    val discount = calculateDiscount(order)
    repository.applyDiscount(orderId, discount)
}
```

### Guidelines

- Depend on interfaces at module boundaries, not concrete classes.
- Constructor injection only — avoid service locators or `lateinit var` for dependencies.
- No mutable static/global state.
- Test behavior, not implementation — assert on outputs and side effects.

## Error Handling Decision Guide

| Situation | Strategy | Example |
|---|---|---|
| Programmer error (bug) | `require()` / `check()` / `error()` | `require(age >= 0)` |
| Expected business outcome | Sealed class hierarchy | `LoginResult.InvalidCredentials` |
| Recoverable I/O failure | `Result` / `runCatching` | `runCatching { httpClient.get(url) }` |
| Unrecoverable failure | Exception (let it propagate) | `throw DatabaseConnectionException(...)` |

**Sealed classes** — when the caller must handle every case:

```kotlin
sealed interface LoginResult {
    data class Success(val token: AuthToken) : LoginResult
    data class InvalidCredentials(val attemptsLeft: Int) : LoginResult
    data object AccountLocked : LoginResult
}
```

**`Result`** — for I/O with functional-style chaining:

```kotlin
val user = runCatching { api.fetchUser(id) }
    .recover { cache.getCachedUser(id) ?: throw it }
    .getOrThrow()
```

**Exceptions** — for truly unexpected failures that should propagate.
