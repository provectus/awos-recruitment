---
name: fastapi-best-practices
description: >-
  FastAPI best practices and conventions. Use when writing, reviewing, or refactoring
  FastAPI applications — route handlers, Pydantic schemas, dependency injection,
  project structure, async patterns, testing, or API documentation. Triggers on tasks
  involving FastAPI routers, endpoints, request validation, response models, or
  application configuration. Does not cover general Python syntax or typing — see
  modern-python-development for that.
version: 0.1.0
---

# FastAPI Best Practices

Opinionated conventions for building production FastAPI applications. Covers project layout, async routing, Pydantic usage, dependency injection, REST design, testing, and operational concerns. General Python idioms (naming, type hints, error handling, dataclasses) are covered by the `modern-python-development` skill — this skill focuses on FastAPI-specific patterns.

## Project Structure

Organize code by **domain**, not by file type. Each domain package follows a standard module layout.

```
src/
├── auth/
│   ├── router.py        # API endpoints
│   ├── schemas.py       # Pydantic request/response models
│   ├── models.py        # Database models
│   ├── service.py       # Business logic
│   ├── dependencies.py  # Route dependencies
│   ├── config.py        # Domain-specific env vars (BaseSettings)
│   ├── constants.py     # Constants and error codes
│   ├── exceptions.py    # Domain-specific exceptions
│   └── utils.py         # Non-business helpers
├── posts/
│   └── ...              # Same module pattern
├── config.py            # Global configuration
├── models.py            # Shared DB models
├── exceptions.py        # Global exception handlers
├── database.py          # DB connection setup
└── main.py              # FastAPI app initialization
```

### Import convention

Use explicit module names when importing across domains:

```python
from src.auth import constants as auth_constants
from src.notifications import service as notification_service
```

## Async Routes

### Rules

| Route type | When to use | How it runs |
|---|---|---|
| `async def` | Non-blocking I/O only (`await` calls) | Directly on the event loop |
| `def` (sync) | Blocking I/O (sync DB drivers, file I/O) | Automatically in a threadpool |
| CPU-intensive | Heavy computation, data processing | Offload to Celery / multiprocessing |

### Critical mistake — blocking in async routes

```python
# WRONG — blocks the entire event loop
@router.get("/bad")
async def bad():
    time.sleep(10)
    return {"done": True}

# CORRECT — sync route runs in threadpool
@router.get("/good")
def good():
    time.sleep(10)
    return {"done": True}

# CORRECT — non-blocking async
@router.get("/best")
async def best():
    await asyncio.sleep(10)
    return {"done": True}
```

### Sync libraries in async context

```python
from fastapi.concurrency import run_in_threadpool

@router.get("/")
async def call_sync_lib():
    result = await run_in_threadpool(sync_client.make_request, data=my_data)
    return result
```

For detailed async patterns including threadpool caveats and CPU-bound guidance, see `references/async-patterns.md`.

## Pydantic

### Leverage built-in validators

```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128, pattern="^[A-Za-z0-9-_]+$")
    email: EmailStr
    age: int = Field(ge=18)
```

### Custom base model for consistent serialization

```python
from pydantic import BaseModel, ConfigDict

class CustomModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={datetime: datetime_to_gmt_str},
        populate_by_name=True,
    )
```

### Split BaseSettings by domain

```python
# src/auth/config.py
from pydantic_settings import BaseSettings

class AuthConfig(BaseSettings):
    JWT_ALG: str
    JWT_SECRET: str
    JWT_EXP: int = 5

auth_settings = AuthConfig()
```

For response serialization gotchas, ValueError behavior, and more Pydantic patterns, see `references/pydantic-patterns.md`.

## Dependencies

Use dependencies for **request validation**, not just DI:

```python
async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post

@router.get("/posts/{post_id}")
async def get_post(post: dict[str, Any] = Depends(valid_post_id)):
    return post
```

### Key rules

- **Chain dependencies** to compose validation logic without repetition
- **Dependencies are cached per request** — the same dependency called multiple times executes once
- **Prefer `async` dependencies** to avoid unnecessary threadpool overhead
- Use consistent path variable names across routes to enable dependency reuse

For dependency chaining, caching behavior, and advanced patterns, see `references/dependencies.md`.

## REST Conventions

- Use consistent path variable names for dependency reuse across routes
- Rename path variables to match shared dependencies when semantically equivalent

```python
# Both use profile_id — shared valid_profile_id dependency works for both
GET /profiles/{profile_id}
GET /creators/{profile_id}  # creator is a profile, so reuse profile_id
```

## API Documentation

### Hide docs in production

```python
SHOW_DOCS_ENVIRONMENT = ("local", "staging")

app_configs = {"title": "My API"}
if ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)
```

### Document endpoints properly

```python
@router.post(
    "/endpoints",
    response_model=DefaultResponseModel,
    status_code=status.HTTP_201_CREATED,
    description="Description of the endpoint",
    tags=["Category"],
    responses={
        status.HTTP_201_CREATED: {"model": CreatedResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    },
)
```

## Testing

Use an async test client from day one to avoid event loop conflicts:

```python
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.mark.asyncio
async def test_create_post(client: AsyncClient):
    resp = await client.post("/posts")
    assert resp.status_code == 201
```

## Quick Reference

| Scenario | Solution |
|---|---|
| Non-blocking I/O | `async def` route with `await` |
| Blocking I/O | `def` route (sync, runs in threadpool) |
| Sync library in async | `run_in_threadpool()` |
| CPU-intensive work | Celery or multiprocessing |
| Request validation with DB | Dependencies, not Pydantic validators |
| Shared validation logic | Chain dependencies |
| Config per domain | Separate `BaseSettings` subclasses |
| Complex DB queries | SQL-first with JSON aggregation |
| Docs in production | Set `openapi_url=None` |

## Reference Files

For detailed guidance beyond this overview, consult:
- **`references/async-patterns.md`** — Async vs sync routes, event loop blocking, CPU-bound tasks, `run_in_threadpool`
- **`references/dependencies.md`** — Dependency chaining, caching, validation patterns, auth flows
- **`references/pydantic-patterns.md`** — Custom base model, BaseSettings, response serialization, ValueError gotcha
- **`references/project-conventions.md`** — DB naming, Alembic migrations, linting, detailed project structure
