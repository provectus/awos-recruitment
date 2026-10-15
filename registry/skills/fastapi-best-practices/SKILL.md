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

Opinionated conventions for building production FastAPI applications. General Python idioms (naming, type hints, error handling, dataclasses) are covered by `modern-python-development` — this skill focuses on FastAPI-specific patterns.

## Categories

| Category | Impact | Reference |
|---|---|---|
| Project Structure | HIGH | `references/project-conventions.md` |
| Async Routes | CRITICAL | `references/async-patterns.md` |
| Pydantic Integration | HIGH | `references/pydantic-patterns.md` |
| Dependency Injection | HIGH | `references/dependencies.md` |
| Database & Migrations | MEDIUM | `references/project-conventions.md` |
| Testing | MEDIUM | `references/project-conventions.md` |
| API Documentation | LOW | `references/project-conventions.md` |

## Quick Reference

### Async Routes

- `async def` — use ONLY with non-blocking `await` calls; blocks event loop otherwise
- `def` (sync) — use for blocking I/O; runs in threadpool automatically
- CPU-intensive — offload to Celery or multiprocessing, not threads
- Sync SDK in async route — use `run_in_threadpool()` from Starlette

See `references/async-patterns.md` for decision matrix, threadpool caveats, and examples.

### Project Structure

Organize by **domain**, not by file type:

```
src/
├── auth/                # Domain package
│   ├── router.py        # Endpoints
│   ├── schemas.py       # Pydantic models
│   ├── models.py        # DB models
│   ├── service.py       # Business logic
│   ├── dependencies.py  # Route dependencies
│   ├── config.py        # Env vars (BaseSettings)
│   ├── constants.py     # Constants, error codes
│   ├── exceptions.py    # Domain exceptions
│   └── utils.py         # Helpers
├── posts/               # Another domain
│   └── ...
├── config.py            # Global config
├── database.py          # DB connection
└── main.py              # App init
```

- Import across domains with explicit module names: `from src.auth import constants as auth_constants`

See `references/project-conventions.md` for full layout, DB naming, Alembic, and linting.

### Pydantic

- Use built-in validators (`Field`, `EmailStr`, `AnyUrl`) before writing custom ones
- Create a custom base model for consistent serialization across the app
- Split `BaseSettings` by domain — one per module, not a single global config
- Beware: `ValueError` in validators becomes a 422 response with the full message
- Response models are created twice — once by you, once by FastAPI for validation

See `references/pydantic-patterns.md` for base model template, schema design, and ORM mode.

### Dependencies

- Use for **request validation** (DB lookups, auth), not just DI
- Declare as `Annotated[T, Depends(fn)]`, not `param: T = Depends(fn)`; reuse a module-level alias
- Chain dependencies to compose validation without repetition
- Dependencies are **cached per request** — same dependency in multiple chains runs once
- Prefer `async` dependencies to avoid threadpool overhead on trivial operations
- Use consistent path variable names across routes for dependency reuse

See `references/dependencies.md` for chaining, auth, pagination, and DB session patterns.

### Database

- Table names: `lower_case_snake`, singular (`post`, `user`, `post_like`)
- DateTime columns: `_at` suffix; date columns: `_date` suffix
- Set explicit index naming conventions in SQLAlchemy metadata
- Prefer SQL-first — complex joins and JSON aggregation belong in the database

See `references/project-conventions.md` for index naming template, Alembic migration conventions, and SQL-first examples.

### Testing

- Set up an async test client (httpx + ASGITransport) from day one
- Mixing sync/async test patterns later causes event loop conflicts

See `references/project-conventions.md` for async test fixture setup.

### API Documentation

- Hide docs in production: set `openapi_url=None` for non-allowed environments
- Always set `response_model`, `status_code`, `description`, `tags` on endpoints

See `references/project-conventions.md` for docs configuration and endpoint documentation examples.

## How to Use

Each reference file contains detailed explanations, correct/incorrect code examples, and rationale. Read individual files as needed for the category you're working on.
