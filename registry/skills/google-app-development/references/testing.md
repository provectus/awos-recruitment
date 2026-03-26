# Testing Reference

Covers unit testing, ViewModel testing, Compose UI testing, integration testing, instrumented/E2E testing, coroutine testing, and test architecture for Android projects. For coroutine fundamentals and structured concurrency, see `concurrency.md`. For ViewModel and lifecycle patterns, see `android-lifecycle.md`. For Compose patterns used in UI tests, see `compose-patterns.md`.

## Contents
- Gradle Setup — JUnit 5, AndroidX Test, Compose testing, MockK, Turbine
- Unit Testing — JUnit 5, assertions, parameterized tests, test doubles
- MockK — mocking, stubbing, relaxed mocks, verification, coroutine mocks
- ViewModel Testing — `runTest`, `TestDispatcher`, Turbine for Flow, SavedStateHandle
- Coroutine Testing — `runTest`, `StandardTestDispatcher`, `UnconfinedTestDispatcher`, `advanceUntilIdle`
- Compose UI Testing — `createComposeRule`, semantics, finders, actions, assertions
- Integration Testing — Robolectric, AndroidX Test, Room in-memory testing, Hilt testing
- Instrumented / E2E Testing — Espresso basics, Compose on-device tests, test orchestrator
- Test Architecture — test pyramid, what to test where, MVI/MVVM strategies
- Common Patterns — fake vs mock, TestRule, test fixtures, CI considerations
- Best Practices — deterministic tests, naming, flaky test prevention


## Gradle Setup

```kotlin
// libs.versions.toml
[versions]
junit5 = "<latest>"
androidx-test = "<latest>"
androidx-test-runner = "<latest>"
compose-bom = "<latest>"
mockk = "<latest>"
turbine = "<latest>"
robolectric = "<latest>"
coroutines-test = "<latest>"
truth = "<latest>"

[libraries]
junit5-api = { module = "org.junit.jupiter:junit-jupiter-api", version.ref = "junit5" }
junit5-engine = { module = "org.junit.jupiter:junit-jupiter-engine", version.ref = "junit5" }
junit5-params = { module = "org.junit.jupiter:junit-jupiter-params", version.ref = "junit5" }
androidx-test-core = { module = "androidx.test:core-ktx", version.ref = "androidx-test" }
androidx-test-runner = { module = "androidx.test:runner", version.ref = "androidx-test-runner" }
compose-bom = { module = "androidx.compose:compose-bom", version.ref = "compose-bom" }
compose-ui-test = { module = "androidx.compose.ui:ui-test-junit4" }
compose-ui-test-manifest = { module = "androidx.compose.ui:ui-test-manifest" }
mockk = { module = "io.mockk:mockk", version.ref = "mockk" }
mockk-android = { module = "io.mockk:mockk-android", version.ref = "mockk" }
turbine = { module = "app.cash.turbine:turbine", version.ref = "turbine" }
robolectric = { module = "org.robolectric:robolectric", version.ref = "robolectric" }
coroutines-test = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-test", version.ref = "coroutines-test" }
truth = { module = "com.google.truth:truth", version.ref = "truth" }
```

```kotlin
// build.gradle.kts (app or feature module)
plugins {
    id("de.mannodermaus.android-junit-framework") // JUnit 5+ support for Android
}

dependencies {
    // Unit tests
    testImplementation(libs.junit5.api)
    testRuntimeOnly(libs.junit5.engine)
    testImplementation(libs.junit5.params)
    testImplementation(libs.mockk)
    testImplementation(libs.turbine)
    testImplementation(libs.coroutines.test)
    testImplementation(libs.truth)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)

    // Instrumented tests
    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.compose.ui.test)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.mockk.android)
    debugImplementation(libs.compose.ui.test.manifest)
}
```

> **Note:** JUnit 5 on Android requires the `android-junit5` Gradle plugin. JUnit 4 is still needed for Compose UI tests (`ui-test-junit4`) and instrumented tests via AndroidJUnitRunner.


## Unit Testing

JUnit 5 is the recommended test framework. It provides lifecycle callbacks, parameterized tests, nested test classes, and display names.

### Basic Test Structure

```kotlin
class PriceCalculatorTest {

    private lateinit var calculator: PriceCalculator

    @BeforeEach
    fun setUp() {
        calculator = PriceCalculator(taxRate = 0.1)
    }

    @Test
    fun `apply discount reduces price by percentage`() {
        val result = calculator.applyDiscount(price = 100.0, discountPercent = 20)
        assertThat(result).isEqualTo(80.0)
    }

    @Test
    fun `negative discount throws IllegalArgumentException`() {
        assertThrows<IllegalArgumentException> {
            calculator.applyDiscount(price = 100.0, discountPercent = -5)
        }
    }
}
```

### Parameterized Tests

```kotlin
class EmailValidatorTest {

    @ParameterizedTest
    @ValueSource(strings = ["test@example.com", "user.name@domain.org", "a@b.co"])
    fun `valid emails pass validation`(email: String) {
        assertThat(EmailValidator.isValid(email)).isTrue()
    }

    @ParameterizedTest
    @CsvSource(
        "''          , false",
        "'no-at-sign', false",
        "'@no-local' , false",
        "'user@'     , false",
    )
    fun `invalid emails fail validation`(email: String, expected: Boolean) {
        assertThat(EmailValidator.isValid(email)).isEqualTo(expected)
    }

    @ParameterizedTest
    @MethodSource("edgeCases")
    fun `edge case emails`(email: String, expected: Boolean) {
        assertThat(EmailValidator.isValid(email)).isEqualTo(expected)
    }

    companion object {
        @JvmStatic
        fun edgeCases() = listOf(
            Arguments.of("very.long.email.address@subdomain.example.com", true),
            Arguments.of("user+tag@example.com", true),
        )
    }
}
```

### Nested Tests

```kotlin
class OrderServiceTest {

    @Nested
    inner class `when order is pending` {
        @Test
        fun `can be cancelled`() { /* ... */ }

        @Test
        fun `can be confirmed`() { /* ... */ }
    }

    @Nested
    inner class `when order is shipped` {
        @Test
        fun `cannot be cancelled`() { /* ... */ }

        @Test
        fun `can be returned within 30 days`() { /* ... */ }
    }
}
```


## MockK

MockK is the idiomatic Kotlin mocking library. Prefer fakes for simple interfaces; use MockK when fake implementation would be complex or when verifying interactions matters.

### Basic Mocking

```kotlin
class OrderRepositoryTest {

    private val api = mockk<OrderApi>()
    private val dao = mockk<OrderDao>(relaxUnitFun = true) // auto-stubs Unit functions
    private val repository = OrderRepository(api, dao)

    @Test
    fun `fetches orders from API and caches in DB`() = runTest {
        val orders = listOf(Order(id = "1", name = "Widget"))
        coEvery { api.getOrders() } returns orders

        val result = repository.refreshOrders()

        assertThat(result).isEqualTo(orders)
        coVerify { dao.insertAll(orders) }
    }

    @Test
    fun `returns cached orders when API fails`() = runTest {
        val cached = listOf(Order(id = "1", name = "Cached"))
        coEvery { api.getOrders() } throws IOException("Network error")
        coEvery { dao.getAll() } returns cached

        val result = repository.getOrders()

        assertThat(result).isEqualTo(cached)
    }
}
```

### Argument Capturing

```kotlin
@Test
fun `logs analytics event with correct parameters`() {
    val slot = slot<AnalyticsEvent>()
    every { analytics.track(capture(slot)) } returns Unit

    viewModel.onPurchaseCompleted(orderId = "123")

    assertThat(slot.captured.name).isEqualTo("purchase_complete")
    assertThat(slot.captured.params["order_id"]).isEqualTo("123")
}
```


## ViewModel Testing

ViewModels are the primary unit test target in Android. Test state emissions and side effects.

### Basic ViewModel Test

```kotlin
class ItemListViewModelTest {

    // Replace Main dispatcher for tests
    @JvmField
    @RegisterExtension
    val mainDispatcherRule = MainDispatcherExtension()

    private val repository = mockk<ItemRepository>()
    private lateinit var viewModel: ItemListViewModel

    @Test
    fun `loading items emits Loading then Success`() = runTest {
        val items = listOf(Item(id = "1", name = "Widget"))
        coEvery { repository.getItems() } returns items

        viewModel = ItemListViewModel(repository)

        viewModel.uiState.test { // Turbine
            assertThat(awaitItem()).isEqualTo(UiState.Loading)
            assertThat(awaitItem()).isEqualTo(UiState.Success(items))
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun `error from repository emits Error state`() = runTest {
        coEvery { repository.getItems() } throws IOException("fail")

        viewModel = ItemListViewModel(repository)

        viewModel.uiState.test {
            assertThat(awaitItem()).isEqualTo(UiState.Loading)
            val error = awaitItem()
            assertThat(error).isInstanceOf(UiState.Error::class.java)
            cancelAndIgnoreRemainingEvents()
        }
    }
}
```

### MainDispatcher Extension (JUnit 5)

```kotlin
class MainDispatcherExtension(
    private val dispatcher: TestDispatcher = UnconfinedTestDispatcher(),
) : BeforeEachCallback, AfterEachCallback {

    override fun beforeEach(context: ExtensionContext?) {
        Dispatchers.setMain(dispatcher)
    }

    override fun afterEach(context: ExtensionContext?) {
        Dispatchers.resetMain()
    }
}
```

### Testing SavedStateHandle

```kotlin
@Test
fun `restores selected tab from SavedStateHandle`() = runTest {
    val savedState = SavedStateHandle(mapOf("selected_tab" to 2))
    viewModel = SettingsViewModel(savedState)

    assertThat(viewModel.selectedTab.value).isEqualTo(2)
}
```


## Coroutine Testing

Use `kotlinx-coroutines-test` for controlling coroutine execution in tests. See `concurrency.md` for production coroutine patterns.

### runTest and TestDispatchers

```kotlin
@Test
fun `debounced search waits before querying`() = runTest {
    val searchRepository = FakeSearchRepository()
    val viewModel = SearchViewModel(searchRepository, StandardTestDispatcher(testScheduler))

    viewModel.onQueryChanged("kot")
    advanceTimeBy(200) // less than debounce threshold
    assertThat(searchRepository.queryCount).isEqualTo(0)

    advanceTimeBy(400) // past debounce threshold
    assertThat(searchRepository.queryCount).isEqualTo(1)
}
```

| Dispatcher | Behavior | Use when |
|---|---|---|
| `StandardTestDispatcher` | Manual advancement, fine control | Testing delays, debounce, timeouts |
| `UnconfinedTestDispatcher` | Eager execution | Simple state tests, ViewModels |

### Testing Flow with Turbine

```kotlin
@Test
fun `combines user and preferences into profile`() = runTest {
    val userFlow = MutableStateFlow(User(name = "Andrii"))
    val prefsFlow = MutableStateFlow(Prefs(darkMode = true))

    val profileFlow = combine(userFlow, prefsFlow) { user, prefs ->
        Profile(user.name, prefs.darkMode)
    }

    profileFlow.test {
        assertThat(awaitItem()).isEqualTo(Profile("Andrii", darkMode = true))

        prefsFlow.value = Prefs(darkMode = false)
        assertThat(awaitItem()).isEqualTo(Profile("Andrii", darkMode = false))

        cancelAndIgnoreRemainingEvents()
    }
}
```


## Compose UI Testing

Compose tests use semantics tree, not view hierarchy. Both local (Robolectric) and on-device (instrumented) execution are supported.

> **Compose Testing v2:** Recent versions of `ui-test-junit4` introduce v2 testing APIs that use `StandardTestDispatcher` by default (v1 used `UnconfinedTestDispatcher`). The v1 APIs (`createComposeRule()`, `createAndroidComposeRule()`) are being deprecated. If your project uses a recent alpha/beta Compose testing version (1.11.0+), migrate to the v2 APIs. The finders, actions, and assertions (`onNodeWithText`, `performClick`, `assertIsDisplayed`) remain the same across both versions.

### Gradle Note

Compose UI tests use JUnit 4 rule (`createComposeRule`). Even in a JUnit 5 project, Compose tests run with JUnit 4.

### Basic Compose Test

```kotlin
class GreetingScreenTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun displays_greeting_with_name() {
        composeTestRule.setContent {
            GreetingScreen(name = "Andrii")
        }

        composeTestRule
            .onNodeWithText("Hello, Andrii!")
            .assertIsDisplayed()
    }

    @Test
    fun clicking_button_triggers_callback() {
        var clicked = false
        composeTestRule.setContent {
            GreetingScreen(
                name = "Andrii",
                onButtonClick = { clicked = true },
            )
        }

        composeTestRule
            .onNodeWithText("Greet")
            .performClick()

        assertThat(clicked).isTrue()
    }
}
```

### Finders, Actions, Assertions

```kotlin
// Finders
onNodeWithText("Submit")                              // by text
onNodeWithContentDescription("Close button")          // by content description
onNodeWithTag("email_input")                          // by testTag
onNode(hasText("Error") and hasTestTag("banner"))     // combined matchers
onAllNodesWithTag("list_item")                        // multiple nodes

// Actions
.performClick()
.performTextInput("user@example.com")
.performTextClearance()
.performScrollTo()
.performTouchInput { swipeLeft() }

// Assertions
.assertIsDisplayed()
.assertIsNotDisplayed()
.assertIsEnabled()
.assertIsNotEnabled()
.assertTextEquals("Expected")
.assertHasClickAction()
.assertCountEquals(3)                                 // on SemanticsNodeInteractionCollection
```

### Testing LazyColumn

```kotlin
@Test
fun lazy_column_shows_all_items() {
    val items = (1..50).map { "Item $it" }
    composeTestRule.setContent {
        ItemList(items = items)
    }

    // Scroll to item and verify
    composeTestRule
        .onNodeWithTag("item_list")
        .performScrollToIndex(49)

    composeTestRule
        .onNodeWithText("Item 50")
        .assertIsDisplayed()
}
```

### TestTag for Testability

```kotlin
// Production code — add testTag for test targeting
@Composable
fun ItemCard(item: Item, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.testTag("item_card_${item.id}")
    ) {
        Text(item.name)
    }
}
```

### Waiting for Async Content

```kotlin
@Test
fun shows_data_after_loading() {
    composeTestRule.setContent {
        DataScreen(viewModel = testViewModel)
    }

    // Wait for loading to complete
    composeTestRule.waitUntil(timeoutMillis = 5_000) {
        composeTestRule
            .onAllNodesWithTag("data_item")
            .fetchSemanticsNodes()
            .isNotEmpty()
    }

    composeTestRule
        .onAllNodesWithTag("data_item")
        .assertCountEquals(3)
}
```


## Integration Testing

### Robolectric

Run Android framework tests on JVM without a device. Faster than instrumented tests.

```kotlin
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class NotificationHelperTest {

    private val context = ApplicationProvider.getApplicationContext<Application>()

    @Test
    fun `creates notification channel on API 26+`() {
        val helper = NotificationHelper(context)
        helper.createChannels()

        val manager = context.getSystemService(NotificationManager::class.java)
        val channel = manager.getNotificationChannel("alerts")
        assertThat(channel).isNotNull()
        assertThat(channel.importance).isEqualTo(NotificationManager.IMPORTANCE_HIGH)
    }
}
```

### Room In-Memory Testing

```kotlin
class ItemDaoTest {

    private lateinit var db: AppDatabase
    private lateinit var dao: ItemDao

    @BeforeEach
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            AppDatabase::class.java,
        ).allowMainThreadQueries().build()
        dao = db.itemDao()
    }

    @AfterEach
    fun tearDown() {
        db.close()
    }

    @Test
    fun `insert and query items`() = runTest {
        val item = ItemEntity(id = "1", name = "Widget", price = 9.99)
        dao.insert(item)

        val result = dao.getById("1")
        assertThat(result).isEqualTo(item)
    }

    @Test
    fun `delete removes item`() = runTest {
        dao.insert(ItemEntity(id = "1", name = "Widget", price = 9.99))
        dao.deleteById("1")

        assertThat(dao.getById("1")).isNull()
    }
}
```

### Hilt Testing

```kotlin
@HiltAndroidTest
@RunWith(RobolectricTestRunner::class)
class OrderServiceTest {

    @get:Rule
    val hiltRule = HiltAndroidRule(this)

    @Inject
    lateinit var orderService: OrderService

    @BindValue
    val fakeApi: OrderApi = FakeOrderApi()

    @BeforeEach
    fun setUp() {
        hiltRule.inject()
    }

    @Test
    fun `places order through injected service`() = runTest {
        val result = orderService.placeOrder(OrderRequest(itemId = "1", quantity = 2))
        assertThat(result.isSuccess).isTrue()
    }
}
```


## Instrumented / E2E Testing

Run on real device or emulator. Use for tests that require actual Android system services.

### Compose On-Device Test

```kotlin
// src/androidTest/kotlin/...
@HiltAndroidTest
class CheckoutFlowTest {

    @get:Rule(order = 0)
    val hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun complete_checkout_flow() {
        // Add item to cart
        composeRule
            .onNodeWithText("Add to Cart")
            .performClick()

        // Navigate to checkout
        composeRule
            .onNodeWithText("Checkout")
            .performClick()

        // Fill shipping info
        composeRule
            .onNodeWithTag("address_input")
            .performTextInput("123 Main St")

        // Confirm order
        composeRule
            .onNodeWithText("Place Order")
            .performClick()

        // Verify confirmation
        composeRule
            .onNodeWithText("Order Confirmed")
            .assertIsDisplayed()
    }
}
```

### Test Orchestrator

Isolates each test in its own Instrumentation invocation — prevents shared state between tests.

```kotlin
// build.gradle.kts
android {
    defaultConfig {
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    testOptions {
        execution = "ANDROIDX_TEST_ORCHESTRATOR"
    }
}

dependencies {
    androidTestUtil("androidx.test:orchestrator:<latest>")
}
```


## Test Architecture

### Test Pyramid

| Level | Speed | Scope | Typical count |
|---|---|---|---|
| **Unit** | Fast (ms) | Single class/function | Many (70-80%) |
| **Integration** | Medium (s) | Multiple components | Moderate (15-20%) |
| **E2E/UI** | Slow (s-min) | Full user flow | Few (5-10%) |

### What to Test Where

| Component | Test type | Key assertions |
|---|---|---|
| **ViewModel** | Unit | State transitions, error handling, one-off events |
| **Repository** | Unit | Correct API calls, caching logic, error mapping |
| **Room DAO** | Integration | Queries return correct data, migrations work |
| **Use Case** | Unit | Business logic, input validation |
| **Composable** | UI (local) | Renders correctly, callbacks fire, state reflected |
| **Navigation flow** | E2E | Screens appear in correct order |

### MVI Testing Pattern

```kotlin
// Given: initial state
// When: intent/event dispatched
// Then: verify state transitions in order

@Test
fun `add to cart intent updates state`() = runTest {
    viewModel.uiState.test {
        assertThat(awaitItem().cartItems).isEmpty() // initial

        viewModel.onEvent(CartEvent.AddItem(itemId = "1"))

        val updated = awaitItem()
        assertThat(updated.cartItems).hasSize(1)
        assertThat(updated.cartItems.first().id).isEqualTo("1")

        cancelAndIgnoreRemainingEvents()
    }
}
```


## Common Patterns

### Fake vs Mock Decision

| Use | When |
|---|---|
| **Fake** | Simple interfaces, stateful behavior needed, reusable across tests |
| **Mock (MockK)** | Complex dependencies, verifying interactions, one-off stubbing |

```kotlin
// Fake — reusable, stateful
class FakeItemRepository : ItemRepository {
    private val items = mutableListOf<Item>()

    override suspend fun getItems(): List<Item> = items.toList()
    override suspend fun addItem(item: Item) { items.add(item) }
    override suspend fun deleteItem(id: String) { items.removeAll { it.id == id } }
}
```

### Custom TestRule (JUnit 4, for Compose tests)

```kotlin
class FakeTimeRule(private val fixedTime: Instant) : TestWatcher() {
    override fun starting(description: Description?) {
        TimeProvider.override(fixedTime)
    }

    override fun finished(description: Description?) {
        TimeProvider.reset()
    }
}
```

### CI Considerations

```kotlin
// build.gradle.kts — run unit tests in CI
tasks.withType<Test> {
    useJUnitPlatform() // JUnit 5
    testLogging {
        events("passed", "skipped", "failed")
        showStandardStreams = true
    }
    reports {
        html.required.set(true)
        junitXml.required.set(true)
    }
}
```

```bash
# CI: run unit tests
./gradlew testDebugUnitTest

# CI: run instrumented tests (requires emulator or device)
./gradlew connectedDebugAndroidTest
```


## Best Practices

- **Deterministic tests.** Never depend on real network, system time, or random values. Inject fakes or test doubles.
- **One assertion concept per test.** A test can have multiple `assertThat` calls, but they should verify one logical behavior.
- **Descriptive names.** Use backtick names: `` `cancelling order refunds payment` ``. The name should describe the behavior, not the method.
- **Arrange-Act-Assert.** Structure every test clearly. Use blank lines to separate sections.
- **No test interdependence.** Each test must set up its own state. Use `@BeforeEach`, not shared mutable state across tests.
- **Prefer `Truth` over JUnit assertions.** `assertThat(result).isEqualTo(expected)` reads better and provides better failure messages.
- **Test behavior, not implementation.** Verify what the code does, not how it does it. Avoid verifying internal method call order unless interaction is the contract.
- **Keep Compose testTags minimal.** Only add `testTag` where semantic matchers (`onNodeWithText`, `onNodeWithContentDescription`) are insufficient.
- **Flaky test = broken test.** Investigate and fix immediately. Common causes: timing, shared state, animation races. Use `composeTestRule.waitUntil` for async UI.
- **Run tests locally before push.** Fast feedback loop: `./gradlew testDebugUnitTest` should complete in under 60 seconds for a module.
