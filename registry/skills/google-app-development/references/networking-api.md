# Networking & API Layer Reference

Covers HTTP clients, JSON serialization, repository pattern for network calls, error handling, authentication, caching, pagination, and testing. For coroutines and Flow patterns used with network calls, see `concurrency.md`. For architecture and ViewModel patterns, see the main `SKILL.md`.

## Contents
- Retrofit + OkHttp — setup, API definition, interceptors, authentication
- Ktor Client — KMP-compatible alternative, setup, plugins
- JSON Serialization — Kotlin Serialization, Moshi, Gson comparison
- Repository Pattern — wrapping network calls, Result type, offline-first
- Error Handling — sealed result types, mapping HTTP errors, retry strategies
- OkHttp Interceptors — logging, auth token injection, headers
- Certificate Pinning — OkHttp CertificatePinner
- Caching — OkHttp cache, ETag/Last-Modified, offline-first with Room
- Connectivity Monitoring — ConnectivityManager, NetworkCallback, reactive status
- Pagination — custom pagination (recommended), Paging 3 (optional)
- File Upload / Download — multipart, progress tracking
- Testing — MockWebServer, fake repositories


## Retrofit + OkHttp

Retrofit is the standard HTTP client for Android. It uses OkHttp under the hood and generates API implementations from interface definitions.

### Gradle Setup

```kotlin
// libs.versions.toml
[versions]
retrofit = "<latest>"
okhttp = "<latest>"
kotlinx-serialization = "<latest>"
retrofit-kotlinx-serialization = "<latest>"

[libraries]
retrofit = { module = "com.squareup.retrofit2:retrofit", version.ref = "retrofit" }
okhttp = { module = "com.squareup.okhttp3:okhttp", version.ref = "okhttp" }
okhttp-logging = { module = "com.squareup.okhttp3:logging-interceptor", version.ref = "okhttp" }
kotlinx-serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "kotlinx-serialization" }
retrofit-kotlinx-serialization = { module = "com.jakewharton.retrofit:retrofit2-kotlinx-serialization-converter", version.ref = "retrofit-kotlinx-serialization" }
```

```kotlin
// build.gradle.kts (app module)
plugins {
    kotlin("plugin.serialization")
}

dependencies {
    implementation(libs.retrofit)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.retrofit.kotlinx.serialization)
}
```

### API Definition

```kotlin
// Define API interface — one per backend service
interface ItemApi {

    @GET("items")
    suspend fun getItems(): List<ItemDto>

    @GET("items/{id}")
    suspend fun getItem(@Path("id") id: String): ItemDto

    @POST("items")
    suspend fun createItem(@Body item: CreateItemRequest): ItemDto

    @PUT("items/{id}")
    suspend fun updateItem(
        @Path("id") id: String,
        @Body item: UpdateItemRequest,
    ): ItemDto

    @DELETE("items/{id}")
    suspend fun deleteItem(@Path("id") id: String)

    @GET("items")
    suspend fun searchItems(
        @Query("q") query: String,
        @Query("page") page: Int,
        @Query("limit") limit: Int = 20,
    ): PaginatedResponse<ItemDto>
}
```

### OkHttp & Retrofit Instance

```kotlin
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
    ): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(
            HttpLoggingInterceptor().apply {
                level = if (BuildConfig.DEBUG) {
                    HttpLoggingInterceptor.Level.BODY
                } else {
                    HttpLoggingInterceptor.Level.NONE
                }
            }
        )
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(
            Json { ignoreUnknownKeys = true }
                .asConverterFactory("application/json".toMediaType())
        )
        .build()

    @Provides
    @Singleton
    fun provideItemApi(retrofit: Retrofit): ItemApi =
        retrofit.create(ItemApi::class.java)
}
```

**Rules:**
- One `OkHttpClient` and `Retrofit` instance per app (singleton). Create separate API interfaces per backend service.
- Set `ignoreUnknownKeys = true` on `Json` to avoid crashes when the backend adds new fields.
- Use `BuildConfig` fields for base URL — never hardcode URLs.
- Logging interceptor must be `NONE` in release builds — never log request/response bodies in production.


## Ktor Client

Ktor Client is the KMP-compatible alternative. Prefer it for Kotlin Multiplatform projects or when you need WebSocket/SSE support built-in.

### Gradle Setup

```kotlin
// libs.versions.toml
[versions]
ktor = "<latest>"

[libraries]
ktor-client-core = { module = "io.ktor:ktor-client-core", version.ref = "ktor" }
ktor-client-okhttp = { module = "io.ktor:ktor-client-okhttp", version.ref = "ktor" }
ktor-client-content-negotiation = { module = "io.ktor:ktor-client-content-negotiation", version.ref = "ktor" }
ktor-serialization-json = { module = "io.ktor:ktor-serialization-kotlinx-json", version.ref = "ktor" }
ktor-client-logging = { module = "io.ktor:ktor-client-logging", version.ref = "ktor" }
ktor-client-auth = { module = "io.ktor:ktor-client-auth", version.ref = "ktor" }
```

### Client Setup

```kotlin
@Module
@InstallIn(SingletonComponent::class)
object KtorModule {

    @Provides
    @Singleton
    fun provideHttpClient(tokenProvider: TokenProvider): HttpClient = HttpClient(OkHttp) {
        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true })
        }
        install(Logging) {
            level = if (BuildConfig.DEBUG) LogLevel.BODY else LogLevel.NONE
        }
        install(Auth) {
            bearer {
                loadTokens { BearerTokens(tokenProvider.accessToken(), "") }
                refreshTokens {
                    val newToken = tokenProvider.refresh()
                    BearerTokens(newToken, "")
                }
            }
        }
        install(HttpTimeout) {
            requestTimeoutMillis = 30_000
            connectTimeoutMillis = 30_000
        }
        defaultRequest {
            url(BuildConfig.API_BASE_URL)
            contentType(ContentType.Application.Json)
        }
    }
}
```

```kotlin
// Usage in repository
class ItemRepository(private val client: HttpClient) {
    suspend fun getItems(): List<ItemDto> =
        client.get("items").body()

    suspend fun createItem(request: CreateItemRequest): ItemDto =
        client.post("items") { setBody(request) }.body()
}
```

**When to choose Ktor over Retrofit:**
- KMP shared module — Ktor is multiplatform, Retrofit is Android/JVM only.
- WebSocket or SSE — Ktor has built-in support.
- Prefer Retrofit for Android-only projects — larger ecosystem, more community examples, simpler annotation-based API.


## JSON Serialization

| Library | Pros | Cons | Use When |
|---|---|---|---|
| **Kotlin Serialization** | KMP-compatible, compile-time, no reflection | Requires compiler plugin | New projects, KMP, default choice |
| **Moshi** | Kotlin-aware, codegen or reflection | JVM only | Existing projects using Moshi |
| **Gson** | Widespread, simple | No Kotlin awareness, reflection-based, no null safety | Legacy projects only |

**Rule:** Use Kotlin Serialization for new projects. It integrates with both Retrofit (via converter) and Ktor natively.

### Kotlin Serialization Models

```kotlin
@Serializable
data class ItemDto(
    val id: String,
    val name: String,
    val description: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class PaginatedResponse<T>(
    val data: List<T>,
    val total: Int,
    val page: Int,
    @SerialName("per_page") val perPage: Int,
)

@Serializable
data class CreateItemRequest(
    val name: String,
    val description: String? = null,
)

@Serializable
data class ApiError(
    val code: String,
    val message: String,
    val details: Map<String, String>? = null,
)
```

**Rules:**
- Use `@SerialName` for snake_case backend fields — keep Kotlin properties camelCase.
- Provide defaults for optional fields (`= null`, `= emptyList()`) to handle missing keys gracefully.
- Keep DTOs separate from domain models. Map in the repository layer.


## Repository Pattern with Network Layer

```kotlin
// Domain model — clean, no serialization annotations
data class Item(
    val id: String,
    val name: String,
    val description: String?,
    val createdAt: Instant,
)

// Mapper — DTO to domain
fun ItemDto.toDomain(): Item = Item(
    id = id,
    name = name,
    description = description,
    createdAt = Instant.parse(createdAt),
)

// Repository interface
interface ItemRepository {
    suspend fun getItems(): Result<List<Item>>
    suspend fun getItem(id: String): Result<Item>
    suspend fun createItem(name: String, description: String?): Result<Item>
    suspend fun deleteItem(id: String): Result<Unit>
    fun observeItems(): Flow<List<Item>>
}

// Implementation
class DefaultItemRepository(
    private val api: ItemApi,
    private val dao: ItemDao,
) : ItemRepository {

    override suspend fun getItems(): Result<Item> = safeApiCall {
        api.getItems().map { it.toDomain() }
    }

    override suspend fun getItem(id: String): Result<Item> = safeApiCall {
        api.getItem(id).toDomain()
    }

    override suspend fun createItem(name: String, description: String?): Result<Item> =
        safeApiCall {
            api.createItem(CreateItemRequest(name, description)).toDomain()
        }

    override suspend fun deleteItem(id: String): Result<Unit> = safeApiCall {
        api.deleteItem(id)
    }

    override fun observeItems(): Flow<List<Item>> =
        dao.observeAll().map { entities -> entities.map { it.toDomain() } }
}
```

**Rules:**
- Repositories return `Result<T>` — never throw from a repository method.
- Map DTOs to domain models at the repository boundary.
- Repository is the single source of truth. ViewModels never call API interfaces directly.


## Error Handling

### Safe API Call Wrapper

```kotlin
suspend fun <T> safeApiCall(block: suspend () -> T): Result<T> = try {
    Result.success(block())
} catch (e: HttpException) {
    val errorBody = e.response()?.errorBody()?.string()
    val apiError = errorBody?.let {
        try { Json.decodeFromString<ApiError>(it) } catch (_: Exception) { null }
    }
    Result.failure(
        ApiException(
            httpCode = e.code(),
            apiError = apiError,
            cause = e,
        )
    )
} catch (e: IOException) {
    Result.failure(NetworkException(cause = e))
} catch (e: CancellationException) {
    throw e // never swallow cancellation
} catch (e: Exception) {
    Result.failure(UnexpectedException(cause = e))
}
```

### Exception Hierarchy

```kotlin
sealed class AppException(message: String, cause: Throwable?) : Exception(message, cause) {

    class NetworkException(
        cause: Throwable,
    ) : AppException("Network unavailable", cause)

    class ApiException(
        val httpCode: Int,
        val apiError: ApiError?,
        cause: Throwable,
    ) : AppException(apiError?.message ?: "HTTP $httpCode", cause)

    class UnexpectedException(
        cause: Throwable,
    ) : AppException("Unexpected error", cause)
}
```

### Mapping Errors in ViewModel

```kotlin
// In ViewModel
private fun loadItems() {
    viewModelScope.launch {
        _uiState.update { it.copy(isLoading = true, error = null) }
        repository.getItems()
            .onSuccess { items ->
                _uiState.update { it.copy(items = items, isLoading = false) }
            }
            .onFailure { error ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        error = error.toUserMessage(),
                    )
                }
            }
    }
}

// Map exceptions to user-facing messages
fun Throwable.toUserMessage(): String = when (this) {
    is AppException.NetworkException -> "No internet connection. Check your network and try again."
    is AppException.ApiException -> when (httpCode) {
        401 -> "Session expired. Please sign in again."
        403 -> "You don't have permission to perform this action."
        404 -> "The requested resource was not found."
        in 500..599 -> "Server error. Please try again later."
        else -> apiError?.message ?: "Something went wrong."
    }
    else -> "Something went wrong."
}
```

**Rules:**
- Never swallow `CancellationException` — always rethrow it.
- Parse error bodies when available — backends often return structured error responses.
- Map technical errors to user-friendly messages in the ViewModel/UI layer, not in the repository.


## OkHttp Interceptors

### Auth Token Interceptor

```kotlin
class AuthInterceptor @Inject constructor(
    private val tokenProvider: TokenProvider,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenProvider.accessToken()
        val request = if (token != null) {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}
```

### Token Refresh Authenticator

```kotlin
class TokenAuthenticator @Inject constructor(
    private val tokenProvider: TokenProvider,
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        // Avoid infinite retry loops
        if (response.request.header("X-Retry-Auth") != null) return null

        val newToken = runBlocking { tokenProvider.refresh() } ?: return null

        return response.request.newBuilder()
            .header("Authorization", "Bearer $newToken")
            .header("X-Retry-Auth", "true")
            .build()
    }
}
```

```kotlin
// Wire up in OkHttpClient
OkHttpClient.Builder()
    .addInterceptor(authInterceptor)       // add token to every request
    .authenticator(tokenAuthenticator)      // refresh on 401
    .build()
```

**Rules:**
- Use `Interceptor` for adding headers to every request. Use `Authenticator` for 401 token refresh.
- Guard against infinite retry loops in `Authenticator`.
- `runBlocking` in `Authenticator` is acceptable — OkHttp calls it from a background thread.


## Certificate Pinning

```kotlin
val client = OkHttpClient.Builder()
    .certificatePinner(
        CertificatePinner.Builder()
            .add("api.example.com", "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
            .add("api.example.com", "sha256/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=") // backup pin
            .build()
    )
    .build()
```

**Rules:**
- Always include a backup pin (different CA or next certificate in chain).
- Pin against the intermediate CA certificate, not the leaf — leaf certificates rotate frequently.
- Do not pin in debug builds — it blocks proxy tools like Charles/Proxyman.

```kotlin
// Disable pinning in debug
val builder = OkHttpClient.Builder()
if (!BuildConfig.DEBUG) {
    builder.certificatePinner(certificatePinner)
}
```


## Caching

### OkHttp HTTP Cache

```kotlin
val client = OkHttpClient.Builder()
    .cache(Cache(context.cacheDir.resolve("http_cache"), 10L * 1024 * 1024)) // 10 MB
    .build()
```

The cache respects standard HTTP headers (`Cache-Control`, `ETag`, `Last-Modified`). No additional code needed if the server sets appropriate headers.

### Offline-First with Room

```kotlin
class OfflineFirstItemRepository(
    private val api: ItemApi,
    private val dao: ItemDao,
) : ItemRepository {

    override fun observeItems(): Flow<List<Item>> =
        dao.observeAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun refresh(): Result<Unit> = safeApiCall {
        val items = api.getItems()
        dao.replaceAll(items.map { it.toEntity() })
    }

    override suspend fun getItems(): Result<List<Item>> {
        // Return cache first, then refresh in background
        val cached = dao.getAll().map { it.toDomain() }
        if (cached.isNotEmpty()) return Result.success(cached)
        // No cache — fetch from network
        return safeApiCall {
            val items = api.getItems()
            dao.replaceAll(items.map { it.toEntity() })
            items.map { it.toDomain() }
        }
    }
}
```

**Rules:**
- Use OkHttp cache for simple GET caching with proper server headers.
- Use Room (offline-first) when the app must work offline or when data is displayed in lists/feeds.
- Room is the single source of truth — network updates go through Room, UI observes Room.


## Connectivity Monitoring

```kotlin
class ConnectivityObserver @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    val isOnline: StateFlow<Boolean> = callbackFlow {
        val manager = context.getSystemService<ConnectivityManager>()!!
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { trySend(true) }
            override fun onLost(network: Network) { trySend(false) }
        }
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        manager.registerNetworkCallback(request, callback)

        // Initial state
        val current = manager.activeNetwork?.let {
            manager.getNetworkCapabilities(it)
                ?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        } ?: false
        trySend(current)

        awaitClose { manager.unregisterNetworkCallback(callback) }
    }.stateIn(CoroutineScope(Dispatchers.Default), SharingStarted.WhileSubscribed(5000), false)
}
```

```kotlin
// Usage in ViewModel
class HomeViewModel @Inject constructor(
    private val repository: ItemRepository,
    private val connectivity: ConnectivityObserver,
) : ViewModel() {

    val isOffline: StateFlow<Boolean> = connectivity.isOnline
        .map { !it }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), false)
}
```

**Rule:** Use `ConnectivityManager.NetworkCallback` — do not poll or use deprecated `NetworkInfo`. Expose connectivity as a `StateFlow` for reactive UI updates.


## Pagination

### Custom Pagination (Recommended)
---

For most use cases, a simple custom pagination approach is easier to implement, debug, and customize than Paging 3. The ViewModel tracks page state and loading, while the UI triggers load-more on scroll.

#### Repository

```kotlin
class ItemRepository @Inject constructor(
    private val api: ItemApi,
) {
    suspend fun getItems(page: Int, pageSize: Int): Result<List<Item>> = runCatching {
        api.getItems(page = page, limit = pageSize).data.map { it.toDomain() }
    }
}
```

#### ViewModel

```kotlin
data class ItemListUiState(
    val items: List<Item> = emptyList(),
    val isLoading: Boolean = false,
    val isLoadingMore: Boolean = false,
    val hasMore: Boolean = true,
    val error: String? = null,
)

@HiltViewModel
class ItemListViewModel @Inject constructor(
    private val repository: ItemRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ItemListUiState())
    val uiState: StateFlow<ItemListUiState> = _uiState.asStateFlow()

    private var currentPage = 1
    private val pageSize = 20

    init { loadItems() }

    fun loadItems() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            currentPage = 1
            repository.getItems(page = currentPage, pageSize = pageSize)
                .onSuccess { items ->
                    _uiState.update {
                        it.copy(
                            items = items,
                            isLoading = false,
                            hasMore = items.size >= pageSize,
                        )
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoading = false, error = e.message) }
                }
        }
    }

    fun loadMore() {
        if (_uiState.value.isLoadingMore || !_uiState.value.hasMore) return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingMore = true) }
            val nextPage = currentPage + 1
            repository.getItems(page = nextPage, pageSize = pageSize)
                .onSuccess { items ->
                    currentPage = nextPage
                    _uiState.update {
                        it.copy(
                            items = it.items + items,
                            isLoadingMore = false,
                            hasMore = items.size >= pageSize,
                        )
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoadingMore = false, error = e.message) }
                }
        }
    }
}
```

#### Compose UI

```kotlin
@Composable
fun ItemListScreen(viewModel: ItemListViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LazyColumn {
        items(uiState.items, key = { it.id }) { item ->
            ItemCard(item)
        }

        // Trigger load-more when approaching the end
        item {
            if (uiState.hasMore && !uiState.isLoadingMore) {
                LaunchedEffect(Unit) { viewModel.loadMore() }
            }
            if (uiState.isLoadingMore) {
                LoadingIndicator()
            }
        }
    }
}
```

### Paging 3 (Optional)
---

Paging 3 (`androidx.paging`) is available but notoriously difficult to work with — prefer the custom approach above for most use cases. Paging 3 may be worth considering when you need efficient pagination over a large local Room database, as Room's built-in `PagingSource` integration handles incremental loading well.

```kotlin
// Gradle
implementation("androidx.paging:paging-runtime:<latest>")
implementation("androidx.paging:paging-compose:<latest>")

// PagingSource for network-only
class ItemPagingSource(
    private val api: ItemApi,
    private val query: String,
) : PagingSource<Int, Item>() {
    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, Item> = try {
        val page = params.key ?: 1
        val response = api.searchItems(query = query, page = page, limit = params.loadSize)
        LoadResult.Page(
            data = response.data.map { it.toDomain() },
            prevKey = if (page == 1) null else page - 1,
            nextKey = if (response.data.size < params.loadSize) null else page + 1,
        )
    } catch (e: Exception) {
        LoadResult.Error(e)
    }

    override fun getRefreshKey(state: PagingState<Int, Item>): Int? =
        state.anchorPosition?.let { state.closestPageToPosition(it)?.prevKey?.plus(1) }
}

// ViewModel: always cachedIn(viewModelScope) to survive configuration changes
val items: Flow<PagingData<Item>> = Pager(PagingConfig(pageSize = 20)) {
    ItemPagingSource(api, query)
}.flow.cachedIn(viewModelScope)

// Compose: collectAsLazyPagingItems()
val items = viewModel.items.collectAsLazyPagingItems()
```


## File Upload / Download

### Multipart Upload (Retrofit)

```kotlin
interface FileApi {
    @Multipart
    @POST("upload")
    suspend fun upload(
        @Part file: MultipartBody.Part,
        @Part("description") description: RequestBody,
    ): UploadResponse
}

// Usage
suspend fun uploadFile(uri: Uri, context: Context) {
    val stream = context.contentResolver.openInputStream(uri)!!
    val body = stream.readBytes().toRequestBody("image/*".toMediaType())
    val part = MultipartBody.Part.createFormData("file", "photo.jpg", body)
    api.upload(part, "Profile photo".toRequestBody())
}
```

### Download with Progress

```kotlin
suspend fun downloadFile(url: String, output: File): Flow<DownloadProgress> = callbackFlow {
    val request = Request.Builder().url(url).build()
    val response = okHttpClient.newCall(request).execute()
    val body = response.body ?: throw IOException("Empty body")
    val totalBytes = body.contentLength()

    body.byteStream().use { input ->
        output.outputStream().use { out ->
            val buffer = ByteArray(8192)
            var bytesRead: Long = 0
            var read: Int
            while (input.read(buffer).also { read = it } != -1) {
                out.write(buffer, 0, read)
                bytesRead += read
                trySend(DownloadProgress(bytesRead, totalBytes))
            }
        }
    }
    close()
}

data class DownloadProgress(val bytesDownloaded: Long, val totalBytes: Long) {
    val fraction: Float get() = if (totalBytes > 0) bytesDownloaded.toFloat() / totalBytes else 0f
}
```


## Testing

### MockWebServer (Retrofit / OkHttp)

```kotlin
class ItemApiTest {

    private val mockWebServer = MockWebServer()
    private lateinit var api: ItemApi

    @Before
    fun setup() {
        mockWebServer.start()
        val retrofit = Retrofit.Builder()
            .baseUrl(mockWebServer.url("/"))
            .addConverterFactory(Json.asConverterFactory("application/json".toMediaType()))
            .build()
        api = retrofit.create(ItemApi::class.java)
    }

    @After
    fun tearDown() { mockWebServer.shutdown() }

    @Test
    fun `getItems returns parsed list`() = runTest {
        mockWebServer.enqueue(
            MockResponse()
                .setBody("""[{"id":"1","name":"Test","created_at":"2024-01-01T00:00:00Z","updated_at":"2024-01-01T00:00:00Z"}]""")
                .setHeader("Content-Type", "application/json")
        )

        val items = api.getItems()

        assertEquals(1, items.size)
        assertEquals("Test", items[0].name)

        val request = mockWebServer.takeRequest()
        assertEquals("GET", request.method)
        assertEquals("/items", request.path)
    }

    @Test
    fun `getItems throws on server error`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(500))

        assertFailsWith<HttpException> { api.getItems() }
    }
}
```

### Fake Repository for ViewModel Tests

```kotlin
class FakeItemRepository : ItemRepository {
    private val items = MutableStateFlow<List<Item>>(emptyList())
    var shouldFail = false

    override suspend fun getItems(): Result<List<Item>> =
        if (shouldFail) Result.failure(AppException.NetworkException(IOException()))
        else Result.success(items.value)

    override fun observeItems(): Flow<List<Item>> = items

    fun emit(list: List<Item>) { items.value = list }
}
```

**Rules:**
- Use `MockWebServer` to test API interface definitions and serialization.
- Use fake repositories to test ViewModels — no network dependency in ViewModel tests.
- Test error paths: server errors, network failures, malformed responses.
