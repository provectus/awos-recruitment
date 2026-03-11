# Fixtures Reference

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

Use `yield` for setup/teardown:

```python
@pytest.fixture
def temp_file():
    """Create and cleanup a temporary file."""
    path = Path("/tmp/test_file.txt")
    path.write_text("test content")
    yield path  # Test runs here
    path.unlink(missing_ok=True)  # Cleanup after test
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