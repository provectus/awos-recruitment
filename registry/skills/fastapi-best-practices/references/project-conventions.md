# Project Conventions

## Contents
- Domain-Based Module Layout (full tree, module reference, global vs domain, cross-domain imports)
- Database Naming Conventions (tables, columns, explicit index naming)
- SQL-First Approach
- Alembic Migrations (rules, file naming)
- API Documentation (hiding docs in production, endpoint documentation)
- Testing (async test client)
- Linting

## Domain-Based Module Layout

Organize by **domain** (auth, posts, payments), not by file type (routers/, models/, services/). Each domain is a self-contained package with a standard set of modules.

### Full project tree

```
fastapi-project/
├── alembic/                     # Migration scripts
├── src/
│   ├── auth/                    # Auth domain
│   │   ├── router.py            # API endpoints
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── models.py            # Database (ORM) models
│   │   ├── service.py           # Business logic
│   │   ├── dependencies.py      # Route-level dependencies
│   │   ├── config.py            # Domain env vars (BaseSettings)
│   │   ├── constants.py         # Constants and error codes
│   │   ├── exceptions.py        # Domain exceptions (e.g., InvalidCredentials)
│   │   └── utils.py             # Non-business helpers
│   ├── posts/                   # Posts domain
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── service.py
│   │   ├── dependencies.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   └── utils.py
│   ├── aws/                     # External service client
│   │   ├── client.py            # SDK wrapper
│   │   ├── schemas.py
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   └── utils.py
│   ├── config.py                # Global configuration
│   ├── models.py                # Shared DB models
│   ├── exceptions.py            # Global exception handlers
│   ├── pagination.py            # Shared modules (pagination, etc.)
│   ├── database.py              # DB engine & session setup
│   └── main.py                  # FastAPI app initialization
├── tests/
│   ├── auth/                    # Tests mirror domain structure
│   ├── posts/
│   └── aws/
├── templates/                   # Jinja2 templates (if needed)
├── .env
├── alembic.ini
└── pyproject.toml
```

### Domain module reference

| Module | Purpose | When to create |
|---|---|---|
| `router.py` | API endpoints — the core of each domain | Always |
| `schemas.py` | Pydantic request/response models | Always |
| `models.py` | Database (ORM) models | When domain has DB tables |
| `service.py` | Business logic functions | When logic goes beyond simple CRUD |
| `dependencies.py` | Route-level dependencies (validation, auth) | When routes need shared validation |
| `config.py` | Domain-specific env vars via `BaseSettings` | When domain has its own config |
| `constants.py` | Constants and error codes | Always |
| `exceptions.py` | Domain-specific exceptions | Always |
| `utils.py` | Non-business helpers (normalization, enrichment) | When needed |
| `client.py` | External service SDK wrapper | For external service integrations |

### Global vs domain modules

Global modules at `src/` root handle cross-cutting concerns:

| Module | Purpose |
|---|---|
| `main.py` | App init, middleware, router mounting |
| `config.py` | Global settings (DB URL, Redis, CORS, environment) |
| `database.py` | Engine, session factory, base model |
| `models.py` | Shared models (if any) |
| `exceptions.py` | Global exception handlers, base exception classes |
| `pagination.py` | Shared utilities used across domains |

### Cross-domain imports

Always use explicit module names to make the origin clear:

```python
from src.auth import constants as auth_constants
from src.notifications import service as notification_service
from src.posts.constants import ErrorCode as PostsErrorCode
```

### When to create a new domain package

- The feature has its own API endpoints → new domain
- The feature is an external service integration (AWS, Stripe) → new domain with `client.py`
- Shared utilities used across multiple domains → keep at `src/` root level, not in a domain

## Database Naming Conventions

### Table names
- `lower_case_snake` format
- Singular form: `post`, `user`, `post_like`
- Group related tables with a prefix: `payment_account`, `payment_bill`
- Use `_at` suffix for datetime columns: `created_at`, `updated_at`
- Use `_date` suffix for date columns: `birth_date`, `start_date`

### Column naming consistency
- Use `profile_id` across all tables that reference profiles
- Use concrete names where semantically appropriate: `creator_id` when only creators are valid, `course_id` instead of generic `post_id` in a course-specific table

### Explicit index naming

Set naming conventions in SQLAlchemy metadata to avoid auto-generated names:

```python
from sqlalchemy import MetaData

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)
```

## SQL-First Approach

Prefer database-level operations over Python-side processing:
- Complex joins and filtering belong in SQL
- Aggregate nested JSON in the database for responses with nested objects
- The database handles data processing faster and cleaner than CPython

```python
select_query = (
    select(
        posts.c.id,
        posts.c.slug,
        posts.c.title,
        func.json_build_object(
            text("'id', profiles.id"),
            text("'first_name', profiles.first_name"),
            text("'last_name', profiles.last_name"),
        ).label("creator"),
    )
    .select_from(posts.join(profiles, posts.c.owner_id == profiles.c.id))
    .where(posts.c.owner_id == creator_id)
    .limit(limit)
    .offset(offset)
    .order_by(desc(coalesce(posts.c.updated_at, posts.c.created_at)))
)
```

## Alembic Migrations

### Rules
- Migrations must be **static and reversible** — structure should not depend on dynamic data
- Use **descriptive file names** with slugs that explain the change
- Always generate both upgrade and downgrade functions

### File naming

Configure a human-readable template in `alembic.ini`:

```ini
file_template = %%(year)d-%%(month).2d-%%(day).2d_%%(slug)s
```

This produces files like `2024-03-15_add_post_content_idx.py` instead of cryptic revision hashes.

## API Documentation

### Hide docs in production

```python
from src.constants import Environment

SHOW_DOCS_ENVIRONMENT = ("local", "staging")

app_configs = {"title": "My API"}
if settings.ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)
```

### Endpoint documentation

Always set `response_model`, `status_code`, `description`, and `tags`:

```python
@router.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a new post",
    tags=["Posts"],
    summary="Create Post",
    responses={
        status.HTTP_201_CREATED: {
            "model": PostResponse,
            "description": "Post created successfully",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ValidationErrorResponse,
            "description": "Validation failed",
        },
    },
)
async def create_post(data: PostCreate):
    ...
```

## Testing

### Async test client from day one

Setting up an async test client early prevents event loop conflicts that arise when mixing sync and async test patterns later:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.mark.asyncio
async def test_create_post(client: AsyncClient):
    resp = await client.post("/posts", json={"title": "Test", "content": "Body"})
    assert resp.status_code == 201
```

## Linting

Use [ruff](https://github.com/astral-sh/ruff) for formatting and linting — it replaces black, isort, autoflake, and supports 600+ rules:

```shell
ruff check --fix src
ruff format src
```

**Important:** Always read linting rules from the project's configuration (`pyproject.toml`, `ruff.toml`, or `.ruff.toml`) before applying or suggesting fixes. Projects define their own rule sets, line length, ignore lists, and per-file overrides — do not assume defaults or add rules that conflict with the existing config.
