---
name: google-app-development
description: "This skill should be used when the user asks to \"build an Android app\", \"create a Composable\", \"set up an Android project\", \"review Android code\", \"refactor Android\", \"add a screen\", \"create a Wear OS app\", \"build for Android TV\", \"build for Android Auto\", \"build for Android Automotive\", \"adapt for Meta Quest\", \"build for Fire TV\", \"build for Fire Tablet\", \"set up Room database\", \"add local storage\", \"use DataStore\", \"persist data\", \"add database migration\", \"encrypt storage\", \"add in-app purchases\", \"integrate Google Play Billing\", \"add subscriptions\", \"implement billing\", \"monetize app\", \"write Android tests\", \"test ViewModel\", \"test Composable\", \"set up Android testing\", \"add unit tests\", \"configure Android Lint\", \"add custom lint rule\", \"set up lint baseline\", or when generating any Kotlin code targeting Google/Android platforms (including AOSP-based devices). Provides modern Jetpack Compose-first best practices covering UI patterns, app lifecycle, navigation, local storage, billing/payments, testing, Android Lint, and platform-specific guidance. Use together with `kotlin-development` for language fundamentals. Always generates Kotlin unless the project explicitly requires Java."
version: 0.1.0
---

# Google App Development (Jetpack Compose / Kotlin)

Modern best practices for building apps across Google platforms. Targets Jetpack Compose as the primary UI framework with Kotlin. Covers Android (phone), tablet, foldables, Wear OS, Google TV / Android TV, Android Auto, Android Automotive OS, and AOSP-based platforms (Meta Quest, Amazon Fire TV, Amazon Fire Tablets).

For Kotlin language fundamentals (null safety, coroutines, data modeling, error handling, idiomatic patterns), see the `kotlin-development` skill. This skill focuses on platform and framework patterns.

## Important Rules

- **Always generate Kotlin.** Only write Java when the project explicitly requires it (legacy codebase, Java-only API). See `references/java-interop.md` for bridging patterns.
- **Compose-first.** Use View-based UI only when Compose lacks the capability or the project has an existing View-based codebase. See `references/view-interop.md` for interop patterns.
- **Check the project context.** Before applying patterns, check the `minSdk`, Compose BOM version, and existing architecture. Adapt recommendations accordingly.

## Reference Files

- **`references/compose-patterns.md`** — Composables, state hoisting, recomposition, `remember`, `LazyColumn`, navigation, theming, Material 3, side effects
- **`references/concurrency.md`** — Coroutines in Android context: `viewModelScope`, `lifecycleScope`, `repeatOnLifecycle`, WorkManager, foreground services
- **`references/android-lifecycle.md`** — Activity/Fragment lifecycle, `ViewModel`, saved state, process death, configuration changes
- **`references/view-interop.md`** — `AndroidView`, `ComposeView`, embedding Compose in Views and Views in Compose, migration strategies
- **`references/project-structure.md`** — Gradle setup, multi-module architecture, build variants, version catalogs, convention plugins
- **`references/tablet-patterns.md`** — Adaptive layouts, `WindowSizeClass`, multi-window, foldable devices, large screen guidelines
- **`references/wear-os-patterns.md`** — Compose for Wear OS, Tiles, complications, Health Services, watch face
- **`references/tv-patterns.md`** — Compose for TV, focus management, Leanback, D-pad navigation, Google TV / Android TV
- **`references/android-auto-patterns.md`** — Car App Library, templates, phone projection, media apps, messaging apps
- **`references/android-automotive-patterns.md`** — Android Automotive OS (AAOS), embedded car system, car hardware APIs, system UI
- **`references/java-interop.md`** — Calling Java from Kotlin, nullability annotations, SAM conversions, incremental migration
- **`references/meta-quest-patterns.md`** — Adapting Android APK for Meta Quest, spatial UI, entitlement check, VR input, passthrough
- **`references/local-storage.md`** — Room database (entities, DAOs, relations, migrations, testing), DataStore (Preferences and Proto), encrypted storage (Android Keystore, DataStore + Tink, SQLCipher), file storage (internal, scoped storage, FileProvider), storage selection guide
- **`references/networking-api.md`** — Retrofit, OkHttp, Ktor Client, JSON serialization, repository pattern, error handling, interceptors, certificate pinning, caching, connectivity, Paging 3, file upload/download, testing
- **`references/fire-tv-patterns.md`** — Amazon Fire TV, Appstore, Amazon IAP, Alexa integration, missing Google Play Services
- **`references/media-playback.md`** — Media3 / ExoPlayer, MediaSession, audio focus, Picture-in-Picture, offline downloads, DRM, streaming formats, caching
- **`references/billing-payments.md`** — Google Play Billing Library (PBL 8), BillingClient, one-time purchases (consumable / non-consumable), subscriptions (base plans, offers, replacement modes), subscription offers (eligibility types, pricing phases, offer tags, developer-determined offers, winback offers, promo codes), purchase verification, RTDN, subscription lifecycle (grace period, account hold, pause), alternative billing, testing
- **`references/fire-tablet-patterns.md`** — Amazon Fire Tablets, device capabilities, Show Mode, Kids Edition, Special Offers
- **`references/testing.md`** — JUnit 5, MockK, Turbine, ViewModel testing, Compose UI testing, Robolectric, Room in-memory testing, Hilt testing, Espresso, coroutine testing (`runTest`, `TestDispatcher`), test architecture (pyramid, MVI/MVVM strategies), fakes vs mocks, CI integration
- **`references/code-quality.md`** — Android Lint configuration (`lint {}` block, `lint.xml`, severity levels), baseline management, suppression (`@SuppressLint`, `tools:ignore`), built-in check categories (correctness, security, performance, accessibility), Compose lint checks, custom lint rules (`Detector`, `Issue`, `IssueRegistry`), CI integration (SARIF, GitHub Code Scanning), multi-module convention plugin. For Detekt/ktlint, see `kotlin-development` skill's `references/static-analysis.md`

## Code Style

For Kotlin language style (naming, null safety, type annotations), follow the `kotlin-development` skill. Below are Android/Compose-specific conventions.

- **Composable naming** — `PascalCase` for UI-emitting composables, `camelCase` for composables that return values.
- **Modifier parameter** — always the first optional parameter, default to `Modifier`.
- **Preview functions** — prefix with `Preview`, annotate with `@Preview`.
- **Define a custom app theme and apply it at the root.** Every app must have a custom `AppTheme` composable that wraps `MaterialTheme` with app-specific colors, typography, and shapes. Apply it once at the top level (`setContent { AppTheme { ... } }`). All UI code must reference theme tokens — never raw values.

```kotlin
// 1. Define custom theme (once, in ui/theme/)
@Composable
fun AppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) AppDarkColorScheme else AppLightColorScheme
    MaterialTheme(
        colorScheme = colorScheme,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}

// 2. Apply at root (once)
setContent { AppTheme { AppNavGraph() } }

// 3. Use theme tokens everywhere — never raw values
Text(
    text = "Hello",
    style = MaterialTheme.typography.bodyMedium,             // not fontSize = 14.sp
    color = MaterialTheme.colorScheme.onSurface,             // not Color(0xFF1C1B1F)
)
Card(shape = MaterialTheme.shapes.medium) { ... }           // not RoundedCornerShape(8.dp)
```

For values not covered by Material tokens (spacing, elevation, icon sizes), define app-level design tokens:

```kotlin
object AppSpacing {
    val small = 8.dp
    val medium = 16.dp
    val large = 24.dp
}
```

**No magic numbers in UI code.** If a numeric value appears in UI, it must be either a Material theme token or an app-defined design constant. For theming details see `references/compose-patterns.md`.

## Naming Conventions (Android-Specific)

| Element | Convention | Example |
|---|---|---|
| Composable (UI) | `PascalCase` | `UserProfileScreen`, `SettingsCard` |
| Composable (value) | `camelCase` | `rememberScrollState()` |
| ViewModel | Suffix `ViewModel` | `SettingsViewModel` |
| Screen composable | Suffix `Screen` | `HomeScreen`, `ProfileScreen` |
| UI State | Suffix `UiState` | `HomeUiState`, `ProfileUiState` |
| Activity | Suffix `Activity` | `MainActivity` |
| Fragment (legacy) | Suffix `Fragment` | `HomeFragment` |
| Repository | Suffix `Repository` | `UserRepository` |
| Use case | Verb phrase | `GetUserUseCase`, `SyncDataUseCase` |
| Module | Feature name, kebab-case | `:feature:auth`, `:core:network` |

## Jetpack Compose Essentials

```kotlin
// UI State
data class HomeUiState(
    val items: List<Item> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

// ViewModel
class HomeViewModel(
    private val repository: ItemRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            repository.getItems()
                .onSuccess { items -> _uiState.update { it.copy(items = items, isLoading = false) } }
                .onFailure { e -> _uiState.update { it.copy(error = e.message, isLoading = false) } }
        }
    }
}

// Composable
@Composable
fun HomeScreen(
    viewModel: HomeViewModel = viewModel(),
    onItemClick: (Item) -> Unit,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    when {
        uiState.isLoading -> LoadingIndicator()
        uiState.error != null -> ErrorMessage(uiState.error!!)
        else -> ItemList(items = uiState.items, onItemClick = onItemClick)
    }
}
```

Rules:
- Use `StateFlow` + `collectAsStateWithLifecycle()` for state in ViewModels.
- State hoisting — composables receive state and emit events, they don't own state.
- Use `remember` for composable-local state, `rememberSaveable` for state surviving config changes.
- Keep composables small. Extract when a composable exceeds ~40 lines.

For navigation, theming, side effects, lists, animations see `references/compose-patterns.md`.

## Android Concurrency

For coroutines language fundamentals (Flow, structured concurrency, cancellation), see the `kotlin-development` skill. Below are Android-specific patterns.

```kotlin
// ViewModel scope — cancelled when ViewModel is cleared
class UserViewModel(private val repo: UserRepository) : ViewModel() {
    val users = repo.observeUsers()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}

// Lifecycle-aware collection in Compose
@Composable
fun UserScreen(viewModel: UserViewModel = viewModel()) {
    val users by viewModel.users.collectAsStateWithLifecycle()
    UserList(users)
}

// Lifecycle-aware collection in Activity/Fragment (legacy)
lifecycleScope.launch {
    repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.users.collect { updateUI(it) }
    }
}
```

Rules:
- **`viewModelScope`** for ViewModel operations — auto-cancelled on clear.
- **`collectAsStateWithLifecycle()`** in Compose — lifecycle-aware, stops collection when not visible.
- **`repeatOnLifecycle`** in Activities/Fragments — restarts collection on lifecycle transitions.
- **`WhileSubscribed(5000)`** for `stateIn` — keeps upstream active 5s after last subscriber (survives rotation).
- **WorkManager** for deferrable background work. **Foreground services** for user-visible ongoing tasks.

For WorkManager, foreground services, and advanced patterns see `references/concurrency.md`.

## Architecture

**Recommended: MVI (Model-View-Intent)** for new projects. MVI enforces unidirectional data flow with a single immutable state and explicit user intents, which maps naturally to Compose. If the project already uses MVVM, MVP, or MVC — adapt to the existing architecture instead of forcing a rewrite.

### MVI Pattern

```kotlin
// 1. State — single immutable data class per screen
data class HomeUiState(
    val items: List<Item> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

// 2. Intent — sealed interface of all user actions
sealed interface HomeIntent {
    data object LoadItems : HomeIntent
    data class DeleteItem(val id: String) : HomeIntent
    data object RetryLoad : HomeIntent
}

// 3. ViewModel — reduces intents into state
@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: ItemRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    fun onIntent(intent: HomeIntent) {
        when (intent) {
            is HomeIntent.LoadItems -> loadItems()
            is HomeIntent.DeleteItem -> deleteItem(intent.id)
            is HomeIntent.RetryLoad -> loadItems()
        }
    }

    private fun loadItems() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.getItems()
                .onSuccess { items -> _uiState.update { it.copy(items = items, isLoading = false) } }
                .onFailure { e -> _uiState.update { it.copy(error = e.message, isLoading = false) } }
        }
    }

    private fun deleteItem(id: String) {
        viewModelScope.launch {
            repository.delete(id)
            _uiState.update { it.copy(items = it.items.filter { item -> item.id != id }) }
        }
    }
}

// 4. View — renders state, emits intents
@Composable
fun HomeScreen(viewModel: HomeViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) { viewModel.onIntent(HomeIntent.LoadItems) }

    when {
        uiState.isLoading -> LoadingIndicator()
        uiState.error != null -> ErrorScreen(
            message = uiState.error!!,
            onRetry = { viewModel.onIntent(HomeIntent.RetryLoad) },
        )
        else -> ItemList(
            items = uiState.items,
            onDelete = { id -> viewModel.onIntent(HomeIntent.DeleteItem(id)) },
        )
    }
}
```

### Project Structure

```
app/
├── MainActivity.kt
├── navigation/
│   └── AppNavGraph.kt
├── feature/
│   ├── home/
│   │   ├── HomeScreen.kt
│   │   ├── HomeViewModel.kt
│   │   ├── HomeUiState.kt
│   │   └── HomeIntent.kt
│   ├── profile/
│   └── settings/
├── core/
│   ├── data/
│   │   ├── repository/
│   │   └── model/
│   ├── network/
│   └── database/
└── ui/
    ├── theme/
    └── components/
```

### Rules

- Organize by feature, not by technical layer.
- **Unidirectional Data Flow (UDF)** — intents flow up, state flows down.
- **Single state per screen** — one `UiState` data class, one `StateFlow`.
- **Explicit intents** — all user actions are modeled as sealed interface members. No ad-hoc methods on ViewModel.
- **Repository pattern** — single source of truth for data. Repositories expose Flows.
- **Use case classes** (optional) — encapsulate complex business logic. Skip for simple CRUD.
- One screen composable per file. ViewModel per screen.
- **Adapt to existing architecture.** If the project uses MVVM/MVP/MVC, follow the established pattern. Propose MVI for new screens or new projects.

For multi-module architecture, Gradle setup, and build variants see `references/project-structure.md`.

## Dependency Injection

```kotlin
// Hilt (recommended)
@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: ItemRepository,
) : ViewModel() { ... }

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {
    @Binds
    abstract fun bindItemRepository(impl: DefaultItemRepository): ItemRepository
}

// Manual DI (for small projects or libraries)
class AppContainer {
    private val api: ApiService by lazy { RetrofitApiService() }
    val repository: ItemRepository by lazy { DefaultItemRepository(api) }
}
```

Rules:
- **Hilt** for apps — standard Android DI, integrates with ViewModel, WorkManager, Navigation.
- **Manual DI or Koin** for libraries or KMP shared modules.
- Inject interfaces, not implementations.
- Use `@Singleton` sparingly — scope to the narrowest lifecycle.

## Testable Design

- **Inject dependencies** via constructor. ViewModels receive repositories, not context.
- **Repository interfaces** — swap real implementations with fakes in tests.
- **UI state as data class** — easy to assert in unit tests.
- **Compose testing** — `createComposeRule()`, semantic matchers, `onNodeWithText`.

```kotlin
class HomeViewModelTest {
    private val fakeRepository = FakeItemRepository()
    private val viewModel = HomeViewModel(fakeRepository)

    @Test
    fun `load items updates state`() = runTest {
        fakeRepository.emit(listOf(Item("1", "Test")))
        viewModel.load()
        assertEquals(listOf(Item("1", "Test")), viewModel.uiState.value.items)
    }
}
```

Test naming: `fun 'description of behavior'()` with backtick syntax, or `test_method_condition_expected()`.

## Platform-Specific Guidance

The core skill covers Android phone by default. For other platforms, consult the corresponding reference:

| Platform | Reference | Key Topics |
|---|---|---|
| Tablet / Foldable | `references/tablet-patterns.md` | `WindowSizeClass`, adaptive layouts, multi-window, foldable postures |
| Wear OS | `references/wear-os-patterns.md` | Compose for Wear, Tiles, complications, Health Services |
| Google TV / Android TV | `references/tv-patterns.md` | Compose for TV, focus/D-pad navigation, Leanback |
| Android Auto | `references/android-auto-patterns.md` | Car App Library, templates, phone projection |
| Android Automotive | `references/android-automotive-patterns.md` | AAOS, embedded system, car hardware APIs |
| Meta Quest | `references/meta-quest-patterns.md` | Adapting APK for VR, spatial UI, entitlement, passthrough |
| Amazon Fire TV | `references/fire-tv-patterns.md` | Appstore, Amazon IAP, Alexa, missing GMS |
| Amazon Fire Tablets | `references/fire-tablet-patterns.md` | Device lineup, Show Mode, Kids Edition |

## Quick Reference: Common Mistakes

| Mistake | Fix |
|---|---|
| Collecting Flow without lifecycle awareness | Use `collectAsStateWithLifecycle()` in Compose |
| Business logic in composables | Move to ViewModel, expose as StateFlow |
| `mutableStateOf` in ViewModel | Use `MutableStateFlow` + `asStateFlow()` |
| Passing `Context` to ViewModel | Use `AndroidViewModel` only if truly needed, prefer abstractions |
| `LaunchedEffect(Unit)` for one-time loads | Consider loading in ViewModel `init` block |
| Hardcoded strings in composables | Use `stringResource(R.string.xxx)` |
| Not handling process death | Use `SavedStateHandle` in ViewModel, `rememberSaveable` in Compose |
| God ViewModel (500+ lines) | Split by screen, extract use cases |
| Not using `Modifier` parameter | Always accept `modifier: Modifier = Modifier` as first optional param |
| `remember` for complex objects | Use `remember` with proper keys, or move to ViewModel |
| Ignoring configuration changes | Test with rotation, dark mode, font scale |
| Using `GlobalScope` | Use `viewModelScope` or structured concurrency |
| View-based navigation in Compose app | Use Compose Navigation (`NavHost`) |
| `LiveData` in new code | Use `StateFlow` + `collectAsStateWithLifecycle()` |
| Magic numbers in UI (`padding(16.dp)`, `fontSize = 14.sp`) | Define design tokens (`AppSpacing.medium`) or use `MaterialTheme` tokens |
