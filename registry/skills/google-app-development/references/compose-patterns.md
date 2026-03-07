# Jetpack Compose Patterns Reference

## Composable Design

### Stateless vs Stateful

```kotlin
// Stateless — receives state, emits events (preferred)
@Composable
fun UserCard(
    name: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(modifier = modifier.clickable(onClick = onClick)) {
        Text(name, style = MaterialTheme.typography.titleMedium)
    }
}

// Stateful — owns its own state (use sparingly)
@Composable
fun ExpandableCard(title: String, modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(false) }
    Card(modifier = modifier.clickable { expanded = !expanded }) {
        Text(title)
        AnimatedVisibility(expanded) { Text("Details...") }
    }
}
```

Rules:
- Prefer stateless composables — easier to test, preview, and reuse.
- Hoist state to the caller. The composable that *creates* the state should be the one that *owns* it.
- Accept `modifier: Modifier = Modifier` as the first optional parameter.

### Slot-Based APIs

```kotlin
@Composable
fun AppBar(
    title: @Composable () -> Unit,
    navigationIcon: @Composable () -> Unit = {},
    actions: @Composable RowScope.() -> Unit = {},
) {
    TopAppBar(
        title = title,
        navigationIcon = navigationIcon,
        actions = actions,
    )
}

// Usage
AppBar(
    title = { Text("Home") },
    navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) } },
    actions = { IconButton(onClick = onSettings) { Icon(Icons.Default.Settings, null) } },
)
```

Use `@Composable` lambda parameters (slots) instead of configuration parameters for flexible composition.


## State Management

### remember and rememberSaveable

```kotlin
// remember — survives recomposition, lost on config change
var count by remember { mutableIntStateOf(0) }

// rememberSaveable — survives config change AND process death
var query by rememberSaveable { mutableStateOf("") }

// remember with keys — recomputes when key changes
val filtered = remember(items, query) { items.filter { it.contains(query) } }
```

### derivedStateOf

```kotlin
// Avoid recomposition when the derived value hasn't changed
val hasItems by remember { derivedStateOf { items.isNotEmpty() } }

// Good: LazyColumn recomposes only when firstVisibleItemIndex crosses threshold
val showButton by remember {
    derivedStateOf { listState.firstVisibleItemIndex > 0 }
}
```

Use `derivedStateOf` when the derived value changes less often than its inputs.

### snapshotFlow

```kotlin
// Convert Compose state to a Flow
LaunchedEffect(listState) {
    snapshotFlow { listState.firstVisibleItemIndex }
        .distinctUntilChanged()
        .collect { index -> analytics.trackScroll(index) }
}
```

### State Holders

```kotlin
// For complex state logic, extract a state holder
class SearchBarState(
    initialQuery: String = "",
    private val onSearch: (String) -> Unit,
) {
    var query by mutableStateOf(initialQuery)
        private set
    var active by mutableStateOf(false)
        private set

    fun updateQuery(new: String) { query = new }
    fun submit() { onSearch(query); active = false }
    fun activate() { active = true }
}

@Composable
fun rememberSearchBarState(onSearch: (String) -> Unit): SearchBarState {
    return remember { SearchBarState(onSearch = onSearch) }
}
```


## Recomposition

### What Triggers Recomposition

- Reading a `State<T>` value that has changed.
- Parent composable recomposing and passing new parameters.

### Stability

```kotlin
// Stable — Compose can skip recomposition when equal
data class User(val id: String, val name: String)  // data class with immutable vals = stable

// Unstable — Compose must always recompose
data class UserList(val users: MutableList<User>)   // mutable collection = unstable

// Fix: use immutable collections
data class UserList(val users: List<User>)           // List (read-only interface) = stable
```

### @Stable and @Immutable

```kotlin
// Mark types that Compose can't infer stability for
@Stable
interface UserRepository {
    fun getUser(id: String): Flow<User>
}

// @Immutable — guarantees all properties will never change after construction
@Immutable
data class Theme(val primary: Color, val background: Color)
```

### Performance Pitfalls

```kotlin
// BAD — lambda created every recomposition, causes child to recompose
items.forEach { item ->
    ItemCard(onClick = { viewModel.select(item) })
}

// GOOD — stable lambda reference
items.forEach { item ->
    val onClick = remember(item.id) { { viewModel.select(item) } }
    ItemCard(onClick = onClick)
}

// BAD — new list every recomposition
val sorted = items.sortedBy { it.name }

// GOOD — derived state
val sorted by remember { derivedStateOf { items.sortedBy { it.name } } }
```


## Navigation

### NavHost and Type-Safe Navigation

```kotlin
// Define routes as serializable classes (type-safe navigation)
@Serializable data object Home
@Serializable data class Profile(val userId: String)
@Serializable data object Settings

@Composable
fun AppNavGraph(navController: NavHostController = rememberNavController()) {
    NavHost(navController = navController, startDestination = Home) {
        composable<Home> {
            HomeScreen(onUserClick = { id -> navController.navigate(Profile(id)) })
        }
        composable<Profile> { backStackEntry ->
            val profile: Profile = backStackEntry.toRoute()
            ProfileScreen(userId = profile.userId)
        }
        composable<Settings> { SettingsScreen() }
    }
}
```

### Nested Graphs

```kotlin
NavHost(navController, startDestination = Home) {
    composable<Home> { HomeScreen() }
    navigation<AuthGraph>(startDestination = Login) {
        composable<Login> { LoginScreen() }
        composable<Register> { RegisterScreen() }
    }
}
```

### Bottom Navigation

```kotlin
@Composable
fun MainScreen() {
    val navController = rememberNavController()
    Scaffold(
        bottomBar = {
            NavigationBar {
                val backStackEntry by navController.currentBackStackEntryAsState()
                val currentRoute = backStackEntry?.destination

                topLevelRoutes.forEach { route ->
                    NavigationBarItem(
                        selected = currentRoute?.hasRoute(route.route::class) == true,
                        onClick = {
                            navController.navigate(route.route) {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(route.icon, contentDescription = route.label) },
                        label = { Text(route.label) },
                    )
                }
            }
        },
    ) { innerPadding ->
        NavHost(navController, startDestination = Home, Modifier.padding(innerPadding)) { ... }
    }
}
```

### Deep Links

```kotlin
composable<Profile>(
    deepLinks = listOf(navDeepLink<Profile>(basePath = "https://example.com/user")),
) { ... }
```


## Side Effects

| Effect | When to Use |
|---|---|
| `LaunchedEffect(key)` | Run suspend code when key changes; cancels on key change or leave |
| `DisposableEffect(key)` | Set up / tear down non-suspend resources (listeners, callbacks) |
| `SideEffect` | Publish Compose state to non-Compose code every recomposition |
| `rememberCoroutineScope()` | Launch coroutines from event handlers (onClick, etc.) |
| `rememberUpdatedState(value)` | Capture latest value in a long-lived effect without restarting it |
| `produceState(initial)` | Convert non-Compose state (Flow, callback) into Compose State |

```kotlin
// LaunchedEffect — one-time load
LaunchedEffect(userId) {
    viewModel.loadUser(userId)
}

// DisposableEffect — register/unregister
DisposableEffect(lifecycleOwner) {
    val observer = LifecycleEventObserver { _, event -> ... }
    lifecycleOwner.lifecycle.addObserver(observer)
    onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
}

// rememberUpdatedState — capture latest callback in long-running effect
@Composable
fun Timer(onTick: () -> Unit) {
    val currentOnTick by rememberUpdatedState(onTick)
    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            currentOnTick()
        }
    }
}

// produceState — convert Flow to State
@Composable
fun UserName(userId: String): State<String?> = produceState<String?>(null, userId) {
    repository.observeUser(userId).collect { value = it.name }
}
```


## Lists and Grids

### LazyColumn

```kotlin
LazyColumn(
    contentPadding = PaddingValues(16.dp),
    verticalArrangement = Arrangement.spacedBy(8.dp),
) {
    // ALWAYS provide keys for stable identity
    items(items = users, key = { it.id }) { user ->
        UserCard(user)
    }

    // Sticky headers
    stickyHeader { SectionHeader("Active") }
    items(activeUsers, key = { it.id }) { UserCard(it) }
}
```

### LazyVerticalGrid

```kotlin
LazyVerticalGrid(
    columns = GridCells.Adaptive(minSize = 160.dp),
    contentPadding = PaddingValues(16.dp),
    horizontalArrangement = Arrangement.spacedBy(8.dp),
    verticalArrangement = Arrangement.spacedBy(8.dp),
) {
    items(items = photos, key = { it.id }) { photo ->
        PhotoCard(photo)
    }
}
```

### Pagination with Paging 3

```kotlin
@Composable
fun UserListScreen(viewModel: UserViewModel = viewModel()) {
    val users = viewModel.userPager.collectAsLazyPagingItems()

    LazyColumn {
        items(count = users.itemCount, key = users.itemKey { it.id }) { index ->
            users[index]?.let { UserCard(it) }
        }

        when (users.loadState.append) {
            is LoadState.Loading -> item { LoadingIndicator() }
            is LoadState.Error -> item { RetryButton(onClick = { users.retry() }) }
            else -> {}
        }
    }
}
```


## Theming and Material 3

### Custom Theme

```kotlin
private val LightColors = lightColorScheme(
    primary = Color(0xFF6750A4),
    secondary = Color(0xFF625B71),
    tertiary = Color(0xFF7D5260),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFD0BCFF),
    secondary = Color(0xFFCCC2DC),
    tertiary = Color(0xFFEFB8C8),
)

@Composable
fun AppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            if (darkTheme) dynamicDarkColorScheme(LocalContext.current)
            else dynamicLightColorScheme(LocalContext.current)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = AppTypography,
        content = content,
    )
}
```

### CompositionLocal

```kotlin
// Define
data class AppDimens(val spacing: Dp = 16.dp, val cardElevation: Dp = 4.dp)
val LocalAppDimens = staticCompositionLocalOf { AppDimens() }

// Provide
CompositionLocalProvider(LocalAppDimens provides AppDimens(spacing = 24.dp)) {
    content()
}

// Consume
val spacing = LocalAppDimens.current.spacing
```

Use `CompositionLocal` sparingly — prefer explicit parameters. Good for: theme, navigation, analytics.


## Animations

```kotlin
// animate*AsState — simple value animation
val alpha by animateFloatAsState(if (visible) 1f else 0f, label = "alpha")

// AnimatedVisibility — show/hide with transition
AnimatedVisibility(
    visible = expanded,
    enter = fadeIn() + expandVertically(),
    exit = fadeOut() + shrinkVertically(),
) {
    DetailsContent()
}

// AnimatedContent — animate between different content
AnimatedContent(targetState = screen, label = "screen") { target ->
    when (target) {
        Screen.Home -> HomeContent()
        Screen.Profile -> ProfileContent()
    }
}

// Shared element transitions (Compose 1.7+)
SharedTransitionLayout {
    AnimatedContent(targetState = showDetail) { isDetail ->
        if (isDetail) {
            DetailScreen(
                Modifier.sharedElement(
                    rememberSharedContentState(key = "image-$id"),
                    animatedVisibilityScope = this@AnimatedContent,
                )
            )
        } else {
            ListItem(
                Modifier.sharedElement(
                    rememberSharedContentState(key = "image-$id"),
                    animatedVisibilityScope = this@AnimatedContent,
                )
            )
        }
    }
}
```


## Modifiers

### Ordering Matters

```kotlin
// Padding THEN background — padding is outside the background
Box(Modifier.padding(16.dp).background(Color.Red))

// Background THEN padding — padding is inside the background
Box(Modifier.background(Color.Red).padding(16.dp))
```

### Custom Modifier (Modern Approach — Modifier.Node)

```kotlin
// Modifier.Node — preferred for performance
fun Modifier.shimmer(): Modifier = this then ShimmerElement()

private class ShimmerElement : ModifierNodeElement<ShimmerNode>() {
    override fun create() = ShimmerNode()
    override fun update(node: ShimmerNode) {}
    override fun hashCode() = "shimmer".hashCode()
    override fun equals(other: Any?) = other is ShimmerElement
}

private class ShimmerNode : DrawModifierNode, Modifier.Node() {
    override fun ContentDrawScope.draw() {
        drawContent()
        // draw shimmer overlay
    }
}
```


## Dialogs, Sheets, Snackbars

```kotlin
// AlertDialog
var showDialog by remember { mutableStateOf(false) }
if (showDialog) {
    AlertDialog(
        onDismissRequest = { showDialog = false },
        title = { Text("Delete?") },
        text = { Text("This cannot be undone.") },
        confirmButton = { TextButton(onClick = { onDelete(); showDialog = false }) { Text("Delete") } },
        dismissButton = { TextButton(onClick = { showDialog = false }) { Text("Cancel") } },
    )
}

// ModalBottomSheet
var showSheet by remember { mutableStateOf(false) }
if (showSheet) {
    ModalBottomSheet(onDismissRequest = { showSheet = false }) {
        Column(Modifier.padding(16.dp)) {
            Text("Options", style = MaterialTheme.typography.titleLarge)
            // sheet content
        }
    }
}

// Snackbar with Scaffold
val snackbarHostState = remember { SnackbarHostState() }
Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }) { padding ->
    // To show:
    val scope = rememberCoroutineScope()
    Button(onClick = {
        scope.launch {
            val result = snackbarHostState.showSnackbar("Item deleted", actionLabel = "Undo")
            if (result == SnackbarResult.ActionPerformed) viewModel.undo()
        }
    }) { Text("Delete") }
}
```


## Text and Input

```kotlin
// TextField with validation
var email by rememberSaveable { mutableStateOf("") }
var emailError by rememberSaveable { mutableStateOf<String?>(null) }

OutlinedTextField(
    value = email,
    onValueChange = { email = it; emailError = null },
    label = { Text("Email") },
    isError = emailError != null,
    supportingText = emailError?.let { { Text(it) } },
    keyboardOptions = KeyboardOptions(
        keyboardType = KeyboardType.Email,
        imeAction = ImeAction.Next,
    ),
    keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(FocusDirection.Down) }),
    singleLine = true,
)

// Focus management
val focusManager = LocalFocusManager.current
val (emailFocus, passwordFocus) = remember { FocusRequester.createRefs() }

OutlinedTextField(
    modifier = Modifier.focusRequester(emailFocus),
    keyboardActions = KeyboardActions(onNext = { passwordFocus.requestFocus() }),
    ...
)
OutlinedTextField(
    modifier = Modifier.focusRequester(passwordFocus),
    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); submit() }),
    ...
)
```


## Performance

### Rules

1. **Provide keys** in `LazyColumn`/`LazyRow` — enables stable item identity.
2. **Use `derivedStateOf`** when derived values change less often than source.
3. **Avoid allocations in composition** — no `listOf()`, `mapOf()`, lambdas in body without `remember`.
4. **Use `@Stable`/`@Immutable`** on classes Compose can't infer stability for.
5. **Defer reads** — pass lambda instead of value when possible (`Modifier.offset { intOffset }` not `Modifier.offset(offset)`).
6. **Use `Modifier.Node`** for custom modifiers instead of `Modifier.composed`.

### Debugging

```kotlin
// Print recomposition count in debug builds
@Composable
fun DebugRecomposition(tag: String) {
    if (BuildConfig.DEBUG) {
        val count = remember { mutableIntStateOf(0) }
        count.intValue++
        Log.d("Recomposition", "$tag: ${count.intValue}")
    }
}
```

Use Layout Inspector in Android Studio to visualize recomposition counts and identify unnecessary recompositions.
