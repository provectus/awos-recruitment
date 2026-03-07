# Java-Kotlin Interop Reference

> This reference focuses on practical Java-Kotlin interoperability in Android projects.
> For Kotlin language fundamentals, see the `kotlin-development` skill.
> **Always prefer Kotlin for new code.**


## Calling Java from Kotlin

### Platform Types
---
When Kotlin calls Java code, the return types become **platform types** (shown as `Type!` in IDE tooltips). The Kotlin compiler does not enforce nullability on these types, which means you lose null-safety guarantees at the boundary.

```kotlin
// Java method: String getName() — no nullability annotation
val name = javaObject.name // inferred as String! (platform type)

// DANGER: this compiles but crashes at runtime if getName() returns null
val length = javaObject.name.length
```

#### Best practices
- Assign platform types to explicitly typed variables immediately:
  ```kotlin
  val name: String? = javaObject.name // safe
  ```
- Treat every un-annotated Java return value as nullable until proven otherwise.
- Add `@NonNull` / `@Nullable` annotations to Java code you own.

### Handling Nullability from Java
---
```kotlin
// Safe patterns when consuming Java APIs
val result: String = javaObject.name ?: "default"
val length: Int = javaObject.name?.length ?: 0
```


## Calling Kotlin from Java

### @JvmStatic
---
Makes a companion object function or property accessible as a real Java static member.

```kotlin
class Analytics {
    companion object {
        @JvmStatic
        fun track(event: String) { /* ... */ }
    }
}
```
```java
// Without @JvmStatic: Analytics.Companion.track("click");
// With @JvmStatic:    Analytics.track("click");
```

### @JvmField
---
Exposes a Kotlin property as a plain Java field (no getter/setter generated).

```kotlin
class Config {
    @JvmField
    val MAX_RETRIES = 3
}
```
```java
int retries = config.MAX_RETRIES; // direct field access
```

Use `@JvmField` on `companion object` constants and public properties consumed from Java. For compile-time constants, prefer `const val` inside a `companion object`.

### @JvmOverloads
---
Generates overloaded Java methods for Kotlin functions with default parameters.

```kotlin
class CustomView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr)
```

Without this annotation, Java callers must provide every argument. This is critical for custom Android views, which require specific constructor overloads for inflation.

### @JvmName
---
Changes the JVM name of a generated method or file facade. Useful for resolving signature clashes.

```kotlin
@get:JvmName("isActive")
val active: Boolean = true

// Resolves clashes between type-erased signatures
@JvmName("filterStrings")
fun filter(list: List<String>): List<String> = TODO()

@JvmName("filterInts")
fun filter(list: List<Int>): List<Int> = TODO()
```


## SAM Conversions

### Java Functional Interfaces in Kotlin
---
Kotlin automatically converts lambdas to Java single-abstract-method (SAM) interfaces.

```kotlin
// Java interface: interface OnClickListener { void onClick(View v); }
button.setOnClickListener { view ->
    // lambda body
}
```

### Kotlin fun interface
---
For SAM conversion to work with Kotlin-defined interfaces, declare them with `fun interface`.

```kotlin
fun interface EventHandler {
    fun handle(event: AppEvent)
}

// Callers can use a lambda
val handler = EventHandler { event -> log(event) }
```

Without `fun`, Kotlin interfaces require explicit `object :` syntax. Prefer `fun interface` over `typealias` for function types that carry semantic meaning.


## Nullability Annotations

### Recognized Annotations
---
Kotlin recognizes nullability annotations from multiple packages. In Android projects, prefer AndroidX annotations.

| Annotation Source | Package | Notes |
|---|---|---|
| AndroidX | `androidx.annotation` | Preferred for Android code |
| JetBrains | `org.jetbrains.annotations` | Preferred for pure Kotlin/JVM libraries |
| JSR-305 | `javax.annotation` | Widely supported, legacy |

### Applying Annotations in Java Code
---
```java
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

public class UserRepository {
    @NonNull
    public String getDisplayName() { return "Guest"; }

    @Nullable
    public String getEmail() { return null; }
}
```

Kotlin then infers correct types automatically:
```kotlin
val displayName: String = repo.displayName   // String (non-null)
val email: String? = repo.email              // String? (nullable)
```

### Package-Level Defaults
---
Use `@ParametersAreNonnullByDefault` (JSR-305) or AndroidX `@NonNull` at the package level via `package-info.java` to reduce annotation noise:

```java
@ParametersAreNonnullByDefault
package com.example.data;
```


## Collection Interop

### Mutable vs Immutable at the Boundary
---
Kotlin distinguishes `List` (read-only) from `MutableList`, but both map to `java.util.List` on the JVM. Java code receiving a Kotlin `List` can still mutate it at runtime.

```kotlin
// Kotlin side
fun getItems(): List<String> = listOf("a", "b")

// Java side — compiles and mutates the underlying list
List<String> items = getItems();
items.add("c"); // UnsupportedOperationException at runtime for listOf()
```

### Defensive Copying
---
When passing collections across the boundary, copy defensively:

```kotlin
// Kotlin receiving from Java — wrap to be safe
val safeList: List<Item> = ArrayList(javaObject.items)

// Kotlin exposing to Java — return a copy
fun getItems(): MutableList<Item> = items.toMutableList()
```

When Java code must receive a mutable collection, return `toMutableList()` or `toMutableMap()` explicitly rather than exposing internal state.


## Type Mapping

### Primitives
---
| Kotlin Type | JVM / Java Type | Notes |
|---|---|---|
| `Int` | `int` / `Integer` | Nullable `Int?` boxes to `Integer` |
| `Long` | `long` / `Long` | Same boxing rule |
| `Boolean` | `boolean` / `Boolean` | Same boxing rule |
| `Double` | `double` / `Double` | Same boxing rule |

Kotlin uses primitives when possible; nullable types and generics force boxing.

### Arrays
---
| Kotlin | Java |
|---|---|
| `IntArray` | `int[]` |
| `Array<Int>` | `Integer[]` |
| `ByteArray` | `byte[]` |

Prefer `IntArray`, `LongArray`, etc. over `Array<Int>` for performance-critical code and JNI interop.

### Unit vs void
---
- Kotlin `Unit` maps to `void` in generated bytecode for regular functions.
- When `Unit` is used as a generic type argument (e.g., `Continuation<Unit>`), it becomes `kotlin.Unit` on the JVM.

```java
// Calling a Kotlin function that returns Unit from Java
kotlinObject.doWork(); // works fine, void return

// When Unit is a type parameter
Function1<String, Unit> callback = s -> {
    System.out.println(s);
    return Unit.INSTANCE; // required
};
```


## Coroutines and Java

### Calling Suspend Functions from Java
---
Suspend functions compile to methods with an extra `Continuation` parameter. Calling them directly from Java is impractical. Instead, expose a bridge.

```kotlin
// Kotlin bridge for Java callers
object UserApi {
    // Suspend function (Kotlin callers)
    suspend fun getUser(id: String): User = repository.fetchUser(id)

    // Bridge for Java callers
    @JvmStatic
    fun getUserAsync(id: String): ListenableFuture<User> {
        return GlobalScope.future { getUser(id) }
    }
}
```

With `kotlinx-coroutines-jdk8`, use `future {}` to return `CompletableFuture`:

```kotlin
@JvmStatic
fun getUserAsync(id: String): CompletableFuture<User> =
    GlobalScope.future { getUser(id) }
```

### Wrapping Java Callbacks as Coroutines
---
Use `suspendCancellableCoroutine` to convert callback-based Java APIs into suspend functions.

```kotlin
suspend fun fetchLocation(): Location = suspendCancellableCoroutine { cont ->
    val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            cont.resume(result.lastLocation)
        }

        override fun onError(error: Exception) {
            cont.resumeWithException(error)
        }
    }

    locationClient.requestLocation(callback)

    cont.invokeOnCancellation {
        locationClient.removeCallback(callback)
    }
}
```

### Wrapping Callbacks as Flows
---
For streaming callbacks, use `callbackFlow`:

```kotlin
fun locationUpdates(): Flow<Location> = callbackFlow {
    val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            trySend(result.lastLocation)
        }
    }
    locationClient.requestUpdates(callback)
    awaitClose { locationClient.removeCallback(callback) }
}
```


## Migration Strategy

### Recommended Priorities
---
1. **Data classes and models** — straightforward conversion, immediate benefits from `equals`/`hashCode`/`copy`.
2. **Utility classes** — static methods become top-level or extension functions.
3. **New features** — always write in Kotlin.
4. **Tests** — convert test classes to Kotlin for readability.
5. **Activities/Fragments** — convert last; highest risk due to lifecycle complexity.

### File-by-File Approach
---
- Convert one file at a time and run tests after each conversion.
- Start with leaf files (no dependents) and work inward.
- Keep both `.java` and `.kt` files compiling together during migration; Gradle handles mixed compilation.

### Android Studio Converter Pitfalls
---
The built-in "Convert Java File to Kotlin File" tool (`Ctrl+Alt+Shift+K` / `Cmd+Alt+Shift+K`) produces a starting point, but expect to fix:

| Issue | What Happens | Fix |
|---|---|---|
| Platform types | Converter guesses `String!` as `String` (non-null) | Audit every type; add `?` where null is possible |
| Force unwraps | Generates `!!` liberally | Replace with safe calls, defaults, or `require` |
| Static members | Puts everything in `companion object` without `@JvmStatic` | Add `@JvmStatic` if Java callers remain |
| Property access | Converts `getFoo()` to `foo` but may break overrides | Check overridden methods carefully |
| SAM conversions | May leave verbose `object :` syntax | Simplify to lambdas |
| Nullability | Ignores missing annotations | Add null checks for platform-type values |

Always review the diff after conversion rather than blindly committing.


## Mixed Codebase Patterns

### Wrapping Java Builders
---
Java builders are verbose in Kotlin. Wrap them with a DSL-style extension:

```kotlin
// Java builder: AlertDialog.Builder(context).setTitle(...).setMessage(...).create()

inline fun Context.alertDialog(block: AlertDialog.Builder.() -> Unit): AlertDialog =
    AlertDialog.Builder(this).apply(block).create()

// Usage
alertDialog {
    setTitle("Confirm")
    setMessage("Delete item?")
    setPositiveButton("OK") { _, _ -> delete() }
}
```

### Extension Functions for Java Classes
---
Add Kotlin-idiomatic APIs to Java classes you cannot modify:

```kotlin
fun SharedPreferences.edit(block: SharedPreferences.Editor.() -> Unit) {
    val editor = edit()
    editor.block()
    editor.apply()
}

// Usage
prefs.edit {
    putString("key", "value")
    putBoolean("onboarded", true)
}
```

### Adapting Listeners to Flows
---
Convert Java listener patterns into reactive Kotlin Flows:

```kotlin
fun EditText.textChanges(): Flow<CharSequence> = callbackFlow {
    val watcher = object : TextWatcher {
        override fun beforeTextChanged(s: CharSequence, start: Int, count: Int, after: Int) {}
        override fun onTextChanged(s: CharSequence, start: Int, before: Int, count: Int) {
            trySend(s)
        }
        override fun afterTextChanged(s: Editable) {}
    }
    addTextChangedListener(watcher)
    awaitClose { removeTextChangedListener(watcher) }
}

// Usage in a ViewModel
editText.textChanges()
    .debounce(300)
    .distinctUntilChanged()
    .collectLatest { query -> search(query.toString()) }
```


## Common Pitfalls

### Platform Type Crashes
---
The most frequent interop bug. A Java method returns `null`, Kotlin assumes non-null, and the app crashes with `NullPointerException` — not at the call site, but at first usage.

```kotlin
// DANGEROUS
val name: String = javaObject.name // crashes here if null

// SAFE
val name: String = javaObject.name ?: "Unknown"
```

### Static Access
---
Kotlin has no `static` keyword. Without proper annotations, Java callers face awkward access patterns:

```kotlin
// Without annotations
class Constants {
    companion object {
        val TAG = "MyApp"            // Java: Constants.Companion.getTAG()
    }
}

// With annotations
class Constants {
    companion object {
        @JvmField val TAG = "MyApp"  // Java: Constants.TAG
        const val MAX = 100           // Java: Constants.MAX (compile-time constant)
    }
}
```

### Checked Exceptions
---
Kotlin does not have checked exceptions. Java callers of Kotlin functions that throw will not be warned by the compiler.

```kotlin
// Kotlin — no checked exception declaration
fun parse(json: String): Data {
    throw IOException("bad data")
}

// Java — compiles without try/catch, crashes at runtime
Data data = parse(jsonString); // IOException is unchecked from Java's perspective
```

Fix with `@Throws`:
```kotlin
@Throws(IOException::class)
fun parse(json: String): Data { /* ... */ }
```

### Property Name Conflicts
---
Kotlin generates getters/setters for properties. If a Java subclass already has a method like `getType()`, and you declare a Kotlin property `type`, you get a compilation error due to conflicting JVM signatures.

```kotlin
// Conflicts with inherited Java method getType()
// val type: String  // won't compile

// Fix: rename the property or use @JvmName
@get:JvmName("getItemType")
val type: String = "default"
```

### Internal Visibility
---
Kotlin `internal` compiles to `public` on the JVM with a mangled name. Java code can still call internal members (with ugly names). Do not rely on `internal` for security at the interop boundary.

### Companion Object Overhead
---
Each `companion object` creates a separate class (`MyClass$Companion`). In performance-critical paths, prefer top-level functions and `const val` over companion objects.
