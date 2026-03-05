# Kotlin Coroutines Reference

## Contents
- Flow (cold streams, operators, StateFlow, SharedFlow, collection patterns, `flowOn`)
- Channels (hot communication, buffer types, Channel vs Flow)
- Exception handling (`coroutineScope` vs `supervisorScope`, `CoroutineExceptionHandler`, propagation rules)
- Cancellation (cooperative, `CancellationException`, `NonCancellable`)
- Timeouts (`withTimeout`, `withTimeoutOrNull`)
- Structured concurrency patterns (parallel decomposition, fan-out, scope management)
- Testing (`runTest`, `TestDispatcher`, testing StateFlow)
- Common pitfalls

## Flow — Cold Asynchronous Streams

A `Flow` is a cold stream — it doesn't produce values until collected. The async equivalent of `Sequence`.

```kotlin
fun numbers(): Flow<Int> = flow {
    for (i in 1..3) { delay(100); emit(i) }
}

suspend fun main() {
    numbers().collect { println(it) }
}

// Operators — same as collection operations
val result = numbers().filter { it % 2 != 0 }.map { it * 10 }.take(2).toList()
```

### `StateFlow` and `SharedFlow`

| Type | Hot/Cold | Replays | Use for |
|---|---|---|---|
| `Flow` | Cold | No | One-shot data streams, transformations |
| `StateFlow` | Hot | Last value (always) | Observable state (replaces `LiveData`) |
| `SharedFlow` | Hot | Configurable | Events, broadcasts to multiple collectors |

```kotlin
class UserViewModel {
    private val _state = MutableStateFlow<UiState>(UiState.Loading)
    val state: StateFlow<UiState> = _state.asStateFlow()

    suspend fun loadUser(id: String) {
        _state.value = UiState.Loading
        _state.value = runCatching { repository.findById(id) }.fold(
            onSuccess = { UiState.Success(it) },
            onFailure = { UiState.Error(it.message ?: "Unknown error") },
        )
    }
}
```

### Flow collection and error handling

```kotlin
events
    .onStart { showLoading() }
    .onEach { event -> process(event) }
    .catch { error -> showError(error) }
    .onCompletion { hideLoading() }
    .launchIn(scope)
```

### `flowOn` — change upstream dispatcher

```kotlin
fun readLines(path: String): Flow<String> = flow {
    File(path).useLines { lines -> lines.forEach { emit(it) } }
}.flowOn(Dispatchers.IO)
```

`flowOn` only affects operators **above** it. Collection happens in the collector's context.

## Channels — Hot Communication

Channels are for coroutine-to-coroutine communication. Unlike Flow, values are sent regardless of receivers.

```kotlin
val channel = Channel<Int>()
launch { for (i in 1..5) channel.send(i); channel.close() }
for (value in channel) println(value)
```

| Type | Behavior |
|---|---|
| `RENDEZVOUS` (default) | Sender suspends until receiver ready |
| `BUFFERED` | Platform-default buffer (64) |
| `CONFLATED` | Keeps only latest value |
| `Channel(n)` | Fixed-size buffer |

Prefer `Flow` unless you specifically need channel semantics (fan-out, backpressure, rendezvous).

## Exception Handling

### `coroutineScope` vs `supervisorScope`

```kotlin
// coroutineScope — one child failure cancels all siblings
suspend fun loadAll() = coroutineScope {
    val user = async { fetchUser() }      // if this fails...
    val orders = async { fetchOrders() }  // ...this gets cancelled
    Pair(user.await(), orders.await())
}

// supervisorScope — children fail independently
suspend fun loadBestEffort() = supervisorScope {
    val user = async { fetchUser() }
    val orders = async { fetchOrders() }
    Dashboard(runCatching { user.await() }.getOrNull(), runCatching { orders.await() }.getOrNull())
}
```

### `CoroutineExceptionHandler`

Last-resort handler for uncaught exceptions in `launch` (not `async`):

```kotlin
val handler = CoroutineExceptionHandler { _, ex ->
    logger.error("Uncaught: ${ex.message}", ex)
}
val scope = CoroutineScope(SupervisorJob() + handler)
```

### Exception propagation rules

| Builder | Exception behavior |
|---|---|
| `launch` | Propagates to parent immediately |
| `async` | Stores exception, throws on `await()` |
| `coroutineScope` | Rethrows first child exception |
| `supervisorScope` | Children handle their own exceptions |

## Cancellation

Cancellation is cooperative — your code must check for it. All `kotlinx.coroutines` suspending functions check automatically.

```kotlin
suspend fun processItems(items: List<Item>) = coroutineScope {
    for (item in items) {
        ensureActive()  // throws CancellationException if cancelled
        process(item)
    }
}
```

### Never swallow `CancellationException`

```kotlin
// Bad — swallows CancellationException, breaks structured concurrency
try { suspendingOperation() }
catch (e: Exception) { logger.error("Failed", e) }

// Good — rethrow CancellationException
try { suspendingOperation() }
catch (e: CancellationException) { throw e }
catch (e: Exception) { logger.error("Failed", e) }
```

Note: `runCatching` also catches `CancellationException`. In coroutines, prefer explicit try/catch.

### `NonCancellable` — cleanup that must complete

```kotlin
suspend fun closeResource(resource: Resource) {
    withContext(NonCancellable) {
        resource.flush()
        resource.close()
    }
}
```

## Timeouts

```kotlin
val result = withTimeout(5000) { fetchData() }              // throws on timeout
val result = withTimeoutOrNull(5000) { fetchData() }        // null on timeout
```

## Structured Concurrency Patterns

### Parallel decomposition

```kotlin
suspend fun loadDashboard(userId: String): Dashboard = coroutineScope {
    val profile = async { fetchProfile(userId) }
    val orders = async { fetchOrders(userId) }
    Dashboard(profile.await(), orders.await())
}
```

### Fan-out with concurrency limit

```kotlin
suspend fun processAll(items: List<Item>, concurrency: Int = 10) = coroutineScope {
    val semaphore = Semaphore(concurrency)
    items.forEach { item ->
        launch { semaphore.withPermit { processItem(item) } }
    }
}
```

### Scope management

```kotlin
class Application {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    fun start() {
        scope.launch { startBackgroundSync() }
        scope.launch { startHealthCheck() }
    }

    fun shutdown() { scope.cancel() }
}
```

**Never use `GlobalScope`** — it breaks structured concurrency and leaks coroutines.

## Testing Coroutines

### `runTest` — auto-advances virtual time

```kotlin
@Test
fun `fetches user by id`() = runTest {
    val service = UserService(InMemoryUserRepository())
    val user = service.findById("1")
    assertEquals("Alice", user?.name)
}
```

### `TestDispatcher` for controlled execution

```kotlin
@Test
fun `processes items in background`() = runTest {
    val testDispatcher = StandardTestDispatcher(testScheduler)
    val service = BackgroundProcessor(testDispatcher)
    service.enqueue(item)
    advanceUntilIdle()
    assertTrue(service.isProcessed(item))
}
```

### Testing `StateFlow`

```kotlin
@Test
fun `emits loading then success`() = runTest {
    val viewModel = UserViewModel(FakeRepository())
    val states = mutableListOf<UiState>()
    val job = launch { viewModel.state.toList(states) }
    viewModel.loadUser("1")
    advanceUntilIdle()
    job.cancel()
    assertEquals(UiState.Loading, states[0])
    assertIs<UiState.Success>(states[1])
}
```

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| `GlobalScope.launch` | Use structured scopes: `coroutineScope`, lifecycle-bound scopes |
| Blocking in coroutine (`Thread.sleep`) | Use `withContext(Dispatchers.IO)` for blocking, `Default` for CPU |
| Catching `CancellationException` | Always rethrow it, or catch specific exception types |
| `async` without `await` | Exceptions silently dropped — always await or use `launch` |
| `runBlocking` in production | Only in `main()` or tests — never inside other coroutines |
| Mutable shared state | Use `Mutex`, `StateFlow`, or `Channel` for concurrent access |
| `flow { }` with `emit` from other coroutine | Use `channelFlow { }` for concurrent emission |
