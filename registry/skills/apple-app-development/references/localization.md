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
