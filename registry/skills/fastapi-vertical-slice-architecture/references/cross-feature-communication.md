# Cross-Feature Communication

**Contents:** The Decision Table · Channel 1: Same-Transaction Write · Channel 2: Outbox Events · Subscriber Slice Anatomy · Testing Both Channels · Anti-Pattern Gallery

How features affect each other at runtime — the three channels, the outbox machinery that makes the second one safe, and the shapes that only look like a fourth channel. Where shared code should *live* (domain/, the pipeline, deliberate duplication) is references/shared-code.md's question; this file answers what a slice does across a family boundary while the request or event is in flight. Rule 9 names the constraint: cross-feature effects use only these three channels, and no others — everything below either is one of the three or explains why the thing that looks like a fourth is really one of them in disguise.

## The Decision Table

SKILL.md § Cross-Feature Effects holds the four-row decision table; this section expands each row with the reasoning that makes its answer the only correct one. Three rows are channels. The fourth is not — "use a sibling slice's logic" is the need that tempts a sibling import, and its answer routes back into the first three: push the logic down, or duplicate the query. There is no separate mechanism for it.

**Change another family's entity state.** The entity — `Order` — is a shared model; every family that legally moves it already has ORM access to it. What it may not do is invent its own rule for which moves are legal — that's `transition()`, declared once in `domain/order.py` (references/shared-code.md). Billing loads the order, calls the shared transition rule, and writes the new status in the same `db.commit()` as its own payment row. No message crosses a process boundary because none needs to: one session already touches everything the operation changes. The transaction boundary is the `AsyncSession`'s commit, not a family boundary — a family only ever owns the *rule* for its own entity's transitions, never exclusive write access to the row.

**Read another family's data.** Shipping needs the order's address. It does not call into `orders`' code to get it — it runs its own `select(Order.address_json).where(...)` against the shared model, in `shipping`'s own slice. The query is small, it drifts independently of whatever `orders` does with the same column, and duplicating it costs a few lines against a coupling that would otherwise survive both features' whole lifetime. This differs from a sibling import in kind, not just in size: a duplicated query creates no compile-time dependency on `orders`' code at all — `shipping` depends on the shared `Order` model, exactly as `orders` itself does, and neither family can break the other's build.

**Trigger a consequence another family owns.** Cancelling an order needs inventory released — but `orders` has no business knowing `inventory` has reservations, let alone how one is structured. `orders` emits `OrderCancelled`; `inventory` subscribes to it and does whatever "release" means, entirely on its own schedule. The event names a fact that already happened (`OrderCancelled`), never a command (`ReleaseReservation`) — naming it as a command is what turns this channel into the orchestration Rule 9 forbids.

**Use a sibling slice's logic.** Two slices independently need to validate an address. Neither may import the other's `handler.py` (Rule 4) or its `schemas.py` (Rule 5) to get there. If the shared thing is a rule — a calculation, a validation — it goes to `domain/` as a pure function or value object (Rule 7, references/shared-code.md's push-down). If the shared thing is a query shape or a mapping, it is not a rule at all, and the fourth row's answer is the third row's answer restated: duplicate it, per Channel 1's sibling-import example below.

## Channel 1: Same-Transaction Write

```python
# features/billing/process_payment/handler.py
from src.database import AsyncSession
from src.domain import order as order_rules
from src.domain.events import PaymentDeclined
from src.domain.order import OrderStatus
from src.exceptions import NotFound
from src.models import Order, Payment
from src.outbox import emit
from src.payments_client import charge

async def process_payment(db: AsyncSession, order_id: int, card_token: str) -> Payment:
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFound("order")
    result = await charge(card_token)
    new_status = OrderStatus.PAID if result.ok else OrderStatus.DECLINED
    order.status = order_rules.transition(order.status, new_status)
    payment = Payment(order_id=order.id, amount=order.total, succeeded=result.ok)
    db.add(payment)
    if not result.ok:
        await emit(db, PaymentDeclined(order_id=order.id))
    return payment
```

The version this channel replaces — importing the sibling's use-case code — looks like this:

```python
# WRONG — use-case code imported across families (Rules 3, 4, 5)
from src.features.orders.cancel_order.handler import cancel_order
from src.features.orders.create_order.schemas import OrderResponse
```

Shared models and shared rules are the sanctioned surface; sibling use-case code never is. `billing` reaches `Order` and `order_rules.transition` — both live outside any slice — and never reaches into `orders/cancel_order/` for a function or a type. One session, one transaction: the payment row and the status change commit atomically, or neither does. There is no window where a `Payment` row exists against an order still `PENDING`, and no second call to fail into.

## Channel 2: Outbox Events

The problem this machinery solves: a family that both writes to its own table and publishes an event has two systems to agree with, and no single commit can span both. Publish after the database commit, and a crash in between loses the event with the database showing no trace anything is wrong. Publish before, and a rolled-back transaction has already told the world about a change that never happened. Either ordering has a failure window; the outbox removes it by making the event write the same kind of write as the row it announces — a row in the same database, in the same transaction, subject to the same commit and the same rollback. A separate loop (`relay`) reads that table and forwards to real subscribers on its own schedule, so the one hard part — "did this actually happen" — is answered by the database's own atomicity guarantee instead of by coordinating two systems.

```python
# domain/events.py — frozen dataclasses; names are the wire format
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class OrderCancelled:
    order_id: int

@dataclass(frozen=True, slots=True)
class PaymentDeclined:
    order_id: int
```

```python
# models.py — the outbox table lives beside the entities it commits with
class OutboxMessage(Base):
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str]
    payload: Mapped[str]  # JSON of the dataclass fields
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    delivered_at: Mapped[datetime | None]
```

```python
# src/outbox.py — emit, subscribe, relay: plumbing beside database.py
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.database import AsyncSession
from src.models import OutboxMessage

log = logging.getLogger(__name__)

type EventHandler = Callable[[Any], Awaitable[None]]

SUBSCRIBERS: dict[str, list[EventHandler]] = {}
EVENT_TYPES: dict[str, type] = {}

def subscribe(event_type: type, handler: EventHandler) -> None:
    EVENT_TYPES[event_type.__name__] = event_type
    SUBSCRIBERS.setdefault(event_type.__name__, []).append(handler)

async def emit(session: AsyncSession, event: Any) -> None:
    session.add(OutboxMessage(event_type=type(event).__name__,
                              payload=json.dumps(asdict(event))))

async def relay(
    session_factory: async_sessionmaker[AsyncSession], poll_interval: float = 0.5
) -> None:
    while True:
        async with session_factory() as session:
            rows = (await session.execute(
                select(OutboxMessage).where(OutboxMessage.delivered_at.is_(None))
                .order_by(OutboxMessage.id).limit(100)
                .with_for_update(skip_locked=True))).scalars().all()
            for row in rows:
                handlers = SUBSCRIBERS.get(row.event_type, [])
                try:
                    if handlers:
                        event = EVENT_TYPES[row.event_type](**json.loads(row.payload))
                        for handler in handlers:
                            await handler(event)
                except Exception:
                    log.exception("outbox delivery failed: id=%s type=%s", row.id, row.event_type)
                    continue  # row stays undelivered — the next poll retries it; the rest of the batch still commits
                row.delivered_at = datetime.now(UTC)
            await session.commit()
        await asyncio.sleep(poll_interval)
```

`emit()` does one thing: it `session.add()`s an `OutboxMessage` row. Emitting is inserting a row **in the same session** as the state change — not a second write, not a second transaction — so atomicity is structural: the event exists if and only if the change it announces committed. There is no code path where `PaymentDeclined` is emitted and the order never actually got declined, or vice versa.

`relay()` is in-process — started once, `asyncio.create_task(relay(session_factory))` in `main.py`'s lifespan, polling the `outbox` table and dispatching to whatever handlers `subscribe()` registered. Swapping the relay loop for a broker later (SQS, Kafka, whatever) changes `relay()`'s internals and nothing else: `emit()` still just inserts a row, `subscribe()` still just registers a handler, and every slice on both ends is untouched.

An event nobody subscribes to is not an error, which is why the loop checks `SUBSCRIBERS` before it touches `EVENT_TYPES`: with no handler registered, the row is marked delivered untouched and skipped — never reconstructed, never a `KeyError` that would kill the loop on every poll. That is what lets a family emit a fact before any consumer exists, exactly as `add_participant` emits `ParticipantAdded` with nothing subscribed to it yet (references/example-chat-backend.md).

Delivery is at-least-once: a crash between a handler returning and the batch's commit redelivers every still-undelivered row on the next poll. **Every subscriber is idempotent** — hard rule, in one of two shapes: a write that lands identically on redelivery (`release_reservation` below), or, when the effect leaves the process — a push, an email — a delivery log keyed by the business fact, checked before sending (worked in references/example-chat-backend.md). The per-row `try`/`except` is what keeps one failing handler from killing the loop or blocking its batch: the row that raised stays undelivered and retries next poll while the rest still commit. The `with_for_update(skip_locked=True)` lock is what lets a second relay instance poll the same table without double-dispatching. One limit stays open by design: a row whose handler always raises retries on every poll — production layers a retry cap or a dead-letter mark on top of this shape.

## Subscriber Slice Anatomy

```python
# features/inventory/release_reservation/subscriber.py — the entry point
from src.domain.events import OrderCancelled
from src.outbox import subscribe

from .handler import release_reservation

def register() -> None:
    subscribe(OrderCancelled, release_reservation)
```

```python
# features/inventory/release_reservation/handler.py
from sqlalchemy import select

from src.database import session_factory
from src.domain.events import OrderCancelled
from src.models import Reservation

async def release_reservation(event: OrderCancelled) -> None:
    async with session_factory() as db:
        reservation = (await db.execute(
            select(Reservation).where(Reservation.order_id == event.order_id)
        )).scalar_one_or_none()
        if reservation is None:
            return  # idempotent: nothing reserved, nothing to do
        reservation.released = True
        await db.commit()
```

`subscriber.py` is the event slice's entry point, standing in `router.py`'s place — it does exactly one thing, which is call `subscribe()` with the event type and the handler, and owns none of the use-case logic itself. `register()` is what the slice's `__init__.py` exports and what `main.py` calls during startup, alongside the family routers and the outbox relay: the subscriber counterpart of `include_router`. The idempotency the outbox's at-least-once delivery demands lives in `reservation.released = True`, not in the early return: the reservation row is never deleted, so a redelivered `OrderCancelled` finds the same row and sets the same field to the same value again — an assignment that lands identically whether it runs once or five times, which is what "check whether the consequence already happened" cashes out to here, structurally rather than by an explicit check. The `if reservation is None: return` guard covers a different case entirely — an event naming an order nothing was ever reserved against — not redelivery; on an actual redelivery `reservation` is never `None`, so that branch never even runs.

Notice `release_reservation` opens its own session with `session_factory()` instead of taking `db: AsyncSession` from `Depends(get_db)`. There is no HTTP request here for FastAPI's dependency injection to attach to — `relay()` calls the handler directly, so the handler is responsible for its own session, exactly as `relay()` itself is. This is the one place event-slice handlers and HTTP-slice handlers structurally differ; everything else about the slice — one folder, its own test, no sibling imports — is identical.

Channel 1 and Channel 2 are not alternatives picked once per operation — most non-trivial handlers use both. `process_payment` above transitions the order (Channel 1) and, on the declined branch, emits `PaymentDeclined` (Channel 2) in the same function, the same session, the same commit. The two channels compose because they're really one write with two effects: the row that changes state, and the row that announces it.

## Testing Both Channels

Both channels are exercised the same way every other slice is: through its public entry point, against a real test database, never by mocking the session. The difference from a single-slice test is what gets asserted afterward — a cross-feature effect leaves evidence in a second place (a status column, an outbox row, a downstream handler's own writes), and the test asserts that evidence, not just the immediate response. Full fixtures and per-entry-point recipes: references/slice-testing.md. The shapes:

- **Channel 1 (same-transaction write).** Drive it through the HTTP entry point with the `client` fixture, then assert twice: the response the caller sees, and — via `db_session` — that the affected row (the order's `status` column) actually changed. A handler that returns the right response but never wrote the row is still a bug.
- **Emission.** Trigger the call that should emit, then query the `outbox` table with `db_session` and assert a row with the expected `event_type` exists. This tests that the slice emitted — it does not exercise the relay loop or any subscriber.
- **Subscription.** Never go through the outbox to test a subscriber. Construct the event dataclass directly and call the handler with it — `await release_reservation(OrderCancelled(order_id=order.id))` — then assert the effect. No transport, no relay, no polling: the event is the contract, and the handler's test proves the handler, not the delivery mechanism.

## Anti-Pattern Gallery

Every row below is a way of reaching for a fourth channel that doesn't exist, or of misusing one of the three well enough to recreate the coupling they exist to prevent. Each is greppable or lintable — most are the concrete "find a breach by" moves for Rule 9 and its neighbors, spelled out.

| Symptom | Why it fails | Fix |
| --- | --- | --- |
| Sibling import (`from src.features.orders...handler import cancel_order`) | The importing slice stops being deletable on its own; the law's first half breaks directly | Push the shared piece to `domain/` (rule) or duplicate it (query/mapping) — Rule 4 |
| Self-HTTP call from a handler | A network hop, a second transaction, and a retry story bought to reach code already running in the same process | Same-transaction write against the shared model, or an outbox event if the effect belongs to another family |
| Reusing a sibling's `schemas.py` type | Two features now release on one contract's schedule; a field either slice needs breaks the other | Each slice defines and owns its own request/response types — Rule 5 |
| Event-as-RPC — emit, then wait for the subscriber's result | The outbox is fire-and-forget by design; blocking on a subscriber turns an async, decoupled channel into a synchronous call with extra steps and no return path | If the caller needs the result now, it's Channel 1 (same transaction) or Channel 2 (own query), not an event |
| Saga-in-a-monolith — events chaining one synchronous use case across families | Control flow hides in a chain of handlers instead of living in one readable function; a mid-chain failure has no natural transaction boundary | One use case spanning families is one slice, one transaction, in the family that owns the capability (Never list: events as orchestration) |
| `BackgroundTasks` for a business consequence | The process can die after the response ships and before the task runs — the consequence is silently lost, with no row anywhere recording it should have happened | Outbox event: the row committed in the same transaction as the state change is what makes the consequence durable |
| Transition side effects inside the state machine | `transition()` stops being answerable by "is this move legal" alone, and stops being unit-testable without a session | Emit the outbox event in the calling slice, after `transition()` returns successfully — references/shared-code.md |
| Status checks duplicated in handlers | The same legality check, maintained independently in two slices, drifts the moment one gets edited and the other doesn't | Push down to the `domain/` transition table on the second appearance — Rule 7 |
| Per-slice status enums | Each slice's private notion of "is this order still changeable" disagrees with every other slice's, and nothing catches the disagreement until data corrupts | One `OrderStatus` in `domain/order.py`, referenced everywhere the concept applies — references/shared-code.md |
| Data-neediness — a handler reaching into many of another family's entity fields per operation | The dependency isn't a rule or a single field read; it's the shape of a whole concept that family doesn't actually own | The slice belongs in the family whose data it needs, or an unnamed domain concept needs naming and moving to `domain/` |
