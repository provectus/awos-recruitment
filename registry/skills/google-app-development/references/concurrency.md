# Android Concurrency Reference

> Covers Android-specific concurrency patterns only. For coroutines fundamentals (Flow, Channels,
> exception handling, cancellation, structured concurrency, `runTest` basics), see the
> `kotlin-development` skill's `coroutines.md` reference.

## Contents
- viewModelScope — auto-cancellation, launching operations
- lifecycleScope — lifecycle-aware coroutine launching
- repeatOnLifecycle — restarting collection on lifecycle state changes
- collectAsStateWithLifecycle — Compose lifecycle-aware collection
- StateFlow in ViewModels — `stateIn`, `SharingStarted` strategies, combining flows
- WorkManager — Workers, constraints, chaining, periodic work, expedited work
- Testing — ViewModel testing, TestDispatcher injection, Turbine

For Foreground Services, Background Limits (Doze, App Standby), and AlarmManager, see `android-background-work.md`.


## viewModelScope

`viewModelScope` is a `CoroutineScope` tied to the `ViewModel`. It uses `SupervisorJob() + Dispatchers.Main.immediate` and cancels automatically in `onCleared()`.

```kotlin
class OrderViewModel(
    private val repository: OrderRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<OrderUiState>(OrderUiState.Loading)
    val uiState: StateFlow<OrderUiState> = _uiState.asStateFlow()

    fun loadOrders() {
        viewModelScope.launch {
            _uiState.value = OrderUiState.Loading
            try {
                val orders = repository.getOrders() // suspend, runs on caller dispatcher
                _uiState.value = OrderUiState.Success(orders)
            } catch (e: IOException) {
                _uiState.value = OrderUiState.Error("Network error")
            }
        }
    }

    // Parallel decomposition inside viewModelScope
    fun loadDashboard() {
        viewModelScope.launch {
            coroutineScope {
                val orders = async { repository.getOrders() }
                val profile = async { repository.getProfile() }
                _uiState.value = OrderUiState.Dashboard(orders.await(), profile.await())
            }
        }
    }
}
```

Key points:
- Uses `SupervisorJob` so one failed child does not cancel siblings.
- Dispatches on `Main.immediate` by default; switch with `withContext(Dispatchers.IO)` for blocking calls inside the repository layer, not the ViewModel.
- No manual cancellation needed; the scope is cancelled when the ViewModel is cleared (screen destroyed permanently).
- Survives configuration changes (rotation, dark mode toggle) because ViewModel outlives the Activity/Fragment.


## lifecycleScope

`lifecycleScope` is available on any `LifecycleOwner` (Activity, Fragment). It cancels when the lifecycle reaches `DESTROYED`. Uses `SupervisorJob() + Dispatchers.Main.immediate`.

```kotlin
class OrderListActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // One-shot work — fine with lifecycleScope.launch
        lifecycleScope.launch {
            val config = fetchRemoteConfig()
            applyConfig(config)
        }
    }
}
```

### When to use lifecycleScope vs viewModelScope

| Scope | Survives rotation | Tied to | Use for |
|---|---|---|---|
| `viewModelScope` | Yes | ViewModel clear | Data loading, business logic, state management |
| `lifecycleScope` | No | Activity/Fragment destroy | UI operations, one-shot lifecycle work, collecting flows |

Do **not** use `lifecycleScope.launch` to collect Flows directly. The coroutine stays active in the background when the UI is not visible, wasting resources and potentially updating a detached UI. Use `repeatOnLifecycle` instead.


## repeatOnLifecycle

`repeatOnLifecycle` suspends, then launches its block every time the lifecycle reaches the target state, and cancels it each time the lifecycle falls below that state. This is the correct way to collect flows in Activities and Fragments.

```kotlin
class OrderListActivity : ComponentActivity() {

    private val viewModel: OrderViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                // This block runs when STARTED, cancels when STOPPED,
                // restarts when STARTED again.
                viewModel.uiState.collect { state ->
                    when (state) {
                        is OrderUiState.Loading -> showLoading()
                        is OrderUiState.Success -> showOrders(state.orders)
                        is OrderUiState.Error -> showError(state.message)
                    }
                }
            }
        }
    }
}
```

### Collecting multiple flows

Launch separate coroutines inside `repeatOnLifecycle` so they collect concurrently:

```kotlin
lifecycleScope.launch {
    repeatOnLifecycle(Lifecycle.State.STARTED) {
        launch { viewModel.uiState.collect { updateUi(it) } }
        launch { viewModel.events.collect { handleEvent(it) } }
    }
}
```

### Why repeatOnLifecycle over launchWhenStarted

`launchWhenStarted` / `launchWhenResumed` are **deprecated**. They only **suspend** the coroutine when the lifecycle drops below the target state but keep the upstream Flow active:
- The upstream flow producer keeps emitting while the coroutine is suspended.
- Emissions are buffered, wasting memory and CPU.
- When the lifecycle resumes, all buffered values are delivered at once.

`repeatOnLifecycle` properly **cancels** the block when the lifecycle drops below the state and **restarts** it when the lifecycle returns. No wasted work, no buffered emissions.

```kotlin
// Bad — deprecated, wastes resources
lifecycleScope.launchWhenStarted {
    viewModel.locationUpdates.collect { /* suspended but producer still running */ }
}

// Good — cancels collection, stops upstream work
lifecycleScope.launch {
    repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.locationUpdates.collect { updateLocationUI(it) }
    }
}
```

### flowWithLifecycle — single-flow convenience

```kotlin
lifecycleScope.launch {
    viewModel.uiState
        .flowWithLifecycle(lifecycle, Lifecycle.State.STARTED)
        .collect { updateUI(it) }
}
```

Use `repeatOnLifecycle` when collecting multiple flows. Use `flowWithLifecycle` when collecting a single flow.


## collectAsStateWithLifecycle

The Compose equivalent of `repeatOnLifecycle`. Converts a Flow to Compose `State` while respecting the lifecycle. Stops collection when the composable's lifecycle falls below the specified state.

Dependency: `androidx.lifecycle:lifecycle-runtime-compose`

```kotlin
@Composable
fun OrderListScreen(viewModel: OrderViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    when (val state = uiState) {
        is OrderUiState.Loading -> LoadingIndicator()
        is OrderUiState.Success -> OrderList(state.orders)
        is OrderUiState.Error -> ErrorMessage(state.message)
    }
}
```

### Parameters

```kotlin
// Default — collects while STARTED or above
val state by flow.collectAsStateWithLifecycle()

// Custom lifecycle minimum
val state by flow.collectAsStateWithLifecycle(
    minActiveState = Lifecycle.State.RESUMED,
)

// With initial value for non-StateFlow sources
val results by searchFlow.collectAsStateWithLifecycle(initialValue = emptyList())
```

Always prefer `collectAsStateWithLifecycle()` over `collectAsState()` in Android. The plain `collectAsState` does not stop collection when the app is in the background.


## StateFlow in ViewModels

### stateIn — convert cold Flow to StateFlow

```kotlin
class SearchViewModel(
    private val repository: SearchRepository,
) : ViewModel() {

    private val query = MutableStateFlow("")

    val searchResults: StateFlow<List<Result>> = query
        .debounce(300)
        .filter { it.length >= 2 }
        .flatMapLatest { repository.search(it) }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),
            initialValue = emptyList(),
        )

    fun onQueryChanged(newQuery: String) {
        query.value = newQuery
    }
}
```

### SharingStarted strategies

| Strategy | Upstream active | Use case |
|---|---|---|
| `WhileSubscribed(stopTimeoutMillis)` | While subscribers exist + timeout after last unsubscribe | Most UI state (recommended default) |
| `Eagerly` | Immediately, never stops | Data that must always be fresh (connectivity status) |
| `Lazily` | On first subscriber, never stops | Expensive computation needed for ViewModel lifetime |

`WhileSubscribed(5_000)` is the recommended default for UI state. The 5-second timeout keeps the upstream alive during configuration changes (screen rotation typically completes in under 5 seconds) but releases resources when the user navigates away.

```kotlin
// With replay expiration — reset to initialValue when upstream stops
SharingStarted.WhileSubscribed(
    stopTimeoutMillis = 5_000,
    replayExpirationMillis = 0,  // reset cached value immediately on stop
)
```

### Combining multiple flows

```kotlin
class DashboardViewModel(
    ordersRepo: OrderRepository,
    profileRepo: ProfileRepository,
    notificationRepo: NotificationRepository,
) : ViewModel() {

    private val orders = ordersRepo.observeOrders()
    private val profile = profileRepo.observeProfile()
    private val isRefreshing = MutableStateFlow(false)

    val uiState: StateFlow<DashboardUiState> = combine(
        orders,
        profile,
        isRefreshing,
    ) { orderList, userProfile, refreshing ->
        DashboardUiState(
            orders = orderList,
            profile = userProfile,
            isRefreshing = refreshing,
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = DashboardUiState(),
    )
}
```

### Atomic state updates with MutableStateFlow.update

```kotlin
// Atomic read-modify-write — safe from concurrent coroutines
_uiState.update { current -> current.copy(isLoading = false, items = newItems) }

// Avoid direct assignment when reading previous state — race condition risk
// Bad:
_uiState.value = _uiState.value.copy(isLoading = false)
// Good:
_uiState.update { it.copy(isLoading = false) }
```


## WorkManager

WorkManager is the recommended solution for deferrable, guaranteed background work that must survive process death and device reboots. Uses JobScheduler (API 23+) under the hood.

> **Note:** `androidx.work:work-runtime-ktx` was merged into `work-runtime`. Remove it from dependencies if present.

### When to use WorkManager

| Scenario | Solution |
|---|---|
| Deferrable background task (sync, upload, cleanup) | WorkManager |
| Must complete even after app killed | WorkManager |
| Immediate coroutine work tied to UI | viewModelScope |
| User-visible ongoing operation | Foreground Service |
| Exact time trigger | AlarmManager |

### Worker types

```kotlin
// CoroutineWorker — preferred for async work
class SyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        return try {
            val repository = SyncRepository(applicationContext)
            repository.syncAll()
            Result.success()
        } catch (e: Exception) {
            if (runAttemptCount < 3) Result.retry() else Result.failure()
        }
    }
}
```

Use `Configuration.Builder().setWorkerCoroutineContext(dispatcher)` to control the dispatcher for all CoroutineWorkers — useful for testing.

### Result types

| Result | Behavior |
|---|---|
| `Result.success()` | Work completed. Optionally pass output data via `Result.success(outputData)`. |
| `Result.failure()` | Work failed permanently. Dependent chained work is not executed. |
| `Result.retry()` | Retry with the configured backoff policy. |

### Enqueuing work with constraints

```kotlin
val constraints = Constraints.Builder()
    .setRequiredNetworkType(NetworkType.CONNECTED)
    .setRequiresBatteryNotLow(true)
    .setRequiresStorageNotLow(true)
    .build()

val syncRequest = OneTimeWorkRequestBuilder<SyncWorker>()
    .setConstraints(constraints)
    .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
    .setInputData(workDataOf("userId" to userId))
    .addTag("sync")
    .build()

WorkManager.getInstance(context).enqueueUniqueWork(
    "sync-$userId",
    ExistingWorkPolicy.KEEP,  // KEEP, REPLACE, or APPEND
    syncRequest,
)
```

### Chaining work

```kotlin
WorkManager.getInstance(context)
    .beginWith(listOf(downloadWork, fetchConfigWork))  // parallel
    .then(processWork)                                  // sequential after both complete
    .then(uploadWork)
    .enqueue()
```

### Periodic work

```kotlin
val periodicSync = PeriodicWorkRequestBuilder<SyncWorker>(
    repeatInterval = 1, TimeUnit.HOURS,
    flexInterval = 15, TimeUnit.MINUTES,  // run within last 15 min of each hour
)
    .setConstraints(constraints)
    .build()

WorkManager.getInstance(context).enqueueUniquePeriodicWork(
    "periodic-sync",
    ExistingPeriodicWorkPolicy.UPDATE,
    periodicSync,
)
```

Minimum repeat interval is 15 minutes.

### Expedited work

For urgent work that must start immediately (e.g., user-initiated upload, payment processing). On API 31+, uses JobScheduler expedited jobs. On older APIs, falls back to a foreground service.

```kotlin
val urgentUpload = OneTimeWorkRequestBuilder<UploadWorker>()
    .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
    .build()

WorkManager.getInstance(context).enqueue(urgentUpload)
```

The Worker must override `getForegroundInfo()` to provide a notification (required for pre-API 31 fallback):

```kotlin
class UploadWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun getForegroundInfo(): ForegroundInfo {
        val notification = NotificationCompat.Builder(applicationContext, CHANNEL_ID)
            .setContentTitle("Uploading...")
            .setSmallIcon(R.drawable.ic_upload)
            .build()
        return ForegroundInfo(NOTIFICATION_ID, notification)
    }

    override suspend fun doWork(): Result { /* ... */ }
}
```

### Observing work status

```kotlin
// In ViewModel — observe as Flow
val syncStatus: Flow<WorkInfo?> = WorkManager.getInstance(context)
    .getWorkInfoByIdFlow(syncRequest.id)

// In Compose
@Composable
fun SyncStatusIndicator(workId: UUID) {
    val workInfo by WorkManager.getInstance(LocalContext.current)
        .getWorkInfoByIdFlow(workId)
        .collectAsStateWithLifecycle(initialValue = null)

    when (workInfo?.state) {
        WorkInfo.State.RUNNING -> CircularProgressIndicator()
        WorkInfo.State.SUCCEEDED -> Icon(Icons.Default.Check, contentDescription = "Done")
        WorkInfo.State.FAILED -> Icon(Icons.Default.Error, contentDescription = "Failed")
        else -> {}
    }
}
```


## Testing

The `kotlin-development` skill covers `runTest`, `TestDispatcher`, and basic StateFlow testing. This section covers Android-specific testing patterns.

### MainDispatcherRule — replacing Dispatchers.Main in tests

`Dispatchers.Main` requires the Android main looper, unavailable in unit tests. `viewModelScope` uses `Dispatchers.Main.immediate`, so this rule is required for any ViewModel test:

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    private val testDispatcher: TestDispatcher = UnconfinedTestDispatcher(),
) : TestWatcher() {

    override fun starting(description: Description) {
        Dispatchers.setMain(testDispatcher)
    }

    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
```

### Testing ViewModels

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class OrderViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val fakeRepository = FakeOrderRepository()

    @Test
    fun `loadOrders emits success state`() = runTest {
        val viewModel = OrderViewModel(fakeRepository)

        viewModel.loadOrders()
        advanceUntilIdle()

        assertIs<OrderUiState.Success>(viewModel.uiState.value)
    }

    @Test
    fun `loadOrders emits error on failure`() = runTest {
        fakeRepository.shouldFail = true
        val viewModel = OrderViewModel(fakeRepository)

        viewModel.loadOrders()
        advanceUntilIdle()

        assertIs<OrderUiState.Error>(viewModel.uiState.value)
    }
}
```

### Dispatcher injection for full control

Inject dispatchers as constructor parameters to control execution in tests:

```kotlin
// Production code
class OrderViewModel(
    private val repository: OrderRepository,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {

    fun loadOrders() {
        viewModelScope.launch {
            val orders = withContext(ioDispatcher) { repository.getOrders() }
            _uiState.value = OrderUiState.Success(orders)
        }
    }
}

// Test
@Test
fun `loadOrders with injected dispatcher`() = runTest {
    val testDispatcher = StandardTestDispatcher(testScheduler)
    val viewModel = OrderViewModel(fakeRepository, ioDispatcher = testDispatcher)

    viewModel.loadOrders()
    advanceUntilIdle()

    assertIs<OrderUiState.Success>(viewModel.uiState.value)
}
```

### StandardTestDispatcher vs UnconfinedTestDispatcher

| Dispatcher | Behavior | Use when |
|---|---|---|
| `StandardTestDispatcher` | Coroutines do not run until explicitly advanced (`advanceUntilIdle()`, `advanceTimeBy()`) | You need fine-grained control over execution order and timing |
| `UnconfinedTestDispatcher` | Coroutines run eagerly on `launch` | You want simpler tests; useful for flow collectors that must start immediately |

```kotlin
// StandardTestDispatcher — need advanceUntilIdle() to execute
@Test
fun `with standard dispatcher`() = runTest {
    val states = mutableListOf<OrderUiState>()
    val job = launch(StandardTestDispatcher(testScheduler)) {
        viewModel.uiState.toList(states)
    }
    viewModel.loadOrders()
    advanceUntilIdle()  // required to execute coroutines
    // assert states
    job.cancel()
}

// UnconfinedTestDispatcher — collector starts immediately
@Test
fun `with unconfined dispatcher`() = runTest {
    val states = mutableListOf<OrderUiState>()
    val job = launch(UnconfinedTestDispatcher(testScheduler)) {
        viewModel.uiState.toList(states)
    }
    viewModel.loadOrders()
    advanceUntilIdle()  // still needed if ViewModel work uses delays
    // assert states
    job.cancel()
}
```

### Testing Flows with Turbine

[Turbine](https://github.com/cashapp/turbine) provides a clean API for testing Flow emissions without manual collection boilerplate.

```kotlin
// testImplementation("app.cash.turbine:turbine:<version>")

@Test
fun `search emits results after debounce`() = runTest {
    val viewModel = SearchViewModel(FakeSearchRepository())

    viewModel.searchResults.test {
        // Initial value from stateIn
        assertEquals(emptyList<Result>(), awaitItem())

        viewModel.onQueryChanged("kotlin")
        advanceTimeBy(300)  // debounce delay

        val results = awaitItem()
        assertTrue(results.isNotEmpty())
        assertTrue(results.all { it.title.contains("kotlin", ignoreCase = true) })

        cancelAndIgnoreRemainingEvents()
    }
}
```

### Turbine with SharedFlow (one-shot events)

```kotlin
@Test
fun `shows snackbar on save error`() = runTest {
    val viewModel = EditorViewModel(FailingRepository())

    viewModel.events.test {
        viewModel.save()
        val event = awaitItem()
        assertIs<UiEvent.ShowSnackbar>(event)
        assertEquals("Save failed", event.message)
    }
}
```

### Turbine with combined StateFlow

```kotlin
@Test
fun `dashboard combines user and orders`() = runTest {
    val userRepo = FakeUserRepository()
    val orderRepo = FakeOrderRepository()
    val viewModel = DashboardViewModel(userRepo, orderRepo, FakeNotificationRepository())

    viewModel.uiState.test {
        val initial = awaitItem()
        assertEquals("", initial.userName)

        userRepo.emitUser(User("Alice"))
        orderRepo.emitOrders(listOf(testOrder))

        val updated = expectMostRecentItem()
        assertEquals("Alice", updated.userName)
        assertEquals(1, updated.recentOrders.size)

        cancelAndIgnoreRemainingEvents()
    }
}
```

### Testing WorkManager

Use `TestListenableWorkerBuilder` from the `work-testing` artifact to test Workers in isolation:

```kotlin
// testImplementation("androidx.work:work-testing:<version>")

@Test
fun `SyncWorker returns success on valid data`() = runTest {
    val worker = TestListenableWorkerBuilder<SyncWorker>(
        context = ApplicationProvider.getApplicationContext(),
    )
        .setInputData(workDataOf("userId" to "123"))
        .build()

    val result = worker.doWork()

    assertEquals(ListenableWorker.Result.success(), result)
}

@Test
fun `SyncWorker retries on network error`() = runTest {
    val worker = TestListenableWorkerBuilder<SyncWorker>(
        context = ApplicationProvider.getApplicationContext(),
    )
        .setRunAttemptCount(0)
        .build()

    val result = worker.doWork()

    assertEquals(ListenableWorker.Result.retry(), result)
}
```

### Common test pitfalls

| Pitfall | Fix |
|---|---|
| `Dispatchers.Main` unavailable in unit tests | Use `MainDispatcherRule` to replace with test dispatcher |
| StateFlow `.value` checked before coroutine completes | Call `advanceUntilIdle()` or use Turbine's `awaitItem()` |
| Flaky tests due to timing | Use `StandardTestDispatcher` for deterministic control |
| `stateIn(WhileSubscribed)` not emitting in tests | Ensure a collector is active before triggering; use `UnconfinedTestDispatcher` for the collector coroutine |
| Testing WorkManager without `work-testing` | Use `TestListenableWorkerBuilder`, not a real `WorkManager` instance |
| `runTest` completes before child coroutines finish | Call `advanceUntilIdle()` to drain the test scheduler |
| Turbine `awaitItem()` hangs | Ensure the flow actually emits; check that `advanceUntilIdle()` or `advanceTimeBy()` is called for time-dependent flows |
