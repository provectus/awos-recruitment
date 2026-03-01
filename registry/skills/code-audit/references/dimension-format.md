# How to Write a Dimension

A dimension is a single `.md` file dropped into the `dimensions/` folder. It is automatically discovered on the next audit run.

## File Structure

```markdown
---
name: my-dimension
title: My Dimension
description: What this dimension measures
severity: high
depends-on: [project-topology]
---

# My Dimension

Brief description of what this dimension audits and why it matters.

## Checks

### CHECK-01: Short name for the check

- **What:** What to verify
- **How:** Glob/Grep/Read commands or agent instructions to evaluate this check
- **Pass:** Criteria for PASS status
- **Fail:** Criteria for FAIL status
- **Warn:** (optional) Criteria for WARN status — partial compliance
- **Skip-When:** (optional) Condition under which this check is automatically skipped (e.g., "topology artifact shows no backend layer")
- **Severity:** critical | high | medium | low

### CHECK-02: Another check

…
```

## Frontmatter Fields

| Field          | Required | Type    | Description |
|----------------|----------|---------|-------------|
| `name`         | yes      | string  | Unique identifier, used for CLI filtering (e.g., `/code-audit my-dimension`) |
| `title`        | yes      | string  | Human-readable display name |
| `description`  | yes      | string  | One-line purpose of this dimension |
| `severity`     | yes      | string  | Default severity for all checks: `critical`, `high`, `medium`, or `low`. Individual checks can override. |
| `depends-on`   | no       | list of strings | Dimension `name`s that must complete before this one starts. The engine uses this to build a DAG — dimensions whose dependencies are all satisfied run in parallel. If absent, the dimension has no dependencies and can run immediately. |

## Check Fields

| Field        | Required | Description |
|--------------|----------|-------------|
| **What**     | yes      | Plain-English description of what is being verified |
| **How**      | yes      | Concrete instructions — tool calls, file patterns, or agent tasks |
| **Pass**     | yes      | What constitutes a passing result |
| **Fail**     | yes      | What constitutes a failing result |
| **Warn**     | no       | What constitutes a warning (partial compliance) |
| **Skip-When**| no       | Condition that causes this check to auto-SKIP (read from a prior dimension's artifact) |
| **Severity** | no       | Override dimension-level severity for this specific check |

## Artifacts

Each dimension writes its results to an artifact file during execution:

```
context/audits/YYYY-MM-DD/{name}.md
```

Example: the `project-topology` dimension writes to `context/audits/2026-03-01/project-topology.md`.

Dimensions with satisfied `depends-on` can read earlier artifacts. For instance, the documentation dimension reads the topology artifact to know which service READMEs to expect.

### Artifact Content

An artifact file contains:
1. The dimension's check results table
2. A structured summary section specific to the dimension (e.g., `## Topology Summary` for project-topology)

The engine passes the artifact directory path (`context/audits/YYYY-MM-DD/`) to each dimension so it can read prior artifacts and write its own.

## Tips

- Keep checks atomic — one thing per check
- Write **How** as if instructing an agent that has no project context
- Use Glob patterns and Grep regex in **How** so checks are reproducible
- Prefer concrete thresholds over subjective judgments (e.g., "at least 1 file exists" vs. "documentation looks good")
- Use **Skip-When** to gracefully handle checks that depend on project topology (e.g., "no frontend detected" → skip frontend-specific checks)
- Use `depends-on` to declare which dimensions must finish first — the engine parallelizes everything else

## Example

```markdown
---
name: testing
title: Test Coverage
description: Verifies test infrastructure and coverage thresholds
severity: high
depends-on: [project-topology]
---

# Test Coverage

Checks that the project has testing infrastructure and adequate coverage.

## Checks

### TEST-01: Test runner configured

- **What:** A test runner is configured and runnable
- **How:** Check for test scripts in package.json (`pnpm test` or `npm test`) or build.gradle.kts (test task)
- **Pass:** Test command exists and can be invoked
- **Fail:** No test command found
- **Severity:** critical

### TEST-02: Tests exist

- **What:** The project contains test files
- **How:** Glob for `**/*.test.{ts,tsx,js,jsx}` or `**/*Test.kt`
- **Pass:** At least 10 test files found
- **Warn:** 1–9 test files found
- **Fail:** No test files found
- **Skip-When:** Topology artifact shows no backend or frontend layers
```
