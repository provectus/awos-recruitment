# Local Storage Reference

Covers Room database, DataStore (Preferences and Proto), encrypted storage, file storage, and storage selection guidance. For network caching and offline-first repository pattern, see `networking-api.md`. For coroutines and Flow patterns used with storage, see `concurrency.md`. For multi-module setup of `:core:database`, see `project-structure.md`.

## Contents
- Room — setup, entities, DAOs, database, type converters, relations, migrations, testing
- DataStore — Preferences DataStore, Proto DataStore, migration from SharedPreferences
- Encrypted Storage — EncryptedSharedPreferences, encrypted Room, encrypted DataStore
- File Storage — internal storage, external storage, scoped storage, FileProvider
- Storage Selection Guide — decision table for choosing the right storage mechanism


## Room

Room is the recommended persistence library for structured data. It provides compile-time verification of SQL queries and seamless integration with Kotlin coroutines and Flow.

### Gradle Setup

```kotlin
// libs.versions.toml
[versions]
room = "<latest>"

[libraries]
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }
room-testing = { module = "androidx.room:room-testing", version.ref = "room" }
room-paging = { module = "androidx.room:room-paging", version.ref = "room" }

[plugins]
room = { id = "androidx.room", version.ref = "room" }
```

> **Note:** `androidx.room:room-ktx` was merged into `room-runtime` as of Room 2.7.0. Remove it from dependencies if present.

```kotlin
// build.gradle.kts (database module)
plugins {
    id("com.google.devtools.ksp")
    alias(libs.plugins.room)
}

room {
    schemaDirectory("$projectDir/schemas") // required for migration testing
}

dependencies {
    implementation(libs.room.runtime) // includes former room-ktx APIs
    ksp(libs.room.compiler)
    testImplementation(libs.room.testing)
    // Optional: Room + Paging 3 integration
    implementation(libs.room.paging)
}
```

### Entity Definition

```kotlin
@Entity(
    tableName = "items",
    indices = [
        Index(value = ["category"]),
        Index(value = ["title"], unique = true),
    ],
)
data class ItemEntity(
    @PrimaryKey
    val id: String,
    val title: String,
    val description: String?,
    val category: String,
    @ColumnInfo(name = "created_at")
    val createdAt: Long,
    @ColumnInfo(name = "is_favorite", defaultValue = "0")
    val isFavorite: Boolean = false,
)
```

**Rules:**
- Use `@PrimaryKey` with `String` (UUID) or `Long` (`autoGenerate = true`).
- Use `@ColumnInfo(name = "...")` when the column name differs from the property name. Prefer `snake_case` for column names.
- Use `@Ignore` for properties that should not be persisted.
- Keep entities as plain data holders — no business logic.

### DAO (Data Access Object)

```kotlin
@Dao
interface ItemDao {

    // Observe — returns Flow for reactive updates
    @Query("SELECT * FROM items ORDER BY created_at DESC")
    fun observeAll(): Flow<List<ItemEntity>>

    @Query("SELECT * FROM items WHERE id = :id")
    fun observeById(id: String): Flow<ItemEntity?>

    // Query — suspend for one-shot reads
    @Query("SELECT * FROM items WHERE id = :id")
    suspend fun getById(id: String): ItemEntity?

    @Query("SELECT * FROM items WHERE category = :category ORDER BY title ASC")
    suspend fun getByCategory(category: String): List<ItemEntity>

    @Query("SELECT COUNT(*) FROM items")
    suspend fun count(): Int

    // Write operations
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(item: ItemEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<ItemEntity>)

    @Update
    suspend fun update(item: ItemEntity)

    @Delete
    suspend fun delete(item: ItemEntity)

    @Query("DELETE FROM items WHERE id = :id")
    suspend fun deleteById(id: String)

    @Query("DELETE FROM items")
    suspend fun deleteAll()

    // Transaction — atomic multi-table operations
    @Transaction
    suspend fun replaceAll(items: List<ItemEntity>) {
        deleteAll()
        upsertAll(items)
    }
}
```

**Rules:**
- Use `Flow<T>` return type for reactive queries — Room re-emits on table changes automatically.
- Use `suspend` for one-shot queries and write operations.
- Use `@Transaction` for operations that must be atomic or for queries returning relations.
- Prefer `OnConflictStrategy.REPLACE` for network-synced data (upsert pattern).
- DAO methods should operate on entities, not domain models — mapping happens in the repository.

### Database

```kotlin
@Database(
    entities = [
        ItemEntity::class,
        CategoryEntity::class,
    ],
    version = 1,
    exportSchema = true, // always true — needed for migration testing
)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun itemDao(): ItemDao
    abstract fun categoryDao(): CategoryDao
}
```

```kotlin
// DI module (Hilt)
@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase =
        Room.databaseBuilder(context, AppDatabase::class.java, "app.db")
            .fallbackToDestructiveMigration() // only in dev — use migrations in production
            .build()

    @Provides
    fun provideItemDao(db: AppDatabase): ItemDao = db.itemDao()
}
```

**Rules:**
- Always set `exportSchema = true` — Room exports the schema to JSON, needed for migration testing.
- One `RoomDatabase` subclass per app, provided as `@Singleton`.
- Never call `Room.databaseBuilder` outside of DI — always inject the database or DAOs.
- Use `fallbackToDestructiveMigration()` only during development. Production apps must provide proper migrations.

### Type Converters

```kotlin
class Converters {

    @TypeConverter
    fun fromInstant(value: Instant?): Long? = value?.toEpochMilli()

    @TypeConverter
    fun toInstant(value: Long?): Instant? = value?.let { Instant.ofEpochMilli(it) }

    @TypeConverter
    fun fromStringList(value: List<String>): String = Json.encodeToString(value)

    @TypeConverter
    fun toStringList(value: String): List<String> = Json.decodeFromString(value)
}
```

**Rules:**
- Register converters via `@TypeConverters` on the database class.
- Prefer simple types (Long for timestamps, String for serialized lists) — avoid storing complex objects as JSON blobs unless necessary.
- For enum types, convert to/from `String` (name) rather than `Int` (ordinal) to survive reordering.

### Relations (Embedded & Relations)

```kotlin
// One-to-many: Item has many Tags
@Entity(
    tableName = "tags",
    foreignKeys = [
        ForeignKey(
            entity = ItemEntity::class,
            parentColumns = ["id"],
            childColumns = ["item_id"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index("item_id")],
)
data class TagEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "item_id") val itemId: String,
    val label: String,
)

// Relation query result (not an @Entity)
data class ItemWithTags(
    @Embedded val item: ItemEntity,
    @Relation(
        parentColumn = "id",
        entityColumn = "item_id",
    )
    val tags: List<TagEntity>,
)

// DAO
@Dao
interface ItemDao {
    @Transaction
    @Query("SELECT * FROM items WHERE id = :id")
    suspend fun getItemWithTags(id: String): ItemWithTags?

    @Transaction
    @Query("SELECT * FROM items")
    fun observeItemsWithTags(): Flow<List<ItemWithTags>>
}
```

**Rules:**
- Always annotate relation queries with `@Transaction` — Room executes multiple queries under the hood.
- Always add an index on the foreign key column — Room warns if missing.
- Use `@Embedded` for flattening a nested object into the same table.
- Use `@Relation` for querying across tables. The result class is not an `@Entity`.
- Prefer `ForeignKey.CASCADE` for dependent data; use `ForeignKey.SET_NULL` when the child can exist independently.

### Migrations

```kotlin
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE items ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
    }
}

val MIGRATION_2_3 = object : Migration(2, 3) {
    override fun migrate(db: SupportSQLiteDatabase) {
        // Create new table, copy data, drop old, rename — for column type changes
        db.execSQL("""
            CREATE TABLE items_new (
                id TEXT NOT NULL PRIMARY KEY,
                title TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.execSQL("INSERT INTO items_new (id, title, priority) SELECT id, title, priority FROM items")
        db.execSQL("DROP TABLE items")
        db.execSQL("ALTER TABLE items_new RENAME TO items")
    }
}

// Register migrations
Room.databaseBuilder(context, AppDatabase::class.java, "app.db")
    .addMigrations(MIGRATION_1_2, MIGRATION_2_3)
    .build()
```

**Auto-migrations (Room 2.4+):**

```kotlin
@Database(
    entities = [ItemEntity::class],
    version = 3,
    autoMigrations = [
        AutoMigration(from = 1, to = 2),
        AutoMigration(from = 2, to = 3, spec = Migration2To3::class),
    ],
    exportSchema = true,
)
abstract class AppDatabase : RoomDatabase() { ... }

// Spec needed only when Room can't infer the change (rename, delete)
@RenameColumn(tableName = "items", fromColumnName = "name", toColumnName = "title")
class Migration2To3 : AutoMigrationSpec
```

**Rules:**
- Prefer auto-migrations for simple schema changes (add column, add table, add index).
- Use manual migrations for complex changes (column type change, data transformation, table merge).
- Always test migrations with `MigrationTestHelper`.
- Never use `fallbackToDestructiveMigration()` in production — users lose data.
- Bump the database `version` for every schema change.

### Migration Testing

```kotlin
@RunWith(AndroidJUnit4::class)
class MigrationTest {

    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        AppDatabase::class.java,
    )

    @Test
    fun migrate1To2() {
        // Create database at version 1
        helper.createDatabase("app.db", 1).apply {
            execSQL("INSERT INTO items (id, title, category, created_at) VALUES ('1', 'Test', 'A', 0)")
            close()
        }

        // Run migration and validate
        val db = helper.runMigrationsAndValidate("app.db", 2, true, MIGRATION_1_2)
        val cursor = db.query("SELECT priority FROM items WHERE id = '1'")
        cursor.moveToFirst()
        assertEquals(0, cursor.getInt(0)) // default value
        cursor.close()
    }
}
```

### Room with Paging 3

```kotlin
// DAO returns PagingSource — Room generates it
@Dao
interface ItemDao {
    @Query("SELECT * FROM items ORDER BY created_at DESC")
    fun pagingSource(): PagingSource<Int, ItemEntity>
}

// ViewModel
class ItemListViewModel(
    private val dao: ItemDao,
) : ViewModel() {
    val pager = Pager(
        config = PagingConfig(pageSize = 20, prefetchDistance = 5),
        pagingSourceFactory = { dao.pagingSource() },
    ).flow.cachedIn(viewModelScope)
}

// Composable
@Composable
fun ItemListScreen(viewModel: ItemListViewModel = viewModel()) {
    val items = viewModel.pager.collectAsLazyPagingItems()
    LazyColumn {
        items(items.itemCount) { index ->
            items[index]?.let { ItemRow(it) }
        }
    }
}
```

For network + Room pagination with `RemoteMediator`, see `networking-api.md`.

### Room Testing (Unit Tests with In-Memory Database)

```kotlin
@RunWith(AndroidJUnit4::class)
class ItemDaoTest {

    private lateinit var db: AppDatabase
    private lateinit var dao: ItemDao

    @Before
    fun setup() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            AppDatabase::class.java,
        ).allowMainThreadQueries().build()
        dao = db.itemDao()
    }

    @After
    fun teardown() {
        db.close()
    }

    @Test
    fun insertAndRetrieve() = runTest {
        val item = ItemEntity(id = "1", title = "Test", description = null, category = "A", createdAt = 0L)
        dao.upsert(item)
        val result = dao.getById("1")
        assertEquals(item, result)
    }

    @Test
    fun observeEmitsOnChange() = runTest {
        val items = dao.observeAll().take(2).toList()
        dao.upsert(ItemEntity(id = "1", title = "Test", description = null, category = "A", createdAt = 0L))
        assertEquals(0, items[0].size)
        assertEquals(1, items[1].size)
    }
}
```


## DataStore

DataStore is the modern replacement for SharedPreferences. It provides asynchronous, transactional, and type-safe key-value or typed-object storage backed by Kotlin coroutines and Flow.

### Preferences DataStore

For simple key-value pairs (settings, flags, tokens).

```kotlin
// libs.versions.toml
[versions]
datastore = "<latest>"

[libraries]
datastore-preferences = { module = "androidx.datastore:datastore-preferences", version.ref = "datastore" }
```

```kotlin
// Define DataStore instance — top-level, one per file
private val Context.settingsDataStore by preferencesDataStore(name = "settings")

// Define keys
object SettingsKeys {
    val DARK_MODE = booleanPreferencesKey("dark_mode")
    val LANGUAGE = stringPreferencesKey("language")
    val FONT_SIZE = intPreferencesKey("font_size")
    val ONBOARDING_COMPLETED = booleanPreferencesKey("onboarding_completed")
}
```

```kotlin
// Repository wrapping DataStore
class SettingsRepository @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val dataStore = context.settingsDataStore

    // Read — Flow of typed values
    val isDarkMode: Flow<Boolean> = dataStore.data
        .catch { e ->
            if (e is IOException) emit(emptyPreferences()) else throw e
        }
        .map { prefs -> prefs[SettingsKeys.DARK_MODE] ?: false }

    val settings: Flow<UserSettings> = dataStore.data
        .catch { e ->
            if (e is IOException) emit(emptyPreferences()) else throw e
        }
        .map { prefs ->
            UserSettings(
                isDarkMode = prefs[SettingsKeys.DARK_MODE] ?: false,
                language = prefs[SettingsKeys.LANGUAGE] ?: "en",
                fontSize = prefs[SettingsKeys.FONT_SIZE] ?: 14,
            )
        }

    // Write — transactional
    suspend fun setDarkMode(enabled: Boolean) {
        dataStore.edit { prefs ->
            prefs[SettingsKeys.DARK_MODE] = enabled
        }
    }

    suspend fun clearAll() {
        dataStore.edit { it.clear() }
    }
}
```

**Rules:**
- Create the `DataStore<Preferences>` instance only once — use the `by preferencesDataStore()` delegate at top level.
- Always handle `IOException` in `.catch` — DataStore can fail on disk I/O.
- Read via `.data` Flow, write via `.edit` — both are async, never block the main thread.
- Do not use SharedPreferences and DataStore for the same file — they will conflict.

### Proto DataStore

For structured, typed data with schema evolution. Uses Protocol Buffers.

```kotlin
// libs.versions.toml
[versions]
datastore = "<latest>"
protobuf = "<latest>"

[libraries]
datastore = { module = "androidx.datastore:datastore", version.ref = "datastore" }
protobuf-javalite = { module = "com.google.protobuf:protobuf-javalite", version.ref = "protobuf" }
```

```protobuf
// user_preferences.proto
syntax = "proto3";
option java_package = "com.example.app.datastore";
option java_multiple_files = true;

message UserPreferences {
  bool dark_mode = 1;
  string language = 2;
  int32 font_size = 3;
  enum Theme {
    SYSTEM = 0;
    LIGHT = 1;
    DARK = 2;
  }
  Theme theme = 4;
}
```

```kotlin
object UserPreferencesSerializer : Serializer<UserPreferences> {
    override val defaultValue: UserPreferences = UserPreferences.getDefaultInstance()

    override suspend fun readFrom(input: InputStream): UserPreferences =
        try {
            UserPreferences.parseFrom(input)
        } catch (e: InvalidProtocolBufferException) {
            throw CorruptionException("Cannot read proto", e)
        }

    override suspend fun writeTo(t: UserPreferences, output: OutputStream) {
        t.writeTo(output)
    }
}

private val Context.userPrefsDataStore by dataStore(
    fileName = "user_preferences.pb",
    serializer = UserPreferencesSerializer,
)
```

```kotlin
class UserPreferencesRepository @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val dataStore = context.userPrefsDataStore

    val preferences: Flow<UserPreferences> = dataStore.data
        .catch { e ->
            if (e is IOException) emit(UserPreferences.getDefaultInstance()) else throw e
        }

    suspend fun setTheme(theme: UserPreferences.Theme) {
        dataStore.updateData { current ->
            current.toBuilder().setTheme(theme).build()
        }
    }
}
```

**When to use Proto over Preferences:**
- Data has nested structure or lists.
- You need schema evolution guarantees (protobuf field numbering).
- Type safety is critical (enum fields, required fields).

### Migrating from SharedPreferences

```kotlin
private val Context.settingsDataStore by preferencesDataStore(
    name = "settings",
    produceMigrations = { context ->
        listOf(SharedPreferencesMigration(context, "legacy_prefs"))
    },
)
```

The migration runs once — it reads all values from the SharedPreferences file, writes them to DataStore, and deletes the SharedPreferences file. Key names are preserved.


## Encrypted Storage

### Sensitive Key-Value Data

> **`EncryptedSharedPreferences` (`androidx.security:security-crypto`) is deprecated** as of 1.1.0. Google recommends using Android Keystore directly or encrypted DataStore.

**Option 1: Android Keystore directly** — for storing a small number of secrets (tokens, API keys). Encrypt/decrypt values with a Keystore-backed key and store the ciphertext in Preferences DataStore or any other storage.

```kotlin
object KeystoreEncryptor {

    private const val KEY_ALIAS = "app_secret_key"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        keyStore.getEntry(KEY_ALIAS, null)?.let {
            return (it as KeyStore.SecretKeyEntry).secretKey
        }
        val spec = KeyGenParameterSpec.Builder(KEY_ALIAS, PURPOSE_ENCRYPT or PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .build()
        return KeyGenerator.getInstance("AES", "AndroidKeyStore")
            .apply { init(spec) }
            .generateKey()
    }

    fun encrypt(plaintext: ByteArray): ByteArray {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(plaintext)
        return iv + ciphertext // prepend IV for decryption
    }

    fun decrypt(data: ByteArray): ByteArray {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        val iv = data.copyOfRange(0, 12) // GCM IV is 12 bytes
        val ciphertext = data.copyOfRange(12, data.size)
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
        return cipher.doFinal(ciphertext)
    }
}
```

**Option 2: Encrypted DataStore with Tink** — for encrypted key-value or proto storage using `datastore-tink`.

```kotlin
// libs.versions.toml
[versions]
datastore = "<latest>"
tink = "<latest>"

[libraries]
datastore-preferences = { module = "androidx.datastore:datastore-preferences", version.ref = "datastore" }
datastore-tink = { module = "androidx.datastore:datastore-tink", version.ref = "datastore" }
tink-android = { module = "com.google.crypto.tink:tink-android", version.ref = "tink" }
```

**Rules:**
- For new code, use Android Keystore + DataStore or DataStore with Tink encryption — not `EncryptedSharedPreferences`.
- Requires `minSdk 23` (Android 6.0) for Android Keystore.
- Existing code using `EncryptedSharedPreferences` still works but should be migrated when practical.

### Database Encryption

**Device-level encryption (recommended for most apps):** Android 7.0+ (API 24) enables file-based encryption (FBE) by default when the user sets a lock screen. Room databases stored in internal storage are encrypted at rest by the OS — no extra library needed. This satisfies most security requirements.

**When app-level database encryption is still needed:**
- Regulatory/compliance mandates encryption independent of device state (HIPAA, PCI-DSS).
- Data must remain encrypted even when the device is unlocked.
- App runs on devices without guaranteed FBE (custom ROMs, old OEM builds).

**App-level encryption with SQLCipher for Android:**

The legacy `net.zetetic:android-database-sqlcipher` is deprecated. Its replacement is `net.zetetic:sqlcipher-android` — open-source, API 23+, and integrates with Room via `SupportOpenHelperFactory`.

```kotlin
// libs.versions.toml
[versions]
sqlcipher = "<latest>"

[libraries]
sqlcipher-android = { module = "net.zetetic:sqlcipher-android", version.ref = "sqlcipher" }
```

```kotlin
// Room integration
@Provides
@Singleton
fun provideDatabase(
    @ApplicationContext context: Context,
    passphraseProvider: PassphraseProvider,
): AppDatabase {
    System.loadLibrary("sqlcipher")
    val passphrase = passphraseProvider.getPassphrase().toByteArray()
    val factory = SupportOpenHelperFactory(passphrase)
    return Room.databaseBuilder(context, AppDatabase::class.java, "app_encrypted.db")
        .openHelperFactory(factory)
        .build()
}
```

**Rules:**
- For most apps, device encryption + EncryptedSharedPreferences for tokens is sufficient.
- Use `net.zetetic:sqlcipher-android` when compliance requires app-level DB encryption (HIPAA, PCI-DSS) or data must stay encrypted even while the device is unlocked.
- Store the passphrase in Android Keystore — never hardcode.
- Adds ~2-3 MB to APK size (native libraries for armeabi-v7a, arm64-v8a, x86, x86_64).


## File Storage

### Internal Storage

Private to the app, automatically deleted on uninstall.

```kotlin
// Write file
suspend fun saveFile(context: Context, filename: String, content: String) {
    withContext(Dispatchers.IO) {
        context.openFileOutput(filename, Context.MODE_PRIVATE).bufferedWriter().use { writer ->
            writer.write(content)
        }
    }
}

// Read file
suspend fun readFile(context: Context, filename: String): String? {
    return withContext(Dispatchers.IO) {
        try {
            context.openFileInput(filename).bufferedReader().use { it.readText() }
        } catch (e: FileNotFoundException) {
            null
        }
    }
}

// Cache directory — system may delete when space is low
val cacheFile = File(context.cacheDir, "temp_data.json")
```

### External / Shared Storage (Scoped Storage)

Since Android 10 (API 29), apps use scoped storage — no broad file system access.

```kotlin
// Save image to MediaStore (shared gallery)
suspend fun saveImageToGallery(context: Context, bitmap: Bitmap, displayName: String): Uri? {
    return withContext(Dispatchers.IO) {
        val contentValues = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, displayName)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/AppName")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
        }

        val uri = context.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, contentValues)
        uri?.let {
            context.contentResolver.openOutputStream(it)?.use { stream ->
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                contentValues.clear()
                contentValues.put(MediaStore.Images.Media.IS_PENDING, 0)
                context.contentResolver.update(it, contentValues, null, null)
            }
        }
        uri
    }
}

// Open a document via SAF (Storage Access Framework)
val openDocumentLauncher = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
    uri?.let { readDocument(it) }
}
openDocumentLauncher.launch(arrayOf("application/pdf"))
```

### FileProvider (Sharing Files with Other Apps)

```xml
<!-- AndroidManifest.xml -->
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data
        android:name="android.support.FILE_PROVIDER_PATHS"
        android:resource="@xml/file_paths" />
</provider>
```

```xml
<!-- res/xml/file_paths.xml -->
<paths>
    <cache-path name="cache" path="shared/" />
    <files-path name="files" path="exports/" />
</paths>
```

```kotlin
fun shareFile(context: Context, file: File) {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "application/pdf"
        putExtra(Intent.EXTRA_STREAM, uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, "Share via"))
}
```


## Storage Selection Guide

| Need | Solution | Why |
|---|---|---|
| Structured relational data | **Room** | SQL queries, relations, migrations, Flow integration |
| Simple key-value settings | **Preferences DataStore** | Async, type-safe, coroutine-based |
| Typed structured config | **Proto DataStore** | Schema evolution, nested types, enums |
| Sensitive tokens/keys | **Android Keystore + DataStore** | Keystore-backed encryption, async, type-safe |
| Sensitive structured data | **Room + device encryption** | FBE on API 24+; app-level encryption if compliance requires |
| User-facing files (images, docs) | **MediaStore / SAF** | Scoped storage, system gallery/picker |
| App-private temp files | **Internal storage / cache** | Auto-deleted on uninstall, no permissions needed |
| Sharing files with other apps | **FileProvider** | Secure content URI, granular permissions |
| Legacy key-value (existing code) | **SharedPreferences** | Migrate to DataStore for new code |

**Decision flow:**
1. Is it structured/relational? → **Room**
2. Is it a small set of key-value settings? → **Preferences DataStore**
3. Is it sensitive? → Add encryption layer (Android Keystore + DataStore, or SQLCipher for full DB)
4. Is it a file the user should access? → **MediaStore / SAF**
5. Is it a temporary cache? → **Internal cache directory**
