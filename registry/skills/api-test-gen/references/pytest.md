# Python + pytest Reference

## Project layout
```
api-tests/
├── pytest.ini
├── requirements.txt
├── .env.example
├── tests/
│   ├── conftest.py          # session-scoped client + auth
│   ├── test_<tag>.py
│   └── workflows/
│       └── test_<tag>_workflow.py
├── helpers/
│   └── factories.py
└── reports/
```

## conftest.py
```python
import os
import pytest
import httpx
from dotenv import load_dotenv
load_dotenv()

def build_auth_headers() -> dict:
    if os.getenv("auth_bearer"):
        return {"Authorization": f"Bearer {os.getenv('auth_bearer')}"}
    if os.getenv("auth_apikey"):
        header = os.getenv("auth_apikey_header", "X-API-Key")
        return {header: os.getenv("auth_apikey")}
    if os.getenv("auth_basic"):
        return {"Authorization": f"Basic {os.getenv('auth_basic')}"}
    return {}

@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=os.getenv("BASE_URL"), headers=build_auth_headers()) as client:
        yield client

@pytest.fixture(scope="session")
def anon():
    with httpx.Client(base_url=os.getenv("BASE_URL")) as client:
        yield client
```

## Test file template
```python
import pytest

class TestPOSTUsers:

    def test_post_users_happy_valid_body(self, api):
        res = api.post("/users", json={"name": "test-string-name", "email": "test@example.com"})
        assert res.status_code == 201
        body = res.json()
        assert "id" in body
        assert body["email"] == "test@example.com"

    def test_post_users_neg_missing_email(self, api):
        res = api.post("/users", json={"name": "test-string-name"})
        assert res.status_code in (400, 422)

    def test_post_users_neg_no_auth(self, anon):
        res = anon.post("/users", json={"name": "test-string-name", "email": "test@example.com"})
        assert res.status_code in (401, 403)

    def test_post_users_edge_name_max_length(self, api):
        res = api.post("/users", json={"name": "a" * 255, "email": "test@example.com"})
        assert res.status_code == 201

    def test_post_users_edge_name_over_max_length(self, api):
        res = api.post("/users", json={"name": "a" * 256, "email": "test@example.com"})
        assert res.status_code in (400, 422)
```

## Workflow test template
```python
import pytest

@pytest.fixture(scope="module")
def created_resource(api):
    res = api.post("/users", json={"name": "workflow-user", "email": "wf@example.com"})
    assert res.status_code == 201
    resource_id = res.json()["id"]
    yield resource_id
    api.delete(f"/users/{resource_id}")  # cleanup

class TestUsersCRUDWorkflow:

    def test_step1_read(self, api, created_resource):
        res = api.get(f"/users/{created_resource}")
        assert res.status_code == 200

    def test_step2_update(self, api, created_resource):
        res = api.put(f"/users/{created_resource}", json={"name": "workflow-user-updated"})
        assert res.status_code == 200
        assert res.json()["name"] == "workflow-user-updated"

    def test_step3_delete(self, api, created_resource):
        res = api.delete(f"/users/{created_resource}")
        assert res.status_code in (200, 204)

    def test_step4_confirm_gone(self, api, created_resource):
        res = api.get(f"/users/{created_resource}")
        assert res.status_code == 404
```

## requirements.txt
```
pytest>=8.0
httpx>=0.27
pytest-html>=4.0
pytest-json-report>=1.5
python-dotenv>=1.0
```

## pytest.ini
```ini
[pytest]
testpaths = tests
addopts = -v --json-report --json-report-file=reports/results.json --html=reports/index.html
```

## Run command
```bash
pip install -r requirements.txt --break-system-packages
cp .env.example .env
BASE_URL=https://api.example.com auth_bearer=token pytest
```
