# Slice Testing

**Contents:** Doctrine · Where Tests and Fixtures Live · The Fixture Recipe · The Three Assertions · Per-Entry-Point Recipes · Case Coverage per Slice

How every slice proves itself — the fixture recipe, what a test must assert, and how much of the failure surface one test file owes. SKILL.md's Rule 10 states the requirement: every slice has a subcutaneous test, real app, real Postgres. Rule 6 explains why nothing weaker qualifies — mocking the session invents exactly the single-implementation seam Rule 6 forbids everywhere else inside a slice. This file is the mechanics underneath: the conftest, the assertions, and the coverage a slice's test file owes.

## Doctrine

**Subcutaneous, not unit, not handler-in-isolation.** A slice's test drives its entry point exactly as a real caller would: through the actual FastAPI app, wired with `ASGITransport` instead of a socket, against a real Postgres instance started via `testcontainers`. No layer between the test and production is stubbed.

**`domain/` is the one exception, and it is a different tier, not a diluted one.** Rule 8 purity is what buys this: pure functions and value objects, zero fixtures, no app, no database, no event loop. `transition(OrderStatus.PENDING, OrderStatus.PAID)` runs standalone in a bare pytest process, and its test co-locates like every other — `domain/test_order.py`, beside the rule it proves. Every module outside `domain/` gives up that shortcut the moment it imports a session or a model — it tests through the app or it does not count.

**There is no handler-with-mocked-session tier, and adding one is a regression, not a gap.** A mocked `AsyncSession` is a single-implementation seam smuggled in through the test file instead of the production code — the thing Rule 6 already forbids. A test built on it proves the mock was called with the right arguments; it proves nothing about whether the query it stands in for returns the right rows, enforces the right constraint, or interacts correctly with whatever else changed in the same transaction. `dependency_overrides` exists in this doctrine for exactly one purpose: pointing `get_db` at the test database. It is never a seam for stubbing an in-process collaborator — a slice has none of those to stub; its only in-process collaborators are `domain/` calls (real, pure, cheap to run for real) and the database (real, via the container). The one sanctioned exception sits outside the process entirely: a thin client wrapping a third-party **process** — a payment provider, an email or push gateway — is the one seam this doctrine allows a test to stub: replace that client's function wherever the handler looks it up, never the session, the query, or anything `domain/` owns (see the subscriber-session note below for why the importing module, not the source, is the actual patch target). Everything that runs in-process — session, domain, pipeline — stays real regardless.

## Where Tests and Fixtures Live

Tests are co-located: a slice's test sits inside the slice folder, so deleting the folder deletes the whole use case, test included. Fixtures follow the same placement logic as production code — shared substrate deep and singular, everything below flat:

| What | Home | Production analogue |
| --- | --- | --- |
| Substrate fixtures — the recipe below | `conftest.py` at the **project root** | `database.py` / the pipeline: wired once, every slice picks it up by position |
| Arrangement a slice's second test file shares | That slice's own `tests/conftest.py` — promotion below | `handler.py`: slice-internal decomposition, free under Rule 6 |
| Test helpers shared across slices | Nowhere — duplicate the three lines of setup | `shared/`, `utils.py`: the routing failure, in test form |

pytest loads `conftest.py` files along the filesystem path from rootdir down to each test file, so the root conftest reaches every slice test with zero imports, and one slice's conftest is structurally invisible to every sibling — Rule 4 for fixtures, enforced by pytest's own mechanism. Two placements must not happen: a root `tests/` directory (it sits on no co-located test's path, so a conftest there is loaded for nothing — the substrate belongs at the project root), and a family-level `features/{family}/conftest.py` (shared arrangement across slices is the shared `service.py` problem reborn as fixtures — duplicate the setup instead).

**A slice's `tests/` folder is earned, not scaffolded** — the same grammar as `handler.py`:

- Default: one co-located `test_{verb_noun}.py`, forever, for most slices.
- Promote to `features/{family}/{verb_noun}/tests/` — empty `__init__.py`, the test files, optionally a `conftest.py` — when a second test file is earned or an arrangement fixture serves multiple files in the slice.
- A slice `conftest.py` builds **on top of** root fixtures (`paid_order(db_session)` seeding one committed order) and never **overrides** one by name — one slice silently testing against different plumbing is the single-implementation seam in fixture form.

When the root conftest outgrows a couple of screens, split it into fixture modules registered as plugins — `pytest_plugins = ["testing.db", "testing.transports"]` in the root conftest, modules in a top-level `testing/` package. pytest permits `pytest_plugins` only in the rootdir conftest, which forces the wanted shape anyway: substrate deep and singular, everything below flat. Shipped artifacts exclude tests at build time (`test_*.py`, `**/tests`); nothing at runtime imports them regardless.

If an organization mandates tests outside `src/`, the sanctioned deviation is a mirror of the slice tree — `tests/features/{family}/{verb_noun}/` — under three conditions: the mirror follows slices, never roles (`tests/routers/`, `tests/unit/` is the layered regression in test clothes); CI enforces the slice↔mirror bijection (a `diff` of the two directory listings, failing on orphans); and the substrate conftest moves to `tests/conftest.py`, with an added import-linter independence contract over `tests.features.*.*` to replace the sibling-import protection co-location gives for free.

## The Fixture Recipe

```python
# conftest.py — project root, on the discovery path of every co-located slice test
from collections.abc import AsyncGenerator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from src.database import get_db
from src.main import app
from src.models import Base

@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        yield pg.get_connection_url()

@pytest.fixture(scope="session")
async def engine(pg_url: str) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:  # dependency-ordered wipe beats schema recreation
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session

@pytest.fixture
async def client(
    engine: AsyncEngine, db_session: AsyncSession
) -> AsyncGenerator[AsyncClient, None]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        async with maker() as session:
            yield session
    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

The two scopes in the recipe pay for different things. `pg_url`/`engine` are session-scoped: one container, one schema creation, for the entire test run — starting Postgres is the slow part, and nothing about test isolation requires paying it more than once. `db_session` is function-scoped: it wipes every table before yielding, so each test starts from empty without a second container boot. `client` depends on both `engine` and `db_session` so the app's connection pool and the assertion session are backed by the same wiped state, not two independently-provisioned views of the database.

Pytest config needs all three settings together — `asyncio_mode` alone is not enough for this conftest:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

The session-scoped `engine` and every test that uses it must share one event loop: asyncpg futures bind to the loop that created them, so under pytest-asyncio's own defaults — session-scoped fixtures on a session-scoped loop, each test function on its own loop — the engine built in `engine`'s loop gets awaited from a different one, and the very first test fails with "Future attached to a different loop". Pinning `asyncio_default_fixture_loop_scope` and `asyncio_default_test_loop_scope` to `"session"` together is what closes that gap. Inside a test, setup, execute, and verify still stay in **separate committed units of work** — a fixture and a handler call sharing one open transaction hides exactly the bugs production would hit, because production never gets that shared transaction either. That is also why the recipe wipes tables instead of wrapping each test in a rolled-back transaction: the faster, common alternative buys its speed by never committing, so commit-time failures — constraint enforcement, `expire_on_commit` surprises — stay invisible until production. `db_session`'s wipe-and-yield shape keeps setup and verification each honest about what actually persisted. No in-memory substitute: SQLite is not Postgres — different constraint enforcement, different JSON handling, different transaction semantics — and a slice that passes against SQLite and fails against Postgres is exactly the gap this doctrine exists to close.

**Subscriber handlers open their own sessions.** Per references/cross-feature-communication.md § Subscriber Slice Anatomy, a subscriber handler calls `session_factory()` itself rather than taking `db` from `Depends(get_db)` — there's no HTTP request for the base recipe's `dependency_overrides` to attach to, so `client`/`db_session` never reach it. A test calling such a handler directly needs its own patch:

```python
# conftest.py (root) — appended fixture, only needed by subscriber slices that open their own session
from collections.abc import Callable

@pytest.fixture
def patch_subscriber_session(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], None]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    def _patch(target: str) -> None:
        monkeypatch.setattr(target, maker)
    return _patch
```

Call it with the dotted path to `session_factory` **as imported into the handler's own module** — `patch_subscriber_session("src.features.notifications.notify_new_message.handler.session_factory")` — never `src.database.session_factory`. `from src.database import session_factory` binds a name in the handler module's own namespace at import time; patching the attribute on `src.database` afterward never touches that already-bound name, because the handler looks `session_factory` up in its own module's globals at call time, not through `src.database` again. Patching the importer, not the source, is what actually redirects the handler to the test database.

## The Three Assertions

Every slice test asserts in three places, not one — matching references/cross-feature-communication.md's Testing Both Channels list, generalized to any slice rather than only ones with cross-feature effects:

1. **The response.** Status code and body the caller receives back from `client`.
2. **Persisted state, read in a fresh scope.** Not the object still attached to whatever session the handler used — a separate read via `db_session`, proving the write reached the database rather than living only in an ORM identity map or an uncommitted transaction.
3. **The outbox row, when the slice emits.** Query `OutboxMessage` via `db_session` for the expected `event_type`. A slice with no emission skips this assertion; a slice that emits and is never checked on it has an unverified side effect.

```python
resp = await client.post("/orders/1/cancellation")
assert resp.status_code == 200                          # 1: the response

order = await db_session.get(Order, 1)
assert order.status == OrderStatus.CANCELLED             # 2: persisted state, fresh scope

row = (await db_session.execute(
    select(OutboxMessage).where(OutboxMessage.event_type == "OrderCancelled")
)).scalar_one_or_none()
assert row is not None                                    # 3: the outbox row
```

A handler that returns the right response but never wrote the row, or wrote the row but never emitted the event, passes assertion one and fails silently on the ones that matter. Canonical worked test carrying all three: references/example-orders-backend.md.

## Per-Entry-Point Recipes

**HTTP.** `await client.post("/orders", json={...})` — or `get`/`patch`/`delete` as the route demands — against the `client` fixture; assert `.status_code` and `.json()`, then The Three Assertions' second and third points via `db_session`.

**WebSocket.** `httpx-ws`'s `aconnect_ws` needs a client built on `httpx_ws.transport.ASGIWebSocketTransport` — the base recipe's `ASGITransport` can't complete a WebSocket handshake, so `client` itself doesn't work here. A dedicated fixture supplies the right transport, wired the same way `client` wires `ASGITransport`:

```python
# conftest.py (root) — appended fixture, only needed by WebSocket entry points
from httpx_ws.transport import ASGIWebSocketTransport

@pytest.fixture
async def ws_client(
    engine: AsyncEngine, db_session: AsyncSession
) -> AsyncGenerator[AsyncClient, None]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        async with maker() as session:
            yield session
    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

```python
from src.realtime import registry  # plumbing, like any slice touching the socket registry

async with aconnect_ws("/conversations/1/stream", ws_client) as ws:
    await registry.send_to_conversation(1, {"type": "message", "text": "hi"})
    frame = await ws.receive_json()
assert frame["text"] == "hi"
```

Starlette's `TestClient.websocket_connect` (sync) is the alternative SKILL.md's Precedence 1 leaves open; pick one per project and stay consistent — framework usage is a project standard, not a per-slice choice.

**Subscribers.** No transport, no relay loop, no polling. Construct the event dataclass directly and call the handler — `await release_reservation(OrderCancelled(order_id=order.id))` — then assert the effect via `db_session`. Routing an event through the outbox and waiting for `relay()` to dispatch it tests the relay, not the handler; the event is the contract, so the test starts at the contract. The handler opens its own session rather than taking `db_session`'s, so the test also takes `patch_subscriber_session` (the fixture recipe above) to point that session at the test database.

## Case Coverage per Slice

Every slice's test file covers three cases, no fewer:

1. **Happy path.** The use case succeeds; The Three Assertions apply in full.
2. **Each domain failure the slice can trigger.** One test per `DomainError` subclass the handler's `domain/` call can raise — e.g. `InvalidTransition` asserts a 409 (references/shared-code.md's mapping) and that no state changed.
3. **One invalid-request case**, proving request validation is actually wired to the route — a malformed body returns 422. This is not exhaustive: every schema-level validation rule (field bounds, enum membership, format checks) belongs at the unit level against the Pydantic model or the `domain/` value object it defers to, never repeated per slice against the live app.

Past that floor, a fourth case is earned the way a file is: a boundary the handler itself owns, a concurrency hazard, a second failure branch. Two growth patterns stay smells: re-proving schema validation through the live app (the unit level's job, per case 3), and a test count climbing because the slice quietly hosts two use cases — split the slice, not the test file.
