# Tablet and Foldable Patterns Reference

>[toc]


## WindowSizeClass

### Breakpoints and Classification
---

`WindowSizeClass` is the foundation for building adaptive UIs in Compose. It classifies the current window into discrete size buckets so layouts can respond to meaningful thresholds rather than raw pixel values.

#### Setup

Add the dependency:

```kotlin
implementation("androidx.compose.material3.adaptive:adaptive:1.1.0")
```

#### Calculating the Size Class

```kotlin
@Composable
fun MyApp() {
    val windowSizeClass = currentWindowAdaptiveInfo().windowSizeClass

    when (windowSizeClass.windowWidthSizeClass) {
        WindowWidthSizeClass.COMPACT  -> CompactLayout()
        WindowWidthSizeClass.MEDIUM   -> MediumLayout()
        WindowWidthSizeClass.EXPANDED -> ExpandedLayout()
    }
}
```

#### Width Breakpoints

| Class | Breakpoint | Typical Devices |
|-------|-----------|-----------------|
| `COMPACT` | < 600dp | Phones in portrait |
| `MEDIUM` | 600dp - 839dp | Foldables unfolded, small tablets |
| `EXPANDED` | >= 840dp | Tablets, desktops, landscape foldables |

#### Height Breakpoints

| Class | Breakpoint | Typical Devices |
|-------|-----------|-----------------|
| `COMPACT` | < 480dp | Phones in landscape |
| `MEDIUM` | 480dp - 899dp | Tablets in landscape |
| `EXPANDED` | >= 900dp | Tablets in portrait, desktops |

**Key point**: Always branch on `windowWidthSizeClass` for primary layout decisions. Use `windowHeightSizeClass` as a secondary signal (e.g., to hide a bottom bar in landscape).


## Adaptive Layouts

### ListDetailPaneScaffold
---

`ListDetailPaneScaffold` implements the canonical list-detail pattern with automatic pane management based on window size.

#### Dependency

```kotlin
implementation("androidx.compose.material3.adaptive:adaptive-layout:1.1.0")
implementation("androidx.compose.material3.adaptive:adaptive-navigation:1.1.0")
```

#### Basic Usage

```kotlin
@OptIn(ExperimentalMaterial3AdaptiveApi::class)
@Composable
fun ListDetailScreen() {
    val navigator = rememberListDetailPaneScaffoldNavigator<String>()

    BackHandler(navigator.canNavigateBack()) {
        navigator.navigateBack()
    }

    ListDetailPaneScaffold(
        directive = navigator.scaffoldDirective,
        value = navigator.scaffoldValue,
        listPane = {
            AnimatedPane {
                ItemList(
                    onItemClick = { itemId ->
                        navigator.navigateTo(
                            pane = ListDetailPaneScaffoldRole.Detail,
                            content = itemId
                        )
                    }
                )
            }
        },
        detailPane = {
            AnimatedPane {
                navigator.currentDestination?.content?.let { itemId ->
                    ItemDetail(itemId = itemId)
                }
            }
        }
    )
}
```

**Behavior by window size**:
- **Compact**: Single pane; navigating to detail replaces the list with a back gesture to return.
- **Medium/Expanded**: Side-by-side panes; list remains visible when detail is shown.

#### Three-Pane (Extra Pane)

```kotlin
ListDetailPaneScaffold(
    directive = navigator.scaffoldDirective,
    value = navigator.scaffoldValue,
    listPane = { /* ... */ },
    detailPane = { /* ... */ },
    extraPane = {
        AnimatedPane {
            // Tertiary content (e.g., comments, metadata)
        }
    }
)
```

### NavigationSuiteScaffold
---

`NavigationSuiteScaffold` automatically switches between bottom navigation, navigation rail, and navigation drawer based on window size.

#### Dependency

```kotlin
implementation("androidx.compose.material3:material3-adaptive-navigation-suite:1.4.0")
```

#### Usage

```kotlin
@Composable
fun AppScaffold(currentDestination: Destination) {
    NavigationSuiteScaffold(
        navigationSuiteItems = {
            Destination.entries.forEach { destination ->
                item(
                    icon = { Icon(destination.icon, contentDescription = destination.label) },
                    label = { Text(destination.label) },
                    selected = destination == currentDestination,
                    onClick = { /* navigate */ }
                )
            }
        }
    ) {
        // Screen content
        CurrentScreen(currentDestination)
    }
}
```

**Automatic layout selection**:

| Window Width | Navigation Component |
|-------------|---------------------|
| Compact | Bottom navigation bar |
| Medium | Navigation rail (start edge) |
| Expanded | Persistent navigation drawer |

#### Overriding the Layout Type

```kotlin
NavigationSuiteScaffold(
    layoutType = if (isTopLevelDest) {
        NavigationSuiteType.NavigationBar
    } else {
        NavigationSuiteType.None
    },
    navigationSuiteItems = { /* ... */ }
) { /* ... */ }
```


## Multi-Window

### Split-Screen and Freeform Windows
---

Android supports multi-window modes: split-screen (two apps side-by-side) and freeform (resizable desktop-style windows). Compose apps that use `WindowSizeClass` adapt automatically, but there are additional considerations.

#### Lifecycle Behavior

In multi-window, all visible activities are in `STARTED` state but only the focused one is `RESUMED`. Use `Lifecycle.State.STARTED` (not `RESUMED`) to gate operations that should run while visible:

```kotlin
val lifecycleOwner = LocalLifecycleOwner.current
val isAtLeastStarted by lifecycleOwner.lifecycle
    .currentStateFlow
    .collectAsState()

if (isAtLeastStarted) {
    // Continue video playback, sensor updates, etc.
}
```

#### Configuration Changes

When entering or exiting multi-window, the system triggers a configuration change. Compose handles recomposition automatically if you derive layout from `WindowSizeClass`. Avoid caching layout decisions in `ViewModel` -- always read from the current window info.

#### Drag and Drop Between Windows

```kotlin
Modifier.dragAndDropTarget(
    shouldStartDragAndDrop = { event ->
        event.mimeTypes().any { it == ClipDescription.MIMETYPE_TEXT_PLAIN }
    },
    target = remember {
        object : DragAndDropTarget {
            override fun onDrop(event: DragAndDropEvent): Boolean {
                val text = event.toAndroidDragEvent()
                    .clipData.getItemAt(0).text
                // Handle dropped text
                return true
            }
        }
    }
)
```

#### Manifest Declarations

For activities that support multi-window properly:

```xml
<activity
    android:name=".MainActivity"
    android:resizeableActivity="true"
    android:configChanges="screenSize|smallestScreenSize|screenLayout|orientation" />
```

Setting `resizeableActivity="false"` does **not** prevent multi-window on large screens (API 31+). It only enters size-compatibility mode.


## Foldable Devices

### WindowInfoTracker, Fold Postures, and Hinge Detection
---

Jetpack `WindowManager` provides fold-aware APIs to detect hinge position and fold state.

#### Dependency

```kotlin
implementation("androidx.window:window:1.4.0")
implementation("androidx.window:window-core:1.4.0")
```

#### Observing Fold State in Compose

```kotlin
@Composable
fun FoldAwareScreen() {
    val context = LocalContext.current
    val activity = context as Activity

    val layoutInfo by WindowInfoTracker.getOrCreate(activity)
        .windowLayoutInfo(activity)
        .collectAsState(initial = null)

    val foldingFeature = layoutInfo?.displayFeatures
        ?.filterIsInstance<FoldingFeature>()
        ?.firstOrNull()

    when {
        foldingFeature == null -> {
            // Flat or non-foldable device
            StandardLayout()
        }
        foldingFeature.state == FoldingFeature.State.HALF_OPENED -> {
            // Tabletop or book posture
            if (foldingFeature.orientation == FoldingFeature.Orientation.HORIZONTAL) {
                TabletopLayout(foldingFeature)
            } else {
                BookLayout(foldingFeature)
            }
        }
        foldingFeature.state == FoldingFeature.State.FLAT -> {
            // Fully unfolded -- treat as tablet
            ExpandedLayout()
        }
    }
}
```

#### Fold Postures

| Posture | Fold State | Orientation | Use Case |
|---------|-----------|-------------|----------|
| **Tabletop** | HALF_OPENED | HORIZONTAL | Video on top, controls on bottom |
| **Book** | HALF_OPENED | VERTICAL | Two-pane reading, side-by-side compare |
| **Flat** | FLAT | Any | Standard tablet layout |

#### Calculating Hinge Position

```kotlin
@Composable
fun HingeAwareLayout(foldingFeature: FoldingFeature) {
    val density = LocalDensity.current
    val hingeBounds = foldingFeature.bounds

    // Convert hinge bounds to Dp
    val hingePosition = with(density) {
        if (foldingFeature.orientation == FoldingFeature.Orientation.VERTICAL) {
            hingeBounds.left.toDp()
        } else {
            hingeBounds.top.toDp()
        }
    }
    val hingeSize = with(density) {
        if (foldingFeature.orientation == FoldingFeature.Orientation.VERTICAL) {
            hingeBounds.width().toDp()
        } else {
            hingeBounds.height().toDp()
        }
    }

    // Place content on either side of the hinge, avoiding overlap
    if (foldingFeature.orientation == FoldingFeature.Orientation.VERTICAL) {
        Row {
            Box(Modifier.width(hingePosition)) { LeftPane() }
            Spacer(Modifier.width(hingeSize))
            Box(Modifier.weight(1f)) { RightPane() }
        }
    }
}
```

#### Occlusion vs. Separation

```kotlin
if (foldingFeature.isSeparating) {
    // Content on opposite sides of the fold may not be visible simultaneously.
    // Add spacing or avoid placing interactive elements across the hinge.
}

if (foldingFeature.occlusionType == FoldingFeature.OcclusionType.FULL) {
    // Physical hinge obscures content -- never draw across it.
}
```


## Large Screen Navigation

### List-Detail Pattern and Two-Pane Layouts
---

#### Canonical Layout Recommendations

Google recommends three canonical layouts for large screens:

| Layout | When to Use | Implementation |
|--------|------------|----------------|
| **List-Detail** | Browse + inspect | `ListDetailPaneScaffold` |
| **Supporting Panel** | Primary content + reference | `SupportingPaneScaffold` |
| **Feed** | Scrollable homogeneous content | Adaptive grid with `LazyVerticalGrid` |

#### SupportingPaneScaffold

```kotlin
@OptIn(ExperimentalMaterial3AdaptiveApi::class)
@Composable
fun SupportingPaneScreen() {
    val navigator = rememberSupportingPaneScaffoldNavigator()

    SupportingPaneScaffold(
        directive = navigator.scaffoldDirective,
        value = navigator.scaffoldValue,
        mainPane = {
            AnimatedPane {
                MainContent(
                    onShowSupporting = {
                        navigator.navigateTo(SupportingPaneScaffoldRole.Supporting)
                    }
                )
            }
        },
        supportingPane = {
            AnimatedPane {
                SupportingContent()
            }
        }
    )
}
```

#### Adaptive Grid for Feed Layouts

```kotlin
@Composable
fun AdaptiveFeed(items: List<FeedItem>) {
    val windowSizeClass = currentWindowAdaptiveInfo().windowSizeClass
    val columns = when (windowSizeClass.windowWidthSizeClass) {
        WindowWidthSizeClass.COMPACT  -> 1
        WindowWidthSizeClass.MEDIUM   -> 2
        WindowWidthSizeClass.EXPANDED -> 3
        else -> 1
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(columns),
        contentPadding = PaddingValues(16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        items(items) { item ->
            FeedCard(item)
        }
    }
}
```

#### Navigation Patterns by Screen Size

| Width Class | Primary Nav | Secondary Nav |
|------------|------------|---------------|
| Compact | Bottom bar | Top app bar |
| Medium | Navigation rail | Top app bar |
| Expanded | Persistent drawer | Contextual toolbar |

Use `NavigationSuiteScaffold` (see Adaptive Layouts above) to handle this automatically.


## Input Support

### Keyboard Shortcuts, Mouse Hover, and Stylus
---

Large screen devices frequently use keyboard, mouse, trackpad, and stylus input. Supporting these inputs properly is critical for a polished experience.

#### Keyboard Shortcuts

```kotlin
@Composable
fun ShortcutAwareScreen() {
    var showSearch by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .onPreviewKeyEvent { event ->
                if (event.type == KeyEventType.KeyDown &&
                    event.isCtrlPressed &&
                    event.key == Key.F
                ) {
                    showSearch = true
                    true
                } else {
                    false
                }
            }
    ) {
        // Screen content
    }
}
```

#### Common Shortcut Conventions

| Shortcut | Action |
|----------|--------|
| Ctrl+C / Ctrl+V | Copy / Paste |
| Ctrl+Z / Ctrl+Shift+Z | Undo / Redo |
| Ctrl+F | Find / Search |
| Ctrl+S | Save |
| Ctrl+A | Select all |
| Tab / Shift+Tab | Focus navigation |
| Escape | Dismiss / Back |

#### Mouse Hover and Right-Click

```kotlin
@Composable
fun HoverAwareCard(item: Item) {
    var isHovered by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        val event = awaitPointerEvent()
                        when (event.type) {
                            PointerEventType.Enter -> isHovered = true
                            PointerEventType.Exit -> isHovered = false
                        }
                    }
                }
            },
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (isHovered) 8.dp else 2.dp
        )
    ) {
        // Card content
    }
}
```

#### Context Menu (Right-Click)

```kotlin
@Composable
fun ContextMenuExample(text: String) {
    var showMenu by remember { mutableStateOf(false) }
    var menuOffset by remember { mutableStateOf(Offset.Zero) }

    Box(
        modifier = Modifier
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        val event = awaitPointerEvent()
                        if (event.type == PointerEventType.Press &&
                            event.button == PointerButton.Secondary
                        ) {
                            menuOffset = event.changes.first().position
                            showMenu = true
                        }
                    }
                }
            }
    ) {
        Text(text)
        DropdownMenu(
            expanded = showMenu,
            onDismissRequest = { showMenu = false },
            offset = DpOffset(menuOffset.x.dp, menuOffset.y.dp)
        ) {
            DropdownMenuItem(
                text = { Text("Copy") },
                onClick = { /* copy action */ }
            )
            DropdownMenuItem(
                text = { Text("Share") },
                onClick = { /* share action */ }
            )
        }
    }
}
```

#### Stylus Support

```kotlin
@Composable
fun StylusCanvas() {
    val paths = remember { mutableStateListOf<Path>() }
    val currentPath = remember { mutableStateOf<Path?>(null) }

    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        val event = awaitPointerEvent()
                        val change = event.changes.first()

                        // Detect stylus via input type
                        val isStylusInput = change.type == PointerType.Stylus

                        when (event.type) {
                            PointerEventType.Press -> {
                                currentPath.value = Path().apply {
                                    moveTo(change.position.x, change.position.y)
                                }
                            }
                            PointerEventType.Move -> {
                                currentPath.value?.lineTo(
                                    change.position.x,
                                    change.position.y
                                )
                            }
                            PointerEventType.Release -> {
                                currentPath.value?.let { paths.add(it) }
                                currentPath.value = null
                            }
                        }

                        // Use pressure for stroke width (stylus-specific)
                        val pressure = change.pressure
                        change.consume()
                    }
                }
            }
    ) {
        paths.forEach { path ->
            drawPath(path, Color.Black, style = Stroke(width = 4f))
        }
        currentPath.value?.let { path ->
            drawPath(path, Color.Black, style = Stroke(width = 4f))
        }
    }
}
```

**Stylus considerations**:
- Read `pressure` for variable stroke width.
- Read `tilt` for brush angle effects.
- Distinguish `PointerType.Stylus` from `PointerType.Touch` to support palm rejection.


## Desktop Windowing

### Chrome OS, Desktop Mode, and Minimum Sizes
---

On Chrome OS and Android desktop windowing mode (introduced with large screen devices), apps run in resizable windows similar to traditional desktop operating systems.

#### Minimum Window Size

Declare minimum dimensions in the manifest to prevent layouts from breaking at very small sizes:

```xml
<activity
    android:name=".MainActivity"
    android:minWidth="400dp"
    android:minHeight="300dp"
    android:resizeableActivity="true" />
```

#### Handling Window Resize Gracefully

Compose apps that derive layout from `WindowSizeClass` handle resizing automatically. Avoid fixed-size layouts. Instead:

```kotlin
@Composable
fun ResponsiveContent() {
    BoxWithConstraints {
        when {
            maxWidth < 600.dp -> CompactContent()
            maxWidth < 840.dp -> MediumContent()
            else -> ExpandedContent()
        }
    }
}
```

#### Chrome OS Specifics

- **Keyboard and trackpad are always present**: Always support keyboard navigation and hover states.
- **Window management**: Users expect standard windowing controls (minimize, maximize, close). These are handled by the system; no app code is needed.
- **Free-form resizing**: The window can be any arbitrary size. Test with unusual aspect ratios (very wide, very tall).
- **Multi-display**: Chrome OS supports external monitors. Use `WindowMetricsCalculator` to get the correct display metrics for the current window, not the default display.

#### Detecting Desktop Windowing Mode

```kotlin
val windowMetrics = WindowMetricsCalculator
    .getOrCreate()
    .computeCurrentWindowMetrics(activity)

val currentBounds = windowMetrics.bounds
val screenBounds = WindowMetricsCalculator
    .getOrCreate()
    .computeMaximumWindowMetrics(activity)
    .bounds

val isWindowed = currentBounds != screenBounds
```


## Testing Large Screens

### Device Config Overrides and Foldable Emulators
---

#### Emulator Profiles for Large Screens

Use these AVD profiles in Android Studio for testing:

| Profile | Resolution | Size Class |
|---------|-----------|-----------|
| Pixel Tablet | 2560 x 1600 | Expanded |
| Pixel Fold | 2208 x 1840 (inner) | Expanded |
| Medium Phone | 1080 x 2400 | Compact |
| 7" Tablet | 1200 x 1920 | Medium |
| 10" Tablet | 1600 x 2560 | Expanded |
| Desktop (Chrome OS) | Freeform | Variable |

#### Foldable Emulator Configuration

Android Studio provides foldable emulator profiles with virtual hinge controls:

1. Create an AVD using the **7.6" Fold-in** or **8" Fold-out** hardware profile.
2. In the running emulator, use **Extended Controls > Virtual sensors > Hinge angle** to simulate fold states.
3. Test at key angles: 0 (closed), 90 (half-opened/tabletop), 180 (flat).

#### Compose UI Testing with Overridden Window Size

```kotlin
@OptIn(ExperimentalMaterial3AdaptiveApi::class)
@Test
fun listDetailLayout_expandedWidth_showsBothPanes() {
    composeTestRule.setContent {
        // Override the adaptive info for testing
        CompositionLocalProvider(
            LocalWindowAdaptiveInfo provides WindowAdaptiveInfo(
                windowSizeClass = WindowSizeClass(
                    windowWidthSizeClass = WindowWidthSizeClass.EXPANDED,
                    windowHeightSizeClass = WindowHeightSizeClass.MEDIUM
                ),
                windowPosture = Posture()
            )
        ) {
            ListDetailScreen()
        }
    }

    // Both panes should be visible simultaneously
    composeTestRule.onNodeWithTag("list_pane").assertIsDisplayed()
    composeTestRule.onNodeWithTag("detail_pane").assertIsDisplayed()
}

@Test
fun listDetailLayout_compactWidth_showsOnlyList() {
    composeTestRule.setContent {
        CompositionLocalProvider(
            LocalWindowAdaptiveInfo provides WindowAdaptiveInfo(
                windowSizeClass = WindowSizeClass(
                    windowWidthSizeClass = WindowWidthSizeClass.COMPACT,
                    windowHeightSizeClass = WindowHeightSizeClass.MEDIUM
                ),
                windowPosture = Posture()
            )
        ) {
            ListDetailScreen()
        }
    }

    composeTestRule.onNodeWithTag("list_pane").assertIsDisplayed()
    composeTestRule.onNodeWithTag("detail_pane").assertDoesNotExist()
}
```

#### Testing Foldable Postures

```kotlin
@Test
fun layout_tabletopPosture_splitContent() {
    val hingeFeature = FoldingFeature(
        activity = composeTestRule.activity,
        state = FoldingFeature.State.HALF_OPENED,
        orientation = FoldingFeature.Orientation.HORIZONTAL,
        size = 0 // Zero-width hinge
    )

    composeTestRule.setContent {
        CompositionLocalProvider(
            LocalWindowAdaptiveInfo provides WindowAdaptiveInfo(
                windowSizeClass = WindowSizeClass(
                    windowWidthSizeClass = WindowWidthSizeClass.MEDIUM,
                    windowHeightSizeClass = WindowHeightSizeClass.MEDIUM
                ),
                windowPosture = Posture(
                    isTabletop = true,
                    hingeList = listOf(hingeFeature)
                )
            )
        ) {
            FoldAwareScreen()
        }
    }

    composeTestRule.onNodeWithTag("top_content").assertIsDisplayed()
    composeTestRule.onNodeWithTag("bottom_content").assertIsDisplayed()
}
```

#### Testing Checklist for Large Screens

- [ ] App renders correctly at Compact, Medium, and Expanded widths
- [ ] List-detail shows side-by-side on Expanded, single-pane on Compact
- [ ] Navigation switches between bottom bar, rail, and drawer appropriately
- [ ] Content does not overlap the hinge area on foldables
- [ ] Tabletop posture positions content correctly above and below fold
- [ ] Keyboard shortcuts work (Ctrl+key combinations)
- [ ] Mouse hover states are visible
- [ ] Right-click context menus function
- [ ] App handles multi-window resize without crashes
- [ ] Drag and drop between windows works for applicable content types
- [ ] Minimum window size is enforced and layout does not break
- [ ] Configuration changes (rotation, fold/unfold) preserve state
