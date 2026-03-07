# View Interop Reference

Target: Compose BOM `2025.05.00+` (Compose UI 1.8+, Navigation 2.9+)

---

## AndroidView

`AndroidView` hosts a classic Android `View` inside a Compose layout.

```kotlin
@Composable
fun LegacyChartWrapper(data: List<Float>) {
    AndroidView(
        // factory runs once — create the View here
        factory = { context ->
            LineChartView(context).apply {
                layoutParams = ViewGroup.LayoutParams(MATCH_PARENT, WRAP_CONTENT)
            }
        },
        // update runs on every recomposition where inputs change
        update = { chart ->
            chart.setData(data)
            chart.invalidate()
        },
        // onRelease runs when the composable leaves composition (Compose 1.6+)
        onRelease = { chart ->
            chart.cleanup()
        },
        modifier = Modifier.fillMaxWidth().height(200.dp)
    )
}
```

### Key Parameters
---
| Parameter | Purpose |
|-----------|---------|
| `factory: (Context) -> T` | One-time View creation. Receives `ComponentActivity` context by default. |
| `update: (T) -> Unit` | Called on initial composition and whenever recomposition occurs with changed state. Keep idempotent. |
| `onReset: (T) -> Unit` | Called when the node is reused in a `ReusableContent` scope (Compose 1.6+). |
| `onRelease: (T) -> Unit` | Called when the `AndroidView` permanently leaves composition. Use for teardown. |
| `modifier` | Standard Compose modifier; sizing is respected by the underlying `ViewGroup`. |

### Important Notes
- `factory` receives the nearest `LocalContext.current`. If you need a themed context, wrap with `ContextThemeWrapper`.
- Avoid capturing mutable Compose state directly inside `factory` — use `update` for reactive bindings.
- The View is added to a `ComposeView`-internal `ViewGroup`; do not call `removeView` manually.


## AndroidViewBinding

Wraps a `ViewBinding`-inflated layout, useful when you have existing XML layouts.

```kotlin
@Composable
fun PlayerScreen(uri: Uri) {
    AndroidViewBinding(PlayerLayoutBinding::inflate) {
        // 'this' is the binding instance — runs like update
        playerView.player = ExoPlayer.Builder(playerView.context).build().apply {
            setMediaItem(MediaItem.fromUri(uri))
            prepare()
        }
    }
}
```

- Requires `viewBinding` build feature enabled in the module's `build.gradle.kts`.
- The trailing lambda behaves like `update` — it re-runs on recomposition.
- Fragment inflation via `FragmentContainerView` inside the binding is supported but requires `FragmentActivity`.


## ComposeView

Embeds Compose content inside an Activity, Fragment, or any `ViewGroup`.

### In an Activity
```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {  // shorthand — creates a ComposeView internally
            AppTheme { MainScreen() }
        }
    }
}
```

### In a Fragment
```kotlin
class ProfileFragment : Fragment() {
    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?
    ): View {
        return ComposeView(requireContext()).apply {
            setViewCompositionStrategy(
                ViewCompositionStrategy.DisposeOnViewTreeLifecycleDestroyed
            )
            setContent {
                AppTheme { ProfileScreen() }
            }
        }
    }
}
```

### ViewCompositionStrategy
---
Controls when the Composition is disposed.

| Strategy | Disposes when | Use case |
|----------|---------------|----------|
| `DisposeOnDetachedFromWindow` | View detaches from window (default) | Simple Activity usage |
| `DisposeOnDetachedFromWindowOrReleasedFromPool` | Detach or RecyclerView pool release | ComposeView inside RecyclerView items |
| `DisposeOnViewTreeLifecycleDestroyed` | Fragment view lifecycle `ON_DESTROY` | Fragments (prevents leaks on back-stack) |
| `DisposeOnLifecycleDestroyed(lifecycle)` | Specific lifecycle destroyed | Dialogs, custom lifecycle owners |

Use `DisposeOnViewTreeLifecycleDestroyed` in Fragments. The default strategy causes recomposition issues when Fragments go on the back-stack without destroying their view.


## AbstractComposeView

Create a reusable Compose-backed View that can be used in XML layouts.

```kotlin
class StarRatingView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : AbstractComposeView(context, attrs) {

    var rating by mutableIntStateOf(0)

    @Composable
    override fun Content() {
        AppTheme {
            StarRatingBar(
                rating = rating,
                onRatingChanged = { rating = it }
            )
        }
    }
}
```

```xml
<com.example.ui.StarRatingView
    android:id="@+id/starRating"
    android:layout_width="wrap_content"
    android:layout_height="wrap_content" />
```

- Expose mutable state as public properties; `AbstractComposeView` triggers recomposition automatically when Compose `State` objects change.
- Override `measurePolicy` only if you need custom intrinsic measurement.
- Set the composition strategy via `setViewCompositionStrategy()` if used inside Fragments.


## Navigation Interop

### Mixing Fragment Navigation and Compose Navigation
---

#### Option A: Fragment NavHost with Compose Destinations
Keep the existing `NavHostFragment` and use `ComposeView` inside Fragment destinations. Best when migrating incrementally.

```kotlin
// Fragment destination that hosts Compose
class SettingsFragment : Fragment() {
    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        return ComposeView(requireContext()).apply {
            setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnViewTreeLifecycleDestroyed)
            setContent {
                AppTheme { SettingsScreen(onBack = { findNavController().popBackStack() }) }
            }
        }
    }
}
```

#### Option B: Compose NavHost with Fragment Destinations
Use `composable()` for new screens and `fragment<MyFragment>(route)` for legacy screens (requires `navigation-fragment-compose` artifact).

```kotlin
// build.gradle.kts
implementation("androidx.navigation:navigation-fragment-compose:2.9.0")

// In Compose
NavHost(navController, startDestination = "home") {
    composable("home") { HomeScreen() }
    fragment<LegacyDetailFragment>("detail/{id}") {
        argument("id") { type = NavType.StringType }
    }
}
```

#### Option C: Full Compose Navigation
Replace the Fragment `NavHost` entirely. Preferred for greenfield or fully migrated apps.

### Shared Navigation Tips
- Pass a single `NavController` or a navigation callback lambda; avoid creating multiple NavControllers.
- Deep links and back-stack behavior work across both systems when using the `navigation-fragment-compose` bridge.
- Test navigation transitions manually — animation interop between Fragment transitions and Compose animations may require tuning.


## When to Use Views

### Decision Guide
---

| Component | Recommendation | Reason |
|-----------|---------------|--------|
| **Google Maps** (`MapView`) | Use `AndroidView` or the `maps-compose` library | Compose wrapper is mature (`com.google.maps.android:maps-compose`). Prefer the library. |
| **WebView** | Use `AndroidView` | No Compose equivalent. Wrap with `update` for URL changes. Handle `onRelease` for `destroy()`. |
| **AdView** (AdMob) | Use `AndroidView` | SDK is View-based. Follow Google's `AndroidView` guide for ad lifecycle. |
| **ExoPlayer / Media3** `PlayerView` | Use `AndroidView` or `AndroidViewBinding` | Media3 provides experimental Compose components, but `PlayerView` is still more stable. |
| **CameraX PreviewView** | Use `AndroidView` | Bind `ProcessCameraProvider` in `factory`, unbind in `onRelease`. |
| **Custom drawing with Canvas** | Prefer Compose `Canvas` | Compose Canvas covers most use cases. Fall back to View Canvas only for `SurfaceView`/`TextureView`. |
| **PDF rendering** | Use `AndroidView` with `PdfRenderer` | No Compose equivalent. |

### General Rule
Use `AndroidView` when:
- The component has no Compose equivalent.
- A well-tested View-based SDK wraps complex native behavior (maps, ads, video).
- Performance-critical rendering relies on `SurfaceView` or `TextureView`.

Prefer Compose when:
- You can replicate the behavior with Compose primitives.
- The View is purely layout/UI with no native binding (buttons, text fields, lists).


## Migration Strategy

### Screen-by-Screen (Recommended)
---
1. **Pick a leaf screen** (no child Fragments, minimal shared state).
2. Wrap the Activity/Fragment content with `ComposeView` and `setContent`.
3. Replace the XML layout with Compose equivalents, keeping the Fragment shell.
4. Once all content is Compose, convert the Fragment to a Compose `NavHost` destination.
5. Repeat for adjacent screens, working inward toward the host Activity.

### Shared ViewModels
---
ViewModels bridge View and Compose worlds seamlessly.

```kotlin
// ViewModel shared between Fragment host and Compose content
class OrderViewModel : ViewModel() {
    val items = MutableStateFlow<List<OrderItem>>(emptyList())
}

// In Fragment
val viewModel: OrderViewModel by viewModels()

// In ComposeView inside the same Fragment
setContent {
    val vm: OrderViewModel = viewModel()   // resolves the same instance
    val items by vm.items.collectAsStateWithLifecycle()
    OrderList(items)
}
```

- `viewModel()` and `hiltViewModel()` inside `ComposeView` resolve against the Fragment's `ViewModelStoreOwner` by default.
- `collectAsStateWithLifecycle()` (from `lifecycle-runtime-compose`) is preferred over `collectAsState()` — it respects lifecycle and avoids updates when the UI is not visible.

### Bottom-Up Approach
---
1. **Start with leaf components**: buttons, cards, list items. Wrap them in `AbstractComposeView` so they can be used in XML.
2. **Replace RecyclerView adapters**: migrate item ViewHolders to Compose items (see RecyclerView Interop below).
3. **Replace layouts**: swap `ConstraintLayout`/`LinearLayout` XML with Compose equivalents inside `ComposeView`.
4. **Replace navigation**: migrate from Fragment-based to Compose-based `NavHost`.
5. **Remove Fragment shells**: once a screen is fully Compose, eliminate the Fragment.


## RecyclerView Interop

### LazyColumn vs RecyclerView
---
| Aspect | `LazyColumn` / `LazyRow` | `RecyclerView` |
|--------|--------------------------|----------------|
| View recycling | Automatic (composition-based) | Explicit `ViewHolder` pattern |
| Item types | Composable lambdas | `ViewType` + `ViewHolder` |
| Performance (large lists) | Good; use `key` for stable identity | Excellent with `DiffUtil` |
| Nested scrolling | Built-in | Requires `NestedScrollView` config |
| Item animations | `animateItem()` modifier (Compose 1.7+) | `ItemAnimator` |

For most new development, prefer `LazyColumn`. Use `RecyclerView` only for very large, heterogeneous lists where you observe measurable performance differences.

### Compose Items Inside RecyclerView
---
When migrating incrementally, you can use `ComposeView` inside a `RecyclerView.ViewHolder`.

```kotlin
class ComposeItemViewHolder(
    val composeView: ComposeView
) : RecyclerView.ViewHolder(composeView) {
    init {
        composeView.setViewCompositionStrategy(
            ViewCompositionStrategy.DisposeOnDetachedFromWindowOrReleasedFromPool
        )
    }
}

// In Adapter
override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ComposeItemViewHolder {
    return ComposeItemViewHolder(ComposeView(parent.context))
}

override fun onBindViewHolder(holder: ComposeItemViewHolder, position: Int) {
    holder.composeView.setContent {
        AppTheme { ItemCard(items[position]) }
    }
}
```

- Always use `DisposeOnDetachedFromWindowOrReleasedFromPool` to prevent leaks when items are recycled.
- Calling `setContent` in `onBindViewHolder` is safe — Compose handles recomposition efficiently.
- Consider migrating the entire `RecyclerView` to `LazyColumn` once all item types are Compose.


## Common Pitfalls

### Memory Leaks
---
- **Fragment back-stack**: Using the default `DisposeOnDetachedFromWindow` in Fragments causes the Composition to live beyond `onDestroyView`. Always use `DisposeOnViewTreeLifecycleDestroyed`.
- **AndroidView cleanup**: Resources allocated in `factory` (players, camera providers, database cursors) must be released in `onRelease`. Forgetting this is the most common source of leaks.
- **Coroutine scopes**: Avoid launching coroutines in `factory` or `update`. Use `LaunchedEffect` or `DisposableEffect` in the enclosing composable instead.

### Theme Bridging
---
- Compose `MaterialTheme` and View `Theme.Material3` are independent. Use `MdcTheme` or `Mdc3Theme` from `com.google.android.material:compose-theme-adapter-3` to bridge XML theme attributes into Compose.
- Alternatively, define a shared design token layer and apply it to both systems.
- Watch for color mismatches: View `?attr/colorPrimary` and Compose `MaterialTheme.colorScheme.primary` may differ if not synchronized.

```kotlin
// Bridge the XML theme into Compose
Mdc3Theme {
    // MaterialTheme values now match the Activity's XML theme
    MyComposeScreen()
}
```

### Keyboard (IME) Handling
---
- `AndroidView` text fields manage their own `InputMethodManager` — Compose's `FocusRequester` does not control them.
- When mixing Compose `TextField` and View `EditText`, test focus transitions carefully. Use `LocalFocusManager` for Compose and `View.requestFocus()` for Views — they do not interoperate automatically.
- Use `WindowCompat.setDecorFitsSystemWindows(window, false)` and `imePadding()` modifier for consistent keyboard inset behavior.

### Focus and Accessibility
---
- Focus traversal between Compose and View elements can break if `nextFocusDown` / `nextFocusUp` XML attributes conflict with Compose's focus order.
- Content descriptions set via `Modifier.semantics { contentDescription = "..." }` in Compose do not propagate to sibling Views. Ensure both systems declare accessibility metadata independently.
- Test with TalkBack whenever mixing Compose and View hierarchies — traversal order is a frequent source of bugs.

### Lifecycle Awareness
---
- `AndroidView` does not forward `onPause` / `onResume` to the hosted View. If the View relies on lifecycle callbacks (e.g., `MapView.onResume()`), observe the lifecycle manually:

```kotlin
AndroidView(
    factory = { context ->
        MapView(context).also { it.onCreate(null) }
    },
    update = { }
)

val lifecycle = LocalLifecycleOwner.current.lifecycle
DisposableEffect(lifecycle) {
    val observer = LifecycleEventObserver { _, event ->
        when (event) {
            Lifecycle.Event.ON_RESUME -> mapView.onResume()
            Lifecycle.Event.ON_PAUSE -> mapView.onPause()
            Lifecycle.Event.ON_DESTROY -> mapView.onDestroy()
            else -> {}
        }
    }
    lifecycle.addObserver(observer)
    onDispose { lifecycle.removeObserver(observer) }
}
```

### State Synchronization
---
- Two-way state binding between a View property and Compose `MutableState` can cause infinite update loops. Use flags or `snapshotFlow` with `distinctUntilChanged` to break cycles.
- Prefer unidirectional data flow: Compose state as source of truth, pushed to Views via `update`.
