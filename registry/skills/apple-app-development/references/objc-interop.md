# Objective-C Interop Reference

Practical guide for working with mixed Swift/Objective-C codebases. Always prefer Swift for new code; use interop to maintain and incrementally migrate existing Objective-C.


## Bridging Headers

A bridging header lets Swift code call Objective-C APIs within an app or framework target.

### Setup

Xcode can auto-create the bridging header when you first add a Swift file to an Objective-C project (or vice versa). To create one manually:

1. Create a file named `MyApp-Bridging-Header.h`.
2. In **Build Settings**, set **Objective-C Bridging Header** to the path relative to the project root:

```
SWIFT_OBJC_BRIDGING_HEADER = MyApp/MyApp-Bridging-Header.h
```

### Importing Obj-C Headers into Swift

Add `#import` statements for every Objective-C header you want visible in Swift:

```objc
// MyApp-Bridging-Header.h
#import "LegacyNetworkManager.h"
#import "OBJCUserModel.h"
#import <ThirdPartySDK/ThirdPartySDK.h>
```

All imported declarations become available in every Swift file in the target without additional `import` statements.

### Best Practices

- Keep the bridging header minimal. Only import what Swift actually uses.
- Never import Swift-generated headers (`MyApp-Swift.h`) in the bridging header -- this causes circular dependencies.
- For framework targets, use umbrella headers instead of bridging headers.


## Swift to Obj-C

Swift declarations are exposed to Objective-C through a compiler-generated header.

### The Generated Header

Xcode generates `MyApp-Swift.h` (derived from the module name). Import it in Objective-C files:

```objc
// LegacyViewController.m
#import "MyApp-Swift.h"
```

Only declarations marked for Objective-C visibility appear in this header.

### `@objc` Attribute

Expose individual declarations:

```swift
class AnalyticsService: NSObject {
    @objc func trackEvent(_ name: String, properties: [String: Any]) {
        // ...
    }

    @objc static let shared = AnalyticsService()
}
```

### `@objcMembers`

Expose all compatible members of a class at once:

```swift
@objcMembers
class UserProfile: NSObject {
    var displayName: String = ""
    var email: String = ""
    var loginCount: Int = 0

    func formattedName() -> String {
        return displayName.capitalized
    }
}
```

Use `@nonobjc` to opt specific members out:

```swift
@objcMembers
class DataManager: NSObject {
    func fetchLegacyData() -> [String] { /* visible to Obj-C */ }

    @nonobjc
    func fetchTypedData<T: Decodable>(_ type: T.Type) -> T? { /* Swift-only */ }
}
```

### Limitations

The following Swift features cannot be represented in Objective-C:

| Feature | Workaround |
|---|---|
| Generics | Use type-erased wrappers or `Any` |
| Enums with associated values | Create Obj-C-compatible enum + separate data class |
| Structs | Wrap in an `NSObject` subclass |
| Top-level functions | Wrap in a class with static methods |
| Default parameter values | Create overloaded methods |
| Tuples | Use a small wrapper class or `NSArray` |
| Swift-only protocols (without `@objc`) | Add `@objc` or create an adapter |


## NS_SWIFT_NAME

Rename Objective-C APIs to feel natural in Swift.

### Basic Renaming

```objc
// Objective-C
typedef NS_ENUM(NSInteger, ABCNetworkErrorCode) {
    ABCNetworkErrorCodeTimeout,
    ABCNetworkErrorCodeUnreachable,
    ABCNetworkErrorCodeUnauthorized,
} NS_SWIFT_NAME(NetworkErrorCode);

@interface ABCNetworkClient : NSObject

- (void)sendRequestWithURL:(NSURL *)url
                completion:(void (^)(NSData * _Nullable, NSError * _Nullable))completion
    NS_SWIFT_NAME(send(url:completion:));

+ (instancetype)clientWithConfiguration:(ABCConfiguration *)config
    NS_SWIFT_NAME(init(configuration:));

@end
```

Swift sees:

```swift
let client = NetworkClient(configuration: config)
client.send(url: myURL) { data, error in /* ... */ }
```

### NS_REFINED_FOR_SWIFT

Hide the Objective-C API (prefixes it with `__`) so you can provide a better Swift wrapper:

```objc
@interface ABCLocationManager : NSObject

- (void)fetchLocationWithCompletion:(void (^)(CLLocation * _Nullable, NSError * _Nullable))completion
    NS_REFINED_FOR_SWIFT;

@end
```

```swift
extension ABCLocationManager {
    func fetchLocation() async throws -> CLLocation {
        try await withCheckedThrowingContinuation { continuation in
            __fetchLocation { location, error in
                if let location {
                    continuation.resume(returning: location)
                } else {
                    continuation.resume(throwing: error ?? LocationError.unknown)
                }
            }
        }
    }
}
```


## Nullability Annotations

Nullability annotations control how Objective-C types map to Swift optionals.

### Annotations

| Obj-C Annotation | Swift Mapping | Meaning |
|---|---|---|
| `nonnull` | `Type` | Never nil |
| `nullable` | `Type?` | May be nil |
| `null_unspecified` | `Type!` (IUO) | Unaudited (default) |
| `null_resettable` | `Type!` | Getter nonnull, setter nullable |

### Audited Regions

Wrap large sections where most parameters are nonnull:

```objc
NS_ASSUME_NONNULL_BEGIN

@interface UserService : NSObject

// displayName is nonnull (from the region default)
// nickname is explicitly nullable
- (instancetype)initWithDisplayName:(NSString *)displayName
                           nickname:(nullable NSString *)nickname;

- (void)updateProfile:(NSDictionary<NSString *, id> *)fields
            completion:(nullable void (^)(NSError * _Nullable error))completion;

@property (nonatomic, copy) NSString *displayName;           // String
@property (nonatomic, copy, nullable) NSString *nickname;    // String?

@end

NS_ASSUME_NONNULL_END
```

### Impact on Swift

```swift
let service = UserService(displayName: "Alice", nickname: nil)
// service.displayName -> String  (guaranteed non-optional)
// service.nickname    -> String? (optional)
```

Annotating nullability is the single highest-value step when preparing Objective-C code for Swift interop. Without annotations, every reference type becomes an implicitly unwrapped optional (`!`), hiding potential crashes.


## Type Bridging

Foundation types bridge automatically between Objective-C and Swift.

### Core Bridged Types

| Objective-C | Swift | Notes |
|---|---|---|
| `NSString` | `String` | Value type in Swift, copy semantics |
| `NSArray` | `Array` | Untyped `NSArray` becomes `[Any]` |
| `NSDictionary` | `Dictionary` | Untyped becomes `[AnyHashable: Any]` |
| `NSNumber` | Various (`Int`, `Double`, `Bool`) | Context-dependent |
| `NSError` | `Error` | Bridged via `Error` protocol |
| `NSData` | `Data` | Value type in Swift |
| `NSURL` | `URL` | Value type in Swift |
| `NSDate` | `Date` | Value type in Swift |
| `NSSet` | `Set` | Requires `Hashable` elements |

### Typed Collections

Use lightweight generics in Objective-C for clean Swift bridging:

```objc
// Objective-C with lightweight generics
@property (nonatomic, copy) NSArray<NSString *> *tags;           // -> [String]
@property (nonatomic, copy) NSDictionary<NSString *, NSNumber *> *scores; // -> [String: NSNumber]
@property (nonatomic, copy) NSArray *untypedItems;               // -> [Any]
```

### NSNumber Bridging

```swift
// NSNumber bridges to specific Swift numeric types based on context
let objcDict: NSDictionary = legacyAPI.fetchConfig()

// Explicit casting required for untyped collections
if let timeout = objcDict["timeout"] as? TimeInterval {
    // use timeout as Double
}
if let retryCount = objcDict["retryCount"] as? Int {
    // use retryCount as Int
}
```

### NSError to Swift Error

```objc
// Objective-C error domain
NSString *const ABCServiceErrorDomain;

typedef NS_ERROR_ENUM(ABCServiceErrorDomain, ABCServiceErrorCode) {
    ABCServiceErrorCodeNotFound,
    ABCServiceErrorCodePermissionDenied,
    ABCServiceErrorCodeServerError,
};
```

```swift
// Swift sees this as a typed error
do {
    try service.performAction()
} catch let error as ABCServiceError {
    switch error.code {
    case .notFound: handleNotFound()
    case .permissionDenied: handleDenied()
    case .serverError: handleServerError()
    @unknown default: handleUnknown()
    }
}
```


## Protocol Bridging

### @objc Protocol

```objc
@protocol DataSourceDelegate <NSObject>

@required
- (NSInteger)numberOfItems;
- (NSString *)itemAtIndex:(NSInteger)index;

@optional
- (void)didSelectItemAtIndex:(NSInteger)index;
- (void)didDeselectItemAtIndex:(NSInteger)index;

@end
```

### Swift Implementation

```swift
class ItemController: NSObject, DataSourceDelegate {
    func numberOfItems() -> Int {
        return items.count
    }

    func item(at index: Int) -> String {
        return items[index]
    }

    // Optional methods -- implement only if needed
    func didSelectItem(at index: Int) {
        print("Selected \(items[index])")
    }
}
```

### Checking Optional Methods

```objc
// Objective-C -- responds(to:) check
if ([self.delegate respondsToSelector:@selector(didSelectItemAtIndex:)]) {
    [self.delegate didSelectItemAtIndex:index];
}
```

```swift
// Swift -- optional chaining
delegate?.didSelectItem?(at: index)
```

### Swift Protocol vs Obj-C Protocol Differences

| Aspect | Swift Protocol | @objc Protocol |
|---|---|---|
| Optional methods | Not supported (use default impl) | Supported via `@optional` |
| Value type conformance | Structs, enums, classes | Classes only (NSObject) |
| Associated types | Supported | Not supported |
| Default implementations | Via extensions | Not available |
| Property requirements | `var` with get/set | `@property` declarations |

### Defining a Protocol in Swift for Obj-C Use

```swift
@objc protocol NavigationDelegate: AnyObject {
    func didNavigate(to route: String)
    @objc optional func shouldNavigate(to route: String) -> Bool
}
```


## Memory Management

### ARC in Mixed Codebases

ARC manages memory in both languages. The rules are the same, but awareness of retain cycles matters more in mixed code where ownership is less obvious.

### Common Cycle: Delegate Pattern

```objc
// Objective-C -- always use weak for delegates
@interface LegacyController : NSObject
@property (nonatomic, weak) id<ControllerDelegate> delegate;
@end
```

```swift
// Swift wrapper
class ModernController {
    private let legacy = LegacyController()

    init() {
        legacy.delegate = self // safe: LegacyController holds weak ref
    }
}
```

### autoreleasepool

Use `autoreleasepool` when calling Objective-C APIs that return autoreleased objects in tight loops:

```swift
func processLargeDataSet(_ items: [LegacyItem]) {
    for item in items {
        autoreleasepool {
            // Each iteration drains autoreleased objects from Obj-C calls
            let processed = item.legacyTransform() // returns autoreleased NSData
            store(processed)
        }
    }
}
```

### weak vs unowned Across Languages

| Scenario | Use | Why |
|---|---|---|
| Obj-C delegate property | `weak` in Obj-C | Delegates outlive the delegator unpredictably |
| Swift closure capturing Obj-C object | `[weak self]` | Obj-C object may deallocate while closure is retained |
| Swift closure where lifetime is guaranteed | `[unowned self]` | Slightly cheaper; crashes if wrong |
| Obj-C block capturing Swift object | `__weak` in Obj-C | Same cycle-avoidance semantics |

```objc
// Objective-C block with weak capture
__weak typeof(self) weakSelf = self;
[self.swiftService fetchDataWithCompletion:^(NSArray *results) {
    __strong typeof(weakSelf) strongSelf = weakSelf;
    if (!strongSelf) return;
    [strongSelf handleResults:results];
}];
```


## Incremental Migration Strategy

### Guiding Principles

1. Never rewrite working, stable Objective-C "just because." Migrate when you need to change it.
2. All new code is Swift.
3. Wrap before rewrite -- create Swift interfaces around Objective-C internals.

### Screen-by-Screen Migration

Migrate at the view controller boundary:

```
Phase 1: New screens in Swift, calling Obj-C services
Phase 2: Wrap shared Obj-C services with Swift protocols
Phase 3: Replace Obj-C service implementations one at a time
Phase 4: Migrate remaining Obj-C screens when they need changes
```

```swift
// Phase 2: Swift protocol wrapping Obj-C service
protocol UserRepository {
    func fetchUser(id: String) async throws -> User
}

// Obj-C adapter (temporary, removed in Phase 3)
class LegacyUserRepository: UserRepository {
    private let objcService: OBJCUserService

    init(objcService: OBJCUserService) {
        self.objcService = objcService
    }

    func fetchUser(id: String) async throws -> User {
        try await withCheckedThrowingContinuation { continuation in
            objcService.fetchUser(withID: id) { objcUser, error in
                if let error {
                    continuation.resume(throwing: error)
                } else if let objcUser {
                    continuation.resume(returning: User(legacy: objcUser))
                } else {
                    continuation.resume(throwing: RepositoryError.unexpectedNil)
                }
            }
        }
    }
}
```

### Module-by-Module Migration

For larger codebases, extract modules into Swift packages:

```
MyApp/
  MyApp/                     # Main target (mixed, shrinking)
  Packages/
    NetworkKit/              # Migrated from OBJCNetworking/
    UserDomain/              # Migrated from OBJCUserManager/
    LegacyBridge/            # Adapters for not-yet-migrated Obj-C
```

### Extracting Swift Packages from Obj-C Monolith

1. Identify a cohesive slice of functionality (e.g., networking, analytics).
2. Define a Swift protocol for the public interface.
3. Create a Swift package with the protocol and a new Swift implementation.
4. In the main app, create a bridge adapter that conforms to the protocol using the Obj-C code.
5. Swap the adapter for the real Swift implementation when ready.
6. Delete the Obj-C files.

### When to Rewrite vs Wrap

| Rewrite | Wrap |
|---|---|
| Code needs significant changes anyway | Code is stable, rarely modified |
| Small, well-understood module | Large, complex module with subtle behavior |
| Good test coverage exists | No tests (risky to rewrite) |
| Performance-critical code that benefits from Swift | Performance is already acceptable |
| Security-sensitive code that benefits from Swift's type safety | Low-risk utility code |


## Common Patterns

### Wrapping Obj-C Singletons

```objc
// Objective-C singleton
@interface ABCSessionManager : NSObject
+ (instancetype)sharedManager;
- (void)startSessionWithConfig:(ABCConfig *)config;
- (void)endSession;
@property (nonatomic, readonly) BOOL isActive;
@end
```

```swift
// Swift wrapper with modern API
actor SessionManager {
    static let shared = SessionManager()

    private let legacy = ABCSessionManager.shared()

    func start(config: SessionConfig) {
        let objcConfig = config.toLegacy()
        legacy.startSession(with: objcConfig)
    }

    func end() {
        legacy.endSession()
    }

    var isActive: Bool {
        legacy.isActive
    }
}
```

### Bridging Delegates to async/await

```objc
// Objective-C delegate-based API
@protocol ABCDownloadDelegate <NSObject>
- (void)download:(ABCDownload *)download didFinishWithData:(NSData *)data;
- (void)download:(ABCDownload *)download didFailWithError:(NSError *)error;
@end
```

```swift
// Use @MainActor to ensure thread-safe access to continuations dictionary.
// Without isolation, delegate callbacks and download(from:) could race on the dictionary.
@MainActor
class DownloadService: NSObject, ABCDownloadDelegate {
    private var continuations: [String: CheckedContinuation<Data, Error>] = [:]

    func download(from url: URL) async throws -> Data {
        let download = ABCDownload(url: url)
        download.delegate = self

        return try await withCheckedThrowingContinuation { continuation in
            continuations[url.absoluteString] = continuation
            download.start()
        }
    }

    // MARK: - ABCDownloadDelegate

    nonisolated func download(_ download: ABCDownload, didFinishWith data: Data) {
        let key = download.url.absoluteString
        Task { @MainActor in
            continuations[key]?.resume(returning: data)
            continuations[key] = nil
        }
    }

    nonisolated func download(_ download: ABCDownload, didFailWith error: Error) {
        let key = download.url.absoluteString
        Task { @MainActor in
            continuations[key]?.resume(throwing: error)
            continuations[key] = nil
        }
    }
}
```

### Adapting KVO to Combine

```swift
import Combine

extension LegacyPlayer {
    /// Bridges KVO-observable `isPlaying` to a Combine publisher.
    var isPlayingPublisher: AnyPublisher<Bool, Never> {
        publisher(for: \.isPlaying)
            .removeDuplicates()
            .eraseToAnyPublisher()
    }

    /// Bridges KVO-observable `currentTime` to an AsyncStream.
    var currentTimeStream: AsyncStream<TimeInterval> {
        AsyncStream { continuation in
            let cancellable = publisher(for: \.currentTime)
                .sink { time in
                    continuation.yield(time)
                }
            continuation.onTermination = { _ in
                cancellable.cancel()
            }
        }
    }
}

// Usage
class PlayerViewModel: ObservableObject {
    @Published var isPlaying = false
    private var cancellables = Set<AnyCancellable>()

    init(player: LegacyPlayer) {
        player.isPlayingPublisher
            .receive(on: DispatchQueue.main)
            .assign(to: &$isPlaying)
    }
}
```


## Mixed-Language SPM Modules

### Obj-C and Swift in the Same Package

SPM does not allow mixing Swift and Objective-C/C in the same target. Use separate targets with dependencies:

```swift
// Package.swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "LegacyKit",
    platforms: [.iOS(.v16)],
    products: [
        .library(name: "LegacyKit", targets: ["LegacyKitSwift"]),
    ],
    targets: [
        // Obj-C target with clang module
        .target(
            name: "LegacyKitObjC",
            path: "Sources/LegacyKitObjC",
            publicHeadersPath: "include"
        ),
        // Swift target that depends on the Obj-C target
        .target(
            name: "LegacyKitSwift",
            dependencies: ["LegacyKitObjC"],
            path: "Sources/LegacyKitSwift"
        ),
    ]
)
```

### Directory Structure

```
Sources/
  LegacyKitObjC/
    include/
      LegacyKitObjC.h          # Umbrella header
      LegacyParser.h
      LegacyFormatter.h
    LegacyParser.m
    LegacyFormatter.m
  LegacyKitSwift/
    ModernParser.swift           # imports LegacyKitObjC
    ModernFormatter.swift
```

### Umbrella Header

```objc
// Sources/LegacyKitObjC/include/LegacyKitObjC.h
#import <LegacyKitObjC/LegacyParser.h>
#import <LegacyKitObjC/LegacyFormatter.h>
```

### Consuming from Swift

```swift
// Sources/LegacyKitSwift/ModernParser.swift
import LegacyKitObjC

public struct ModernParser {
    private let legacy = LegacyParser()

    public func parse(_ input: String) -> ParseResult {
        let objcResult = legacy.parse(input)
        return ParseResult(legacy: objcResult)
    }
}
```

### Clang Module Map (Custom)

For advanced cases, provide a custom `module.modulemap`:

```
// Sources/LegacyKitObjC/include/module.modulemap
module LegacyKitObjC {
    umbrella header "LegacyKitObjC.h"
    export *
    module * { export * }
}
```


## Gotchas

### Circular Imports

The most common interop build failure. The cycle:
- `MyApp-Bridging-Header.h` imports `SomeObjCClass.h`
- `SomeObjCClass.m` imports `MyApp-Swift.h`
- `MyApp-Swift.h` depends on the bridging header

**Fix:** Use forward declarations in Objective-C headers:

```objc
// SomeObjCClass.h -- forward declare, do not import
@class SwiftServiceWrapper;

@interface SomeObjCClass : NSObject
@property (nonatomic, strong) SwiftServiceWrapper *service;
@end
```

```objc
// SomeObjCClass.m -- import the generated header only in .m files
#import "MyApp-Swift.h"

@implementation SomeObjCClass
- (void)doWork {
    [self.service performTask];
}
@end
```

**Rule:** Never import `MyApp-Swift.h` in a `.h` file. Always use forward declarations in headers and import in `.m` files only.

### Naming Conflicts

Swift and Objective-C have different naming conventions. Conflicts appear when:

- An Obj-C class name collides with a Swift type (e.g., both define `Router`).
- Obj-C prefixed names become ambiguous after prefix stripping.

```swift
// Disambiguate with module name
let swiftRouter = MyApp.Router()
let objcRouter = LegacyModule.ABCRouter()
```

### Swift 6 Strict Concurrency and ObjC Interop

Swift 6 strict concurrency significantly impacts Objective-C bridging:

```swift
// 1. Suppress concurrency warnings for pre-concurrency ObjC modules
@preconcurrency import LegacyObjCFramework

// 2. Completion handlers imported from ObjC are now @Sendable by default
//    when async variants exist. If the ObjC code isn't actually thread-safe,
//    use @preconcurrency import to suppress warnings.

// 3. ObjC headers can opt out of Sendable checking:
//    __attribute__((swift_attr("@Sendable")))     — mark a type as Sendable
//    __attribute__((swift_attr("@nonSendable")))   — opt out of Sendable

// 4. Actor-wrapped ObjC singletons — all calls become async from outside
actor SafeObjCWrapper {
    private let legacy = LegacyManager.shared()

    func fetchData() -> Data {
        legacy.getData()  // Safe: runs on actor's serial executor
    }
}
// ObjC code cannot call actor methods directly — provide @objc nonisolated bridge if needed.
```

Rules:
- Use `@preconcurrency import` for ObjC modules that haven't been audited for concurrency.
- When wrapping ObjC singletons in actors, remember all calls become `async` from outside the actor.
- Completion-handler-based ObjC APIs are automatically imported as `async` — verify thread safety before using.
- Under Swift 6.2 default MainActor isolation, all ObjC interop code runs on MainActor unless explicitly marked `nonisolated` or `@concurrent`.

### Swift-Only Features Unavailable in Bridged Code

Code using these features is invisible to Objective-C, even with `@objc`:

- Enums with associated values
- Structs (no `@objc` support)
- Protocol extensions with default implementations (Obj-C sees the requirement, not the default)
- Property wrappers (the wrapper itself is not visible)
- Result builders
- Opaque return types (`some Protocol`)
- Actors (Obj-C cannot participate in actor isolation)

### Performance Implications of `@objc dynamic`

```swift
class AnimatableView: UIView {
    // @objc dynamic enables KVO and message dispatch (slower)
    @objc dynamic var progress: CGFloat = 0

    // Regular Swift property uses static/vtable dispatch (faster)
    var internalState: ViewState = .idle
}
```

| Dispatch | Mechanism | Relative Cost |
|---|---|---|
| Static (Swift default) | Direct call | Fastest |
| V-table (Swift class) | Indirect via table | Fast |
| Message send (`@objc dynamic`) | `objc_msgSend` | Slower (~3-5x) |

Use `@objc dynamic` only when you need KVO observability or Objective-C runtime features. For performance-critical paths (tight loops, rendering), prefer plain Swift properties.

### Build Order and Incremental Compilation

- Changes to the bridging header trigger recompilation of all Swift files in the target.
- Changes to Swift `@objc` interfaces trigger regeneration of `MyApp-Swift.h`, potentially recompiling Objective-C files that import it.
- **Mitigation:** Keep interop surfaces small. Fewer declarations in the bridging header and fewer `@objc` annotations mean faster incremental builds.

### NSObject Requirement

All Swift classes exposed to Objective-C must inherit from `NSObject` (or another Obj-C class). Forgetting this is a common compile error:

```swift
// Will not compile for @objc
class BadService {
    @objc func doSomething() { } // Error: @objc requires NSObject
}

// Correct
class GoodService: NSObject {
    @objc func doSomething() { }
}
```
