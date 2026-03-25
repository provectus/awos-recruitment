# Testing Reference (Swift Testing, XCTest, XCUITest)

Comprehensive guide to testing on Apple platforms. Swift Testing is the modern framework — use it for all new test targets (Xcode 16+, Swift 6). XCTest remains essential for UI automation (XCUITest), performance benchmarks, and existing test suites. Both frameworks coexist in the same target.

## Contents
- When to use which framework
- Swift Testing (@Test, @Suite, #expect, #require, traits, parameterized tests)
- XCTest unit tests (XCTestCase, assertions, expectations, performance)
- XCUITest UI tests (element queries, accessibility identifiers, Page Object pattern)
- Test doubles and dependency injection (protocols, mocks, spies, stubs)
- Testing @Observable and SwiftUI
- Test plans and configuration
- CI/CD testing (xcodebuild, result bundles, parallel testing)
- TDD workflow
- Common pitfalls

## When to Use Which

| Scenario | Recommendation |
|---|---|
| New test target (Xcode 16+) | Swift Testing |
| Existing XCTest target | XCTest — migrate incrementally |
| UI automation | XCUITest |
| Performance benchmarks | XCTest (`measure { }`) |
| Integration tests | Swift Testing or XCTest |
| Snapshot / preview tests | swift-snapshot-testing |
| Parameterized test cases | Swift Testing (`@Test(arguments:)`) |
| Async event confirmation | Swift Testing (`confirmation()`) |
| Testing on CI with older Xcode | XCTest |

**Rule:** Default to Swift Testing for new code. Use XCTest when you need UI testing, performance measurement, or must support Xcode 15 and earlier. Both frameworks can coexist in a single test target — no need to choose one exclusively.


## Swift Testing Framework

Swift Testing is Apple's modern test framework (Xcode 16+, Swift 6). It replaces XCTest for unit and integration tests with a cleaner, expression-based API.

### @Test and Basic Assertions
---

```swift
import Testing

@Test("User full name combines first and last name")
func userFullName() {
    let user = User(firstName: "Alice", lastName: "Smith")
    #expect(user.fullName == "Alice Smith")
}

@Test func decodingValidJSON() throws {
    let json = """
    {"id": "550e8400-e29b-41d4-a716-446655440000", "name": "Alice"}
    """.data(using: .utf8)!

    let user = try JSONDecoder().decode(User.self, from: json)
    #expect(user.name == "Alice")
    #expect(user.id == UUID(uuidString: "550e8400-e29b-41d4-a716-446655440000"))
}
```

#### #expect vs #require

`#expect` records a failure and continues. `#require` throws on failure, stopping the test immediately — use it when subsequent assertions depend on the result.

```swift
@Test func loadConfiguration() throws {
    let config = try #require(ConfigLoader.load("settings.json"))
    // If load returns nil, test stops here with a clear failure message
    #expect(config.apiBaseURL.host == "api.example.com")
    #expect(config.maxRetries == 3)
}

@Test func parseResponse() throws {
    let data = try #require(loadFixture("users_response.json"))
    let response = try JSONDecoder().decode(UsersResponse.self, from: data)
    #expect(response.users.count == 5)
    #expect(response.hasMore == true)
}
```

### Traits
---

Traits configure test behavior — disable tests, set time limits, tag for filtering, and more.

```swift
// Disabled test with reason
@Test(.disabled("Server migration in progress — re-enable after v2 API launch"))
func fetchLegacyEndpoint() async throws {
    // ...
}

// Conditional execution
@Test(.enabled(if: ProcessInfo.processInfo.environment["CI"] != nil))
func integrationTest() async throws {
    // Runs only on CI
}

// Time limit — test fails if it exceeds the duration
@Test(.timeLimit(.minutes(1)))
func longRunningSync() async throws {
    let result = try await heavyDataMigration()
    #expect(result.migratedCount > 0)
}

// Bug reference — links to a known issue
@Test(.bug("https://github.com/org/repo/issues/42", "Flaky on iOS 17.0"))
func widgetRefresh() async throws {
    // ...
}

// Multiple traits combine naturally
@Test(
    "Upload retries on transient failure",
    .tags(.networking),
    .timeLimit(.seconds(30)),
    .bug("https://jira.example.com/PROJ-123")
)
func uploadRetry() async throws {
    // ...
}
```

### Custom Tags
---

Tags let you filter and organize tests across suites.

```swift
extension Tag {
    @Tag static var networking: Self
    @Tag static var persistence: Self
    @Tag static var authentication: Self
    @Tag static var slow: Self
}

@Test(.tags(.networking, .authentication))
func tokenRefreshOnExpiry() async throws {
    let client = APIClient(tokenManager: FakeTokenManager(expired: true))
    let user: User = try await client.request(.getProfile)
    #expect(user.name == "Alice")
}

@Test(.tags(.persistence))
func saveAndRetrieveOrder() async throws {
    let store = InMemoryOrderStore()
    let order = Order.sample
    try await store.save(order)
    let retrieved = try await store.fetch(order.id)
    #expect(retrieved == order)
}
```

Run tagged tests from Xcode by selecting tags in the Test Navigator, or filter in test plans. From CLI, use `swift test --filter` with test name patterns — tag-based filtering is supported through Xcode Test Plans.

### Parameterized Tests
---

Run the same test logic across multiple inputs — each argument produces a separate test case in the results.

```swift
@Test("Email validation rejects invalid formats", arguments: [
    "",
    "plaintext",
    "@missing-local.com",
    "missing-domain@",
    "spaces in@email.com",
    "double@@at.com"
])
func invalidEmails(email: String) {
    #expect(EmailValidator.isValid(email) == false)
}

@Test("Currency formatting", arguments: [
    (amount: 1000, locale: Locale(identifier: "en_US"), expected: "$1,000.00"),
    (amount: 1000, locale: Locale(identifier: "de_DE"), expected: "1.000,00 €"),
    (amount: 1000, locale: Locale(identifier: "ja_JP"), expected: "￥1,000"),
])
func currencyFormatting(amount: Int, locale: Locale, expected: String) {
    let formatted = CurrencyFormatter.format(amount, locale: locale)
    #expect(formatted == expected)
}

// Two-dimensional: tests every combination of arguments
@Test(arguments: HTTPMethod.allCases, [200, 401, 500])
func responseHandling(method: HTTPMethod, statusCode: Int) async throws {
    let client = MockHTTPClient(stubbedStatusCode: statusCode)
    let result = await client.handleResponse(method: method)
    if statusCode == 200 {
        #expect(result.isSuccess)
    } else {
        #expect(result.isFailure)
    }
}
```

### @Suite — Test Organization
---

Group related tests into suites. Suites can nest and share setup via `init`/`deinit`.

```swift
@Suite("Authentication Flow")
struct AuthenticationTests {
    let authService: AuthService
    let tokenStore: FakeTokenStore

    init() {
        tokenStore = FakeTokenStore()
        authService = AuthService(
            apiClient: FakeAPIClient(),
            tokenStore: tokenStore
        )
    }

    @Test func loginWithValidCredentials() async throws {
        let session = try await authService.login(email: "alice@example.com", password: "secure123")
        #expect(session.isAuthenticated)
        #expect(tokenStore.storedAccessToken != nil)
    }

    @Test func loginWithInvalidPassword() async throws {
        await #expect(throws: AuthError.invalidCredentials) {
            try await authService.login(email: "alice@example.com", password: "wrong")
        }
    }

    @Test func logoutClearsTokens() async throws {
        try await authService.login(email: "alice@example.com", password: "secure123")
        await authService.logout()
        #expect(tokenStore.storedAccessToken == nil)
        #expect(tokenStore.storedRefreshToken == nil)
    }
}
```

#### Nested Suites

```swift
@Suite("Order Management")
struct OrderTests {
    @Suite("Creation")
    struct CreationTests {
        @Test func createOrderWithValidItems() async throws {
            let service = OrderService(repository: FakeOrderRepository())
            let order = try await service.createOrder(items: [.sample])
            #expect(order.status == .pending)
            #expect(order.items.count == 1)
        }
    }

    @Suite("Cancellation")
    struct CancellationTests {
        @Test func cancelPendingOrder() async throws {
            let repository = FakeOrderRepository(existingOrders: [.pending])
            let service = OrderService(repository: repository)
            try await service.cancel(orderId: Order.pending.id)
            let updated = try await repository.fetch(Order.pending.id)
            #expect(updated.status == .cancelled)
        }

        @Test func cannotCancelShippedOrder() async throws {
            let repository = FakeOrderRepository(existingOrders: [.shipped])
            let service = OrderService(repository: repository)
            await #expect(throws: OrderError.cannotCancel) {
                try await service.cancel(orderId: Order.shipped.id)
            }
        }
    }
}
```

### Lifecycle: init/deinit Instead of setUp/tearDown
---

Swift Testing uses the struct/class lifecycle — no `setUp`/`tearDown` methods. Use `init` for setup and `deinit` for cleanup.

```swift
@Suite struct DatabaseTests {
    let database: TestDatabase

    init() async throws {
        database = try await TestDatabase.createEmpty()
        try await database.runMigrations()
    }

    // Cleanup happens when the struct goes out of scope
    // For explicit cleanup, use a class-based suite:

    @Test func insertAndQuery() async throws {
        try await database.insert(User.sample)
        let users = try await database.fetchAllUsers()
        #expect(users.count == 1)
    }
}
```

### Confirmation for Async Events
---

`confirmation()` waits for an expected async event — the modern replacement for `XCTExpectation`.

```swift
@Test func notificationPostedOnSave() async throws {
    let store = DocumentStore()

    await confirmation("Document saved notification") { confirm in
        NotificationCenter.default.addObserver(
            forName: .documentDidSave, object: nil, queue: nil
        ) { _ in
            confirm()
        }
        try await store.save(Document.sample)
    }
}

// Expected count — confirm must be called exactly N times
@Test func batchProcessingNotifiesPerItem() async throws {
    let processor = BatchProcessor()
    let items = [Item.sample1, Item.sample2, Item.sample3]

    await confirmation("Item processed", expectedCount: 3) { confirm in
        processor.onItemProcessed = { _ in confirm() }
        await processor.processAll(items)
    }
}
```

### Parallel Execution
---

Swift Testing runs tests in parallel by default. Each `@Test` function runs independently. Use `.serialized` trait on a `@Suite` when tests share mutable state that cannot be isolated.

```swift
@Suite(.serialized)
struct FileSystemTests {
    @Test func writeFile() throws {
        try FileManager.default.createFile(at: tempPath, contents: testData)
        #expect(FileManager.default.fileExists(atPath: tempPath))
    }

    @Test func deleteFile() throws {
        try FileManager.default.removeItem(atPath: tempPath)
        #expect(!FileManager.default.fileExists(atPath: tempPath))
    }
}
```

Rules:
- Prefer parallel execution. Design tests to be independent.
- Use `.serialized` only when tests have unavoidable ordering dependencies (shared file system, shared database).
- Each `@Test` gets a fresh `init` of the containing `@Suite` struct — instance properties are not shared.

### Migration from XCTest
---

| XCTest | Swift Testing |
|---|---|
| `XCTestCase` subclass | `@Suite struct` |
| `func test...()` | `@Test func ...()` |
| `setUpWithError()` | `init() throws` |
| `tearDown()` | `deinit` (class suite) |
| `XCTAssertEqual(a, b)` | `#expect(a == b)` |
| `XCTAssertNil(x)` | `#expect(x == nil)` |
| `XCTAssertThrowsError(expr)` | `#expect(throws: ErrorType.self) { try expr }` |
| `XCTExpectation` + `wait` | `confirmation()` |
| `XCTSkipIf(condition)` | `@Test(.enabled(if: !condition))` |
| `measure { }` | No equivalent — keep in XCTest |
| `XCUITest` | No equivalent — keep in XCTest |


## XCTest — Unit Tests

XCTest is Apple's established testing framework. It remains necessary for UI tests, performance measurement, and targets that must support Xcode 15 or earlier.

### XCTestCase Pattern
---

```swift
import XCTest
@testable import MyApp

final class UserServiceTests: XCTestCase {
    private var sut: UserService!
    private var mockRepository: MockUserRepository!

    override func setUp() async throws {
        try await super.setUp()
        mockRepository = MockUserRepository()
        sut = UserService(repository: mockRepository)
    }

    override func tearDown() async throws {
        sut = nil
        mockRepository = nil
        try await super.tearDown()
    }

    func test_fetchUser_returnsDecodedUser() async throws {
        mockRepository.stubbedUser = User(id: UUID(), name: "Alice", email: "alice@example.com")

        let user = try await sut.fetchUser(id: mockRepository.stubbedUser!.id)

        XCTAssertEqual(user.name, "Alice")
        XCTAssertEqual(user.email, "alice@example.com")
    }

    func test_fetchUser_throwsOnNotFound() async {
        mockRepository.stubbedError = UserError.notFound

        do {
            _ = try await sut.fetchUser(id: UUID())
            XCTFail("Expected UserError.notFound")
        } catch {
            XCTAssertTrue(error is UserError)
        }
    }
}
```

### Assertions Quick Reference
---

```swift
// Equality
XCTAssertEqual(actual, expected)
XCTAssertEqual(price, 9.99, accuracy: 0.01) // Floating point

// Boolean
XCTAssertTrue(user.isActive)
XCTAssertFalse(order.isCancelled)

// Nil
XCTAssertNil(error)
XCTAssertNotNil(response)

// Throwing
XCTAssertThrowsError(try parser.parse(invalidJSON)) { error in
    XCTAssertEqual(error as? ParseError, .invalidSyntax)
}
XCTAssertNoThrow(try config.validate())

// Comparison
XCTAssertGreaterThan(results.count, 0)
XCTAssertLessThanOrEqual(latency, 1.0)
```

### XCTExpectation for Async Callbacks
---

Use expectations when testing callback-based (non-async) APIs:

```swift
func test_delegateReceivesUpdate() {
    let expectation = expectation(description: "Delegate called with update")

    let delegate = SpyDelegate()
    delegate.onUpdate = { value in
        XCTAssertEqual(value, 42)
        expectation.fulfill()
    }

    let service = EventService(delegate: delegate)
    service.start()

    waitForExpectations(timeout: 5)
}

// Multiple expectations
func test_batchProcessing_notifiesCompletion() {
    let started = expectation(description: "Processing started")
    let completed = expectation(description: "Processing completed")

    let processor = BatchProcessor()
    processor.onStart = { started.fulfill() }
    processor.onComplete = { completed.fulfill() }

    processor.process(items: testItems)

    wait(for: [started, completed], timeout: 10, enforceOrder: true)
}

// Inverted expectation — asserts something does NOT happen
func test_debounce_doesNotFireImmediately() {
    let fired = expectation(description: "Should not fire")
    fired.isInverted = true

    let debouncer = Debouncer(delay: 1.0)
    debouncer.onFire = { fired.fulfill() }
    debouncer.trigger()

    waitForExpectations(timeout: 0.5) // Passes if NOT fulfilled within 0.5s
}
```

### addTeardownBlock
---

Register cleanup that runs after each test, even on failure. Useful for cleaning up resources created during a test.

```swift
func test_tempFileCreation() throws {
    let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    FileManager.default.createFile(atPath: tempURL.path, contents: Data())

    addTeardownBlock {
        try? FileManager.default.removeItem(at: tempURL)
    }

    XCTAssertTrue(FileManager.default.fileExists(atPath: tempURL.path))
}
```

### Performance Measurement
---

```swift
func test_jsonDecoding_performance() throws {
    let largeJSON = try loadFixture("large_response.json")

    measure {
        _ = try? JSONDecoder().decode([User].self, from: largeJSON)
    }
}

// With metrics and options
func test_imageProcessing_performance() {
    let metrics: [XCTMetric] = [
        XCTClockMetric(),
        XCTMemoryMetric(),
        XCTCPUMetric()
    ]

    let options = XCTMeasureOptions()
    options.iterationCount = 10

    measure(metrics: metrics, options: options) {
        _ = ImageProcessor.resize(largeImage, to: CGSize(width: 100, height: 100))
    }
}
```

Rules:
- `measure` runs the block multiple times and reports average/deviation.
- Set baselines in Xcode to detect performance regressions.
- Performance tests are best kept in a separate test plan to avoid slowing down the main test suite.


## XCUITest — UI Tests

XCUITest automates the app's UI through accessibility elements. It launches the app in a separate process and interacts with it like a user would.

### Application Launch
---

```swift
import XCTest

final class LoginUITests: XCTestCase {
    let app = XCUIApplication()

    override func setUp() {
        super.setUp()
        continueAfterFailure = false

        // Launch arguments to configure app for testing
        app.launchArguments = ["--uitesting", "--reset-state"]
        app.launchEnvironment = [
            "API_BASE_URL": "http://localhost:8080",
            "DISABLE_ANIMATIONS": "1"
        ]
        app.launch()
    }

    override func tearDown() {
        app.terminate()
        super.tearDown()
    }
}
```

### Element Queries
---

```swift
func test_loginFlow() {
    // Text fields
    let emailField = app.textFields["emailTextField"]
    let passwordField = app.secureTextFields["passwordTextField"]

    emailField.tap()
    emailField.typeText("alice@example.com")

    passwordField.tap()
    passwordField.typeText("secure123")

    // Buttons
    app.buttons["loginButton"].tap()

    // Verify navigation to home screen
    let welcomeLabel = app.staticTexts["welcomeLabel"]
    XCTAssertTrue(welcomeLabel.waitForExistence(timeout: 5))
    XCTAssertEqual(welcomeLabel.label, "Welcome, Alice")
}
```

### Accessibility Identifiers
---

Accessibility identifiers are the foundation of reliable UI tests. Set them in your production code:

```swift
// In SwiftUI
struct LoginView: View {
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        VStack {
            TextField("Email", text: $email)
                .accessibilityIdentifier("emailTextField")

            SecureField("Password", text: $password)
                .accessibilityIdentifier("passwordTextField")

            Button("Log In") { login() }
                .accessibilityIdentifier("loginButton")
        }
    }
}

// In UIKit
emailTextField.accessibilityIdentifier = "emailTextField"
passwordField.accessibilityIdentifier = "passwordTextField"
loginButton.accessibilityIdentifier = "loginButton"
```

Rules:
- Always use `accessibilityIdentifier` — not `accessibilityLabel` — for test queries. Labels are user-facing and change with localization.
- Use a consistent naming convention (e.g., `screenName_elementType` or `camelCase` descriptors).
- Define identifiers as constants in a shared enum to avoid string drift between production and test code.

### Waiting for Elements
---

```swift
func test_searchResults_appear() {
    let searchField = app.searchFields["searchField"]
    searchField.tap()
    searchField.typeText("Swift")

    // Wait for results to load
    let firstResult = app.cells["searchResult_0"]
    let exists = firstResult.waitForExistence(timeout: 10)
    XCTAssertTrue(exists, "Search results did not appear within timeout")
}

// Custom predicate-based waiting
func test_loadingIndicator_disappears() {
    app.buttons["refreshButton"].tap()

    let spinner = app.activityIndicators["loadingIndicator"]
    let disappeared = NSPredicate(format: "exists == false")
    let expectation = XCTNSPredicateExpectation(predicate: disappeared, object: spinner)
    let result = XCTWaiter.wait(for: [expectation], timeout: 10)
    XCTAssertEqual(result, .completed)
}
```

### Page Object Pattern
---

Encapsulate screen interactions to keep tests readable and reduce duplication:

```swift
// Page object
struct LoginPage {
    let app: XCUIApplication

    var emailField: XCUIElement { app.textFields["emailTextField"] }
    var passwordField: XCUIElement { app.secureTextFields["passwordTextField"] }
    var loginButton: XCUIElement { app.buttons["loginButton"] }
    var errorLabel: XCUIElement { app.staticTexts["errorLabel"] }

    @discardableResult
    func typeEmail(_ email: String) -> Self {
        emailField.tap()
        emailField.typeText(email)
        return self
    }

    @discardableResult
    func typePassword(_ password: String) -> Self {
        passwordField.tap()
        passwordField.typeText(password)
        return self
    }

    func tapLogin() -> HomePage {
        loginButton.tap()
        return HomePage(app: app)
    }

    func tapLoginExpectingError() -> Self {
        loginButton.tap()
        return self
    }
}

struct HomePage {
    let app: XCUIApplication

    var welcomeLabel: XCUIElement { app.staticTexts["welcomeLabel"] }

    func waitForLoad(timeout: TimeInterval = 5) -> Bool {
        welcomeLabel.waitForExistence(timeout: timeout)
    }
}

// Tests become concise and readable
func test_successfulLogin() {
    let homePage = LoginPage(app: app)
        .typeEmail("alice@example.com")
        .typePassword("secure123")
        .tapLogin()

    XCTAssertTrue(homePage.waitForLoad())
}

func test_invalidCredentials_showsError() {
    let loginPage = LoginPage(app: app)
        .typeEmail("alice@example.com")
        .typePassword("wrong")
        .tapLoginExpectingError()

    XCTAssertTrue(loginPage.errorLabel.waitForExistence(timeout: 5))
    XCTAssertEqual(loginPage.errorLabel.label, "Invalid email or password")
}
```

### Screenshots and Attachments
---

```swift
func test_onboarding_screenshots() {
    let onboarding = OnboardingPage(app: app)

    // Capture screenshot at each step
    let step1 = XCTAttachment(screenshot: app.screenshot())
    step1.name = "Onboarding - Step 1"
    step1.lifetime = .keepAlways
    add(step1)

    onboarding.tapNext()

    let step2 = XCTAttachment(screenshot: app.screenshot())
    step2.name = "Onboarding - Step 2"
    step2.lifetime = .keepAlways
    add(step2)
}

// Automatic screenshot on failure (in setUp)
override func setUp() {
    super.setUp()
    continueAfterFailure = false
    // Xcode automatically captures screenshots on failure — find them in .xcresult
}
```


## Test Doubles & Dependency Injection

Effective testing requires controlling dependencies. Use protocol-based injection to substitute real implementations with test doubles.

### Protocol-Based Mocking
---

```swift
// Define a protocol for the dependency
protocol UserRepository: Sendable {
    func fetch(id: UUID) async throws -> User
    func save(_ user: User) async throws
    func delete(id: UUID) async throws
}

// Production implementation
final class RemoteUserRepository: UserRepository {
    private let apiClient: APIClient

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    func fetch(id: UUID) async throws -> User {
        try await apiClient.request(.getUser(id: id))
    }

    func save(_ user: User) async throws {
        try await apiClient.request(.updateUser(user))
    }

    func delete(id: UUID) async throws {
        try await apiClient.request(.deleteUser(id: id))
    }
}

// Test double — stub
final class StubUserRepository: UserRepository {
    var stubbedUser: User?
    var stubbedError: Error?

    func fetch(id: UUID) async throws -> User {
        if let error = stubbedError { throw error }
        guard let user = stubbedUser else { throw UserError.notFound }
        return user
    }

    func save(_ user: User) async throws {
        if let error = stubbedError { throw error }
    }

    func delete(id: UUID) async throws {
        if let error = stubbedError { throw error }
    }
}
```

### Spy Pattern
---

A spy records interactions for later verification.

```swift
final class SpyUserRepository: UserRepository {
    private(set) var fetchCallCount = 0
    private(set) var fetchedIds: [UUID] = []
    private(set) var savedUsers: [User] = []
    private(set) var deletedIds: [UUID] = []

    var stubbedUser: User?

    func fetch(id: UUID) async throws -> User {
        fetchCallCount += 1
        fetchedIds.append(id)
        return stubbedUser ?? User.sample
    }

    func save(_ user: User) async throws {
        savedUsers.append(user)
    }

    func delete(id: UUID) async throws {
        deletedIds.append(id)
    }
}

// Usage in test
@Test func updateProfile_savesUser() async throws {
    let spy = SpyUserRepository()
    spy.stubbedUser = User.sample
    let service = ProfileService(repository: spy)

    try await service.updateName("Bob", for: User.sample.id)

    #expect(spy.savedUsers.count == 1)
    #expect(spy.savedUsers.first?.name == "Bob")
    #expect(spy.fetchCallCount == 1)
}
```

### Dependency Injection for Testability
---

Structure your app so dependencies are injected, never created internally.

```swift
// View model accepts dependencies via init
@MainActor
@Observable
class OrderListViewModel {
    var orders: [Order] = []
    var isLoading = false

    private let orderRepository: OrderRepository
    private let analytics: AnalyticsService

    init(orderRepository: OrderRepository, analytics: AnalyticsService) {
        self.orderRepository = orderRepository
        self.analytics = analytics
    }

    func loadOrders() async {
        isLoading = true
        defer { isLoading = false }
        do {
            orders = try await orderRepository.fetchAll()
            analytics.track(.ordersLoaded(count: orders.count))
        } catch {
            analytics.track(.ordersLoadFailed(error: error))
        }
    }
}

// Test with injected doubles
@Test @MainActor
func loadOrders_setsOrdersAndTracksAnalytics() async {
    let stubRepo = StubOrderRepository(orders: [.sample1, .sample2])
    let spyAnalytics = SpyAnalyticsService()
    let viewModel = OrderListViewModel(orderRepository: stubRepo, analytics: spyAnalytics)

    await viewModel.loadOrders()

    #expect(viewModel.orders.count == 2)
    #expect(viewModel.isLoading == false)
    #expect(spyAnalytics.trackedEvents.contains(.ordersLoaded(count: 2)))
}
```

### SwiftUI Environment-Based Injection
---

```swift
// Define environment key
private struct UserRepositoryKey: EnvironmentKey {
    static let defaultValue: UserRepository = RemoteUserRepository(apiClient: .shared)
}

extension EnvironmentValues {
    var userRepository: UserRepository {
        get { self[UserRepositoryKey.self] }
        set { self[UserRepositoryKey.self] = newValue }
    }
}

// Use in view
struct UserProfileView: View {
    @Environment(\.userRepository) private var repository
    @State private var user: User?

    var body: some View {
        // ...
    }
}

// Override in tests or previews
#Preview {
    UserProfileView()
        .environment(\.userRepository, StubUserRepository(stubbedUser: .sample))
}
```


## Testing with @Observable and SwiftUI

### Testing @Observable ViewModels
---

```swift
@MainActor
@Observable
class ProductSearchViewModel {
    var query = ""
    var products: [Product] = []
    var isSearching = false
    var errorMessage: String?

    private let searchService: ProductSearchService
    private let clock: any Clock<Duration>
    private var searchTask: Task<Void, Never>?

    init(searchService: ProductSearchService, clock: any Clock<Duration> = ContinuousClock()) {
        self.searchService = searchService
        self.clock = clock
    }

    func search() {
        searchTask?.cancel()
        guard !query.isEmpty else {
            products = []
            return
        }
        searchTask = Task {
            isSearching = true
            defer { isSearching = false }
            do {
                try await clock.sleep(for: .milliseconds(300))
                guard !Task.isCancelled else { return }
                products = try await searchService.search(query: query)
            } catch is CancellationError {
                // Expected — ignore
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

// Tests — inject ImmediateClockProtocol to skip debounce delay
@Suite("Product Search ViewModel")
struct ProductSearchViewModelTests {
    // A test clock that returns immediately, eliminating timing flakiness
    struct ImmediateClock: Clock {
        typealias Duration = Swift.Duration
        typealias Instant = ContinuousClock.Instant
        var now: Instant { ContinuousClock.now }
        var minimumResolution: Duration { .zero }
        func sleep(until deadline: Instant, tolerance: Duration?) async throws {
            try Task.checkCancellation()
        }
    }

    @Test @MainActor
    func search_populatesProducts() async throws {
        let stub = StubProductSearchService(results: [.sample1, .sample2])
        let vm = ProductSearchViewModel(searchService: stub, clock: ImmediateClock())

        vm.query = "shoes"
        vm.search()

        // ImmediateClock skips the debounce — no Task.sleep needed
        try await Task.yield()

        #expect(vm.products.count == 2)
        #expect(vm.isSearching == false)
    }

    @Test @MainActor
    func search_emptyQuery_clearsResults() async {
        let stub = StubProductSearchService(results: [.sample1])
        let vm = ProductSearchViewModel(searchService: stub, clock: ImmediateClock())

        vm.query = ""
        vm.search()

        #expect(vm.products.isEmpty)
    }

    @Test @MainActor
    func search_failure_setsErrorMessage() async throws {
        let stub = StubProductSearchService(error: SearchError.serviceUnavailable)
        let vm = ProductSearchViewModel(searchService: stub, clock: ImmediateClock())

        vm.query = "shoes"
        vm.search()

        try await Task.yield()

        #expect(vm.errorMessage != nil)
        #expect(vm.products.isEmpty)
    }
}
```

Rules:
- Inject `Clock` protocol to make time-dependent code testable without `Task.sleep` in tests.
- Use an `ImmediateClock` test double that returns instantly — eliminates flakiness from timing.
- `Task.yield()` gives the spawned task a chance to run without introducing arbitrary delays.
- In production, `ContinuousClock()` is the default — no behavioral change.

### Snapshot Testing with swift-snapshot-testing
---

Verify UI appearance by comparing rendered views against reference images.

```swift
// Package.swift dependency
// .package(url: "https://github.com/pointfreeco/swift-snapshot-testing", from: "<latest-stable>")

import SnapshotTesting
import SwiftUI
import XCTest
@testable import MyApp

final class ProductCardSnapshotTests: XCTestCase {
    func test_productCard_defaultState() {
        let view = ProductCardView(product: .sample)
            .frame(width: 320)

        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    func test_productCard_soldOut() {
        let product = Product.sample(availableStock: 0)
        let view = ProductCardView(product: product)
            .frame(width: 320)

        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // Test multiple device sizes
    func test_productList_iPhoneSE() {
        let view = NavigationStack {
            ProductListView(products: Product.sampleList)
        }

        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhoneSe)))
    }

    func test_productList_iPhone15Pro() {
        let view = NavigationStack {
            ProductListView(products: Product.sampleList)
        }

        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone15Pro)))
    }
}
```

Rules:
- First run generates reference snapshots (test "fails" to create them). Commit these to the repo.
- Subsequent runs compare against references. Differences cause failure with a diff image.
- Run `record: true` parameter or set `isRecording = true` to update references after intentional UI changes.
- Snapshot tests are fragile across OS versions and simulators — pin to a specific device/OS in CI.


## Test Plans & Configuration

### Xcode Test Plans (.xctestplan)
---

Test plans define which tests to run, with which configuration. They replace scheme-level test settings.

A test plan is a JSON file (`.xctestplan`) configured in Xcode:

```
MyApp.xctestplan
├── Configuration: "Default"
│   ├── Language: en
│   ├── Region: US
│   ├── Sanitizers: none
│   └── Tests: all enabled
├── Configuration: "German"
│   ├── Language: de
│   ├── Region: DE
│   └── Tests: UI tests only
├── Configuration: "Memory Check"
│   ├── Address Sanitizer: enabled
│   ├── Zombie Objects: enabled
│   └── Tests: all enabled
└── Configuration: "Thread Safety"
    ├── Thread Sanitizer: enabled
    └── Tests: unit tests only
```

#### Key settings per configuration

- **Application Language / Region**: Test localization without changing simulator settings.
- **Address Sanitizer (ASan)**: Detects memory corruption (buffer overflows, use-after-free).
- **Thread Sanitizer (TSan)**: Detects data races — critical for concurrency testing.
- **Undefined Behavior Sanitizer (UBSan)**: Catches undefined behavior (integer overflow, null dereference).
- **Code Coverage**: Enable/disable per configuration.
- **Test Repetitions**: Run each test multiple times to catch flaky tests.

### Test Repetitions
---

Available in test plans and xcodebuild:

| Mode | Behavior |
|---|---|
| Fixed repetitions | Run each test N times |
| Until failure | Repeat until a test fails (finds flaky tests) |
| Retry on failure | Retry failed tests up to N times (stabilizes CI) |

```bash
# xcodebuild repetition modes
xcodebuild test \
    -scheme MyApp \
    -testPlan MyApp \
    -test-iterations 5 \
    -retry-tests-on-failure

xcodebuild test \
    -scheme MyApp \
    -test-iterations 100 \
    -run-tests-until-failure
```

### Code Coverage
---

Enable in the test plan or scheme. Xcode generates coverage data in the `.xcresult` bundle.

- Set coverage targets per module (e.g., 80% for core business logic).
- Exclude generated code, third-party code, and UI layers from coverage requirements.
- Coverage is a guide, not a goal — 100% coverage does not mean 100% correctness.


## CI/CD Testing

### xcodebuild Commands
---

```bash
# Run all tests
xcodebuild test \
    -project MyApp.xcodeproj \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.0' \
    -resultBundlePath TestResults.xcresult

# Run with a test plan
xcodebuild test \
    -project MyApp.xcodeproj \
    -scheme MyApp \
    -testPlan CITestPlan \
    -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.0' \
    -resultBundlePath TestResults.xcresult

# Run specific test suite or method
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.0' \
    -only-testing:MyAppTests/AuthenticationTests/testLoginWithValidCredentials

# Skip specific tests
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.0' \
    -skip-testing:MyAppUITests/OnboardingUITests
```

### Parallel Testing on CI
---

```bash
# Parallel testing across multiple simulators
xcodebuild test \
    -scheme MyApp \
    -parallel-testing-enabled YES \
    -maximum-concurrent-test-simulator-destinations 4 \
    -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.0' \
    -resultBundlePath TestResults.xcresult
```

Rules:
- Parallel testing distributes test classes across simulator clones.
- Tests must be independent — no shared mutable state between test classes.
- UI tests often need serial execution — separate them into their own test plan.

### Result Bundles (.xcresult)
---

```bash
# Export test results as JSON
xcrun xcresulttool get test-results summary \
    --path TestResults.xcresult

# Export code coverage
xcrun xcresulttool get code-coverage \
    --path TestResults.xcresult \
    --output-format json > coverage.json

# List attachments (screenshots, logs)
xcrun xcresulttool get test-results attachments \
    --path TestResults.xcresult
```

Result bundles contain:
- Test pass/fail status and duration
- Code coverage data
- Screenshots (automatic on UI test failure)
- Console logs and diagnostics
- Performance metrics


## TDD Workflow

### Red-Green-Refactor
---

1. **Red** — Write a failing test that defines the desired behavior.
2. **Green** — Write the minimum code to make the test pass.
3. **Refactor** — Clean up the code while keeping all tests green.

```swift
// 1. RED — Write the test first
@Test func discountCalculator_applyPercentDiscount() {
    let calculator = DiscountCalculator()
    let result = calculator.apply(.percent(20), to: 100.00)
    #expect(result == 80.00)
}

// 2. GREEN — Minimal implementation
struct DiscountCalculator {
    enum Discount {
        case percent(Double)
    }

    func apply(_ discount: Discount, to price: Double) -> Double {
        switch discount {
        case .percent(let value):
            return price * (1 - value / 100)
        }
    }
}

// 3. REFACTOR — Add more cases, improve naming, extract if needed
// Then write the next failing test:
@Test func discountCalculator_applyFixedDiscount() {
    let calculator = DiscountCalculator()
    let result = calculator.apply(.fixed(15.00), to: 100.00)
    #expect(result == 85.00)
}

@Test func discountCalculator_neverGoesBelowZero() {
    let calculator = DiscountCalculator()
    let result = calculator.apply(.fixed(150.00), to: 100.00)
    #expect(result == 0.00)
}
```

### When TDD is Most Valuable

| Scenario | TDD Value |
|---|---|
| Business logic / domain rules | High — correctness is critical |
| Data parsing / transformation | High — edge cases are common |
| Algorithm implementation | High — incremental approach clarifies design |
| State machine transitions | High — defines valid transitions |
| UI layout / styling | Low — prefer snapshot tests or previews |
| Networking integration | Low — prefer integration tests |
| Rapid prototyping | Low — design is still fluid |


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Flaky tests from timing issues | Use `confirmation()` or `XCTExpectation` with appropriate timeouts — never use `Task.sleep` as the sole synchronization |
| Tests depend on execution order | Each test must be independent. Use `init`/`setUp` to create fresh state |
| Over-mocking hides real bugs | Mock at the boundary (network, disk, system), not between your own classes |
| Testing implementation, not behavior | Test observable outputs (return values, state changes, side effects), not internal method calls |
| `@MainActor` isolation in tests | Annotate test functions with `@MainActor` when testing MainActor-isolated types |
| UI tests break on text changes | Use `accessibilityIdentifier`, not `accessibilityLabel` or visible text, for element queries |
| Snapshot tests fail across environments | Pin CI to a specific simulator and OS version. Use tolerance for minor rendering differences |
| Slow test suite | Separate fast unit tests from slow integration/UI tests using test plans. Run fast tests on every PR, slow tests on merge |
| No test isolation for singletons | Inject dependencies via protocols instead of accessing singletons directly |
| `XCTExpectation` fulfilled multiple times | Set `expectedFulfillmentCount` or use `assertForOverFulfill = true` to catch unexpected extra calls |
| Testing async code without awaiting | Mark test `async`, use `await` on async calls. Unawaited tasks may complete after the test ends |
| Performance tests in the main suite | Move `measure { }` tests to a dedicated test plan — they slow down the feedback loop |

## Related References

- **`references/code-quality.md`** — Xcode Static Analyzer, sanitizers (ASan, TSan, UBSan), Periphery, Xcode build settings. Sanitizers are configured in test plans alongside test configurations described here.
- **`swift-development` skill's `references/static-analysis.md`** — SwiftLint, SwiftFormat configuration and CI integration.
- **`references/concurrency.md`** — async/await, actors, `@MainActor` — essential context for testing concurrent code.
- **`references/project-structure.md`** — test target organization, schemes, and multi-module test setup.
