# Networking Reference (URLSession & Alamofire)

Comprehensive guide to networking on Apple platforms. URLSession is the foundation — use it by default. Alamofire is an optional convenience layer for complex scenarios (interceptors, retry, certificate pinning). Both can coexist in the same project.

## When to Use Which

| Scenario | Recommendation |
|---|---|
| Simple REST API calls | URLSession async/await |
| One-off data fetches | `URLSession.shared` |
| Background downloads/uploads | URLSession background session |
| WebSocket connections | `URLSessionWebSocketTask` |
| Complex auth token refresh | Alamofire `RequestInterceptor` (or custom URLSession wrapper) |
| Automatic retry with backoff | Alamofire `RetryPolicy` |
| Certificate pinning | Alamofire `ServerTrustManager` (simpler) or URLSession delegate (more control) |
| Multipart form uploads | Alamofire (convenient) or manual URLSession (verbose) |
| Request/response logging | Alamofire `EventMonitor` |

**Rule:** Start with URLSession. Add Alamofire only when you genuinely need its advanced features. Don't add it for basic GET/POST — that's one line of native code.


## URLSession — Foundation

### Simple Data Fetch (async/await)
---

```swift
// One-liner with shared session
let (data, response) = try await URLSession.shared.data(from: url)

// With URLRequest for full control
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")
request.httpBody = try JSONEncoder().encode(payload)

let (data, response) = try await URLSession.shared.data(for: request)
```

#### Response Validation

URLSession does **not** throw on HTTP error status codes (4xx, 5xx). Always validate:

```swift
func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T {
    let (data, response) = try await URLSession.shared.data(from: url)

    guard let httpResponse = response as? HTTPURLResponse else {
        throw NetworkError.invalidResponse
    }

    guard (200...299).contains(httpResponse.statusCode) else {
        throw NetworkError.httpError(statusCode: httpResponse.statusCode, data: data)
    }

    return try JSONDecoder().decode(T.self, from: data)
}
```

### API Client Pattern
---

A reusable, protocol-based networking layer:

```swift
protocol APIClient: Sendable {
    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T
}

struct Endpoint {
    let path: String
    let method: HTTPMethod
    let queryItems: [URLQueryItem]?
    let body: Encodable?
    let headers: [String: String]?

    enum HTTPMethod: String {
        case get = "GET"
        case post = "POST"
        case put = "PUT"
        case patch = "PATCH"
        case delete = "DELETE"
    }
}

final class URLSessionAPIClient: APIClient, Sendable {
    private let session: URLSession
    private let baseURL: URL
    private let decoder: JSONDecoder

    init(baseURL: URL, session: URLSession = .shared, decoder: JSONDecoder = .init()) {
        self.baseURL = baseURL
        self.session = session
        self.decoder = decoder
    }

    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let urlRequest = try buildRequest(for: endpoint)
        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw NetworkError.httpError(
                statusCode: httpResponse.statusCode,
                data: data
            )
        }

        return try decoder.decode(T.self, from: data)
    }

    private func buildRequest(for endpoint: Endpoint) throws -> URLRequest {
        guard var components = URLComponents(url: baseURL.appendingPathComponent(endpoint.path),
                                              resolvingAgainstBaseURL: true)
        else { throw NetworkError.invalidResponse }
        components.queryItems = endpoint.queryItems

        guard let url = components.url else { throw NetworkError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = endpoint.method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let body = endpoint.body {
            request.httpBody = try JSONEncoder().encode(body)
        }

        endpoint.headers?.forEach { request.setValue($1, forHTTPHeaderField: $0) }
        return request
    }
}
```

### Session Configuration
---

```swift
// Default — disk caching, cookies, credentials
let defaultConfig = URLSessionConfiguration.default

// Ephemeral — no persistence (private browsing)
let ephemeralConfig = URLSessionConfiguration.ephemeral

// Background — transfers continue when app is suspended
let backgroundConfig = URLSessionConfiguration.background(
    withIdentifier: "com.example.app.background"
)
```

#### Common Configuration Options

```swift
let config = URLSessionConfiguration.default
config.timeoutIntervalForRequest = 30        // Per-request timeout
config.timeoutIntervalForResource = 300      // Total resource timeout
config.waitsForConnectivity = true           // Wait for network instead of failing immediately
config.allowsCellularAccess = true
config.allowsExpensiveNetworkAccess = true
config.allowsConstrainedNetworkAccess = false // Respect Low Data Mode
config.httpMaximumConnectionsPerHost = 6
config.requestCachePolicy = .useProtocolCachePolicy

// Default headers for all requests
config.httpAdditionalHeaders = [
    "Accept": "application/json",
    "X-App-Version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
]

let session = URLSession(configuration: config)
```

### Uploads
---

#### JSON Body

```swift
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")

let payload = CreateUserRequest(name: "Alice", email: "alice@example.com")
request.httpBody = try JSONEncoder().encode(payload)

let (data, response) = try await URLSession.shared.data(for: request)
```

#### File Upload

```swift
let (data, response) = try await URLSession.shared.upload(
    for: request,
    fromFile: fileURL
)
```

#### Multipart Form Data (Manual)

```swift
func createMultipartRequest(url: URL, fileData: Data, fileName: String,
                             mimeType: String, fields: [String: String]) -> URLRequest {
    let boundary = UUID().uuidString
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("multipart/form-data; boundary=\(boundary)",
                     forHTTPHeaderField: "Content-Type")

    var body = Data()

    // Text fields
    for (key, value) in fields {
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"\(key)\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(value)\r\n".data(using: .utf8)!)
    }

    // File
    body.append("--\(boundary)\r\n".data(using: .utf8)!)
    body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
    body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
    body.append(fileData)
    body.append("\r\n".data(using: .utf8)!)

    // Close
    body.append("--\(boundary)--\r\n".data(using: .utf8)!)

    request.httpBody = body
    return request
}
```

### Downloads
---

#### Simple Download

```swift
let (localURL, response) = try await URLSession.shared.download(from: remoteURL)

// Move from temp location to permanent
let documentsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
let destination = documentsURL.appendingPathComponent("file.pdf")
try FileManager.default.moveItem(at: localURL, to: destination)
```

#### Background Downloads

```swift
// 1. Create background session (reuse same identifier across app launches)
let config = URLSessionConfiguration.background(withIdentifier: "com.example.app.download")
config.isDiscretionary = true           // System optimizes timing (Wi-Fi, charging)
config.sessionSendsLaunchEvents = true  // Wake app on completion

let backgroundSession = URLSession(configuration: config, delegate: self, delegateQueue: nil)

// 2. Create and start download
let task = backgroundSession.downloadTask(with: remoteURL)
task.earliestBeginDate = Date().addingTimeInterval(60 * 60)  // Schedule for later
task.countOfBytesClientExpectsToReceive = 10 * 1024 * 1024   // Help system plan
task.resume()

// 3. Handle completion via delegate
func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                didFinishDownloadingTo location: URL) {
    // Move file from temp location — it's deleted after this method returns
    let destination = documentsDirectory.appendingPathComponent("downloaded.pdf")
    try? FileManager.default.moveItem(at: location, to: destination)
}

// 4. Handle app relaunch (AppDelegate)
func application(_ application: UIApplication,
                 handleEventsForBackgroundURLSession identifier: String,
                 completionHandler: @escaping () -> Void) {
    backgroundCompletionHandler = completionHandler
}

func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
    Task { @MainActor in
        backgroundCompletionHandler?()
        backgroundCompletionHandler = nil
    }
}
```

**Background session rules:**
- Must provide a delegate (no async/await or completion handlers)
- HTTP/HTTPS only
- Upload tasks must be file-based (not data/stream)
- Recreate session with same identifier on app relaunch
- Use single session with multiple tasks, not multiple sessions

#### Resumable Downloads

```swift
// Cancel and save resume data
task.cancel { resumeData in
    self.savedResumeData = resumeData
}

// Resume later
if let resumeData = savedResumeData {
    let task = session.downloadTask(withResumeData: resumeData)
    task.resume()
}
```

### Streaming Bytes
---

```swift
let (bytes, response) = try await URLSession.shared.bytes(from: url)

for try await line in bytes.lines {
    processLine(line)
}
```

### WebSocket
---

```swift
let task = URLSession.shared.webSocketTask(with: URL(string: "wss://example.com/ws")!)
task.resume()

// Send
try await task.send(.string("Hello"))
try await task.send(.data(binaryData))

// Receive
let message = try await task.receive()
switch message {
case .string(let text):
    print("Received: \(text)")
case .data(let data):
    print("Received \(data.count) bytes")
@unknown default:
    break
}

// Ping
task.sendPing { error in
    if let error { print("Ping failed: \(error)") }
}

// Close
task.cancel(with: .normalClosure, reason: nil)
```

### Authentication Challenges
---

#### Server Trust (SSL/TLS Validation)

```swift
class NetworkDelegate: NSObject, URLSessionDelegate {
    func urlSession(_ session: URLSession,
                    didReceive challenge: URLAuthenticationChallenge
    ) async -> (URLSession.AuthChallengeDisposition, URLCredential?) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust
        else {
            return (.performDefaultHandling, nil)
        }

        // Custom certificate validation logic here
        return (.useCredential, URLCredential(trust: serverTrust))
    }
}
```

#### Basic/Digest Authentication

```swift
func urlSession(_ session: URLSession, task: URLSessionTask,
                didReceive challenge: URLAuthenticationChallenge
) async -> (URLSession.AuthChallengeDisposition, URLCredential?) {
    if challenge.previousFailureCount == 0 {
        let credential = URLCredential(user: username, password: password,
                                        persistence: .forSession)
        return (.useCredential, credential)
    }
    return (.cancelAuthenticationChallenge, nil)
}
```

### Auth Token Injection (URLSession-only approach)
---

```swift
actor TokenManager {
    private var accessToken: String?
    private var refreshToken: String?
    private var refreshTask: Task<String, Error>?

    func validToken() async throws -> String {
        if let token = accessToken, !isExpired(token) {
            return token
        }
        // All concurrent callers share a single refresh task
        if let existingTask = refreshTask {
            return try await existingTask.value
        }
        let task = Task { [self] () throws -> String in
            defer { refreshTask = nil }
            guard let refreshToken else { throw AuthError.noRefreshToken }
            let newTokens = try await authService.refresh(refreshToken)
            accessToken = newTokens.access
            self.refreshToken = newTokens.refresh
            return newTokens.access
        }
        refreshTask = task
        return try await task.value
    }
}

// Usage in API client
func authorizedRequest(_ endpoint: Endpoint) async throws -> URLRequest {
    var request = try buildRequest(for: endpoint)
    let token = try await tokenManager.validToken()
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    return request
}
```

### Caching
---

```swift
// Configure cache
let cache = URLCache(
    memoryCapacity: 50 * 1024 * 1024,   // 50 MB memory
    diskCapacity: 200 * 1024 * 1024      // 200 MB disk
)
config.urlCache = cache
config.requestCachePolicy = .useProtocolCachePolicy

// Per-request cache policy
var request = URLRequest(url: url)
request.cachePolicy = .reloadIgnoringLocalCacheData  // Skip cache
```

| Policy | Behavior |
|---|---|
| `.useProtocolCachePolicy` | Default — follows HTTP cache headers |
| `.reloadIgnoringLocalCacheData` | Always fetch from network |
| `.returnCacheDataElseLoad` | Use cache if available, else network |
| `.returnCacheDataDontLoad` | Cache only — fail if not cached |

### Network Reachability
---

Use `NWPathMonitor` (Network framework) instead of deprecated `SCNetworkReachability`:

```swift
import Network

@MainActor @Observable
class NetworkMonitor {
    var isConnected = true
    var isExpensive = false
    private let monitor = NWPathMonitor()

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.isConnected = path.status == .satisfied
                self?.isExpensive = path.isExpensive
            }
        }
        monitor.start(queue: DispatchQueue(label: "NetworkMonitor"))
    }

    deinit {
        monitor.cancel()
    }
}
```


## Alamofire — Convenience Layer

Add Alamofire when you need interceptors, automatic retry, or cleaner certificate pinning. It builds on URLSession — they coexist naturally.

### Setup

```swift
// Package.swift
.package(url: "https://github.com/Alamofire/Alamofire.git", from: "<latest-stable>")
```

### Basic Requests
---

```swift
import Alamofire

// GET with Decodable
let users: [User] = try await AF.request("https://api.example.com/users")
    .validate()  // Throws on 4xx/5xx
    .serializingDecodable([User].self)
    .value

// POST with JSON body
let newUser: User = try await AF.request(
    "https://api.example.com/users",
    method: .post,
    parameters: CreateUserRequest(name: "Alice"),
    encoder: JSONParameterEncoder.default
)
.validate()
.serializingDecodable(User.self)
.value
```

### RequestInterceptor (Token Refresh)
---

The primary reason to adopt Alamofire — automatic token injection and refresh:

```swift
class AuthInterceptor: RequestInterceptor {
    private let tokenManager: TokenManager

    init(tokenManager: TokenManager) {
        self.tokenManager = tokenManager
    }

    // Alamofire 5.10+ supports async adapt — prefer this over wrapping Task in completion handler
    func adapt(_ urlRequest: URLRequest, for session: Session) async throws -> URLRequest {
        var request = urlRequest
        let token = try await tokenManager.validToken()
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        return request
    }

    func retry(_ request: Request, for session: Session, dueTo error: Error,
               completion: @escaping (RetryResult) -> Void) {
        guard let response = request.response, response.statusCode == 401,
              request.retryCount < 1
        else {
            completion(.doNotRetry)
            return
        }

        Task {
            do {
                _ = try await tokenManager.refreshAccessToken()
                completion(.retry)
            } catch {
                completion(.doNotRetryWithError(error))
            }
        }
    }
}

// Configure session with interceptor
let session = Session(interceptor: AuthInterceptor(tokenManager: tokenManager))
```

### Automatic Retry
---

```swift
// Built-in retry policy with exponential backoff
let retryPolicy = RetryPolicy(
    retryLimit: 3,
    exponentialBackoffBase: 2,
    exponentialBackoffScale: 0.5,
    retryableHTTPMethods: [.get, .put, .delete],
    retryableHTTPStatusCodes: [408, 500, 502, 503, 504],
    retryableURLErrorCodes: [
        .timedOut, .cannotFindHost, .cannotConnectToHost,
        .networkConnectionLost, .dnsLookupFailed
    ]
)

let session = Session(interceptor: retryPolicy)
```

### Certificate Pinning
---

```swift
let evaluators: [String: ServerTrustEvaluating] = [
    "api.example.com": PinnedCertificatesTrustEvaluator(),         // Pin certificates
    "cdn.example.com": PublicKeysTrustEvaluator(),                  // Pin public keys
    "staging.example.com": DisabledTrustEvaluator(),                // Disable (dev only!)
]

let manager = ServerTrustManager(evaluators: evaluators)
let session = Session(serverTrustManager: manager)
```

### Multipart Upload
---

```swift
let response = try await AF.upload(
    multipartFormData: { formData in
        formData.append(imageData, withName: "avatar",
                        fileName: "photo.jpg", mimeType: "image/jpeg")
        formData.append("Alice".data(using: .utf8)!, withName: "name")
    },
    to: "https://api.example.com/profile"
)
.validate()
.serializingDecodable(ProfileResponse.self)
.value
```

### Download with Progress
---

```swift
let destination: DownloadRequest.Destination = { _, _ in
    let documentsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    return (documentsURL.appendingPathComponent("file.pdf"), [.removePreviousFile, .createIntermediateDirectories])
}

AF.download("https://example.com/large-file.pdf", to: destination)
    .downloadProgress { progress in
        updateProgressUI(progress.fractionCompleted)
    }
    .response { response in
        if let fileURL = response.fileURL {
            print("Downloaded to: \(fileURL)")
        }
    }
```

### Event Monitor (Logging)
---

```swift
let monitor = ClosureEventMonitor()
monitor.requestDidFinish = { request in
    print(request.cURLDescription())  // Full cURL command for debugging
}

let session = Session(eventMonitors: [monitor])
```

### Coexisting with URLSession
---

Alamofire's `Session` wraps a `URLSession`. You can use both in the same project:

```swift
// Alamofire for API calls with auth/retry
let apiSession = Session(interceptor: authInterceptor)

// URLSession for simple/background tasks
let backgroundConfig = URLSessionConfiguration.background(withIdentifier: "com.example.bg")
let backgroundSession = URLSession(configuration: backgroundConfig, delegate: self, delegateQueue: nil)
```

Common pattern: Alamofire for authenticated API layer, raw URLSession for background downloads, WebSocket, or streaming.


## Shared Patterns

### Error Types
---

```swift
enum NetworkError: LocalizedError {
    case invalidResponse
    case httpError(statusCode: Int, data: Data)
    case noConnection
    case timeout
    case decodingFailed(Error)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: "Invalid server response"
        case .httpError(let code, _): "HTTP error \(code)"
        case .noConnection: "No internet connection"
        case .timeout: "Request timed out"
        case .decodingFailed(let error): "Failed to decode response: \(error.localizedDescription)"
        }
    }

    init(urlError: URLError) {
        switch urlError.code {
        case .notConnectedToInternet, .networkConnectionLost:
            self = .noConnection
        case .timedOut:
            self = .timeout
        default:
            self = .invalidResponse
        }
    }
}
```

### JSON Decoding Configuration
---

```swift
let decoder = JSONDecoder()
decoder.keyDecodingStrategy = .convertFromSnakeCase
decoder.dateDecodingStrategy = .iso8601

// For custom date formats
decoder.dateDecodingStrategy = .custom { decoder in
    let container = try decoder.singleValueContainer()
    let string = try container.decode(String.self)
    guard let date = ISO8601DateFormatter().date(from: string) else {
        throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid date")
    }
    return date
}
```

### Pagination Pattern
---

```swift
struct PagedResponse<T: Decodable>: Decodable {
    let items: [T]
    let nextCursor: String?
    let hasMore: Bool
}

func fetchAll<T: Decodable>(endpoint: String, type: T.Type) -> AsyncStream<[T]> {
    AsyncStream { continuation in
        Task {
            var cursor: String? = nil
            repeat {
                var url = URLComponents(string: baseURL + endpoint)!
                if let cursor { url.queryItems = [URLQueryItem(name: "cursor", value: cursor)] }

                let (data, _) = try await URLSession.shared.data(from: url.url!)
                let page = try JSONDecoder().decode(PagedResponse<T>.self, from: data)
                continuation.yield(page.items)
                cursor = page.nextCursor
            } while cursor != nil

            continuation.finish()
        }
    }
}
```

### Testable Networking
---

Abstract behind a protocol for testing:

```swift
protocol HTTPClient: Sendable {
    func data(for request: URLRequest) async throws -> (Data, URLResponse)
}

// Production
extension URLSession: HTTPClient {}

// Test
final class MockHTTPClient: HTTPClient {
    var stubbedData: Data = Data()
    var stubbedStatusCode: Int = 200

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        let response = HTTPURLResponse(
            url: request.url!, statusCode: stubbedStatusCode,
            httpVersion: nil, headerFields: nil
        )!
        return (stubbedData, response)
    }
}

// API client uses protocol
final class APIService {
    private let client: HTTPClient

    init(client: HTTPClient = URLSession.shared) {
        self.client = client
    }

    func fetchUsers() async throws -> [User] {
        let request = URLRequest(url: usersURL)
        let (data, response) = try await client.data(for: request)
        // validate and decode...
    }
}
```


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Not validating HTTP status codes | URLSession doesn't throw on 4xx/5xx — always check `HTTPURLResponse.statusCode` |
| Using `URLSession.shared` for everything | Shared session has no delegate and limited configuration. Create custom sessions for auth, caching, background |
| Blocking main thread with synchronous requests | Always use `async/await` or completion handlers |
| Not handling `waitsForConnectivity` | Set `config.waitsForConnectivity = true` to avoid immediate failures on poor connectivity |
| Leaking URLSession | Sessions hold strong references to delegates. Call `finishTasksAndInvalidate()` when done |
| Ignoring App Transport Security | HTTPS is required by default. Add exceptions in Info.plist only when necessary |
| Not pausing/resuming downloads properly | Store `resumeData` from `cancel(byProducingResumeData:)`, recreate task with it |
| Background session with completion handlers | Background sessions require delegates — async/await and completion handlers don't work |
| Hardcoding base URLs | Use build configuration or Info.plist injection for environment-specific URLs |
| Not setting `Content-Type` header | POST/PUT requests without `Content-Type: application/json` may be rejected by the server |
| Certificate pinning in debug builds | Pinning breaks with Charles/Proxyman. Conditionally disable in debug |
| Ignoring `URLError.cancelled` | Cancelled tasks throw — distinguish cancellation from real errors |
