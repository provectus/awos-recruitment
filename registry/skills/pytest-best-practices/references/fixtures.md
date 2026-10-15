# Fixtures Reference

## Contents
- Basic Fixture
- Built-in Fixtures (`tmp_path`, `tmp_path_factory`, `monkeypatch`, `capsys`, `caplog`)
- Fixture Scopes (function, module, session, class)
- Teardown Pattern (`yield`)
- Fixture Factories
- `conftest.py` and `autouse`
- Fixture Dependencies

<basic_fixture>

```python
import pytest

@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return {"id": 1, "name": "Test User", "email": "test@example.com"}

def test_user_has_email(sample_user):
    assert "email" in sample_user
    assert "@" in sample_user["email"]
```

</basic_fixture>

<builtin_fixtures>

Check these before writing a custom fixture — pytest already gives each test a
fresh copy and reverts every change at teardown, so they stay correct under
`pytest -n auto` where a shared path or a mutated `os.environ` would not.

**tmp_path** - Unique temporary directory per test, as a `pathlib.Path`:
```python
def test_writes_log(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_text("some log content")
    assert (log_dir / "app.log").read_text() == "some log content"
```

**tmp_path_factory** - Session-scoped sibling for fixtures that outlive one test:
```python
@pytest.fixture(scope="session")
def shared_dataset(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "dataset.csv"
    path.write_text("id,name\n1,Alice\n")
    return path
```

**monkeypatch** - Patch env vars, attributes, dict items, `sys.path`, or the cwd;
every change is undone after the test:
```python
def test_reads_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    assert get_api_key() == "test-key"

def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(KeyError):
        get_api_key()

def test_patched_attribute(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "timeout", 1)
    monkeypatch.chdir(tmp_path)  # also: setitem, delitem, syspath_prepend
```

**capsys** - Assert on captured stdout/stderr. `readouterr()` returns a
named tuple (`.out`, `.err`) and resets the buffer:
```python
def test_prints_summary(capsys):
    print_summary(count=3)
    captured = capsys.readouterr()
    assert "3 items" in captured.out
    assert captured.err == ""
```

**caplog** - Assert on log records. Use `caplog.records` for structured checks
and `caplog.set_level()` to lower the threshold for the test:
```python
import logging

def test_logs_warning(caplog):
    caplog.set_level(logging.WARNING)
    process(payload={})
    assert "empty payload" in caplog.text
    assert [r.levelname for r in caplog.records] == ["WARNING"]
```

</builtin_fixtures>

<fixture_scopes>

**function** (default) - New instance per test
```python
@pytest.fixture(scope="function")
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()
```

**module** - Shared across all tests in module
```python
@pytest.fixture(scope="module")
def expensive_resource():
    resource = setup_expensive_thing()
    yield resource
    resource.cleanup()
```

**session** - Shared across entire test session
```python
@pytest.fixture(scope="session")
def app_config():
    return load_config()
```

**class** - Shared across all tests in a class
```python
@pytest.fixture(scope="class")
def class_resource():
    return create_resource()
```

</fixture_scopes>

<teardown_pattern>

Use `yield` for setup/teardown. Build paths from `tmp_path` rather than a literal
`/tmp/...` — pytest gives each test its own directory and cleans it up, so the
fixture stays isolated when tests run in parallel:

```python
@pytest.fixture
def config_file(tmp_path):
    """Create a config file for the test."""
    path = tmp_path / "config.toml"
    path.write_text('name = "test"\n')
    yield path  # Test runs here
    # tmp_path is removed by pytest; only clean up what you created elsewhere
```

Reserve explicit teardown for resources pytest does not own:

```python
@pytest.fixture
def seeded_account(db):
    """Insert a row and remove it afterwards."""
    account = db.accounts.insert(name="test")
    yield account
    db.accounts.delete(account.id)  # Runs even if the test fails
```

</teardown_pattern>

<fixture_factories>

Create multiple instances with custom attributes:

```python
@pytest.fixture
def make_user():
    """Factory fixture for creating users."""
    created_users = []

    def _make_user(name="Test", email=None):
        user = User(name=name, email=email or f"{name.lower()}@test.com")
        created_users.append(user)
        return user

    yield _make_user

    # Cleanup all created users
    for user in created_users:
        user.delete()

def test_multiple_users(make_user):
    user1 = make_user("Alice")
    user2 = make_user("Bob", email="bob@custom.com")
    assert user1.email != user2.email
```

</fixture_factories>

<conftest_pattern>

Share fixtures across modules in `tests/conftest.py`:

```python
# tests/conftest.py
import pytest

@pytest.fixture
def api_client():
    """Shared API client available to all tests."""
    from myapp import create_test_client
    return create_test_client()

@pytest.fixture(autouse=True)
def reset_database(db):
    """Automatically reset DB before each test."""
    db.reset()
    yield
    db.rollback()
```

**autouse=True** - Fixture runs for every test without explicit request.

</conftest_pattern>

<fixture_dependencies>

Fixtures can depend on other fixtures:

```python
@pytest.fixture
def db():
    return create_database()

@pytest.fixture
def user(db):  # Depends on db fixture
    return db.create_user("test")

@pytest.fixture
def authenticated_client(user, api_client):  # Multiple dependencies
    api_client.login(user)
    return api_client
```

</fixture_dependencies>