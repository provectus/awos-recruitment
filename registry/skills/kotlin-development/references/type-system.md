# Kotlin Type System Reference

## Contents
- Generics (basic, constrained, variance `in`/`out`, use-site projection, star projection, reified)
- Type aliases
- Smart casts and type checks (`is`, `as`, `as?`, smart cast conditions, contracts)
- Inline / value classes
- `Nothing` type
- Functional types and SAM conversions (function types, `fun interface`, higher-order, `inline`/`noinline`/`crossinline`)

## Generics

### Basic generics

```kotlin
fun <T> identity(value: T): T = value

fun <T> List<T>.secondOrNull(): T? = if (size >= 2) this[1] else null

class Box<T>(val value: T)
```

### Constrained generics

```kotlin
fun <T : Comparable<T>> max(a: T, b: T): T = if (a >= b) a else b

// Multiple upper bounds
fun <T> sort(list: List<T>) where T : Comparable<T>, T : Serializable {
    list.sorted()
}
```

### Variance — `in` and `out`

Declaration-site variance replaces Java's `? extends` and `? super`:

| Modifier | Meaning | Java equivalent | Mnemonic |
|---|---|---|---|
| `out T` | Covariant — produces `T` | `? extends T` | Output only |
| `in T` | Contravariant — consumes `T` | `? super T` | Input only |
| (none) | Invariant | (exact type) | Both input and output |

```kotlin
// Producer — only outputs T
interface Source<out T> {
    fun next(): T
}

// Consumer — only accepts T
interface Sink<in T> {
    fun send(value: T)
}

// Usage
val strings: Source<String> = ...
val objects: Source<Any> = strings  // OK — String is subtype of Any

val objects: Sink<Any> = ...
val strings: Sink<String> = objects  // OK — Any sink accepts String
```

### Use-site variance (type projection)

When declaration-site variance isn't possible:

```kotlin
// Read-only projection
fun copy(from: Array<out Any>, to: Array<Any>) {
    for (i in from.indices) {
        to[i] = from[i]
    }
}

// Write-only projection
fun fill(dest: Array<in String>, value: String) {
    for (i in dest.indices) {
        dest[i] = value
    }
}
```

### Star projection (`*`)

Use when the type argument is unknown and you don't care about it:

```kotlin
fun printAll(items: List<*>) {
    for (item in items) println(item)  // item is Any?
}
```

`Foo<*>` is equivalent to `Foo<out Any?>` for reading and `Foo<in Nothing>` for writing.

### Reified type parameters

Inline functions can access type information at runtime:

```kotlin
inline fun <reified T> isInstance(value: Any): Boolean = value is T

inline fun <reified T> Gson.fromJson(json: String): T =
    fromJson(json, T::class.java)

// Usage
val isString = isInstance<String>("hello")  // true
```

`reified` only works with `inline` functions. Use it to avoid passing `Class<T>` or `KClass<T>` explicitly.

## Type Aliases

Create alternative names for existing types without introducing new types:

```kotlin
typealias UserId = String
typealias Predicate<T> = (T) -> Boolean
typealias StringMap<V> = Map<String, V>
typealias NodeSet = Set<Network.Node>

// Useful for function types
typealias ClickHandler = (view: View, position: Int) -> Unit
```

Type aliases are fully interchangeable with the original type at compile time.

## Smart Casts and Type Checks

### `is` — type check

```kotlin
fun describe(obj: Any): String = when (obj) {
    is Int -> "Integer: $obj"             // smart cast to Int
    is String -> "String of length ${obj.length}"  // smart cast to String
    is List<*> -> "List of size ${obj.size}"
    else -> "Unknown"
}
```

### `as` and `as?` — explicit cast

```kotlin
val str: String = value as String      // throws ClassCastException if wrong
val str: String? = value as? String    // returns null if wrong
```

Prefer `as?` over `as` — it's the safe cast operator.

### Smart cast conditions

The compiler smart-casts automatically after:
- `is` checks
- `null` checks (`!= null`)
- `require()` / `check()` / `requireNotNull()` / `checkNotNull()`
- Short-circuit `&&` and `||`

Smart casts do NOT work on:
- `var` properties (may change between check and use)
- `open` properties (may be overridden)
- Properties with custom getters
- Delegated properties

```kotlin
// Works — val with no custom getter
data class Container(val value: Any)

fun process(c: Container) {
    if (c.value is String) {
        println(c.value.length)  // smart cast works
    }
}
```

### Contracts (experimental)

Functions like `require`, `check`, `requireNotNull` provide contracts that enable smart casts:

```kotlin
fun validate(input: String?) {
    requireNotNull(input) { "Input must not be null" }
    // input is now smart-cast to String
    println(input.length)
}
```

## Inline / Value Classes

### `@JvmInline value class`

Zero-overhead wrappers that provide type safety without runtime allocation:

```kotlin
@JvmInline
value class Password(val value: String)

@JvmInline
value class UserId(val id: Long)

// Compiler prevents mixing them up
fun authenticate(userId: UserId, password: Password): Boolean { ... }

// This won't compile:
// authenticate(password, userId)
```

Rules:
- Must have exactly one `val` property in the primary constructor
- Can implement interfaces but cannot extend classes
- Can have `init` blocks, functions, and properties (backed by the wrapped value)
- Boxed when used as a nullable type, generic type argument, or interface type

```kotlin
@JvmInline
value class Percentage(val value: Double) {
    init { require(value in 0.0..100.0) { "Must be 0-100" } }

    fun asDecimal(): Double = value / 100.0
}
```

## `Nothing` Type

`Nothing` is the bottom type — no value can be of type `Nothing`. It has two primary uses:

### Functions that never return

```kotlin
fun fail(message: String): Nothing {
    throw IllegalStateException(message)
}

// The compiler knows code after fail() is unreachable
val user = findUser(id) ?: fail("User $id not found")
// user is smart-cast to non-null here
```

### Empty collections with correct type inference

```kotlin
val empty: List<String> = emptyList()  // returns List<Nothing> internally
```

### `Nothing?`

The type whose only value is `null`:

```kotlin
val nothing: Nothing? = null
```

## Functional Types and SAM Conversions

### Function types

```kotlin
val onClick: () -> Unit = { println("Clicked") }
val transform: (String) -> Int = { it.length }
val compare: (Int, Int) -> Boolean = { a, b -> a > b }

// With receiver
val greet: String.() -> String = { "Hello, $this!" }
"World".greet()  // "Hello, World!"

// Nullable function type
val callback: ((Int) -> Unit)? = null
callback?.invoke(42)
```

### SAM (Single Abstract Method) conversions

Kotlin automatically converts lambdas to Java interfaces with a single abstract method:

```kotlin
// Java interface
// public interface OnClickListener { void onClick(View v); }

// Kotlin — SAM conversion
button.setOnClickListener { view -> handleClick(view) }
```

For Kotlin interfaces, use `fun interface` to enable SAM conversions:

```kotlin
fun interface Predicate<T> {
    fun test(value: T): Boolean
}

// SAM conversion works
val isPositive = Predicate<Int> { it > 0 }

// Without `fun`, you'd need:
// val isPositive = object : Predicate<Int> {
//     override fun test(value: Int) = value > 0
// }
```

### Higher-order functions

```kotlin
fun <T> List<T>.customFilter(predicate: (T) -> Boolean): List<T> =
    buildList {
        for (item in this@customFilter) {
            if (predicate(item)) add(item)
        }
    }

// Inline for zero-overhead lambdas
inline fun <T> measureTime(block: () -> T): Pair<T, Long> {
    val start = System.nanoTime()
    val result = block()
    return result to (System.nanoTime() - start)
}
```

### `inline` / `noinline` / `crossinline`

| Modifier | Effect |
|---|---|
| `inline` | Lambda is inlined at call site — no object allocation |
| `noinline` | Opt out specific lambda parameter from inlining |
| `crossinline` | Prevent non-local returns from the lambda |

```kotlin
inline fun execute(
    crossinline setup: () -> Unit,
    noinline cleanup: () -> Unit,
    action: () -> Unit,
) {
    setup()
    try { action() }
    finally { cleanup() }
}
```

Use `inline` for functions with lambda parameters to avoid allocation overhead. Don't inline large functions without lambdas — it increases bytecode size with no benefit.
