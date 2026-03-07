# Swift Type System Reference

## Contents
- Generics (functions, types, constraints, conditional conformances, generic subscripts)
- Protocols with associated types (inheritance, composition, default implementations, Self requirements)
- Opaque types (`some` return/parameter types, benefits over existentials)
- Existential types (`any`, boxing, opening existentials)
- Type erasure (manual pattern, primary associated types)
- Phantom types (state machines, compile-time validation)
- Metatypes (`.self`, `Type`, `type(of:)`)
- `@dynamicMemberLookup` and `@dynamicCallable`
- Value wrappers (type-safe structs, `RawRepresentable`)

## Generics

### Generic functions

```swift
func identity<T>(_ value: T) -> T { value }

func swap<T>(_ a: inout T, _ b: inout T) {
    let temp = a
    a = b
    b = temp
}

func first<T>(_ array: [T]) -> T? {
    array.isEmpty ? nil : array[0]
}
```

### Generic types

```swift
struct Stack<Element> {
    private var storage: [Element] = []

    mutating func push(_ item: Element) {
        storage.append(item)
    }

    mutating func pop() -> Element? {
        storage.popLast()
    }

    var top: Element? { storage.last }
    var isEmpty: Bool { storage.isEmpty }
}

var intStack = Stack<Int>()
intStack.push(42)
```

### Type constraints with `where` clauses

```swift
func max<T: Comparable>(_ a: T, _ b: T) -> T {
    a >= b ? a : b
}

// Multiple constraints using where
func findIndex<T>(of value: T, in array: [T]) -> Int?
    where T: Equatable
{
    array.firstIndex(of: value)
}

// Constraining associated types
func sum<C: Collection>(_ collection: C) -> C.Element
    where C.Element: AdditiveArithmetic
{
    collection.reduce(.zero, +)
}

// Multiple where constraints
func merge<S1: Sequence, S2: Sequence>(_ s1: S1, _ s2: S2) -> [S1.Element]
    where S1.Element == S2.Element, S1.Element: Comparable
{
    (Array(s1) + Array(s2)).sorted()
}
```

### Conditional conformances

```swift
// Array is Equatable only when its Element is Equatable
extension Stack: Equatable where Element: Equatable {
    static func == (lhs: Stack, rhs: Stack) -> Bool {
        lhs.storage == rhs.storage
    }
}

// Conditional Hashable
extension Stack: Hashable where Element: Hashable {
    func hash(into hasher: inout Hasher) {
        hasher.combine(storage)
    }
}

// Conditional CustomStringConvertible
extension Stack: CustomStringConvertible where Element: CustomStringConvertible {
    var description: String {
        storage.map(\.description).joined(separator: ", ")
    }
}
```

### Generic subscripts

```swift
struct JSON {
    private var data: [String: Any]

    subscript<T>(key: String) -> T? {
        data[key] as? T
    }

    // Subscript with default value
    subscript<T>(key: String, default defaultValue: T) -> T {
        (data[key] as? T) ?? defaultValue
    }
}

let json = JSON(data: ["name": "Alice", "age": 30])
let name: String? = json["name"]     // "Alice"
let score: Int = json["score", default: 0]  // 0
```

## Protocols with Associated Types

### Defining and using associated types

```swift
protocol Container {
    associatedtype Item
    var count: Int { get }
    mutating func append(_ item: Item)
    subscript(i: Int) -> Item { get }
}

struct IntBuffer: Container {
    // Item is inferred as Int
    private var storage: [Int] = []
    var count: Int { storage.count }

    mutating func append(_ item: Int) {
        storage.append(item)
    }

    subscript(i: Int) -> Int { storage[i] }
}
```

### Protocol inheritance

```swift
protocol Identifiable {
    associatedtype ID: Hashable
    var id: ID { get }
}

protocol Persistable: Identifiable {
    func save() throws
    static func load(id: ID) throws -> Self
}

protocol Versionable: Persistable {
    var version: Int { get }
}
```

### Protocol composition (`&`)

```swift
protocol Readable {
    func read() -> Data
}

protocol Writable {
    func write(_ data: Data) throws
}

// Compose protocols using &
typealias ReadWrite = Readable & Writable

func transfer(from source: Readable, to destination: Writable) throws {
    let data = source.read()
    try destination.write(data)
}

// Inline composition in function signature
func process(_ item: Identifiable & CustomStringConvertible) {
    print("Processing \(item.id): \(item.description)")
}
```

### Default implementations via extensions

```swift
protocol Validator {
    associatedtype Input
    func validate(_ input: Input) -> Bool
    func validatedOrNil(_ input: Input) -> Input?
}

// Default implementation
extension Validator {
    func validatedOrNil(_ input: Input) -> Input? {
        validate(input) ? input : nil
    }
}

struct RangeValidator: Validator {
    let range: ClosedRange<Int>

    // Only need to implement validate — validatedOrNil comes free
    func validate(_ input: Int) -> Bool {
        range.contains(input)
    }
}
```

### Self requirements

```swift
protocol Copyable {
    func copy() -> Self
}

protocol Chainable {
    func then(_ action: (Self) -> Void) -> Self
}

struct Config: Copyable, Chainable {
    var host: String = "localhost"
    var port: Int = 8080

    func copy() -> Config {
        Config(host: host, port: port)
    }

    func then(_ action: (Config) -> Void) -> Config {
        action(self)
        return self
    }
}
```

## Opaque Types (`some`)

### `some` return types

```swift
// The caller knows it gets *some* specific Sequence of Int,
// but not the concrete type
func makeCounter() -> some Sequence<Int> {
    0..<100
}

// Opaque return type preserves type identity across calls
func doubled() -> some Collection<Int> {
    [1, 2, 3].lazy.map { $0 * 2 }
}

// The concrete type is fixed — both branches must return the same type
func steps(ascending: Bool) -> some Sequence<Int> {
    if ascending {
        return AnySequence(0..<10)
    } else {
        return AnySequence((0..<10).reversed())
    }
}
```

### `some` parameter types (Swift 5.7+)

```swift
// Before Swift 5.7
func printAll<C: Collection>(_ items: C) where C.Element: CustomStringConvertible {
    for item in items { print(item) }
}

// Swift 5.7+ — equivalent, more concise
func printAll(_ items: some Collection<some CustomStringConvertible>) {
    for item in items { print(item) }
}

// Works well for simple generic constraints
func double(_ value: some Numeric) -> some Numeric {
    value + value
}
```

### Benefits over existentials (type identity preserved)

```swift
// With `some`, the compiler knows the concrete type — enables optimizations
func makeSequence() -> some Sequence<Int> {
    [1, 2, 3]  // Compiler retains Array<Int> identity
}

// With `any`, the type is boxed — loses concrete type info
func makeSequence() -> any Sequence<Int> {
    [1, 2, 3]  // Boxed into an existential container
}

// `some` allows using == if the underlying type is Equatable
func areSame(_ a: some Equatable, _ b: some Equatable) -> Bool {
    // Only works if a and b have the same concrete type
    // Compiler enforces this at the call site
    a == b  // error: unless called with same type for both
}
```

### When to use opaque vs existential

| Use Case | Keyword | Reason |
|---|---|---|
| Return a single concrete type (hidden) | `some` | Type identity preserved, better performance |
| Return different concrete types | `any` | Heterogeneous values allowed |
| Store protocol-typed values in a collection | `any` | Different concrete types in one array |
| Function parameter shorthand | `some` | Equivalent to a generic parameter |
| Public API hiding implementation | `some` | Preserves type relationships |

## Existential Types (`any`)

### `any` keyword requirement (Swift 5.6+)

```swift
// Swift 5.6+ requires explicit `any` for existential types
let validators: [any Validator] = [
    RangeValidator(range: 1...100),
    // other validators with different Input types
]

// Function accepting existential
func runValidator(_ validator: any Validator) {
    // Can only use methods that don't depend on associated types
    // without opening the existential
}
```

### Boxing and performance implications

```swift
// Existential containers use boxing — heap allocation for large values
protocol Shape {
    func area() -> Double
}

struct Circle: Shape {
    let radius: Double
    func area() -> Double { .pi * radius * radius }
}

struct Square: Shape {
    let side: Double
    func area() -> Double { side * side }
}

// Each element is boxed in an existential container (up to 3 words inline,
// heap-allocated above that)
let shapes: [any Shape] = [Circle(radius: 5), Square(side: 4)]

// Generic version — no boxing, monomorphized at compile time
func totalArea<S: Shape>(_ shapes: [S]) -> Double {
    shapes.reduce(0) { $0 + $1.area() }
}
```

### Opening existentials (Swift 5.7+)

```swift
protocol Animal: Equatable {
    var name: String { get }
}

struct Dog: Animal {
    let name: String
}

// Swift 5.7 can "open" an existential to access its concrete type
func feed(_ animal: any Animal) {
    // The compiler opens the existential, binding its concrete type
    print("Feeding \(animal.name)")
}

// Passing existential to generic function — Swift 5.7 opens automatically
func describe<A: Animal>(_ animal: A) -> String {
    "Animal: \(animal.name)"
}

let pet: any Animal = Dog(name: "Rex")
let desc = describe(pet)  // Swift 5.7+ opens the existential automatically
```

### When to use `any` vs generics vs `some`

| Scenario | Recommended | Why |
|---|---|---|
| Heterogeneous collection | `any` | Different concrete types |
| Single concrete type, hidden | `some` | Performance, type identity |
| Need to constrain relationships | generics | Full `where` clause power |
| Simple parameter constraint | `some` | Concise syntax (Swift 5.7+) |
| Dynamic dispatch needed | `any` | Runtime polymorphism |

## Type Erasure

### Manual type erasure pattern

```swift
// Protocol with associated type
protocol EventHandler {
    associatedtype Event
    func handle(_ event: Event)
}

// Type-erasing wrapper
struct AnyEventHandler<Event>: EventHandler {
    private let _handle: (Event) -> Void

    init<H: EventHandler>(_ handler: H) where H.Event == Event {
        _handle = handler.handle
    }

    func handle(_ event: Event) {
        _handle(event)
    }
}

// Usage
struct LoggingHandler: EventHandler {
    func handle(_ event: String) {
        print("Log: \(event)")
    }
}

struct AlertHandler: EventHandler {
    func handle(_ event: String) {
        print("Alert: \(event)")
    }
}

// Now we can store different handlers in the same array
let handlers: [AnyEventHandler<String>] = [
    AnyEventHandler(LoggingHandler()),
    AnyEventHandler(AlertHandler()),
]
```

### When type erasure is needed

Type erasure is needed when:
- You must store protocol values with associated types in collections
- You want to hide concrete types behind a uniform interface
- The protocol has `Self` or associated type requirements preventing direct existential use

### Primary associated types as alternative (Swift 5.7+)

```swift
// Declare primary associated type in angle brackets
protocol Repository<Model> {
    associatedtype Model
    func fetch(id: String) async throws -> Model?
    func save(_ model: Model) async throws
}

// Now you can use constrained existentials — no manual type erasure needed
let repo: any Repository<User> = InMemoryUserRepository()

// And constrained opaque types
func makeRepo() -> some Repository<User> {
    InMemoryUserRepository()
}

// Collections of constrained existentials
var repos: [any Repository<User>] = []
```

Primary associated types often eliminate the need for manual `Any*` wrappers.

## Phantom Types

### Type-safe state machines

```swift
// Phantom type markers — no stored properties, zero runtime cost
enum Draft {}
enum Published {}
enum Archived {}

struct Document<State> {
    let title: String
    let content: String
    private let createdAt: Date

    init(title: String, content: String) {
        self.title = title
        self.content = content
        self.createdAt = Date()
    }
}

// Transitions only available in specific states
extension Document where State == Draft {
    func publish() -> Document<Published> {
        Document<Published>(title: title, content: content)
    }
}

extension Document where State == Published {
    func archive() -> Document<Archived> {
        Document<Archived>(title: title, content: content)
    }
}

extension Document where State == Archived {
    func restore() -> Document<Draft> {
        Document<Draft>(title: title, content: content)
    }
}

// Usage — invalid transitions are compile-time errors
let draft = Document<Draft>(title: "Hello", content: "World")
let published = draft.publish()
let archived = published.archive()
// draft.archive()    // compile error — no archive() on Draft
// published.publish() // compile error — no publish() on Published
```

### Compile-time validation

```swift
enum Unvalidated {}
enum Validated {}

struct Email<Status> {
    let rawValue: String
}

func validate(email: Email<Unvalidated>) -> Email<Validated>? {
    guard email.rawValue.contains("@") else { return nil }
    return Email<Validated>(rawValue: email.rawValue)
}

// Only validated emails can be sent
func send(to email: Email<Validated>, body: String) {
    print("Sending to \(email.rawValue)")
}

let raw = Email<Unvalidated>(rawValue: "user@example.com")
// send(to: raw, body: "Hi")  // compile error
if let valid = validate(email: raw) {
    send(to: valid, body: "Hi")  // OK
}
```

### Zero runtime cost

Phantom type parameters exist only at compile time. They add no memory overhead — `Document<Draft>` and `Document<Published>` have identical memory layouts. The type parameter is erased after compilation.

## Metatypes

### `.self` and `Type`

```swift
// .self gives the metatype value
let intType: Int.Type = Int.self
let stringType: String.Type = String.self

// Use metatypes to call static methods or initializers
func create<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
    try JSONDecoder().decode(type, from: data)
}

let user = try create(User.self, from: jsonData)

// Protocol metatype
protocol Plugin {
    init()
    var name: String { get }
}

func register(_ pluginType: any Plugin.Type) {
    let instance = pluginType.init()
    print("Registered: \(instance.name)")
}
```

### `type(of:)` for dynamic dispatch

```swift
class Base {
    class func identify() -> String { "Base" }
}

class Derived: Base {
    override class func identify() -> String { "Derived" }
}

let instance: Base = Derived()

// Static metatype — resolves at compile time
Base.self.identify()         // "Base"

// Dynamic metatype — resolves at runtime
type(of: instance).identify() // "Derived"

// Practical use: dynamic factory
func duplicate<T: Decodable & Encodable>(_ value: T) throws -> T {
    let data = try JSONEncoder().encode(value)
    return try JSONDecoder().decode(type(of: value), from: data)
}
```

## @dynamicMemberLookup and @dynamicCallable

### @dynamicMemberLookup

```swift
@dynamicMemberLookup
struct Environment {
    private var values: [String: String]

    init(_ values: [String: String] = [:]) {
        self.values = values
    }

    subscript(dynamicMember key: String) -> String? {
        values[key]
    }
}

let env = Environment(["host": "localhost", "port": "8080"])
let host = env.host  // "localhost" — accessed as a property
let port = env.port  // "8080"
```

### Integration with key paths

```swift
@dynamicMemberLookup
struct Lens<Root, Value> {
    let get: (Root) -> Value

    subscript<T>(dynamicMember keyPath: KeyPath<Value, T>) -> Lens<Root, T> {
        Lens<Root, T>(get: { self.get($0)[keyPath: keyPath] })
    }
}

struct Address {
    var city: String
    var zip: String
}

struct Person {
    var name: String
    var address: Address
}

let personLens = Lens<Person, Person>(get: { $0 })
let cityLens = personLens.address.city  // Lens<Person, String>

let alice = Person(name: "Alice", address: Address(city: "Zurich", zip: "8000"))
print(cityLens.get(alice))  // "Zurich"
```

### @dynamicCallable

```swift
@dynamicCallable
struct Command {
    let name: String

    func dynamicallyCall(withArguments args: [String]) -> String {
        "\(name) \(args.joined(separator: " "))"
    }

    func dynamicallyCall(withKeywordArguments args: KeyValuePairs<String, String>) -> String {
        let flags = args.map { key, value in
            key.isEmpty ? value : "--\(key)=\(value)"
        }
        return "\(name) \(flags.joined(separator: " "))"
    }
}

let git = Command(name: "git")
git("status", "-s")                    // "git status -s"
git(branch: "main", verbose: "true")   // "git --branch=main --verbose=true"
```

## Value Wrappers

### Using structs for type-safe wrappers

```swift
// Prevent primitive obsession — distinct types for distinct concepts
struct UserId: Hashable, Sendable {
    let rawValue: String
}

struct OrderId: Hashable, Sendable {
    let rawValue: String
}

struct Meters: Hashable, Sendable {
    let rawValue: Double
}

struct Kilograms: Hashable, Sendable {
    let rawValue: Double
}

// The compiler prevents mixing them up
func fetchUser(id: UserId) -> String { "User \(id.rawValue)" }
func fetchOrder(id: OrderId) -> String { "Order \(id.rawValue)" }

let userId = UserId(rawValue: "u-123")
let orderId = OrderId(rawValue: "o-456")

fetchUser(id: userId)    // OK
// fetchUser(id: orderId)  // compile error
```

### RawRepresentable for lightweight wrappers

```swift
struct Email: RawRepresentable, Hashable, Codable, Sendable {
    let rawValue: String

    init?(rawValue: String) {
        guard rawValue.contains("@") else { return nil }
        self.rawValue = rawValue
    }
}

struct Port: RawRepresentable, Hashable, Sendable {
    let rawValue: UInt16

    init?(rawValue: UInt16) {
        guard rawValue > 0 else { return nil }
        self.rawValue = rawValue
    }
}

// RawRepresentable gives free Codable, works with JSON encoding
let email = Email(rawValue: "alice@example.com")  // Optional<Email>
let port = Port(rawValue: 8080)                    // Optional<Port>

// Use in API signatures for self-documenting code
func connect(host: String, port: Port) { /* ... */ }
```

### Preventing primitive obsession

```swift
// Bad — easy to mix up parameters
func createUser(name: String, email: String, phone: String) { /* ... */ }

// Good — each parameter has a distinct type
struct UserName: RawRepresentable, Hashable, Sendable {
    let rawValue: String
    init(rawValue: String) { self.rawValue = rawValue }
}

struct PhoneNumber: RawRepresentable, Hashable, Sendable {
    let rawValue: String
    init?(rawValue: String) {
        guard rawValue.allSatisfy({ $0.isNumber || $0 == "+" || $0 == "-" }) else {
            return nil
        }
        self.rawValue = rawValue
    }
}

func createUser(name: UserName, email: Email, phone: PhoneNumber) { /* ... */ }

// Impossible to accidentally swap arguments
```

### ExpressibleBy literal protocols for convenience

```swift
struct Identifier: RawRepresentable, Hashable, Sendable,
                   ExpressibleByStringLiteral
{
    let rawValue: String

    init(rawValue: String) { self.rawValue = rawValue }
    init(stringLiteral value: String) { self.rawValue = value }
}

// Can initialize with string literals for convenience
let id: Identifier = "abc-123"

struct Percentage: RawRepresentable, Hashable, Sendable,
                   ExpressibleByFloatLiteral
{
    let rawValue: Double

    init?(rawValue: Double) {
        guard (0...100).contains(rawValue) else { return nil }
        self.rawValue = rawValue
    }

    init(floatLiteral value: Double) {
        precondition((0...100).contains(value), "Percentage must be 0-100")
        self.rawValue = value
    }
}

let progress: Percentage = 75.0
```
