# Mocking Reference

<basic_mock>

Use pytest-mock's `mocker` fixture:

```python
def test_api_call(mocker):
    # Mock the requests.get function
    mock_get = mocker.patch("mymodule.requests.get")
    mock_get.return_value.json.return_value = {"status": "ok"}

    result = fetch_status()

    assert result == "ok"
    mock_get.assert_called_once_with("https://api.example.com/status")
```

**Key**: Patch where the function is *used*, not where it's defined.

</basic_mock>

<side_effects>

Return different values on successive calls:

```python
def test_with_side_effect(mocker):
    mock_db = mocker.patch("mymodule.database.query")
    mock_db.side_effect = [
        {"id": 1},  # First call
        {"id": 2},  # Second call
        DatabaseError("Connection lost"),  # Third call raises
    ]

    assert get_item(1)["id"] == 1
    assert get_item(2)["id"] == 2
    with pytest.raises(DatabaseError):
        get_item(3)
```

</side_effects>

<mock_context_manager>

Mock file operations and context managers:

```python
def test_file_operations(mocker):
    mock_open = mocker.patch(
        "builtins.open",
        mocker.mock_open(read_data="test content")
    )

    result = read_config("/fake/path")

    assert result == "test content"
    mock_open.assert_called_once_with("/fake/path", "r")
```

</mock_context_manager>

<mock_async>

Mock async functions:

```python
@pytest.mark.asyncio
async def test_async_api(mocker):
    mock_fetch = mocker.patch("mymodule.async_fetch")
    mock_fetch.return_value = {"data": "test"}

    result = await process_data()

    assert result["data"] == "test"
```

For coroutines that need to be awaited:

```python
@pytest.mark.asyncio
async def test_async_coroutine(mocker):
    async def mock_coro():
        return {"data": "test"}

    mocker.patch("mymodule.async_fetch", side_effect=mock_coro)
    result = await process_data()
    assert result["data"] == "test"
```

</mock_async>

<mock_property>

Mock class properties:

```python
def test_property(mocker):
    mocker.patch.object(MyClass, "config", new_callable=mocker.PropertyMock, return_value={"key": "value"})

    obj = MyClass()
    assert obj.config["key"] == "value"
```

</mock_property>

<mock_environment>

Mock environment variables:

```python
def test_env_var(mocker):
    mocker.patch.dict("os.environ", {"API_KEY": "test-key"})

    result = get_api_key()
    assert result == "test-key"
```

</mock_environment>

<spy_pattern>

Spy on real functions (call real implementation but track calls):

```python
def test_spy(mocker):
    spy = mocker.spy(mymodule, "real_function")

    result = mymodule.real_function("arg")

    # Real function was called
    spy.assert_called_once_with("arg")
    assert result == expected_real_result
```

</spy_pattern>

<mock_assertions>

Common mock assertions:

```python
mock.assert_called()                    # Called at least once
mock.assert_called_once()               # Called exactly once
mock.assert_called_with(arg1, arg2)     # Last call had these args
mock.assert_called_once_with(arg1)      # Called once with these args
mock.assert_not_called()                # Never called
mock.assert_has_calls([call(1), call(2)])  # Called with these in order

# Access call information
mock.call_count                         # Number of calls
mock.call_args                          # Last call's args
mock.call_args_list                     # All calls' args
```

</mock_assertions>