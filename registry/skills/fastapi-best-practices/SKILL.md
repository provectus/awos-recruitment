---
name: fastapi-best-practices
description: >-
  Use when writing, reviewing, or refactoring FastAPI applications — route
  handlers, Pydantic schemas, dependency injection, async routes, database
  conventions, testing, or API documentation. Triggers include FastAPI routers,
  endpoints, request validation, response models, application configuration,
  blocked event loops, or flaky async tests.
version: 0.3.0
---

# FastAPI Best Practices

Opinionated conventions for building production FastAPI applications. This skill focuses on FastAPI-specific patterns.

## Categories

| Category | Impact | Reference |
|---|---|---|
| Async Routes | CRITICAL | `references/async-patterns.md` |
| Pydantic Integration | HIGH | `references/pydantic-patterns.md` |
| Dependency Injection | HIGH | `references/dependencies.md` |
| Database & Migrations | MEDIUM | `references/conventions.md` |
| Testing | MEDIUM | `references/conventions.md` |
| API Documentation | LOW | `references/conventions.md` |

## Quick Reference

### Async Routes

- `async def` — use ONLY with non-blocking `await` calls; blocks event loop otherwise
- `def` (sync) — use for blocking I/O; runs in threadpool automatically
- CPU-intensive — offload to Celery or multiprocessing, not threads
- Sync SDK in async route — use `run_in_threadpool()` from Starlette

See `references/async-patterns.md` for decision matrix, threadpool caveats, and examples.

### Pydantic

- Use built-in validators (`Field`, `EmailStr`, `AnyUrl`) before writing custom ones
- Create a custom base model for consistent serialization across the app
- Split `BaseSettings` by domain — separate settings classes, not one global class; classes live wherever the project's structure keeps config
- Beware: `ValueError` in validators becomes a 422 response with the full message
- Response models are created twice — once by you, once by FastAPI for validation
- `response_model` is always a Pydantic class, never a SQLAlchemy model — a new column must not be able to reach a client by default
- Never share a base model across request and response — duplicate the fields; a shared base is how `X | None`-everything god-schemas start

See `references/pydantic-patterns.md` for base model template, schema design, and ORM mode.

### Dependencies

- Declare with `Annotated[T, Depends(...)]`, never `Depends` in the default position; alias repeated dependencies (`DbSession = Annotated[AsyncSession, Depends(get_db)]`)
- Use for **request validation** (DB lookups, auth), not just DI
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

See `references/conventions.md` for index naming template, Alembic migration conventions, and SQL-first examples.

### Testing

- Set up an async test client (httpx + ASGITransport) from day one
- Mixing sync/async test patterns later causes event loop conflicts

See `references/conventions.md` for async test fixture setup.

### API Documentation

- Hide docs in production: set `openapi_url=None` for non-allowed environments
- Always set `response_model`, `status_code`, `description`, `tags` on endpoints

See `references/conventions.md` for docs configuration and endpoint documentation examples.

## How to Use

Each reference file contains detailed explanations, correct/incorrect code examples, and rationale. Read individual files as needed for the category you're working on.
