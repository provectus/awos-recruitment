# FastAPI Best Practices

Opinionated conventions for building production FastAPI applications — async routing, dependency injection, Pydantic integration, testing, and operational patterns.

> This skill is based on [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices). Big thanks to the author for the foundational work.

## Install

```bash
npx @provectusinc/awos-recruitment skill fastapi-best-practices
```

## Scope

Covers FastAPI-specific patterns only. General Python best practices (naming, type hints, error handling, dataclasses, project layout) are handled by the companion `modern-python-development` skill. Project structure and code placement are owned by the companion fastapi-vertical-slice-architecture skill.

This skill teaches:

- **Async routing** — when to use `async def` vs `def`, event loop blocking, CPU-bound offloading
- **Dependency injection** — validation via dependencies, chaining, caching, auth/pagination patterns
- **Pydantic integration** — custom base models, split BaseSettings, response serialization gotchas
- **Database conventions** — table naming, index naming, SQL-first approach, Alembic migrations
- **Testing** — async test client setup from day one
- **API documentation** — hiding docs in production, endpoint documentation

## Files

| File | Content |
|---|---|
| `SKILL.md` | Quick reference index — categories, rules, and pointers to references |
| `references/async-patterns.md` | Async vs sync routes, threadpool caveats, CPU-bound tasks, `run_in_threadpool`, decision matrix |
| `references/dependencies.md` | Validation via DI, chaining, caching, auth guards, pagination, DB session patterns |
| `references/pydantic-patterns.md` | Custom base model, BaseSettings splitting, response serialization, ValueError gotcha, schema design |
| `references/conventions.md` | DB naming, Alembic migrations, API docs config, testing, linting |

## Usage

Once installed, the skill activates automatically when Claude Code detects FastAPI-related tasks — writing route handlers, reviewing async patterns, setting up dependencies, or configuring Pydantic schemas.
