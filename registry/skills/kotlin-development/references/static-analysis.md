# Static Analysis Reference

Covers Detekt and ktlint — the two primary Kotlin static analysis tools. For Android-specific lint checks (Android Lint / `com.android.tools.lint`), see the `google-app-development` skill's `references/code-quality.md`.

## Contents
- Detekt — setup, configuration, rule sets, custom rules, suppression, baseline, type resolution, Compose rules, CI
- ktlint — setup, `.editorconfig` configuration, standard/experimental rules, custom rules, format vs check, CI
- Detekt vs ktlint — when to use which, overlap and complementary areas
- Shared Configuration — multi-module setup, convention plugins, pre-commit hooks
- Best Practices — incremental adoption, baseline-driven migration, severity tuning


## Detekt

Detekt is a static analysis tool for Kotlin that finds code smells, complexity issues, and style violations. It supports type resolution for deeper analysis and is extensible with custom rules.

### Gradle Setup

```kotlin
// libs.versions.toml
[versions]
detekt = "<latest>"

[plugins]
detekt = { id = "io.gitlab.arturbosch.detekt", version.ref = "detekt" }
```

```kotlin
// build.gradle.kts (root)
plugins {
    alias(libs.plugins.detekt) apply false
}
```

```kotlin
// build.gradle.kts (module)
plugins {
    alias(libs.plugins.detekt)
}

detekt {
    config.setFrom("$rootDir/config/detekt/detekt.yml")
    buildUponDefaultConfig = true // use default rules, override in config
    parallel = true
    autoCorrect = true // requires formatting plugin for auto-fix
}

// Type resolution (recommended — enables deeper checks)
dependencies {
    detektPlugins("io.gitlab.arturbosch.detekt:detekt-formatting:<latest>")
}
```

### Running Detekt

```bash
# Run detekt
./gradlew detekt

# Run with type resolution (recommended)
./gradlew detektMain detektTest

# Auto-correct formatting issues
./gradlew detekt --auto-correct
```

### Configuration (detekt.yml)

```yaml
# config/detekt/detekt.yml
build:
  maxIssues: 0 # fail on any issue

complexity:
  LongMethod:
    active: true
    threshold: 60
  LongParameterList:
    active: true
    functionThreshold: 6
    constructorThreshold: 8
    ignoreAnnotated: ['Composable'] # Composables often have many params
  CyclomaticComplexMethod:
    active: true
    threshold: 15
  TooManyFunctions:
    active: true
    thresholdInFiles: 20
    thresholdInClasses: 15

coroutines:
  GlobalCoroutineUsage:
    active: true
  RedundantSuspendModifier:
    active: true
  SuspendFunWithCoroutineScopeReceiver:
    active: true

empty-blocks:
  EmptyCatchBlock:
    active: true
    allowedExceptionNameRegex: '_|ignored|expected'
  EmptyFunctionBlock:
    active: true
    ignoreOverridden: true

exceptions:
  TooGenericExceptionCaught:
    active: true
    exceptionNames:
      - Exception
      - RuntimeException
      - Throwable
  SwallowedException:
    active: true

naming:
  FunctionNaming:
    active: true
    functionPattern: '[a-z][a-zA-Z0-9]*'
    ignoreAnnotated: ['Composable'] # Composables are PascalCase
  TopLevelPropertyNaming:
    active: true
    constantPattern: '[A-Z][A-Za-z0-9_]*'
  VariableNaming:
    active: true
    variablePattern: '[a-z][a-zA-Z0-9]*'

performance:
  SpreadOperator:
    active: true
  UnnecessaryTemporaryInstantiation:
    active: true

potential-bugs:
  DoubleMutabilityForCollection:
    active: true
  EqualsAlwaysReturnsTrueOrFalse:
    active: true
  UnreachableCatchBlock:
    active: true

style:
  MagicNumber:
    active: true
    ignoreNumbers: ['-1', '0', '1', '2']
    ignoreHashCodeFunction: true
    ignorePropertyDeclaration: true
    ignoreAnnotation: true
    ignoreEnums: true
  MaxLineLength:
    active: true
    maxLineLength: 120
  ReturnCount:
    active: true
    max: 3
    excludeGuardClauses: true
  WildcardImport:
    active: true
    excludeImports: ['java.util.*', 'kotlinx.coroutines.*']
  UnusedPrivateMember:
    active: true
    allowedNames: '_|ignored'
```

### Rule Set Categories

| Category | Focus | Example rules |
|---|---|---|
| `complexity` | Code complexity | `LongMethod`, `CyclomaticComplexMethod`, `LongParameterList` |
| `coroutines` | Coroutine misuse | `GlobalCoroutineUsage`, `RedundantSuspendModifier` |
| `empty-blocks` | Empty code blocks | `EmptyCatchBlock`, `EmptyFunctionBlock` |
| `exceptions` | Exception handling | `TooGenericExceptionCaught`, `SwallowedException` |
| `naming` | Naming conventions | `FunctionNaming`, `VariableNaming`, `ClassNaming` |
| `performance` | Performance issues | `SpreadOperator`, `ArrayPrimitive` |
| `potential-bugs` | Likely bugs | `DoubleMutabilityForCollection`, `EqualsAlwaysReturnsTrueOrFalse` |
| `style` | Code style | `MagicNumber`, `MaxLineLength`, `WildcardImport` |

### Suppression

```kotlin
// Suppress specific rule
@Suppress("MagicNumber")
fun calculateTax(amount: Double): Double = amount * 0.21

// Suppress at file level
@file:Suppress("TooManyFunctions")
package com.example.utils

// Suppress multiple
@Suppress("LongParameterList", "LongMethod")
fun complexSetup(/* ... */) { /* ... */ }
```

### Baseline

```kotlin
// build.gradle.kts
detekt {
    baseline = file("detekt-baseline.xml")
}
```

```bash
# Generate baseline capturing all current issues
./gradlew detektBaseline

# Now ./gradlew detekt only reports NEW issues
```

### Custom Rules

```kotlin
// custom-rules/src/main/kotlin/NoHardcodedUrlRule.kt
class NoHardcodedUrlRule(config: Config) : Rule(config) {

    override val issue = Issue(
        id = "HardcodedUrl",
        severity = Severity.Warning,
        description = "Avoid hardcoded URLs — use BuildConfig or configuration.",
        debt = Debt.FIVE_MINS,
    )

    override fun visitStringTemplateExpression(expression: KtStringTemplateExpression) {
        val text = expression.text
        if (text.contains("http://") || text.contains("https://")) {
            report(CodeSmell(issue, Entity.from(expression), "Hardcoded URL found: $text"))
        }
    }
}

class CustomRuleSetProvider : RuleSetProvider {
    override val ruleSetId: String = "custom-rules"
    override fun instance(config: Config): RuleSet = RuleSet(
        ruleSetId,
        listOf(NoHardcodedUrlRule(config)),
    )
}
```

Register via `META-INF/services/io.gitlab.arturbosch.detekt.api.RuleSetProvider`:
```
com.example.rules.CustomRuleSetProvider
```

### Compose Rules (detekt-compose)

Third-party rule set for Compose-specific patterns:

```kotlin
// build.gradle.kts
dependencies {
    detektPlugins("io.nlopez.compose.rules:detekt:<latest>")
}
```

Key rules:
| Rule | Description |
|---|---|
| `ComposableParametersOrdering` | Modifier should be first optional parameter |
| `MutableStateParam` | Don't pass `MutableState` as parameter — hoist state |
| `ViewModelForwarding` | Don't forward ViewModel to child Composables |
| `ViewModelInjection` | Only inject ViewModel at screen-level Composable |
| `UnstableCollections` | Flag `List`, `Set`, `Map` params (use `ImmutableList`, `PersistentList`) |
| `ModifierMissing` | Top-level Composable should accept `Modifier` parameter |


## ktlint

ktlint is an opinionated Kotlin code formatter and linter. It enforces the Kotlin coding conventions and Android Kotlin style guide with minimal configuration.

### Gradle Setup (ktlint-gradle plugin)

```kotlin
// libs.versions.toml
[versions]
ktlint-gradle = "<latest>"

[plugins]
ktlint = { id = "org.jlleitschuh.gradle.ktlint", version.ref = "ktlint-gradle" }
```

```kotlin
// build.gradle.kts (root)
plugins {
    alias(libs.plugins.ktlint) apply false
}

// Apply to all subprojects
subprojects {
    apply(plugin = "org.jlleitschuh.gradle.ktlint")

    configure<org.jlleitschuh.gradle.ktlint.KtlintExtension> {
        version.set("<latest>")
        android.set(true) // Android Kotlin style guide
        verbose.set(true)
        outputToConsole.set(true)
    }
}
```

### Alternative: Spotless

```kotlin
// build.gradle.kts (root)
plugins {
    id("com.diffplug.spotless") version "<latest>"
}

spotless {
    kotlin {
        target("**/*.kt")
        targetExclude("**/build/**")
        ktlint("<latest>")
            .editorConfigOverride(
                mapOf(
                    "max_line_length" to "120",
                    "ktlint_function_naming_ignore_when_annotated_with" to "Composable",
                )
            )
    }
    kotlinGradle {
        target("**/*.kts")
        ktlint("<latest>")
    }
}
```

### Running ktlint

```bash
# Check formatting
./gradlew ktlintCheck

# Auto-fix formatting
./gradlew ktlintFormat

# With Spotless
./gradlew spotlessCheck
./gradlew spotlessApply
```

### .editorconfig Configuration

ktlint reads `.editorconfig` for configuration. Place at project root:

```ini
# .editorconfig
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 4
insert_final_newline = true
trim_trailing_whitespace = true
max_line_length = 120

[*.{kt,kts}]
# ktlint specific
ktlint_code_style = android_studio

# Disable specific rules
ktlint_standard_no-wildcard-imports = disabled
ktlint_standard_package-name = disabled

# Compose: allow PascalCase functions
ktlint_function_naming_ignore_when_annotated_with = Composable

# Multiline: trailing comma
ktlint_standard_trailing-comma-on-call-site = enabled
ktlint_standard_trailing-comma-on-declaration-site = enabled
```

### Standard Rules (Subset)

| Rule | Description |
|---|---|
| `indentation` | Consistent indentation (spaces) |
| `no-wildcard-imports` | No `import x.*` |
| `no-unused-imports` | Remove unused imports |
| `no-trailing-spaces` | No trailing whitespace |
| `no-empty-first-line-in-class-body` | No blank line after class opening brace |
| `trailing-comma-on-call-site` | Trailing comma on multi-line call sites |
| `trailing-comma-on-declaration-site` | Trailing comma on multi-line declarations |
| `parameter-list-wrapping` | Consistent parameter wrapping |
| `argument-list-wrapping` | Consistent argument wrapping |
| `max-line-length` | Line length limit |
| `function-naming` | Function naming conventions |


## Detekt vs ktlint

| Aspect | Detekt | ktlint |
|---|---|---|
| **Primary focus** | Code smells, complexity, bugs | Code formatting, style |
| **Configuration** | Extensive (`detekt.yml`) | Minimal (`.editorconfig`) |
| **Auto-fix** | Limited (formatting plugin) | Strong (most rules fixable) |
| **Type resolution** | Yes (deeper analysis) | No (syntax-level only) |
| **Custom rules** | Full AST access | Simpler rule API |
| **Compose support** | Via `detekt-compose` plugin | Built-in Compose awareness |
| **Speed** | Slower (full analysis) | Faster (formatting only) |

### Recommendation

Use **both** together:
- **ktlint** — formatting, import ordering, indentation, trailing commas (auto-fixable)
- **Detekt** — complexity, naming (beyond formatting), coroutine misuse, potential bugs, custom rules

Disable formatting-overlap rules in Detekt when using ktlint:

```yaml
# detekt.yml — disable rules that ktlint handles
style:
  MaxLineLength:
    active: false # ktlint handles this
  WildcardImport:
    active: false # ktlint handles this
```


## Shared Configuration

### Multi-module Convention Plugin

```kotlin
// build-logic/convention/src/main/kotlin/KotlinStaticAnalysisConventionPlugin.kt
class KotlinStaticAnalysisConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("io.gitlab.arturbosch.detekt")
            pluginManager.apply("org.jlleitschuh.gradle.ktlint")

            extensions.configure<io.gitlab.arturbosch.detekt.extensions.DetektExtension> {
                config.setFrom("$rootDir/config/detekt/detekt.yml")
                buildUponDefaultConfig = true
                parallel = true
                autoCorrect = true
                baseline = file("detekt-baseline.xml")
            }

            extensions.configure<org.jlleitschuh.gradle.ktlint.KtlintExtension> {
                version.set("<latest>")
                android.set(true)
                verbose.set(true)
            }
        }
    }
}
```

```kotlin
// feature/build.gradle.kts
plugins {
    id("myapp.kotlin.static-analysis")
}
```

### Pre-commit Hook

```bash
#!/bin/sh
# .git/hooks/pre-commit

# Run ktlint on staged Kotlin files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.kts\?$')

if [ -n "$STAGED_FILES" ]; then
    echo "Running ktlint on staged files..."
    ./gradlew ktlintCheck --daemon 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "ktlint failed. Run './gradlew ktlintFormat' to fix."
        exit 1
    fi
fi
```

Or use a Git hook manager like `pre-commit`:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ktlint-format
        name: ktlint format
        entry: ./gradlew ktlintFormat
        language: system
        types: [kotlin]
        pass_filenames: false
      - id: detekt
        name: detekt
        entry: ./gradlew detekt
        language: system
        types: [kotlin]
        pass_filenames: false
```


## Best Practices

- **Adopt incrementally.** Start with baseline, enforce on new code. Shrink baseline over time. Trying to fix all issues at once creates merge conflicts and review fatigue.
- **Run in CI, not just locally.** `./gradlew detekt ktlintCheck` as a required check on PRs. Local runs are for fast feedback; CI is the gate.
- **Auto-fix what you can.** Use `ktlintFormat` and Detekt's `--auto-correct` in local workflow. Reserve manual fixes for semantic issues that tools can't auto-fix.
- **Tune severity, don't disable.** Downgrade noisy rules to `warning` before disabling. This keeps them visible without blocking builds. Disable only after team consensus.
- **Keep config in version control.** `detekt.yml`, `.editorconfig`, baselines — all committed. Configuration drift across developer machines causes inconsistent results.
- **Review baseline periodically.** Schedule quarterly baseline regeneration. Track issue count trends as a health metric.
- **Compose-aware config.** Always set `ignoreAnnotated: ['Composable']` for `FunctionNaming` and `LongParameterList` in Detekt. Configure `ktlint_function_naming_ignore_when_annotated_with = Composable` in `.editorconfig`.
- **Separate formatting from analysis.** ktlint for formatting (fast, auto-fixable), Detekt for deeper analysis. Don't overlap rules between them.
