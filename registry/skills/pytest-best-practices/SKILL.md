---
name: pytest-best-practices
description: >-
  Use when writing or reviewing pytest tests — setting up fixtures,
  parametrizing, mocking dependencies, using markers, testing exceptions or
  async code, or configuring pytest via pytest.ini or pyproject.toml. Triggers
  include conftest.py and fixture-scope questions, flaky or order-dependent
  tests, and coverage setup.
version: 0.2.0
---

<objective>
Provide pytest best practices and patterns for writing maintainable, efficient tests.
</objective>

<essential_principles>

**Test Independence**
- Each test must run in isolation - no shared state between tests
- Use fixtures for setup/teardown, never class-level mutable state
- Tests should pass regardless of execution order

**Naming Conventions**
- Files: `test_*.py` or `*_test.py`
- Functions: `test_<description>()`
- Classes: `Test<ClassName>`
- Fixtures: descriptive `lowercase_with_underscores`

**Test Placement**
Where test files and directories live is owned by the project's structure conventions (architecture or project-layout skills, existing repo layout) — not by this skill. pytest discovers `test_*.py` files and `conftest.py` fixtures along the path from rootdir regardless of layout.

**Core Testing Rules**
- Use plain `assert` statements (pytest provides detailed failure messages)
- One logical assertion per test when practical
- Test edge cases: empty inputs, boundaries, invalid data, errors
- Keep tests focused and readable

</essential_principles>

<quick_reference>

| Pattern | Use Case |
|---------|----------|
| `@pytest.fixture` | Setup/teardown, dependency injection |
| `@pytest.mark.parametrize` | Run test with multiple inputs |
| `@pytest.mark.skip` | Skip test temporarily |
| `@pytest.mark.xfail` | Expected failure (known bug) |
| `pytest.raises(Exception)` | Test exception raising |
| `pytest.approx(value)` | Float comparison |
| `mocker.patch()` | Mock dependencies |
| `conftest.py` | Share fixtures across modules |

**Common Commands**
```bash
pytest -v                    # Verbose
pytest -x                    # Stop on first failure
pytest --lf                  # Run last failed
pytest -k "pattern"          # Match test names
pytest -m "marker"           # Run marked tests
pytest --cov=src             # Coverage report
```

</quick_reference>

<routing>

Based on what you're doing, read the relevant reference:

| Task | Reference |
|------|-----------|
| Setting up fixtures, scopes, factories | `references/fixtures.md` |
| Parametrizing tests, multiple inputs | `references/parametrization.md` |
| Mocking, patching, faking dependencies | `references/mocking.md` |
| Markers, exceptions, assertions, async | `references/patterns.md` |

</routing>

<dependencies>
```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov pytest-xdist
```
</dependencies>
