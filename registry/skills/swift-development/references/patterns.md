# Swift Patterns Reference

## Contents
- Property wrappers (custom wrappers, composition, common patterns)
- Result builders (`@resultBuilder`, builder methods, practical DSLs)
- Key paths (expressions, writable paths, key paths as functions, dynamic member lookup)
- Codable (automatic conformance, custom coding, strategies, nested containers)
- Extensions (organization, retroactive conformance, conditional extensions)
- Copy-on-write (stdlib COW, custom COW types, `isKnownUniquelyReferenced`)
- Error handling patterns (hierarchy design, typed throws, retry, Result chaining)
- Builder pattern (fluent APIs, `@discardableResult`)
- Dependency injection (protocol-based, init injection, factories, testing)
- DSL design (trailing closures, result builders, `@dynamicMemberLookup`, operators)

## Property Wrappers

A property wrapper encapsulates read/write access to a property, adding behavior like validation, clamping, or thread safety.

### Defining a property wrapper

```swift
@propertyWrapper
struct Clamped<Value: Comparable> {
    private var value: Value
    let range: ClosedRange<Value>

    var wrappedValue: Value {
        get { value }
        set { value = min(max(newValue, range.lowerBound), range.upperBound) }
    }

    init(wrappedValue: Value, _ range: ClosedRange<Value>) {
        self.range = range
        self.value = min(max(wrappedValue, range.lowerBound), range.upperBound)
    }
}

struct AudioSettings {
    @Clamped(0...100) var volume: Int = 50
    @Clamped(0.0...1.0) var balance: Double = 0.5
}

var settings = AudioSettings()
settings.volume = 150  // clamped to 100
```

### Projected value

Use `projectedValue` to expose additional metadata via the `$` prefix.

```swift
@propertyWrapper
struct Validated<Value> {
    private var value: Value
    private(set) var isValid: Bool

    var wrappedValue: Value {
        get { value }
        set {
            value = newValue
            isValid = validate(newValue)
        }
    }

    var projectedValue: Validated<Value> { self }

    private let validate: (Value) -> Bool

    init(wrappedValue: Value, _ validate: @escaping (Value) -> Bool) {
        self.validate = validate
        self.value = wrappedValue
        self.isValid = validate(wrappedValue)
    }
}

struct Registration {
    @Validated({ $0.count >= 3 }) var username: String = ""
    @Validated({ $0.contains("@") }) var email: String = ""
}

var form = Registration()
form.username = "ab"
print(form.$username.isValid) // false
```

### Logging wrapper

```swift
@propertyWrapper
struct Logged<Value> {
    private var value: Value
    let label: String

    var wrappedValue: Value {
        get { value }
        set {
            print("[\(label)] \(value) -> \(newValue)")
            value = newValue
        }
    }

    init(wrappedValue: Value, _ label: String) {
        self.label = label
        self.value = wrappedValue
    }
}

struct AppConfig {
    @Logged("debugMode") var debugMode: Bool = false
}
```

### Thread-safe wrapper

```swift
@propertyWrapper
final class Atomic<Value: Sendable>: Sendable {
    private let lock = NSLock()
    private var storage: Value

    var wrappedValue: Value {
        get { lock.withLock { storage } }
        set { lock.withLock { storage = newValue } }
    }

    init(wrappedValue: Value) {
        self.storage = wrappedValue
    }
}
```

### Composition

Property wrappers can be composed — the outermost wrapper wraps the next.

```swift
@propertyWrapper
struct TrimmedString {
    private var value: String = ""

    var wrappedValue: String {
        get { value }
        set { value = newValue.trimmingCharacters(in: .whitespacesAndNewlines) }
    }

    init(wrappedValue: String) {
        self.wrappedValue = wrappedValue
    }
}

struct Profile {
    @TrimmedString @Logged("displayName") var displayName: String = ""
}
```

Note: `@State`, `@Binding`, `@Published`, etc. are platform-specific property wrappers and not covered here.

## Result Builders

Result builders allow declarative construction of complex values using natural Swift syntax.

### Basic result builder

```swift
@resultBuilder
struct ArrayBuilder<Element> {
    static func buildBlock(_ components: Element...) -> [Element] {
        components
    }

    static func buildOptional(_ component: [Element]?) -> [Element] {
        component ?? []
    }

    static func buildEither(first component: [Element]) -> [Element] {
        component
    }

    static func buildEither(second component: [Element]) -> [Element] {
        component
    }

    static func buildArray(_ components: [[Element]]) -> [Element] {
        components.flatMap { $0 }
    }

    // Allow single elements in if/else and loops
    static func buildExpression(_ expression: Element) -> [Element] {
        [expression]
    }

    static func buildBlock(_ components: [Element]...) -> [Element] {
        components.flatMap { $0 }
    }
}
```

### HTML builder example

```swift
protocol HTMLNode {
    func render() -> String
}

struct Text: HTMLNode {
    let content: String
    func render() -> String { content }
}

struct Tag: HTMLNode {
    let name: String
    let children: [HTMLNode]

    func render() -> String {
        let inner = children.map { $0.render() }.joined()
        return "<\(name)>\(inner)</\(name)>"
    }
}

@resultBuilder
struct HTMLBuilder {
    static func buildBlock(_ components: HTMLNode...) -> [HTMLNode] {
        components
    }

    static func buildOptional(_ component: [HTMLNode]?) -> HTMLNode {
        Tag(name: "span", children: component ?? [])
    }

    static func buildEither(first component: [HTMLNode]) -> HTMLNode {
        Tag(name: "span", children: component)
    }

    static func buildEither(second component: [HTMLNode]) -> HTMLNode {
        Tag(name: "span", children: component)
    }
}

func div(@HTMLBuilder content: () -> [HTMLNode]) -> Tag {
    Tag(name: "div", children: content())
}

func p(@HTMLBuilder content: () -> [HTMLNode]) -> Tag {
    Tag(name: "p", children: content())
}

// Usage
let page = div {
    p { Text(content: "Hello, World!") }
    p { Text(content: "Built with result builders.") }
}
```

### Configuration DSL

```swift
struct ServerConfig {
    var host: String = "localhost"
    var port: Int = 8080
    var routes: [Route] = []
}

struct Route {
    let method: String
    let path: String
    let handler: @Sendable () async -> String
}

@resultBuilder
struct RouteBuilder {
    static func buildBlock(_ components: Route...) -> [Route] {
        components
    }
}

func server(
    host: String = "localhost",
    port: Int = 8080,
    @RouteBuilder routes: () -> [Route]
) -> ServerConfig {
    ServerConfig(host: host, port: port, routes: routes())
}

func get(_ path: String, handler: @escaping @Sendable () async -> String) -> Route {
    Route(method: "GET", path: path, handler: handler)
}

// Usage
let config = server(host: "0.0.0.0", port: 3000) {
    get("/health") { "OK" }
    get("/version") { "1.0.0" }
}
```

### When to use result builders

- When the API is naturally declarative (trees, configurations, document structures).
- When nested closures and method chaining become unwieldy.
- Avoid when simple initializers or arrays suffice — result builders add compiler complexity.

## Key Paths

### Key path expressions

```swift
struct User {
    var name: String
    var age: Int
    var address: Address
}

struct Address {
    var city: String
    var zip: String
}

// Type: KeyPath<User, String>
let namePath = \User.name

// Chained key paths
let cityPath = \User.address.city

let user = User(name: "Alice", age: 30, address: Address(city: "Berlin", zip: "10115"))
print(user[keyPath: namePath])   // "Alice"
print(user[keyPath: cityPath])   // "Berlin"
```

### WritableKeyPath and ReferenceWritableKeyPath

```swift
var mutableUser = user

// WritableKeyPath — works on value types with var binding
let agePath: WritableKeyPath<User, Int> = \.age
mutableUser[keyPath: agePath] = 31

// ReferenceWritableKeyPath — works on reference types
class UserStore {
    var currentUser: User = User(name: "Bob", age: 25, address: Address(city: "London", zip: "SW1"))
}

let store = UserStore()
let storePath: ReferenceWritableKeyPath<UserStore, String> = \.currentUser.name
store[keyPath: storePath] = "Charlie"
```

### Key paths as functions

Since Swift 5.2, key paths can be used wherever `(Root) -> Value` is expected.

```swift
let users = [
    User(name: "Alice", age: 30, address: Address(city: "Berlin", zip: "10115")),
    User(name: "Bob", age: 25, address: Address(city: "London", zip: "SW1")),
]

let names = users.map(\.name)           // ["Alice", "Bob"]
let cities = users.map(\.address.city)  // ["Berlin", "London"]
let sorted = users.sorted(by: \.age)    // youngest first (requires custom extension or KeyPathComparator)

// Filter with key paths
let adults = users.filter(\.isAdult)  // requires computed property `var isAdult: Bool`
```

### Dynamic member lookup with key paths

```swift
@dynamicMemberLookup
struct Lens<Root> {
    let root: Root

    subscript<Value>(dynamicMember keyPath: KeyPath<Root, Value>) -> Value {
        root[keyPath: keyPath]
    }
}

let lens = Lens(root: user)
print(lens.name)          // "Alice" — dot syntax via dynamic member lookup
print(lens.address.city)  // "Berlin"
```

## Codable

### Automatic conformance

```swift
struct User: Codable {
    let id: UUID
    let name: String
    let email: String
    let joinedAt: Date
}

// Encode
let encoder = JSONEncoder()
encoder.dateEncodingStrategy = .iso8601
let data = try encoder.encode(user)

// Decode
let decoder = JSONDecoder()
decoder.dateDecodingStrategy = .iso8601
let decoded = try decoder.decode(User.self, from: data)
```

### Custom CodingKeys

```swift
struct Product: Codable {
    let id: Int
    let displayName: String
    let priceInCents: Int
    let isAvailable: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case priceInCents = "price_cents"
        case isAvailable = "is_available"
    }
}
```

### Custom encode/decode for complex JSON

```swift
struct APIResponse: Decodable {
    let users: [User]
    let totalCount: Int
    let nextCursor: String?

    enum CodingKeys: String, CodingKey {
        case data, meta
    }

    enum DataKeys: String, CodingKey {
        case users
    }

    enum MetaKeys: String, CodingKey {
        case totalCount = "total_count"
        case nextCursor = "next_cursor"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        let dataContainer = try container.nestedContainer(keyedBy: DataKeys.self, forKey: .data)
        users = try dataContainer.decode([User].self, forKey: .users)

        let metaContainer = try container.nestedContainer(keyedBy: MetaKeys.self, forKey: .meta)
        totalCount = try metaContainer.decode(Int.self, forKey: .totalCount)
        nextCursor = try metaContainer.decodeIfPresent(String.self, forKey: .nextCursor)
    }
}
```

### Handling missing and optional fields

```swift
struct Settings: Decodable {
    let theme: String
    let fontSize: Int
    let notifications: Bool

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        theme = try container.decodeIfPresent(String.self, forKey: .theme) ?? "light"
        fontSize = try container.decodeIfPresent(Int.self, forKey: .fontSize) ?? 14
        notifications = try container.decodeIfPresent(Bool.self, forKey: .notifications) ?? true
    }

    enum CodingKeys: String, CodingKey {
        case theme, fontSize, notifications
    }
}
```

### Date and enum strategies

```swift
// Date strategies
let decoder = JSONDecoder()
decoder.dateDecodingStrategy = .iso8601                      // "2024-01-15T10:30:00Z"
decoder.dateDecodingStrategy = .secondsSince1970             // 1705312200
decoder.dateDecodingStrategy = .formatted(customFormatter)   // custom DateFormatter
decoder.dateDecodingStrategy = .custom { decoder in          // fully custom
    let container = try decoder.singleValueContainer()
    let string = try container.decode(String.self)
    guard let date = parseFlexibleDate(string) else {
        throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid date: \(string)")
    }
    return date
}

// Enum with raw value — automatic Codable
enum Status: String, Codable {
    case active, inactive, pending
}

// Enum with associated values — manual Codable
enum PaymentMethod: Codable {
    case creditCard(last4: String, expiry: String)
    case bankTransfer(iban: String)
    case wallet(provider: String, id: String)

    enum CodingKeys: String, CodingKey {
        case type, last4, expiry, iban, provider, id
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)
        switch type {
        case "credit_card":
            let last4 = try container.decode(String.self, forKey: .last4)
            let expiry = try container.decode(String.self, forKey: .expiry)
            self = .creditCard(last4: last4, expiry: expiry)
        case "bank_transfer":
            let iban = try container.decode(String.self, forKey: .iban)
            self = .bankTransfer(iban: iban)
        case "wallet":
            let provider = try container.decode(String.self, forKey: .provider)
            let id = try container.decode(String.self, forKey: .id)
            self = .wallet(provider: provider, id: id)
        default:
            throw DecodingError.dataCorruptedError(
                forKey: .type, in: container,
                debugDescription: "Unknown payment type: \(type)"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case .creditCard(let last4, let expiry):
            try container.encode("credit_card", forKey: .type)
            try container.encode(last4, forKey: .last4)
            try container.encode(expiry, forKey: .expiry)
        case .bankTransfer(let iban):
            try container.encode("bank_transfer", forKey: .type)
            try container.encode(iban, forKey: .iban)
        case .wallet(let provider, let id):
            try container.encode("wallet", forKey: .type)
            try container.encode(provider, forKey: .provider)
            try container.encode(id, forKey: .id)
        }
    }
}
```

### nestedContainer and unkeyedContainer

```swift
struct Playlist: Decodable {
    let name: String
    let tracks: [Track]

    struct Track: Decodable {
        let title: String
        let durationSeconds: Int
    }

    enum CodingKeys: String, CodingKey {
        case name, tracks
    }

    enum TrackKeys: String, CodingKey {
        case title, duration
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        name = try container.decode(String.self, forKey: .name)

        var tracksArray = try container.nestedUnkeyedContainer(forKey: .tracks)
        var decoded: [Track] = []
        while !tracksArray.isAtEnd {
            let trackContainer = try tracksArray.nestedContainer(keyedBy: TrackKeys.self)
            let title = try trackContainer.decode(String.self, forKey: .title)
            let duration = try trackContainer.decode(Int.self, forKey: .duration)
            decoded.append(Track(title: title, durationSeconds: duration))
        }
        tracks = decoded
    }
}
```

### CodingUserInfoKey for context injection

```swift
extension CodingUserInfoKey {
    static let apiVersion = CodingUserInfoKey(rawValue: "apiVersion")!
}

struct VersionedResponse: Decodable {
    let value: String

    init(from decoder: Decoder) throws {
        let version = decoder.userInfo[.apiVersion] as? Int ?? 1
        let container = try decoder.singleValueContainer()
        if version >= 2 {
            // v2 wraps in an object
            let wrapper = try container.decode([String: String].self)
            value = wrapper["value"] ?? ""
        } else {
            value = try container.decode(String.self)
        }
    }
}

// Usage
let decoder = JSONDecoder()
decoder.userInfo[.apiVersion] = 2
let response = try decoder.decode(VersionedResponse.self, from: jsonData)
```

## Extensions

### Organizing code with extensions

One extension per protocol conformance keeps each conformance self-contained.

```swift
struct User {
    let id: UUID
    var name: String
    var email: String
}

// MARK: - Equatable
extension User: Equatable {
    static func == (lhs: User, rhs: User) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - CustomStringConvertible
extension User: CustomStringConvertible {
    var description: String {
        "\(name) <\(email)>"
    }
}

// MARK: - Codable
extension User: Codable {}
```

### Retroactive conformance

Add protocol conformance to types you do not own.

```swift
// Make a third-party type Codable
extension ExternalLibrary.Config: Codable {
    enum CodingKeys: String, CodingKey {
        case timeout, retries
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.init(
            timeout: try container.decode(Double.self, forKey: .timeout),
            retries: try container.decode(Int.self, forKey: .retries)
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(timeout, forKey: .timeout)
        try container.encode(retries, forKey: .retries)
    }
}
```

### Conditional extensions (where clauses)

```swift
extension Array where Element: Numeric {
    var sum: Element {
        reduce(0, +)
    }
}

extension Array where Element: Comparable {
    var isSorted: Bool {
        zip(self, dropFirst()).allSatisfy { $0 <= $1 }
    }
}

extension Sequence where Element: Hashable {
    var unique: [Element] {
        var seen: Set<Element> = []
        return filter { seen.insert($0).inserted }
    }
}
```

### Private extensions for internal helpers

```swift
// Internal to this file only
private extension String {
    var isValidEmail: Bool {
        contains("@") && contains(".")
    }

    var normalized: String {
        trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }
}
```

## Copy-on-Write

### How Swift implements COW for collections

`Array`, `Dictionary`, `Set`, and `String` are value types backed by reference-counted storage. Assignment copies the reference; mutation triggers a deep copy only when the reference count is greater than one.

```swift
var a = [1, 2, 3]
var b = a           // no copy — shares storage
b.append(4)         // COW triggers — b gets its own copy
// a is still [1, 2, 3]
```

### Implementing COW for custom types

```swift
final class StorageBuffer<Element> {
    var elements: [Element]

    init(_ elements: [Element]) {
        self.elements = elements
    }

    func copy() -> StorageBuffer {
        StorageBuffer(elements)
    }
}

struct COWCollection<Element> {
    private var storage: StorageBuffer<Element>

    init(_ elements: [Element] = []) {
        storage = StorageBuffer(elements)
    }

    var elements: [Element] {
        storage.elements
    }

    // Call before any mutation
    private mutating func ensureUnique() {
        if !isKnownUniquelyReferenced(&storage) {
            storage = storage.copy()
        }
    }

    mutating func append(_ element: Element) {
        ensureUnique()
        storage.elements.append(element)
    }

    mutating func remove(at index: Int) {
        ensureUnique()
        storage.elements.remove(at: index)
    }
}
```

### isKnownUniquelyReferenced

`isKnownUniquelyReferenced(_:)` returns `true` when the reference count is exactly one, meaning it is safe to mutate in place. Always check this before mutating shared storage.

- Works only with Swift classes (not Objective-C classes).
- Returns `false` if the reference is shared — you must copy.
- The parameter is `inout` to prevent temporary retain count bumps.

## Error Handling Patterns

### Error hierarchy design

```swift
// Enum-based — best for fixed sets of known errors
enum NetworkError: Error {
    case timeout(after: Duration)
    case httpError(statusCode: Int, body: Data?)
    case invalidURL(String)
    case decodingFailed(underlying: Error)
}

// Struct-based — best for rich, extensible error information
struct ValidationError: Error, CustomStringConvertible {
    let field: String
    let message: String
    let code: String

    var description: String { "[\(code)] \(field): \(message)" }
}

// Protocol-based — for shared behavior across error types
protocol AppError: Error {
    var userMessage: String { get }
    var isRetryable: Bool { get }
}

extension NetworkError: AppError {
    var userMessage: String {
        switch self {
        case .timeout: "Request timed out. Please try again."
        case .httpError(let code, _): "Server error (\(code))."
        case .invalidURL: "Invalid request."
        case .decodingFailed: "Unexpected server response."
        }
    }

    var isRetryable: Bool {
        switch self {
        case .timeout, .httpError(500..., _): true
        default: false
        }
    }
}
```

### Typed throws (Swift 6+)

```swift
func parseConfig(_ raw: String) throws(ConfigError) -> Config {
    guard let data = raw.data(using: .utf8) else {
        throw .invalidEncoding
    }
    guard let parsed = try? JSONDecoder().decode(Config.self, from: data) else {
        throw .malformedJSON
    }
    return parsed
}

enum ConfigError: Error {
    case invalidEncoding
    case malformedJSON
    case missingField(String)
}

// Caller knows the exact error type — no need for pattern matching on `Error`
do {
    let config = try parseConfig(rawString)
} catch {
    // error is ConfigError, not Error
    switch error {
    case .invalidEncoding: print("Bad encoding")
    case .malformedJSON: print("Bad JSON")
    case .missingField(let f): print("Missing: \(f)")
    }
}
```

### Retry pattern

```swift
func withRetry<T>(
    maxAttempts: Int = 3,
    delay: Duration = .seconds(1),
    shouldRetry: (Error) -> Bool = { _ in true },
    operation: () async throws -> T
) async throws -> T {
    var lastError: Error?
    for attempt in 1...maxAttempts {
        do {
            return try await operation()
        } catch {
            lastError = error
            guard attempt < maxAttempts, shouldRetry(error) else { break }
            try await Task.sleep(for: delay * attempt)  // linear backoff
        }
    }
    throw lastError!
}

// Usage
let data = try await withRetry(maxAttempts: 3) {
    try await networkClient.fetch(url)
}
```

### Result type patterns

```swift
// Chaining with map and flatMap
func fetchUserName(id: UUID) -> Result<String, NetworkError> {
    fetchUser(id: id)
        .map(\.name)
        .flatMap { name in
            name.isEmpty ? .failure(.decodingFailed(underlying: EmptyNameError())) : .success(name)
        }
}

// Converting between Result and throws
func loadConfig() -> Result<Config, ConfigError> {
    Result { try parseConfigFile() }
        .mapError { _ in ConfigError.malformedJSON }
}

let config = try loadConfig().get()  // throws on failure
```

### Mapping and chaining errors

```swift
extension Result {
    func mapErrorToAppError() -> Result<Success, AppError> where Failure == Error {
        mapError { error in
            (error as? AppError) ?? GenericAppError(underlying: error)
        }
    }
}

struct GenericAppError: AppError {
    let underlying: Error
    var userMessage: String { "An unexpected error occurred." }
    var isRetryable: Bool { false }
}
```

### Error recovery strategies

```swift
func fetchWithFallback(id: UUID) async -> User {
    do {
        return try await remoteRepository.fetch(id: id)
    } catch let error as NetworkError where error.isRetryable {
        // Retry once for retryable errors
        do {
            return try await remoteRepository.fetch(id: id)
        } catch {
            return await localCache.fetch(id: id) ?? User.placeholder
        }
    } catch {
        // Fall back to cache for non-retryable errors
        return await localCache.fetch(id: id) ?? User.placeholder
    }
}
```

## Builder Pattern

### Fluent API design

```swift
struct RequestBuilder {
    private var method: String = "GET"
    private var url: String = ""
    private var headers: [String: String] = [:]
    private var body: Data?
    private var timeout: Duration = .seconds(30)

    @discardableResult
    func method(_ method: String) -> RequestBuilder {
        var copy = self
        copy.method = method
        return copy
    }

    @discardableResult
    func url(_ url: String) -> RequestBuilder {
        var copy = self
        copy.url = url
        return copy
    }

    @discardableResult
    func header(_ name: String, _ value: String) -> RequestBuilder {
        var copy = self
        copy.headers[name] = value
        return copy
    }

    @discardableResult
    func body(_ data: Data) -> RequestBuilder {
        var copy = self
        copy.body = data
        return copy
    }

    @discardableResult
    func timeout(_ duration: Duration) -> RequestBuilder {
        var copy = self
        copy.timeout = duration
        return copy
    }

    func build() throws -> URLRequest {
        guard let url = URL(string: url) else {
            throw RequestError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        request.timeoutInterval = timeout.timeInterval
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
        return request
    }
}

// Usage
let request = try RequestBuilder()
    .method("POST")
    .url("https://api.example.com/users")
    .header("Content-Type", "application/json")
    .body(jsonData)
    .timeout(.seconds(10))
    .build()
```

### Combining builder pattern with result builders

```swift
@resultBuilder
struct MiddlewareBuilder {
    static func buildBlock(_ components: Middleware...) -> [Middleware] {
        components
    }
}

protocol Middleware {
    func process(_ request: inout Request) async throws
}

struct Pipeline {
    let middlewares: [Middleware]

    init(@MiddlewareBuilder _ build: () -> [Middleware]) {
        self.middlewares = build()
    }

    func execute(_ request: inout Request) async throws {
        for middleware in middlewares {
            try await middleware.process(&request)
        }
    }
}

// Usage
let pipeline = Pipeline {
    LoggingMiddleware()
    AuthenticationMiddleware(token: apiToken)
    RateLimitMiddleware(maxRequests: 100)
}
```

## Dependency Injection

### Protocol-based injection (preferred)

```swift
protocol UserRepository: Sendable {
    func fetch(id: UUID) async throws -> User
    func save(_ user: User) async throws
}

protocol EmailService: Sendable {
    func send(to: String, subject: String, body: String) async throws
}
```

### Init injection

```swift
struct UserService {
    private let repository: UserRepository
    private let emailService: EmailService

    init(repository: UserRepository, emailService: EmailService) {
        self.repository = repository
        self.emailService = emailService
    }

    func register(name: String, email: String) async throws -> User {
        let user = User(id: UUID(), name: name, email: email)
        try await repository.save(user)
        try await emailService.send(
            to: email,
            subject: "Welcome",
            body: "Hello, \(name)!"
        )
        return user
    }
}
```

### Factory pattern

```swift
protocol ServiceFactory: Sendable {
    func makeUserRepository() -> UserRepository
    func makeEmailService() -> EmailService
    func makeUserService() -> UserService
}

struct ProductionFactory: ServiceFactory {
    func makeUserRepository() -> UserRepository {
        PostgresUserRepository(connectionPool: pool)
    }

    func makeEmailService() -> EmailService {
        SMTPEmailService(config: smtpConfig)
    }

    func makeUserService() -> UserService {
        UserService(
            repository: makeUserRepository(),
            emailService: makeEmailService()
        )
    }
}
```

### Service locator (when appropriate)

Use sparingly — only when init injection is impractical (e.g., deeply nested dependency graphs with many optional services). Prefer init injection.

```swift
actor ServiceContainer {
    private var services: [String: Any] = [:]

    func register<T>(_ type: T.Type, instance: T) {
        services[String(describing: type)] = instance
    }

    func resolve<T>(_ type: T.Type) -> T? {
        services[String(describing: type)] as? T
    }
}
```

### Testing with fakes

```swift
struct InMemoryUserRepository: UserRepository {
    private var storage: [UUID: User] = [:]

    mutating func save(_ user: User) async throws {
        storage[user.id] = user
    }

    func fetch(id: UUID) async throws -> User {
        guard let user = storage[id] else {
            throw AppError.notFound(resource: "User")
        }
        return user
    }
}

struct FakeEmailService: EmailService {
    var sentEmails: [(to: String, subject: String, body: String)] = []

    mutating func send(to: String, subject: String, body: String) async throws {
        sentEmails.append((to, subject, body))
    }
}

// Test
import Testing

@Test("Registers user and sends welcome email")
func registerUser() async throws {
    var emailService = FakeEmailService()
    var repo = InMemoryUserRepository()
    let service = UserService(repository: repo, emailService: emailService)

    let user = try await service.register(name: "Alice", email: "alice@example.com")

    #expect(user.name == "Alice")
    #expect(emailService.sentEmails.count == 1)
    #expect(emailService.sentEmails.first?.to == "alice@example.com")
}
```

## DSL Design

### Trailing closures for DSL syntax

```swift
struct Configuration {
    var database: DatabaseConfig = .init()
    var logging: LoggingConfig = .init()
}

struct DatabaseConfig {
    var host: String = "localhost"
    var port: Int = 5432
    var name: String = ""
}

struct LoggingConfig {
    var level: String = "info"
    var format: String = "json"
}

func configure(_ setup: (inout Configuration) -> Void) -> Configuration {
    var config = Configuration()
    setup(&config)
    return config
}

// Usage
let config = configure {
    $0.database.host = "db.example.com"
    $0.database.port = 5432
    $0.database.name = "production"
    $0.logging.level = "debug"
    $0.logging.format = "text"
}
```

### Result builders for declarative APIs

See the [Result Builders](#result-builders) section above. Result builders shine when building tree-like or list-like structures declaratively.

### @dynamicMemberLookup for dynamic access

```swift
@dynamicMemberLookup
struct Environment {
    private var values: [String: String]

    init(_ values: [String: String] = ProcessInfo.processInfo.environment) {
        self.values = values
    }

    subscript(dynamicMember key: String) -> String? {
        values[key.uppercased()]
    }
}

let env = Environment()
let home = env.home           // reads "HOME" from environment
let path = env.path           // reads "PATH" from environment

// Type-safe wrapper with key path lookup
@dynamicMemberLookup
struct Ref<Root> {
    private let getter: () -> Root
    private let setter: (Root) -> Void

    subscript<Value>(dynamicMember keyPath: WritableKeyPath<Root, Value>) -> Ref<Value> {
        Ref<Value>(
            getter: { self.getter()[keyPath: keyPath] },
            setter: { newValue in
                var root = self.getter()
                root[keyPath: keyPath] = newValue
                self.setter(root)
            }
        )
    }
}
```

### Operator overloading (use sparingly)

Define custom operators only when they significantly improve readability and the semantics are unambiguous.

```swift
// Pipeline operator for functional composition
precedencegroup PipelinePrecedence {
    associativity: left
    higherThan: AssignmentPrecedence
}

infix operator |>: PipelinePrecedence

func |> <A, B>(value: A, transform: (A) -> B) -> B {
    transform(value)
}

// Usage
let result = "  Hello, World!  "
    |> { $0.trimmingCharacters(in: .whitespaces) }
    |> { $0.lowercased() }
    |> { $0.replacingOccurrences(of: " ", with: "-") }
// "hello,-world!"

// Function composition operator
infix operator >>>: PipelinePrecedence

func >>> <A, B, C>(lhs: @escaping (A) -> B, rhs: @escaping (B) -> C) -> (A) -> C {
    { rhs(lhs($0)) }
}

let normalize = { (s: String) in s.trimmingCharacters(in: .whitespaces) }
    >>> { $0.lowercased() }
    >>> { $0.replacingOccurrences(of: " ", with: "_") }

let normalized = normalize("  Hello World  ")  // "hello_world"
```

Guidelines for operator overloading:

- Only overload when the meaning is immediately obvious at the call site.
- Prefer named methods for domain-specific operations.
- Document the operator with a brief comment explaining semantics.
- Avoid defining operators that conflict with existing Swift operators in meaning.
