# Pytest Best Practices

Expert guidance for writing high-quality pytest tests — covering fixtures, parametrization, mocking, and common patterns for maintainable test suites.

> This skill is based on the [pytest-best-practices](https://github.com/cfircoo/claude-code-toolkit/tree/main/skills/pytest-best-practices) skill originally created by [cfircoo](https://github.com/cfircoo). Big thanks to the authors for the foundational work.

## Install

```bash
npx @provectusinc/awos-recruitment skill pytest-best-practices
```

## Scope

The skill covers:

- Test independence and isolation principles
- Naming conventions and directory structure
- Fixtures: scopes, factories, teardown, `conftest.py`
- Parametrization: basic, IDs, stacking, indirect, edge cases
- Mocking: patching, side effects, async mocks, spies, assertions
- Markers, exception testing, assertions, async testing
- Configuration (`pytest.ini` / `pyproject.toml`)

## Usage

Once installed, the skill activates automatically when Claude Code detects pytest-related tasks — writing tests, setting up fixtures, parametrizing, mocking dependencies, or reviewing test code.

Reference files are organized by topic in `references/`:

```
references/fixtures.md
references/parametrization.md
references/mocking.md
references/patterns.md
```

## Reference Topics

| Topic | File | Covers |
|-------|------|--------|
| Fixtures | `references/fixtures.md` | Scopes, factories, teardown, conftest, dependencies |
| Parametrization | `references/parametrization.md` | Basic, IDs, stacking, indirect, edge cases, conditionals |
| Mocking | `references/mocking.md` | Patching, side effects, async, properties, env vars, spies |
| Patterns | `references/patterns.md` | Markers, exceptions, assertions, async testing, configuration |
