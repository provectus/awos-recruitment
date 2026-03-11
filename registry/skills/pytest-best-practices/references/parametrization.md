# Parametrization Reference

<basic_parametrize>

Run the same test with different inputs:

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (0, 0),
    (-1, -2),
])
def test_double(input, expected):
    assert double(input) == expected
```

</basic_parametrize>

<parametrize_with_ids>

Add descriptive test IDs for better output:

```python
@pytest.mark.parametrize(
    "a,b,expected",
    [
        pytest.param(2, 3, 5, id="positive"),
        pytest.param(-1, 1, 0, id="zero_result"),
        pytest.param(-2, -3, -5, id="negative"),
        pytest.param(0, 0, 0, id="zeros"),
    ]
)
def test_add(a, b, expected):
    assert add(a, b) == expected
```

Output shows: `test_add[positive]`, `test_add[zero_result]`, etc.

</parametrize_with_ids>

<stacking_parametrize>

Combine multiple parametrize decorators for cartesian product:

```python
@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [10, 20])
def test_combinations(x, y):
    # Runs 4 tests: (1,10), (1,20), (2,10), (2,20)
    assert x * y > 0
```

</stacking_parametrize>

<parametrized_fixtures>

Parametrize at fixture level:

```python
@pytest.fixture(params=["sqlite", "postgres", "mysql"])
def database(request):
    """Test against multiple database backends."""
    db = create_database(request.param)
    yield db
    db.cleanup()

def test_query(database):
    # This test runs 3 times, once per database
    result = database.execute("SELECT 1")
    assert result == 1
```

</parametrized_fixtures>

<edge_case_parametrize>

Test edge cases systematically:

```python
@pytest.mark.parametrize("invalid_input", [
    None,
    "",
    [],
    {},
    -1,
    float("inf"),
    "not-a-number",
])
def test_handles_invalid_input(invalid_input):
    with pytest.raises((ValueError, TypeError)):
        process(invalid_input)
```

</edge_case_parametrize>

<conditional_parametrize>

Skip certain parameter combinations:

```python
@pytest.mark.parametrize("browser,platform", [
    ("chrome", "windows"),
    ("chrome", "mac"),
    pytest.param("safari", "windows", marks=pytest.mark.skip(reason="Safari not on Windows")),
    ("safari", "mac"),
])
def test_browser_platform(browser, platform):
    launch_browser(browser, platform)
```

</conditional_parametrize>

<indirect_parametrize>

Pass params through fixtures:

```python
@pytest.fixture
def user_type(request):
    """Create user based on parameter."""
    if request.param == "admin":
        return create_admin_user()
    return create_regular_user()

@pytest.mark.parametrize("user_type", ["admin", "regular"], indirect=True)
def test_user_permissions(user_type):
    assert user_type.can_access_dashboard()
```

</indirect_parametrize>