# Localization

Best practices for localizing user-facing text in Apple platform apps.

## Core Rules

When writing or modifying user-facing text:

- Never use explicit string literals for user-facing text (e.g., `"Welcome back"`, `Text("Sign in")`).
- Always use whichever localization solution is already in use in the project (e.g., String Catalogs, `.strings` files, a custom localization layer). Do not migrate to a different solution unless explicitly asked.
- Apply this to all user-visible surfaces: labels, buttons, alerts, placeholders, accessibility labels, and error messages.
- When you encounter an existing explicit string that should be localized, flag it and suggest the appropriate key name and parameter names, but do not migrate it unless asked.

## String Catalogs (.xcstrings)

If the project uses String Catalogs with code generation, reference the generated Swift accessor. `Localizable` is the default table name and must be omitted — do not write `.Localizable.keyName`. Only include a table name prefix when the string belongs to a non-default, custom table (e.g., `.Settings.keyName` for `Settings.xcstrings`).

### Code Generation Accessors

Xcode generates type-safe accessors automatically from String Catalog entries:

```swift
// Default table (Localizable.xcstrings) — no prefix
String(localized: .welcomeMessage(name: user.name))
String(localized: .itemCount(count: items.count))
String(localized: .lastUpdated(date: formattedDate))

// Custom tables — use table name as namespace prefix
String(localized: .Settings.sectionTitle)                  // Settings.xcstrings
String(localized: .Accessibility.itemDescription(name: …)) // Accessibility.xcstrings
```

### Named Parameter Format

When a string has interpolated values, use the named argument format `%<index>$(<name>)<type>` directly in the string value (e.g., `%1$(name)@`, `%2$(count)d`). Name each parameter to reflect its role in the string — not generic names like `param1` or `value`.

Always include the positional index, even for strings with a single parameter. This ensures consistency and avoids ambiguity when translators reorder parameters.

**Single parameter:**

```
"Hello, %1$(name)@!"
"You have %1$(count)lld unread messages."
"Last updated on %1$(date)@."
```

**Multiple parameters:**

```
"Hello, %1$(name)@! You have %2$(count)lld new notifications."
"Showing %1$(current)lld of %2$(total)lld results."
"Transfer %1$(amount)@ from %2$(source)@ to %3$(destination)@."
```

### Parameter Naming Guidelines

| Pattern | Example | Avoid |
|---|---|---|
| Descriptive role-based names | `%1$(name)@`, `%2$(count)d` | `%1$(param1)@`, `%2$(value)d` |
| Match the Swift accessor parameter name | `%1$(name)@` → `.welcomeMessage(name:)` | `%1$(str)@` |
| Use the domain term | `%1$(minLength)lld` for character limits | `%1$(num)lld` |

## Localization APIs

### String(localized:) API (iOS 15+)

`String(localized:)` is the modern replacement for `NSLocalizedString`. It provides compile-time safety and cleaner syntax for runtime string resolution.

Key parameters: `table:` (which `.xcstrings` file; defaults to `Localizable`), `bundle:` (defaults to `.main`; use `.module` for packages), `defaultValue:` (fallback and source-language value), `comment:` (context for translators, visible in `.xcloc` exports).

```swift
// Basic lookup from Localizable.xcstrings
let welcome = String(localized: "welcome_message",
                     defaultValue: "Welcome back, \(name)")

// Lookup from a custom table
let settings = String(localized: "tab_settings",
                      table: "Settings",
                      comment: "Settings tab title")

// Lookup from a framework bundle
let label = String(localized: "premium_badge",
                   bundle: .module,
                   comment: "Badge shown on premium content")
```

In SwiftUI, `Text` and `Label` accept `LocalizedStringKey` directly, so string literals inside these views are automatically localized against the default table without calling `String(localized:)`.

### Pluralization and Device Variations

String Catalogs natively handle **plural rules** and **device variations**, replacing the legacy `.stringsdict` XML format entirely.

**Plural categories** (per CLDR): `zero`, `one`, `two`, `few`, `many`, `other`. Not every language uses every category — String Catalogs only show categories relevant to each target locale.

To define a plural string, create a key in the String Catalog and set its type to **Plural** in the Xcode editor. Each category then gets its own translation. In code, pass an integer using the `%lld` format specifier:

```swift
// String Catalog key: "unread_count"
// English variations:
//   one  → "%lld unread message"
//   other → "%lld unread messages"

let label = String(localized: "unread_count \(unreadCount)")
```

With code-generated accessors:

```swift
String(localized: .unreadCount(count: unreadCount))
```

**Device variations** allow a single key to resolve differently on iPhone, iPad, Mac, Apple Watch, and Apple TV. Set the variation type to **Device** in the String Catalog editor. This is useful for platform-appropriate terminology (e.g., "tap" vs. "click", "screen" vs. "window").

A key can combine both plural and device variations — Xcode's editor shows a matrix of device × plural category.

### LocalizedStringResource (iOS 16+)

`LocalizedStringResource` stores a reference to a localized string **without resolving it immediately**. Resolution happens when the string is displayed. Essential for:

- **App Intents / Shortcuts** — intent parameter summaries and display names require `LocalizedStringResource`.
- **Widgets** — timeline entries that may render in different locales.
- **SwiftUI modifiers** that accept deferred localization.

```swift
// Creating a resource
let title = LocalizedStringResource("settings_title",
                                    table: "Settings",
                                    comment: "Navigation title for settings screen")

// Resolving later
let resolved = String(localized: title)

// In App Intents
struct OpenSettings: AppIntent {
    static var title: LocalizedStringResource = "open_settings_title"
}
```

`LocalizedStringResource` also supports `defaultValue:` and `bundle:` parameters, matching the `String(localized:)` API.

### Translator Comments

Comments give translators context about where and how a string appears. This reduces translation errors and avoids ambiguity (e.g., "Post" as a noun vs. a verb).

**Adding comments:**

1. **In code** — Use the `comment:` parameter on `String(localized:)` or `LocalizedStringResource`:

```swift
String(localized: "post_action",
       comment: "Verb — button that publishes a new post")
```

2. **In Xcode's String Catalog editor** — Select a key and fill in the Comment field in the inspector panel. This is visible in exported `.xcloc` files.

3. **In SwiftUI views** — `Text` accepts a `comment:` parameter:

```swift
Text("delete_confirmation",
     comment: "Alert title when user deletes an item")
```

**Best practices:**

- Describe the UI context: what element the string appears in, what action it triggers.
- Clarify ambiguous words (noun vs. verb, formal vs. informal).
- Mention character constraints if the string must fit a narrow layout.
- Comments with visual context (screenshots via `.xcloc`) significantly reduce translation errors.

### Migration from .strings / .stringsdict

Xcode provides a built-in migration path to String Catalogs:

1. In the Project Navigator, right-click an existing `.strings` or `.stringsdict` file.
2. Select **Migrate to String Catalog**.
3. Xcode creates a new `.xcstrings` file, merges all existing translations and plural rules, and removes the old files.

Migration preserves all keys, values, comments, and plural variations. If both `.strings` and `.stringsdict` exist for the same table, Xcode merges them into one `.xcstrings` file. After migration, build and check for "missing key" warnings. String Catalogs require **Xcode 15+** — defer migration if older Xcode versions are needed for CI.

### Testing Localization

**Pseudo-languages** (Edit Scheme → Run → Options → App Language):

- **Double-Length** — doubles strings to test truncation and overflow.
- **Right-to-Left** — mirrors UI for RTL layout validation.
- **Accented** — replaces ASCII with accented variants to verify encoding.
- **Bounded String** — wraps strings in brackets to spot unlocalized text.

**Export / Import `.xcloc` for translators:**

```
Product → Export Localizations…
```

This generates `.xcloc` bundles per locale with all strings, screenshots, and comments. Translators edit in Xcode or any XLIFF-compatible tool. Import back:

```
Product → Import Localizations…
```

**Runtime locale override** — add launch arguments in the scheme to force a locale without changing device settings:

```
-AppleLanguages (ja)
-AppleLocale ja_JP
```

**Automated checks** — use `xcodebuild -exportLocalizations` in CI to verify translations exist for required locales. Enable the **Missing Localizability** static analyzer (`CLANG_ANALYZER_LOCALIZABILITY_NONLOCALIZED`) to catch hardcoded strings at build time.
