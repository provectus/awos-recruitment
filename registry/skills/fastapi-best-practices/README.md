# FastAPI Best Practices

Opinionated conventions for building production FastAPI applications — async routing, dependency injection, Pydantic integration, domain-based project structure, testing, and operational patterns.

> This skill is based on [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices). Big thanks to the author for the foundational work.

## Install

```bash
npx @provectusinc/awos-recruitment skill fastapi-best-practices
```

## Scope

Covers FastAPI-specific patterns only. General Python best practices (naming, type hints, error handling, dataclasses, project layout) are handled by the companion `modern-python-development` skill.

This skill teaches:

- **Async routing** — when to use `async def` vs `def`, event loop blocking, CPU-bound offloading
- **Dependency injection** — validation via dependencies, chaining, caching, auth/pagination patterns
- **Pydantic integration** — custom base models, split BaseSettings, response serialization gotchas
- **Project structure** — domain-based module layout with standard file conventions
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
| `references/project-conventions.md` | Domain module layout, DB naming, Alembic migrations, API docs config, testing, linting |

## Usage

Once installed, the skill activates automatically when Claude Code detects FastAPI-related tasks — writing route handlers, reviewing async patterns, setting up dependencies, or configuring Pydantic schemas.

## Evaluation

Test prompts for checking that the skill triggers when it should and stays out of the way
when a sibling skill is the better fit. The registry validator only permits `SKILL.md`,
`README.md`, `references/`, and `scripts/` inside a skill directory, so these live here
rather than in an `evals/` folder — which also keeps them out of the bundled skill
context.

The negative cases matter as much as the positive ones: this skill sits next to
`modern-python-development`, `pytest-best-practices`, and `postgres-best-practices`, and
each one below is a deliberate near-miss that shares vocabulary with this skill but
belongs to a neighbour.

### Should trigger

| # | Prompt | Expected |
|---|---|---|
| 1 | "our `/orders` endpoint takes ~4s under load and i think it's because we call the stripe sdk (the sync client) directly inside an `async def` route in `src/payments/router.py`. what's the right fix?" | `references/async-patterns.md` — blocking call on the event loop, resolve with `run_in_threadpool` |
| 2 | "adding `PATCH /profiles/{profile_id}` and i need the same 'does this profile exist / does the caller own it' check that's already copy-pasted into three other handlers" | `references/dependencies.md` — validation via a chained `Annotated[..., Depends(...)]` dependency |
| 3 | "review `src/posts/schemas.py` — `PostCreate`, `PostUpdate` and `PostResponse` all inherit one model and the response is leaking `internal_notes` to clients" | `references/pydantic-patterns.md` — separate input and output schemas |
| 4 | "starting a new fastapi service for our billing domain, everything is in `main.py` right now. how should the packages be laid out?" | `references/project-conventions.md` — domain-based module layout |

### Should not trigger

| # | Prompt | Expected |
|---|---|---|
| 5 | "can you modernize the type hints in this module? there's a bunch of `Optional[Dict[str, Any]]` that should use the new syntax" | `modern-python-development` — general typing, no FastAPI surface |
| 6 | "my pytest fixtures leak state between tests, the `db` fixture is session-scoped and i think that's the problem" | `pytest-best-practices` — fixture scoping, not FastAPI's async test client |
| 7 | "this query does a seq scan on a 2M-row table, `EXPLAIN` shows the index isn't being used" | `postgres-best-practices` — query planning, not the skill's SQL-first guidance |

### Running them

Use the `skill-creator` skill's description-tuning mode, which runs each prompt several
times and reports a trigger rate per prompt, then proposes description edits from the
cases that fail:

```bash
python -m scripts.run_loop \
  --eval-set <eval-set.json> \
  --skill-path registry/skills/fastapi-best-practices \
  --model <model-id> \
  --max-iterations 5 --verbose
```

That script takes a JSON array of `{"query": ..., "should_trigger": true|false}` objects —
build it from the two tables above. Treat a regression on rows 5-7 as seriously as a miss
on rows 1-4: a description that over-triggers pulls FastAPI conventions into work that
isn't about FastAPI.
