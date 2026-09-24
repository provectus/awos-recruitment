# Pytest Best Practices

Expert guidance for writing high-quality pytest tests — covering fixtures, parametrization, mocking, and common patterns for maintainable test suites.

> This skill is based on the [pytest-best-practices](https://github.com/cfircoo/claude-code-toolkit/tree/main/skills/pytest-best-practices) skill originally created by [cfircoo](https://github.com/cfircoo). Big thanks to the authors for the foundational work.

## Install

```bash
npx @provectusinc/awos-recruitment skill pytest-best-practices
```

## Scope

The skill covers:

- Test independence and isolation principles
- Naming conventions and directory structure
- Fixtures: scopes, factories, teardown, `conftest.py`
- Built-in fixtures: `tmp_path`, `tmp_path_factory`, `monkeypatch`, `capsys`, `caplog`
- Parametrization: basic, IDs, stacking, indirect, edge cases
- Mocking: patching, side effects, async mocks, spies, assertions
- Markers, exception testing, assertions, async testing
- Configuration (`pytest.ini` / `pyproject.toml`)

It deliberately does **not** cover general Python syntax and typing (see
`modern-python-development`) or FastAPI `TestClient` and app-level test setup
(see `fastapi-best-practices`).

## Usage

Once installed, the skill activates automatically when Claude Code detects pytest-related tasks — writing tests, setting up fixtures, parametrizing, mocking dependencies, or reviewing test code.

Reference files are organized by topic in `references/`:

```
references/fixtures.md
references/parametrization.md
references/mocking.md
references/patterns.md
```

## Reference Topics

| Topic | File | Covers |
|-------|------|--------|
| Fixtures | `references/fixtures.md` | Scopes, factories, teardown, conftest, dependencies |
| Parametrization | `references/parametrization.md` | Basic, IDs, stacking, indirect, edge cases, conditionals |
| Mocking | `references/mocking.md` | Patching, side effects, async, properties, env vars, spies |
| Patterns | `references/patterns.md` | Markers, exceptions, assertions, async testing, configuration |

## Trigger evaluation

The registry bundler ships only `SKILL.md` and the flat files under
`references/`, so the trigger prompts live here rather than in an `evals/`
directory. Re-run them after any edit to the `description` front matter — the
"should not trigger" rows are the ones that catch an over-broad description.

**Should trigger**

1. "our `tests/` dir has a `conftest.py` with a session-scoped `db` fixture and half
   the suite fails when I run it with `-p no:randomly`. can you work out which tests
   are leaking state and rewrite them so they pass in any order?"
2. "I need to parametrize `test_parse_duration` over about 15 input strings including
   a couple that should raise `ValueError`. what's the cleanest way to write that so
   the failure output still tells me which case broke?"
3. "writing a test for `load_settings()` which reads `APP_ENV` and `DATABASE_URL` from
   the environment and falls back to defaults. how do I set those per-test without
   trashing my real env?"
4. "review the tests in `src/billing/tests/test_invoice.py` — too many mocks, some
   tests assert nothing useful, and I think a few are testing the mock rather than
   the code"

**Should not trigger** (the near-misses that matter)

1. "add type hints to `parse_config()` and switch it from `Optional[str]` to the
   modern union syntax" → `modern-python-development`
2. "my `@app.get("/items/{id}")` endpoint returns 422 for valid payloads — can you fix
   the response_model and the Pydantic schema?" → `fastapi-best-practices`
3. "set up the test suite for our Next.js app — vitest with react testing library,
   including a couple of tests for the checkout form" → neither; not Python
4. "the CI job times out on the integration suite. can you look at the GitHub Actions
   workflow and figure out why the runner hangs?" → CI diagnosis, not test authoring
