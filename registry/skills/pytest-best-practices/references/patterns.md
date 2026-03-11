# Patterns Reference

<markers>

**Built-in markers:**

```python
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
def test_new_syntax():
    pass

@pytest.mark.xfail(reason="Known bug, ticket #123")
def test_known_bug():
    assert buggy_function() == expected

@pytest.mark.slow
def test_slow_operation():
    time.sleep(10)
```

**Custom markers in pytest.ini:**

```ini
[pytest]
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    smoke: marks tests for smoke testing
```

**Running with markers:**

```bash
pytest -m slow              # Run only slow tests
pytest -m "not slow"        # Skip slow tests
pytest -m "integration or smoke"  # Run either
```

</markers>

<exception_testing>

**Basic exception testing:**

```python
def test_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
```

**Check exception message:**

```python
def test_exception_message():
    with pytest.raises(ValueError) as exc_info:
        validate_age(-1)
    assert "must be positive" in str(exc_info.value)
```

**Match with regex:**

```python
def test_exception_with_match():
    with pytest.raises(ValueError, match=r"invalid .* format"):
        parse_date("not-a-date")
```

**Check exception attributes:**

```python
def test_exception_attributes():
    with pytest.raises(CustomError) as exc_info:
        risky_operation()
    assert exc_info.value.error_code == 500
```

</exception_testing>

<assertions>

**Plain asserts (preferred):**

```python
def test_user():
    user = get_user(1)
    assert user is not None
    assert user.name == "Alice"
    assert user.age >= 18
    assert "admin" in user.roles
```

**Approximate comparisons (floats):**

```python
def test_floating_point():
    result = calculate_pi()
    assert result == pytest.approx(3.14159, rel=1e-5)

def test_list_approx():
    result = [0.1 + 0.2, 0.3]
    assert result == pytest.approx([0.3, 0.3])
```

**Collection assertions:**

```python
def test_collections():
    result = get_items()

    assert len(result) == 3
    assert "apple" in result
    assert set(result) == {"apple", "banana", "cherry"}
    assert result == ["apple", "banana", "cherry"]  # Order matters
```

</assertions>

<async_testing>

**Basic async test:**

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result == expected
```

**Async fixtures:**

```python
@pytest.fixture
async def async_client():
    client = await create_async_client()
    yield client
    await client.close()

@pytest.mark.asyncio
async def test_with_async_fixture(async_client):
    response = await async_client.get("/api/data")
    assert response.status == 200
```

**Configure in pyproject.toml:**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Auto-detect async tests
```

</async_testing>

<test_independence>

**BAD - tests depend on each other:**

```python
class TestUserBad:
    user = None

    def test_create_user(self):
        TestUserBad.user = create_user("test")
        assert TestUserBad.user.id is not None

    def test_get_user(self):
        # Fails if test_create_user didn't run first!
        user = get_user(TestUserBad.user.id)
        assert user.name == "test"
```

**GOOD - each test is independent:**

```python
class TestUserGood:
    @pytest.fixture
    def user(self):
        return create_user("test")

    def test_create_user(self, user):
        assert user.id is not None

    def test_get_user(self, user):
        fetched = get_user(user.id)
        assert fetched.name == "test"
```

</test_independence>

<global_state>

**BAD - modifies global state:**

```python
def test_set_config():
    global_config["debug"] = True
    assert app.debug_mode() == True
    # Other tests may fail!
```

**GOOD - fixture manages state:**

```python
@pytest.fixture(autouse=True)
def reset_config():
    original = global_config.copy()
    yield
    global_config.clear()
    global_config.update(original)
```

</global_state>

<pytest_ini>

**Standard pytest.ini:**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
python_classes = Test*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
markers =
    slow: marks tests as slow
    integration: integration tests
```

**Or in pyproject.toml:**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
markers = [
    "slow: marks tests as slow",
    "integration: integration tests",
]
```

</pytest_ini>

<edge_cases_checklist>

Always test:
- Empty inputs (`""`, `[]`, `{}`, `None`)
- Boundary values (0, -1, max_int, min_int)
- Invalid inputs (wrong types, malformed data)
- Error conditions (network failures, file not found)
- Concurrent access (if applicable)
- Unicode and special characters
- Large inputs (performance edge cases)

</edge_cases_checklist>