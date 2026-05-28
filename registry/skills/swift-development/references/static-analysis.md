# Static Analysis Reference (SwiftLint & SwiftFormat)

Covers SwiftLint and SwiftFormat — the two primary Swift static analysis and formatting tools. They are complementary: SwiftLint detects code smells and enforces conventions, SwiftFormat auto-fixes formatting. Use both together. Applicable to all Swift targets: Apple platforms, server-side (Vapor, Hummingbird), CLI tools, cross-platform (Linux, Windows).

## Contents
- SwiftLint (configuration, rules, custom rules, auto-correct, nested configs)
- SwiftFormat (configuration, rules, editor integration)
- Using SwiftLint + SwiftFormat together (conflict avoidance, execution order)
- CI/CD integration (GitHub Actions, pre-commit hooks)
- Common pitfalls


## SwiftLint

SwiftLint enforces Swift style and conventions via a configurable rule set. It can warn, error, and auto-correct.

### Installation

#### Homebrew

```bash
brew install swiftlint
```

#### Mint

```bash
mint install realm/SwiftLint
```

#### SPM Build Plugin (recommended for reproducibility)

```swift
// Package.swift
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/SimplyDanny/SwiftLintPlugins", from: "0.57.0"),
    ],
    targets: [
        .target(
            name: "MyApp",
            plugins: [
                .plugin(name: "SwiftLintBuildToolPlugin", package: "SwiftLintPlugins"),
            ]
        ),
    ]
)
```

For Xcode projects without SPM, add as a build tool plugin via File > Add Package Dependencies.

### Configuration (`.swiftlint.yml`)

Place `.swiftlint.yml` in the project root. A realistic production configuration:

```yaml
# .swiftlint.yml

# Only lint project sources, not dependencies or generated code
included:
  - Sources
  - Tests

excluded:
  - Sources/Generated
  - Sources/Resources
  - "**/.build"
  - "**/DerivedData"

# Disable rules that conflict with SwiftFormat or are too noisy
disabled_rules:
  - trailing_comma           # SwiftFormat handles this
  - opening_brace            # SwiftFormat handles this
  - vertical_whitespace      # SwiftFormat handles this
  - todo                     # Useful during development

# Enable recommended opt-in rules
opt_in_rules:
  - array_init
  - attributes
  - closure_body_length
  - closure_spacing
  - collection_alignment
  - comma_inheritance
  - contains_over_filter_count
  - contains_over_first_not_nil
  - contains_over_range_nil_comparison
  - convenience_type
  - discouraged_none_name
  - discouraged_object_literal
  - empty_collection_literal
  - empty_count
  - empty_string
  - enum_case_associated_values_count
  - explicit_init
  - extension_access_modifier
  - fallthrough
  - fatal_error_message
  - file_name_no_space
  - first_where
  - flatmap_over_map_reduce
  - force_unwrapping
  - identical_operands
  - implicit_return
  - joined_default_parameter
  - last_where
  - legacy_multiple
  - literal_expression_end_indentation
  - local_doc_comment
  - lower_acl_than_parent
  - modifier_order
  - multiline_arguments
  - multiline_function_chains
  - multiline_parameters
  - number_separator
  - operator_usage_whitespace
  - overridden_super_call
  - override_in_extension
  - pattern_matching_keywords
  - prefer_self_in_static_references
  - prefer_self_type_over_type_of_self
  - prefer_zero_over_explicit_init
  - private_action
  - private_outlet
  - prohibited_super_call
  - raw_value_for_camel_cased_codable_enum
  - reduce_into
  - redundant_nil_coalescing
  - redundant_type_annotation
  - return_value_from_void_function
  - sorted_first_last
  - strong_iboutlet
  - toggle_bool
  - unavailable_function
  - unneeded_parentheses_in_closure_argument
  - unowned_variable_capture
  - untyped_error_in_catch
  - vertical_parameter_alignment_on_call
  - yoda_condition

# Configurable rule thresholds
line_length:
  warning: 120
  error: 200
  ignores_comments: true
  ignores_urls: true
  ignores_interpolated_strings: true

type_body_length:
  warning: 300
  error: 500

file_length:
  warning: 500
  error: 1000
  ignore_comment_only_lines: true

function_body_length:
  warning: 50
  error: 100

function_parameter_count:
  warning: 5
  error: 8

type_name:
  min_length: 3
  max_length:
    warning: 50
    error: 60

identifier_name:
  min_length:
    warning: 2
    error: 1
  max_length:
    warning: 50
    error: 60
  excluded:
    - id
    - x
    - y
    - i
    - j
    - to

nesting:
  type_level:
    warning: 2
  function_level:
    warning: 3

large_tuple:
  warning: 3
  error: 4

cyclomatic_complexity:
  warning: 10
  error: 20

# Reporter type (xcode, json, csv, checkstyle, codeclimate, github-actions-logging)
reporter: "xcode"
```

### Key Rule Categories

#### Style Rules

Rules that enforce consistent code style (indentation, spacing, naming):

- `line_length` — maximum characters per line
- `identifier_name` — variable/function naming conventions
- `type_name` — type naming length and format
- `modifier_order` — consistent ordering of access modifiers
- `implicit_return` — single-expression returns omit `return`

#### Lint Rules

Rules that detect potential bugs or code smells:

- `force_unwrapping` — flags `!` force unwrap usage
- `force_cast` — flags `as!` force cast usage
- `force_try` — flags `try!` usage
- `unowned_variable_capture` — prefer `weak` over `unowned`
- `unused_closure_parameter` — replace unused params with `_`

#### Performance Rules

Rules that flag potentially slow patterns:

- `first_where` — use `.first(where:)` instead of `.filter().first`
- `sorted_first_last` — use `.min()`/`.max()` instead of `.sorted().first`/`.last`
- `contains_over_filter_count` — use `.contains(where:)` instead of `.filter().count > 0`
- `reduce_into` — use `reduce(into:)` for reference types
- `flatmap_over_map_reduce` — use `.flatMap()` instead of `.map().reduce([], +)`
- `empty_count` — use `.isEmpty` instead of `.count == 0`

#### Idiomatic Rules

Rules that enforce modern Swift idioms:

- `prefer_self_in_static_references` — use `Self` instead of type name in static context
- `toggle_bool` — use `.toggle()` instead of `x = !x`
- `legacy_multiple` — use `isMultiple(of:)` instead of `% 2 == 0`
- `joined_default_parameter` — use `.joined()` instead of `.joined(separator: "")`

### Disabling Rules Inline

```swift
// Disable a rule for the entire file (place at top)
// swiftlint:disable force_unwrapping

// Disable for the next line only
// swiftlint:disable:next force_cast
let view = object as! UIView

// Disable for the current line
let url = URL(string: "https://example.com")! // swiftlint:disable:this force_unwrapping

// Disable for a block
// swiftlint:disable cyclomatic_complexity
func complexLegacyFunction() {
    // ... complex logic that cannot be easily refactored
}
// swiftlint:enable cyclomatic_complexity
```

Rules:
- Prefer fixing the violation over disabling the rule.
- When disabling, always use the most narrow scope possible (`:next` > `:this` > block > file).
- Add a comment explaining why the rule is disabled for block-level disables.

### Custom Rules (Regex-Based)

Define project-specific rules directly in `.swiftlint.yml`:

```yaml
custom_rules:
  no_print_in_production:
    name: "No print() in production code"
    regex: 'print\s*\('
    match_kinds:
      - identifier
    message: "Use os_log or Logger instead of print()"
    severity: warning

  no_hardcoded_urls:
    name: "No hardcoded URLs"
    regex: 'URL\(string:\s*"https?://'
    message: "Use environment-based URL configuration instead of hardcoded URLs"
    severity: warning

  no_nslog:
    name: "No NSLog"
    regex: 'NSLog\s*\('
    message: "Use Logger (os.log) instead of NSLog"
    severity: error

  mark_format:
    name: "MARK format"
    regex: '\/\/\s*MARK:\s*[^-\s]'
    message: "Use '// MARK: - Section Name' with a dash for visual separator"
    severity: warning
```

### Auto-Correct

```bash
# Fix all auto-correctable violations
swiftlint lint --fix --config .swiftlint.yml

# Fix specific files
swiftlint lint --fix --path Sources/Models/

# Dry run — show what would be fixed without modifying
swiftlint lint --config .swiftlint.yml
```

Rules:
- Always review auto-correct changes before committing.
- Run auto-correct before linting in CI to reduce noise.
- Not all rules are auto-correctable — some require manual fixes.

### Nested Configurations

Place additional `.swiftlint.yml` files in subdirectories to override the root config:

```
MyProject/
├── .swiftlint.yml              # Root config
├── Sources/
│   └── .swiftlint.yml          # Stricter rules for production code
└── Tests/
    └── .swiftlint.yml          # Relaxed rules for test code
```

```yaml
# Tests/.swiftlint.yml — relax rules for test code
disabled_rules:
  - force_unwrapping       # Acceptable in tests
  - force_cast             # Acceptable in tests
  - function_body_length   # Test methods can be longer
  - type_body_length       # Test classes can be larger
  - file_length            # Test files can be larger
  - identifier_name        # Shorter names OK in tests

line_length:
  warning: 150
  error: 250
```

Child configs inherit from the parent and can override any setting.


## SwiftFormat

SwiftFormat reformats Swift code automatically. Where SwiftLint detects problems, SwiftFormat fixes formatting without human intervention.

### Installation

#### Homebrew

```bash
brew install swiftformat
```

#### Mint

```bash
mint install nicklockwood/SwiftFormat
```

#### SPM Build Plugin

```swift
// Package.swift
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/nicklockwood/SwiftFormat", from: "0.55.0"),
    ],
    targets: [
        .target(
            name: "MyApp",
            plugins: [
                .plugin(name: "SwiftFormatPlugin", package: "SwiftFormat"),
            ]
        ),
    ]
)
```

### Configuration (`.swiftformat`)

Place `.swiftformat` in the project root. A realistic production configuration:

```
# .swiftformat

# File options
--exclude DerivedData,**/.build,Sources/Generated

# Formatting rules
--indent 4
--indentcase false
--trimwhitespace always
--voidtype void
--wraparguments before-first
--wrapparameters before-first
--wrapcollections before-first
--wrapconditions after-first
--wrapreturntype preserve
--maxwidth 120
--closingparen balanced
--commas always
--decimalgrouping 3
--exponentcase lowercase
--extensionacl on-extension
--fractiongrouping disabled
--header ignore
--hexgrouping 4,8
--hexliteralcase uppercase
--ifdef indent
--importgrouping alpha
--nospaceoperators ..<,...
--operatorfunc spaced
--patternlet hoist
--ranges spaced
--redundanttype inferred
--self remove
--semicolons inline
--stripunusedargs closure-only
--swiftversion 6.0
--typeattributes prev-line
--varattributes same-line
--funcattributes prev-line
--storedvarattrs same-line
--computedvarattrs same-line

# Disable rules that conflict with SwiftLint or project conventions
--disable blankLinesAtStartOfScope
--disable blankLinesAtEndOfScope

# Enable additional rules
--enable isEmpty
--enable markTypes
--enable sortSwitchCases
--enable wrapMultilineStatementBraces
--enable docComments
--enable blockComments
```

### Key Formatting Rules

| Rule | What It Does |
|---|---|
| `redundantSelf` | Removes unnecessary `self.` |
| `trailingCommas` | Adds/removes trailing commas in collections |
| `unusedArguments` | Replaces unused closure args with `_` |
| `redundantReturn` | Removes `return` from single-expression functions |
| `sortImports` | Alphabetizes import statements |
| `wrapArguments` | Wraps function arguments consistently |
| `braces` | Enforces brace placement (K&R style) |
| `indent` | Normalizes indentation |
| `blankLinesBetweenScopes` | Adds blank lines between type/function declarations |
| `markTypes` | Adds `// MARK: -` comments for type extensions |
| `isEmpty` | Replaces `.count == 0` with `.isEmpty` |
| `consecutiveSpaces` | Collapses multiple spaces |

### SwiftFormat vs SwiftLint — What Each Handles Best

| Concern | SwiftFormat | SwiftLint |
|---|---|---|
| Indentation | Best — auto-fixes | Detects but limited auto-fix |
| Brace placement | Best — auto-fixes | Detects only |
| Import sorting | Best — auto-fixes | Not covered |
| Trailing commas | Best — auto-fixes | Detects only |
| Redundant code | Good — removes redundant `self`, `return` | Detects broader patterns |
| Naming conventions | Not covered | Best — configurable rules |
| Code complexity | Not covered | Best — cyclomatic complexity, body length |
| Code smells | Not covered | Best — force unwrap, force cast, etc. |
| Force unwrapping | Not covered | Best — warns/errors |
| Custom rules | Not supported | Best — regex-based custom rules |

### Editor Integration

Install the SwiftFormat for Xcode extension from the Mac App Store, or run via command palette in VS Code with the SwiftFormat extension. For Xcode:

1. Install SwiftFormat for Xcode from the App Store
2. Enable in System Settings > Privacy & Security > Extensions > Xcode Source Editor
3. Use Editor > SwiftFormat > Format File (bind to a keyboard shortcut)


## Using SwiftLint + SwiftFormat Together

The key is avoiding conflicts — disable formatting-related rules in SwiftLint and let SwiftFormat handle them.

### Recommended Setup

#### Rules to disable in SwiftLint (let SwiftFormat handle these):

```yaml
# .swiftlint.yml — disable rules that SwiftFormat handles better
disabled_rules:
  - trailing_comma
  - opening_brace
  - vertical_whitespace
  - statement_position
  - return_arrow_whitespace
  - colon
  - comma
  - leading_whitespace
  - trailing_newline
  - trailing_semicolon
  - trailing_whitespace
```

#### Rules to keep in SwiftLint (SwiftFormat cannot enforce these):

```yaml
# These stay in SwiftLint — SwiftFormat has no equivalent
# Default rules (already enabled, just ensure they are not disabled):
#   cyclomatic_complexity, function_body_length, type_body_length,
#   file_length, identifier_name, type_name
# Opt-in rules to add:
opt_in_rules:
  - force_unwrapping
  - empty_count
  - first_where
  - contains_over_filter_count
  - unowned_variable_capture
```

#### Execution order:

1. **SwiftFormat first** — auto-fix formatting
2. **SwiftLint second** — check remaining rules

In build phases, place SwiftFormat before SwiftLint. In CI, run format-check before lint.


## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/swift-quality.yml
name: Swift Code Quality

on:
  pull_request:
    branches: [main, develop]
    paths:
      - '**/*.swift'
      - '.swiftlint.yml'
      - '.swiftformat'

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint-and-format:
    name: SwiftLint & SwiftFormat
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install tools
        run: |
          brew install swiftlint swiftformat

      - name: SwiftFormat check (no modifications)
        run: |
          swiftformat --lint --config .swiftformat Sources/ Tests/

      - name: SwiftLint
        run: |
          swiftlint lint --strict --config .swiftlint.yml --reporter github-actions-logging
```

Rules:
- Use `--reporter github-actions-logging` with SwiftLint to annotate PRs inline.
- Use `swiftformat --lint` (not `swiftformat`) in CI to check without modifying files.
- Use `--strict` with SwiftLint to treat warnings as errors in CI.

### Pre-Commit Hooks

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Get staged Swift files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.swift$')

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

echo "Running SwiftFormat on staged files..."
echo "$STAGED_FILES" | xargs swiftformat --config .swiftformat

echo "Running SwiftLint on staged files..."
echo "$STAGED_FILES" | xargs swiftlint lint --strict --config .swiftlint.yml

LINT_STATUS=$?

# Re-stage formatted files
echo "$STAGED_FILES" | xargs git add

if [ $LINT_STATUS -ne 0 ]; then
    echo "SwiftLint found violations. Please fix them before committing."
    exit 1
fi

exit 0
```

Make executable: `chmod +x .git/hooks/pre-commit`

For team-wide hooks, use a shared hooks directory:

```bash
# Set hooks path for the repo
git config core.hooksPath .githooks/

# Place pre-commit in .githooks/pre-commit (committed to repo)
```


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Over-configuring linting (too many rules enabled) | Start with defaults, enable opt-in rules incrementally. If developers routinely disable rules inline, the rule is too strict |
| Inconsistent configs across modules | Use a single root `.swiftlint.yml` with nested overrides only where necessary (e.g., relaxed test rules) |
| Not auto-fixing what can be auto-fixed | Run `swiftlint lint --fix` and `swiftformat` before linting. Reduces noise and developer friction |
| Running linters before formatters | Always run SwiftFormat first, then SwiftLint. Formatting changes may resolve lint violations |
| SwiftLint and SwiftFormat conflicting on the same rules | Disable formatting rules in SwiftLint, let SwiftFormat handle them exclusively |
| Not pinning tool versions | Different SwiftLint/SwiftFormat versions may produce different results. Pin versions via SPM plugins or Mint |
| Not configuring `excluded` paths | Generated code, vendored code, and build artifacts produce irrelevant violations. Always exclude them |
