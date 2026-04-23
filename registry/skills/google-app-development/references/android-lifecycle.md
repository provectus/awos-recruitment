# Android Lifecycle Reference (Compose-First)

>[toc]


## Activity Lifecycle

### Overview
---
Every Android Activity follows a predictable sequence of callbacks. In a Compose-first app, Activities are thin shells -- they host `setContent {}` and delegate everything else to composables and ViewModels.

#### Callback Sequence

```
onCreate  ->  onStart  ->  onResume
                              |
onPause  ->  onStop  ->  onDestroy
```

| Callback | Lifecycle State | Typical Use | Compose-First Notes |
|----------|----------------|-------------|---------------------|
| `onCreate` | `CREATED` | Call `setContent {}`, set up edge-to-edge, enable predictive back | Primary entry point; keep minimal |
| `onStart` | `STARTED` | Activity becomes visible; register broad observers | Rarely overridden in Compose apps |
| `onResume` | `RESUMED` | Activity gains focus; start camera, sensors, animations | Use `LifecycleEventEffect` instead |
| `onPause` | `STARTED` | Another activity partially covers; pause heavy resources | Commit transient UI state if needed |
| `onStop` | `CREATED` | Activity no longer visible; release UI-bound resources | System may kill process after this |
| `onDestroy` | `DESTROYED` | Activity is finishing or config change | Do NOT rely on this for cleanup -- use ViewModel `onCleared()` |

#### Minimal Compose Activity

```kotlin
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MyAppTheme {
                MyAppNavHost()
            }
        }
    }
}
```

#### Common Pitfalls

- **Leaking references**: Never hold a reference to `Activity` or `Context` inside a ViewModel. Use `applicationContext` when absolutely necessary.
- **Heavy work in `onCreate`**: heavy I/O blocks the main thread and delays first frame. Offload initialization to coroutines scoped to a ViewModel or the App Startup library.
- **Assuming `onDestroy` is called**: The system can kill the process without calling `onDestroy`. Persist critical state via `SavedStateHandle` or `rememberSaveable`.
- **Recreating work on config change**: If you launch a coroutine in `onCreate` without scoping it to a ViewModel, it restarts on every rotation.
- **Ignoring multi-window / PiP**: in multi-window mode an Activity can be in `STARTED` (visible) but not `RESUMED`. Do not gate essential UI updates on `onResume` alone.


## Fragment Lifecycle

### Fragment vs View Lifecycle
---
Fragments have **two** distinct lifecycles:

1. **Fragment lifecycle** (`onCreate` -> `onDestroy`) -- tied to the Fragment instance.
2. **View lifecycle** (`onCreateView` -> `onDestroyView`) -- tied to the Fragment's view hierarchy. Accessible via `viewLifecycleOwner`.

```
Fragment:  onCreate ---------------------------------------- onDestroy
View:              onCreateView -- onDestroyView
                   (may repeat when back-stacked)
```

When a Fragment is on the back stack, its view is destroyed (`onDestroyView`) but the Fragment instance survives. This means:
- `viewLifecycleOwner` is scoped to the view and is the correct owner for UI observations.
- The Fragment's own lifecycle outlives the view -- observing on `this` instead of `viewLifecycleOwner` causes duplicate observers and leaks.

#### viewLifecycleOwner in Practice

```kotlin
// CORRECT -- scoped to view lifecycle
viewLifecycleOwner.lifecycleScope.launch {
    viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.uiState.collect { state -> /* update UI */ }
    }
}

// WRONG -- survives view destruction, leaks observers across view recreations
lifecycleScope.launch {
    repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.uiState.collect { state -> /* update UI */ }
    }
}
```

### When to Use Fragments in Compose-First Apps
---
In a Compose-first architecture, Fragments are generally **unnecessary**. Prefer Compose Navigation (`NavHost`, `composable()` destinations). Valid exceptions:

- **Legacy interop**: Existing Fragment-based features being migrated incrementally.
- **Third-party SDKs**: Some SDKs (e.g., Maps, CameraX viewfinder) still require Fragment or View hosts.
- **Multi-module navigation with legacy modules**: When some modules still use Fragment-based navigation.

For new features, use composable destinations with `NavHost` instead of Fragments. If you must mix, host Compose inside a Fragment via `ComposeView` in `onCreateView` and scope state to `viewLifecycleOwner`.


## ViewModel

### Creation and Scoping
---
ViewModels survive configuration changes and are scoped to a `ViewModelStoreOwner` (Activity, Fragment, or `NavBackStackEntry`).

#### Basic ViewModel with Hilt

```kotlin
@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val userRepository: UserRepository,
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {

    val userId: String = savedStateHandle["userId"]
        ?: error("userId argument is required")

    val uiState: StateFlow<ProfileUiState> = userRepository
        .observeUser(userId)
        .map { ProfileUiState.Success(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), ProfileUiState.Loading)
}
```

#### Accessing in Compose

```kotlin
// Scoped to the nearest NavBackStackEntry (default with Hilt Navigation Compose)
@Composable
fun ProfileScreen(
    viewModel: ProfileViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    // ...
}

// Scoped to Activity (shared ViewModel)
@Composable
fun SomeChildScreen(
    sharedViewModel: SharedViewModel = hiltViewModel(
        viewModelStoreOwner = LocalContext.current as ComponentActivity
    )
) { /* ... */ }

// Scoped to parent nav graph
@Composable
fun FeatureScreen(
    navController: NavController,
    viewModel: FeatureSharedViewModel = hiltViewModel(
        viewModelStoreOwner = navController.getBackStackEntry("feature_graph")
    )
) { /* ... */ }
```

### SavedStateHandle
---
`SavedStateHandle` is a key-value map that survives **process death**. Hilt automatically provides it.

```kotlin
@HiltViewModel
class SearchViewModel @Inject constructor(
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {

    // Automatically saved and restored across process death
    val query = savedStateHandle.getStateFlow("query", "")

    // Alternative: property delegate with Compose state
    var queryState by savedStateHandle.saveable { mutableStateOf("") }
        private set

    fun onQueryChange(newQuery: String) {
        savedStateHandle["query"] = newQuery
    }
}
```

#### saved() Property Delegate (Lifecycle 2.9+)

A lazy property delegate that works with `@Serializable` classes. Automatically saves and restores across process death with minimal boilerplate.

```kotlin
@Serializable
data class FormData(val name: String = "", val email: String = "")

@HiltViewModel
class FormViewModel @Inject constructor(
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {

    // Automatically saved and restored across process death
    var formData by savedStateHandle.saved { FormData() }
        private set

    fun updateName(name: String) {
        formData = formData.copy(name = name)
    }
}
```

Use `saved()` for structured state objects. Use `getStateFlow()` when you need reactive observation of individual values.

Rules for `SavedStateHandle`:
- Store only small, serializable data (IDs, query strings, scroll positions).
- Do not store large objects (bitmaps, lists of hundreds of items). Use a local database or cache instead.
- Maximum bundle size is ~1 MB across the entire saved state tree; exceeding it causes a `TransactionTooLargeException`.

### CreationExtras
---
`CreationExtras` (Lifecycle 2.5+) provide a type-safe way to pass arguments to ViewModel factories without custom `ViewModelProvider.Factory` boilerplate.

```kotlin
class MyViewModel(
    private val repository: Repository,
    private val itemId: String,
) : ViewModel() {

    companion object {
        val ITEM_ID_KEY = object : CreationExtras.Key<String> {}

        val Factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>, extras: CreationExtras): T {
                val app = extras[APPLICATION_KEY] as MyApplication
                val itemId = extras[ITEM_ID_KEY] ?: error("itemId required")
                @Suppress("UNCHECKED_CAST")
                return MyViewModel(app.repository, itemId) as T
            }
        }
    }
}
```

With Hilt, `CreationExtras` are rarely needed directly -- Hilt's `@AssistedInject` or `SavedStateHandle` cover most use cases.

### Scoping Strategies
---

| Scope | Owner | When to Use |
|-------|-------|-------------|
| Activity | `ComponentActivity` | App-wide shared state (auth, theme) |
| Navigation graph | `NavBackStackEntry` (nested graph) | Feature-level state (multi-screen wizard) |
| Destination | `NavBackStackEntry` | Screen-level state (default) |

Avoid scoping ViewModels to the Activity unless the data genuinely needs to outlive individual screens. Over-scoping leads to memory waste and unclear ownership.


## Configuration Changes

### What Triggers a Config Change
---

| Trigger | Default Behavior | `configChanges` Override |
|---------|-----------------|--------------------------|
| Screen rotation | Activity destroyed and recreated | `orientation\|screenSize` |
| Dark/light mode toggle | Activity destroyed and recreated | `uiMode` |
| Locale change | Activity destroyed and recreated | `locale` |
| Font size change | Activity destroyed and recreated | `fontScale` |
| Multi-window resize | Activity destroyed and recreated | `screenSize\|smallestScreenSize\|screenLayout` |
| Keyboard availability | Activity destroyed and recreated | `keyboard\|keyboardHidden` |

### What Survives and What Does Not

| Mechanism | Survives Config Change | Survives Process Death |
|-----------|:---------------------:|:---------------------:|
| `ViewModel` | Yes | No |
| `SavedStateHandle` | Yes | Yes |
| `rememberSaveable` | Yes | Yes |
| `remember` | No | No |
| Static / global state | Yes | No |
| Local variable | No | No |
| SharedPreferences / DataStore | Yes | Yes |
| Room database | Yes | Yes |

### Handling in Compose

```kotlin
@Composable
fun CounterScreen(viewModel: CounterViewModel = hiltViewModel()) {
    // Survives config change (ViewModel) AND process death (SavedStateHandle)
    val count by viewModel.count.collectAsStateWithLifecycle()

    // Survives config change AND process death
    var userInput by rememberSaveable { mutableStateOf("") }

    // Lost on config change
    var ephemeral by remember { mutableStateOf(false) }
}
```

### Overriding Config Changes (Use Sparingly)
---

```xml
<!-- AndroidManifest.xml -- prevents recreation but you must handle changes manually -->
<activity
    android:name=".MainActivity"
    android:configChanges="orientation|screenSize|uiMode|locale" />
```

```kotlin
class MainActivity : ComponentActivity() {
    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        // Manually handle the change -- Compose recomposes automatically for most cases
    }
}
```

Overriding `configChanges` is **discouraged** in Compose-first apps. Compose handles recomposition naturally; let the system recreate the Activity and rely on ViewModel + SavedStateHandle. The override is acceptable only for performance-sensitive surfaces (video players, games) where recreation is too expensive.


## Process Death

### Overview
---
Android can kill a backgrounded process at any time to reclaim memory. When the user returns, the system recreates the Activity and restores the saved instance state bundle.

**Key distinction**: ViewModel instances are destroyed. Only `SavedStateHandle` and `rememberSaveable` data survive.

#### What is Preserved

- Anything written to `SavedStateHandle`.
- Composable state stored via `rememberSaveable`.
- Navigation back stack (Navigation component serializes it automatically).
- Pending intents and alarms.
- SharedPreferences, DataStore, Room data (persisted to disk).

#### What is Lost

- ViewModel instances and all in-memory data.
- Singleton / object state.
- Coroutine jobs.
- Network connections, open files.

### SavedStateHandle for Process Death
---

```kotlin
@HiltViewModel
class FormViewModel @Inject constructor(
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {

    // These survive process death
    val name = savedStateHandle.getStateFlow("name", "")
    val email = savedStateHandle.getStateFlow("email", "")

    fun updateName(value: String) { savedStateHandle["name"] = value }
    fun updateEmail(value: String) { savedStateHandle["email"] = value }
}
```

### rememberSaveable in Compose
---

```kotlin
@Composable
fun FormScreen() {
    // Primitives -- saved automatically
    var text by rememberSaveable { mutableStateOf("") }

    // Custom objects -- provide a Saver
    var selection by rememberSaveable(stateSaver = SelectionSaver) {
        mutableStateOf(Selection.None)
    }
}

// Custom Saver using mapSaver
val SelectionSaver = mapSaver(
    save = { mapOf("id" to it.id, "label" to it.label) },
    restore = { Selection(id = it["id"] as String, label = it["label"] as String) }
)

// Custom Saver using Saver directly
val MyItemSaver = Saver<MyItem, Bundle>(
    save = { bundleOf("id" to it.id, "name" to it.name) },
    restore = { MyItem(it.getString("id")!!, it.getString("name")!!) }
)
```

### Testing Process Death
---

#### Manual Testing

1. **"Don't keep activities"**: Enable **Developer Options > Don't keep activities** to simulate aggressive destruction. Open your app, navigate to the screen under test, press Home, then return via Recents. Verify all user-visible state is restored. Note: this destroys Activities on every navigation, which is more aggressive than real process death.
2. **Android Studio**: Run -> "Terminate Application" while the app is in the background, then relaunch from the recents screen.
3. **ADB**: `adb shell am kill <package_name>` (the app must be backgrounded first).

#### Automated Testing

```kotlin
// ActivityScenario-based test
@Test
fun savedState_survives_processRecreation() {
    val scenario = launchActivity<MainActivity>()
    // Enter data ...
    scenario.recreate() // Simulates process death + recreation
    // Assert data is restored
}

// ViewModel unit test with SavedStateHandle
@Test
fun `restores query after process death`() {
    val savedState = SavedStateHandle(mapOf("query" to "test"))
    val viewModel = SearchViewModel(savedState)

    assertEquals("test", viewModel.query.value)
}
```


## Navigation Component

### NavController Lifecycle
---
`NavController` manages a back stack of `NavBackStackEntry` objects. Each entry is a `LifecycleOwner` and `ViewModelStoreOwner`.

| Event | When |
|-------|------|
| `CREATED` | Destination pushed onto back stack |
| `STARTED` | Destination visible (e.g., under a dialog or in multi-pane) |
| `RESUMED` | Destination is on top, fully interactive |
| `DESTROYED` | Destination popped off back stack; its ViewModels are cleared |

### Compose NavHost Setup

```kotlin
@Composable
fun MyAppNavHost(
    navController: NavHostController = rememberNavController(),
    startDestination: String = "home",
) {
    NavHost(navController = navController, startDestination = startDestination) {
        composable("home") {
            HomeScreen(onNavigateToDetail = { id ->
                navController.navigate("detail/$id")
            })
        }
        composable(
            route = "detail/{itemId}",
            arguments = listOf(navArgument("itemId") { type = NavType.StringType }),
        ) {
            DetailScreen()
        }
    }
}
```

### Back Stack Management
---

```kotlin
// Navigate and clear back stack up to "home", avoiding duplicate entries
navController.navigate("settings") {
    popUpTo("home") { inclusive = false }
    launchSingleTop = true
}

// Navigate and pop the current destination (replace)
navController.navigate("home") {
    popUpTo("login") { inclusive = true }
    launchSingleTop = true
}

// Pop back to a specific destination
navController.popBackStack("home", inclusive = false)

// Bottom navigation pattern -- single instance of each tab
fun NavHostController.navigateToTab(route: String) {
    navigate(route) {
        popUpTo(graph.findStartDestination().id) {
            saveState = true
        }
        launchSingleTop = true
        restoreState = true
    }
}
```

#### popUpTo vs launchSingleTop

| Option | Behavior |
|--------|----------|
| `popUpTo("route")` | Pops all destinations above `route` before navigating |
| `inclusive = true` | Also pops the `route` destination itself |
| `launchSingleTop = true` | If destination is already on top of back stack, do not create a new instance |
| `saveState = true` | Save the state of popped destinations (for bottom nav) |
| `restoreState = true` | Restore previously saved state when navigating back |

Key rules:
- Always use `launchSingleTop = true` for tabs and root destinations to avoid duplicate entries.
- Use `popUpTo` with `inclusive = true` when replacing flows (e.g., after login -> home).
- Do not hold references to `NavBackStackEntry` outside of composition -- it may be destroyed.

### Result Sharing Between Destinations
---
Use `SavedStateHandle` on the **previous** back stack entry to pass results backward without tight coupling:

```kotlin
// In destination B -- set the result
navController.previousBackStackEntry
    ?.savedStateHandle
    ?.set("selected_item_id", itemId)
navController.popBackStack()

// In destination A -- observe the result
val result = navController.currentBackStackEntry
    ?.savedStateHandle
    ?.getStateFlow<String?>("selected_item_id", null)
    ?.collectAsStateWithLifecycle()
```

For complex flows, prefer a shared ViewModel scoped to a nested navigation graph.


## Lifecycle-Aware Components

### DefaultLifecycleObserver
---
Use when you need to react to lifecycle events from non-Compose code (e.g., a manager class, analytics tracker).

```kotlin
class AnalyticsTracker(
    private val analytics: Analytics,
) : DefaultLifecycleObserver {

    override fun onResume(owner: LifecycleOwner) {
        analytics.trackScreenView(owner::class.simpleName ?: "Unknown")
    }

    override fun onPause(owner: LifecycleOwner) {
        analytics.trackScreenExit()
    }
}

// Register in Activity or via Hilt
class MainActivity : ComponentActivity() {
    @Inject lateinit var tracker: AnalyticsTracker

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        lifecycle.addObserver(tracker)
        setContent { AppContent() }
    }
}
```

### LifecycleEventEffect in Compose
---
Preferred approach in Compose for reacting to lifecycle events (Lifecycle 2.7+).

```kotlin
@Composable
fun PlayerScreen(viewModel: PlayerViewModel = hiltViewModel()) {

    // Runs when the composable reaches ON_RESUME, cleans up on ON_PAUSE
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) {
        viewModel.startPlayback()
    }

    LifecycleEventEffect(Lifecycle.Event.ON_PAUSE) {
        viewModel.pausePlayback()
    }

    // For paired start/stop behavior
    LifecycleStartEffect(Unit) {
        viewModel.connectSensor()
        onStopOrDispose {
            viewModel.disconnectSensor()
        }
    }

    // For paired resume/pause behavior
    LifecycleResumeEffect(Unit) {
        viewModel.resumeUpdates()
        onPauseOrDispose {
            viewModel.pauseUpdates()
        }
    }
}
```

### Observing Lifecycle State as Compose State
---

```kotlin
@Composable
fun MyScreen() {
    val lifecycleOwner = LocalLifecycleOwner.current
    val lifecycleState by lifecycleOwner.lifecycle.currentStateFlow
        .collectAsStateWithLifecycle()

    if (lifecycleState.isAtLeast(Lifecycle.State.RESUMED)) {
        // Only perform work when fully resumed
    }
}
```

### DisposableEffect for Manual Observer Management
---

```kotlin
@Composable
fun LocationTracker(locationClient: FusedLocationProviderClient) {
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> locationClient.requestUpdates()
                Lifecycle.Event.ON_STOP -> locationClient.removeUpdates()
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)

        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }
}
```

### collectAsStateWithLifecycle
---
The lifecycle-aware alternative to `collectAsState`. Stops collection when the UI is not visible, reducing wasted work.

```kotlin
@Composable
fun DashboardScreen(viewModel: DashboardViewModel = hiltViewModel()) {
    // Collection pauses when lifecycle drops below STARTED (default)
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    // Custom minimum lifecycle state
    val backgroundState by viewModel.backgroundData
        .collectAsStateWithLifecycle(minActiveState = Lifecycle.State.CREATED)
}
```


## App Startup

### Application Class
---
The `Application` class is created before any Activity and lives for the entire process lifetime. Use it sparingly.

```kotlin
@HiltAndroidApp
class MyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Minimal setup: logging, crash reporting, strict mode (debug)
        if (BuildConfig.DEBUG) {
            StrictMode.enableDefaults()
        }
    }
}
```

Things that belong here: DI initialization (Hilt `@HiltAndroidApp`), crash reporting (Firebase Crashlytics), strict mode, Timber/logging setup.

Things that do **not** belong here: heavy I/O, network calls, UI setup, anything that can be deferred.

### ProcessLifecycleOwner
---
Tracks the entire app's foreground/background state (not individual Activities).

| Event | Meaning |
|-------|---------|
| `ON_START` | App moved to foreground (at least one Activity started) |
| `ON_STOP` | App moved to background (no Activities started) -- delayed ~700ms to ignore config changes |
| `ON_RESUME` / `ON_PAUSE` | Mirrors foreground Activity |
| `ON_DESTROY` | **Never** emitted |

```kotlin
class AppLifecycleObserver @Inject constructor(
    private val analytics: Analytics,
) : DefaultLifecycleObserver {

    override fun onStart(owner: LifecycleOwner) {
        // App moved to foreground
        analytics.trackAppOpen()
    }

    override fun onStop(owner: LifecycleOwner) {
        // App moved to background (all Activities stopped)
        analytics.trackAppBackground()
    }
}

// Register in Application.onCreate or via Hilt initializer
ProcessLifecycleOwner.get().lifecycle.addObserver(appLifecycleObserver)
```

### App Startup Library (Jetpack)
---
Replaces `ContentProvider`-based initialization with a more efficient, dependency-ordered mechanism.

```kotlin
// 1. Define Initializers
class TimberInitializer : Initializer<Unit> {
    override fun create(context: Context) {
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }
    }

    override fun dependencies(): List<Class<out Initializer<*>>> = emptyList()
}

class AnalyticsInitializer : Initializer<Unit> {
    override fun create(context: Context) {
        Analytics.init(context)
    }

    // Depends on Timber being initialized first
    override fun dependencies(): List<Class<out Initializer<*>>> =
        listOf(TimberInitializer::class.java)
}
```

```xml
<!-- 2. Register in AndroidManifest.xml -->
<provider
    android:name="androidx.startup.InitializationProvider"
    android:authorities="${applicationId}.androidx-startup"
    android:exported="false"
    tools:node="merge">
    <meta-data
        android:name="com.example.AnalyticsInitializer"
        android:value="androidx.startup" />
</provider>
```

### Splash Screen API (Android 12+)
---

```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        val splashScreen = installSplashScreen()

        // Keep splash visible while loading initial data
        splashScreen.setKeepOnScreenCondition {
            viewModel.isLoading.value
        }

        // Optional exit animation
        splashScreen.setOnExitAnimationListener { provider ->
            provider.view.animate()
                .alpha(0f)
                .setDuration(300L)
                .withEndAction { provider.remove() }
                .start()
        }

        super.onCreate(savedInstanceState)

        setContent {
            MyAppTheme {
                MyAppNavHost()
            }
        }
    }
}
```

Theme configuration in `res/values/themes.xml`:

```xml
<style name="Theme.App.Starting" parent="Theme.SplashScreen">
    <item name="windowSplashScreenBackground">@color/splash_bg</item>
    <item name="windowSplashScreenAnimatedIcon">@drawable/ic_launcher_foreground</item>
    <item name="postSplashScreenTheme">@style/Theme.App</item>
</style>
```


## Multi-Activity vs Single-Activity

### Decision Framework
---

#### Single-Activity (Default and Recommended)

The modern Android recommendation is a **single Activity** with Compose Navigation. This is the default for all new Compose-first projects.

| Aspect | Single-Activity | Multi-Activity |
|--------|----------------|----------------|
| Navigation | Compose Navigation / NavHost | Intent-based, each screen is an Activity |
| Shared state | ViewModel scoped to Activity or nav graph | Requires IPC or shared persistence |
| Animations | Smooth, customizable transitions | System Activity transitions |
| Deep links | Handled by NavController | Each Activity declares intent filters |
| Complexity | Lower for most apps | Higher coordination overhead |
| Back stack | Managed by NavController | Managed by Activity task stack |

**Advantages of single-Activity:**
- Simpler shared state via navigation-graph-scoped ViewModels.
- Smoother transitions and animations (no Activity transition overhead).
- Consistent back stack management through `NavController`.
- Easier deep link handling — one entry point for custom routing.
- Better support for edge-to-edge, predictive back gestures, and Material transitions.

**Architecture:**

```
MainActivity (setContent)
  |-- NavHost
        |-- HomeScreen
        |-- DetailScreen
        |-- SettingsGraph (nested)
        |     |-- SettingsScreen
        |     |-- ProfileScreen
        |-- AuthGraph (nested)
              |-- LoginScreen
              |-- RegisterScreen
```

#### When Multi-Activity is Appropriate

| Scenario | Reason |
|----------|--------|
| Separate process needed | e.g., video playback in `:player` process |
| Third-party SDK requires its own Activity | Payment SDKs, OAuth redirect Activities |
| Different launch modes (`singleTask`, `singleInstance`) | Task/affinity isolation for notifications |
| Wear OS, TV, or Auto targets | Platform may mandate separate Activities |
| Large legacy codebase | Gradual migration -- keep existing Activities, add Compose incrementally |
| Picture-in-picture, floating windows | Separate task affinity |

#### Anti-Patterns

- Using multiple Activities solely for "code separation" -- use navigation graphs and feature modules instead.
- Passing large data between Activities via Intent extras -- use an ID and load from repository.
- Overriding `onBackPressed()` -- use `OnBackPressedDispatcher` or predictive back APIs.

### Recommended Single-Activity Pattern

```kotlin
// One Activity, one NavHost, multiple composable destinations
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MyAppTheme {
                val navController = rememberNavController()
                Scaffold(
                    bottomBar = { BottomNavBar(navController) }
                ) { padding ->
                    NavHost(
                        navController = navController,
                        startDestination = "home",
                        modifier = Modifier.padding(padding),
                    ) {
                        composable("home") { HomeScreen(navController) }
                        composable("search") { SearchScreen(navController) }
                        composable("profile") { ProfileScreen(navController) }
                        navigation(startDestination = "settings/main", route = "settings") {
                            composable("settings/main") { SettingsScreen(navController) }
                            composable("settings/notifications") { NotificationsScreen(navController) }
                        }
                    }
                }
            }
        }
    }
}
```


## Predictive Back and Edge-to-Edge

### Predictive Back
---
Recent Android versions enable predictive back system animations by default. `onBackPressed()` is no longer called and `KeyEvent.KEYCODE_BACK` is not dispatched for apps targeting these versions.

**Required migration:**
- **Compose**: Use `BackHandler` for simple back handling. Use `PredictiveBackHandler` for custom progress-based back animations.
- **Views**: Use `OnBackPressedDispatcher` and register `OnBackPressedCallback`.
- **Never** override `onBackPressed()` or intercept `KEYCODE_BACK` directly.

```kotlin
// Compose — simple back handling
BackHandler(enabled = showDialog) {
    dismissDialog()
}

// Compose — predictive back with animation progress
PredictiveBackHandler { progress: Flow<BackEventCompat> ->
    progress.collect { event ->
        // event.progress: 0.0 to 1.0
        // Animate UI based on progress
    }
}
```

### Edge-to-Edge
---
Edge-to-edge rendering is mandatory on recent platform versions. Call `enableEdgeToEdge()` in `onCreate` before `setContent`.

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    enableEdgeToEdge()
    setContent { AppTheme { AppNavHost() } }
}
```

Handle system bar insets in your layouts:

```kotlin
Modifier
    .fillMaxSize()
    .systemBarsPadding() // or use WindowInsets.systemBars with padding()
```

The legacy opt-out (`windowOptOutEdgeToEdgeEnforcement`) is deprecated and will be removed in a future platform version.


## Deep Links and Intents

### Intent Filters in AndroidManifest
---

```xml
<activity
    android:name=".MainActivity"
    android:exported="true"
    android:launchMode="singleTop">

    <!-- App Links (verified, HTTPS only) -->
    <intent-filter android:autoVerify="true">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data
            android:scheme="https"
            android:host="www.example.com"
            android:pathPrefix="/product" />
    </intent-filter>

    <!-- Custom scheme deep link -->
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data
            android:scheme="myapp"
            android:host="open" />
    </intent-filter>
</activity>
```

Enable **App Links verification** (`android:autoVerify="true"`) and host a `/.well-known/assetlinks.json` file on your domain for `https` links.

### Custom Deep Link Routing (Recommended)
---

Intercept deep links at the Activity level and route them through your own navigation logic. This gives full control over auth checks, conditional navigation, and back stack construction — unlike `navDeepLink` which couples URIs directly to composable destinations.

```kotlin
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val navController = rememberNavController()
            MyAppTheme {
                MyAppNavHost(navController = navController)
            }
            // Route the initial deep link after composition
            LaunchedEffect(Unit) {
                intent?.let { routeDeepLink(it, navController) }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // Handle deep links arriving while the Activity is already running
        routeDeepLink(intent, navController)
    }
}
```

#### Deep Link Router

Centralize all URI → navigation mapping in a single router. This is the place to add auth gates, feature flags, and conditional redirects.

```kotlin
fun routeDeepLink(intent: Intent, navController: NavController) {
    val uri = intent.data ?: return

    when {
        // https://www.example.com/product/{id} or myapp://open/product/{id}
        uri.pathSegments.firstOrNull() == "product" -> {
            val productId = uri.lastPathSegment ?: return
            navController.navigate("product/$productId")
        }

        // https://www.example.com/user/{id}
        uri.pathSegments.firstOrNull() == "user" -> {
            val userId = uri.lastPathSegment ?: return
            // Auth gate: redirect to login if needed, then forward
            if (!isUserLoggedIn()) {
                navController.navigate("login?redirect=user/$userId")
            } else {
                navController.navigate("user/$userId")
            }
        }

        // Custom actions
        intent.action == "com.example.ACTION_SHOW_NOTIFICATION" -> {
            val notificationId = intent.getStringExtra("notification_id") ?: return
            navController.navigate("notifications/$notificationId")
        }
    }
}
```

#### Why Custom Routing over navDeepLink

| Concern | `navDeepLink` | Custom routing |
|---------|---------------|----------------|
| Auth gates | Not supported — navigates directly | Full control — redirect to login, then forward |
| Conditional navigation | Not supported | Check state, feature flags, A/B tests before routing |
| Complex back stacks | Limited | Build arbitrary back stacks via `NavOptions` |
| Centralized logging | Scattered across graph | Single entry point for analytics and debugging |
| Refactoring | URI patterns coupled to route names | URIs decoupled — change routes without breaking links |

> **Note:** `navDeepLink { uriPattern = ... }` is available in Compose Navigation for simple cases where URIs map 1:1 to destinations with no intermediate logic. For most production apps, prefer custom routing.

### Implicit vs Explicit Deep Links

| Type | Mechanism | Use Case |
|------|-----------|----------|
| **Implicit** | URI-based intent filter → custom router | External links (browser, email, other apps) |
| **Explicit** | `PendingIntent` with `TaskStackBuilder` | Notifications, widgets, shortcuts |

### PendingIntent (Notifications, Widgets, Alarms)
---

```kotlin
fun createDeepLinkPendingIntent(context: Context, itemId: String): PendingIntent {
    val deepLinkIntent = Intent(
        Intent.ACTION_VIEW,
        "https://www.example.com/product/$itemId".toUri(),
        context,
        MainActivity::class.java,
    )

    return TaskStackBuilder.create(context).run {
        addNextIntentWithParentStack(deepLinkIntent)
        getPendingIntent(
            itemId.hashCode(),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )!!
    }
}
```

### Key Rules for Deep Links
---
- Always use `FLAG_IMMUTABLE` for PendingIntents targeting Android 12+.
- Validate and sanitize all incoming deep link parameters — they are untrusted external input.
- Test deep links via ADB: `adb shell am start -a android.intent.action.VIEW -d "https://www.example.com/product/123" com.example.app`.
- Handle the case where a deep link targets a destination that requires authentication — redirect to login first, then forward to the original destination after auth completes.
- For custom schemes (`myapp://`), consider migrating to App Links (`https://`) for better security and user experience.
