---
name: pytest-best-practices
description: >-
  Pytest conventions for Python test suites — fixtures and scopes, parametrization,
  mocking with pytest-mock, built-in fixtures (`tmp_path`, `monkeypatch`, `capsys`,
  `caplog`), markers, exception testing, and async tests. Use when writing, reviewing,
  or refactoring Python tests, `conftest.py` fixtures, or pytest configuration in
  `pytest.ini` / `pyproject.toml`. Does not cover general Python syntax or typing — see
  modern-python-development — nor FastAPI `TestClient` and app-level test setup — see
  fastapi-best-practices.
---

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

**Directory Structure**
```
tests/
├── conftest.py          # Shared fixtures
├── unit/
│   └── test_module.py
├── integration/
│   └── test_api.py
└── fixtures/            # Test data files
```

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

**Built-in fixtures** — reach for these before writing your own; pytest already
isolates and reverts them per test.

| Fixture | Use Case |
|---------|----------|
| `tmp_path` | Per-test temporary directory (`pathlib.Path`) |
| `monkeypatch` | Env vars, attributes, `sys.path`, cwd — auto-reverted |
| `capsys` | Assert on captured stdout/stderr |
| `caplog` | Assert on captured log records |

**Common Commands**
```bash
pytest -v                    # Verbose
pytest -x                    # Stop on first failure
pytest --lf                  # Run last failed
pytest -k "pattern"          # Match test names
pytest -m "marker"           # Run marked tests
pytest --cov=src             # Coverage report
pytest -n auto               # Parallel across CPU cores (pytest-xdist)
```

</quick_reference>

<routing>

Based on what you're doing, read the relevant reference:

| Task | Reference |
|------|-----------|
| Setting up fixtures, scopes, factories, built-in fixtures | `references/fixtures.md` |
| Parametrizing tests, multiple inputs | `references/parametrization.md` |
| Mocking, patching, faking dependencies | `references/mocking.md` |
| Markers, exceptions, assertions, async | `references/patterns.md` |

</routing>

<dependencies>
```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov pytest-xdist
```
</dependencies>
