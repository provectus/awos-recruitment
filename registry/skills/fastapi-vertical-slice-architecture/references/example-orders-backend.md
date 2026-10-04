# Example: Orders Backend

**Contents:** Project Tree · Three Families, One Machine · A Write Slice: cancel_order · A Read Slice: get_order · The Event Consequence · The Canonical Slice Test · Push-Down in This Project

A full realization of the structure SKILL.md's Form 2 sketches — real, runnable code for one project: an e-commerce order backend. Every code block below is an excerpt from that one coherent project; the comment on its first line names the file it lives in. Roles — entry point, feature handler, contracts — are SKILL.md's Slice Roles table; this file assigns them across six slices — five behind HTTP routes, one behind a subscriber — instead of redefining them. The state machine (`OrderStatus`, `_TRANSITIONS`, `transition()`) is defined once in references/shared-code.md and only *used* here; the outbox (`emit()`, `subscribe()`, `relay()`) is defined once in references/cross-feature-communication.md and only *used* here. Test fixtures (`client`, `db_session`) are defined once in references/slice-testing.md and only *used* here. Every Python block in this file is the code a reader would find in the slice named in its header comment — not pseudocode, not an excerpt with the awkward parts trimmed.

## Project Tree

```text
src/
├── features/
│   ├── orders/
│   │   ├── create_order/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # handler inline — one readable function
│   │   │   ├── schemas.py
│   │   │   └── test_create_order.py
│   │   ├── cancel_order/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # thin entry point — calls the handler
│   │   │   ├── handler.py               # earned: load, transition, OrderCancelled emit — past a screen
│   │   │   ├── schemas.py
│   │   │   └── test_cancel_order.py
│   │   ├── get_order/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # five lines, forever — asymmetry is correct
│   │   │   └── test_get_order.py        # no schemas.py — the read model is inline in router.py
│   │   └── router.py                    # three include_router lines
│   ├── billing/
│   │   ├── process_payment/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # thin entry point — calls the handler
│   │   │   ├── handler.py               # earned because: charge, order transition, payment row — three concerns past a screen
│   │   │   ├── schemas.py
│   │   │   └── test_process_payment.py
│   │   └── router.py                    # one include_router line
│   ├── inventory/
│   │   └── release_reservation/         # no family router — this family has no HTTP surface
│   │       ├── __init__.py
│   │       ├── subscriber.py            # entry point is OrderCancelled, not a route
│   │       ├── handler.py
│   │       └── test_release_reservation.py   # no schemas.py — the event is the contract
│   └── fulfillment/
│       ├── ship_order/
│       │   ├── __init__.py
│       │   ├── router.py                # handler inline — the smallest transition-firing slice
│       │   ├── schemas.py
│       │   └── test_ship_order.py
│       └── router.py                    # one include_router line
├── domain/
│   ├── order.py                         # OrderStatus, _TRANSITIONS, transition(), InvalidTransition
│   ├── address.py                       # Address.parse() value object
│   ├── errors.py                        # DomainError base — subclassed in order.py, address.py
│   └── events.py                        # OrderCancelled, PaymentDeclined — nothing else
├── models.py                            # Order, OrderLine, Payment, Reservation, OutboxMessage
├── database.py                          # engine, session factory, get_db, DbSession
├── outbox.py                            # emit, subscribe, relay — references/cross-feature-communication.md
├── payments_client.py                   # thin PSP client — the sanctioned stub seam
├── config.py                            # BaseSettings
├── exceptions.py                        # NotFound + global handlers — DomainError from domain/errors.py
└── main.py                              # app init, family routers, subscribers, outbox relay
```

Six slices — five HTTP, one subscriber — and the shapes they earned:

- `create_order`, `get_order`, `ship_order` stay one file each. `get_order` forever: a read has no invariant to enforce, so nothing exists for a `handler.py` to earn (§ A Read Slice, below).
- `cancel_order` and `process_payment` split into `router.py` + `handler.py`: their orchestration — load, transition, emit; charge, transition, record — outgrows what belongs in transport wiring.
- No slice earned a `repository.py`: no query here serves two code paths inside its own slice (Rule 6's threshold, the only thing that puts the file there) — "earned, not scaffolded" holding across a whole project, not a gap in the example.
- `domain/` holds exactly four modules: `order.py`, the machine, and `address.py`, the value object (both worked in references/shared-code.md); `errors.py`, the `DomainError` base — in `domain/` rather than `src/exceptions.py` because a rule in `domain/order.py` raises it, and `src/exceptions.py` imports it back for the status mapping; and `events.py` — two events, no more, because nothing else in this project has a subscriber.
- `inventory` carries no family router: `release_reservation` is its only slice, and its entry point is `OrderCancelled`, not a route (§ The Event Consequence, below).

## Three Families, One Machine

One `transition()` in `domain/order.py`, called from three families, guarding three different moves:

| Slice | Transition fired |
| --- | --- |
| `cancel_order` | → `CANCELLED` |
| `process_payment` | → `PAID` / `DECLINED` |
| `ship_order` | → `SHIPPED` |

`process_payment`'s call is worked in full in references/cross-feature-communication.md § Channel 1 — it is the slice that pairs a transition with an outbox emission in the same commit. `cancel_order`'s is below (§ A Write Slice). `ship_order`'s is the smallest of the three: no split earned, no event fired, the whole slice in one file:

```python
# features/fulfillment/ship_order/router.py — entry point and feature handler in one
from fastapi import APIRouter, status

from src.database import DbSession
from src.domain import order as order_rules
from src.domain.order import OrderStatus
from src.exceptions import NotFound
from src.models import Order

from .schemas import ShipOrderResponse

router = APIRouter()

@router.post(
    "/orders/{order_id}/shipment",
    response_model=ShipOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ship_order(order_id: int, db: DbSession):
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFound("order")
    order.status = order_rules.transition(order.status, OrderStatus.SHIPPED)
    return ShipOrderResponse(order_id=order.id, status=order.status)
```

Three families, one call to `order_rules.transition()` each, three different legal moves out of `_TRANSITIONS` — that table, declared once in references/shared-code.md, is what keeps `cancel_order` and `ship_order` from ever disagreeing about whether a `SHIPPED` order can still be cancelled. Nothing in `ship_order` — or in any of the three — knows the table's shape; each just asks it a question and acts on the answer.

## A Write Slice: cancel_order

The write path SKILL.md's Slice Roles table describes in full: `router.py` is a thin entry point, `handler.py` earns its split because the orchestration — load, transition, emit, respond — outgrows what belongs in transport wiring, and `schemas.py` holds a request and response neither other slice will ever import (Rule 5). `POST /orders/{order_id}/cancellation` returns `200`, not `201` — nothing is created, an existing order changes state.

```python
# features/orders/cancel_order/router.py — entry point only
from fastapi import APIRouter, status

from src.database import DbSession

from .handler import cancel_order
from .schemas import CancelOrderRequest, CancelOrderResponse

router = APIRouter()

@router.post(
    "/orders/{order_id}/cancellation",
    response_model=CancelOrderResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_order_route(order_id: int, body: CancelOrderRequest, db: DbSession):
    return await cancel_order(db, order_id, body.reason)
```

```python
# features/orders/cancel_order/handler.py — earned: past transport concerns
from src.database import AsyncSession
from src.domain import order as order_rules
from src.domain.events import OrderCancelled
from src.domain.order import OrderStatus
from src.exceptions import NotFound
from src.models import Order
from src.outbox import emit

from .schemas import CancelOrderResponse

async def cancel_order(db: AsyncSession, order_id: int, reason: str) -> CancelOrderResponse:
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFound("order")
    order.status = order_rules.transition(order.status, OrderStatus.CANCELLED)
    await emit(db, OrderCancelled(order_id=order.id))
    return CancelOrderResponse(order_id=order.id, status=order.status)
```

```python
# features/orders/cancel_order/schemas.py
from pydantic import BaseModel, Field

from src.domain.order import OrderStatus

class CancelOrderRequest(BaseModel):
    reason: str = Field(min_length=1)

class CancelOrderResponse(BaseModel):
    order_id: int
    status: OrderStatus
```

`reason` arrives in the request and stops at the handler boundary — nothing in this project's `models.py` persists it. That is a deliberate cut, not an oversight: SKILL.md's "Earned, not scaffolded" applies to fields exactly as it applies to files — a `cancellation_reason` column, and whatever endpoint would read it back, earns its place the day something actually needs it, not before.

Deliberately absent, and why:

- **No `repository.py`.** The single `db.get(Order, order_id)` query doesn't recur elsewhere in this slice — Rule 6's threshold ("a query serves multiple code paths") is never met.
- **No mapping layer.** `CancelOrderResponse(order_id=order.id, status=order.status)` is the whole translation; a separate mapper would be a pass-through split across two files (Rule 6).
- **No transaction code.** `get_db` commits once per request; the slice never opens or commits a session itself.
- **No event-delivery code.** `emit()` inserts the outbox row and returns; forwarding it to `inventory` is `relay()`'s job, not this slice's (references/cross-feature-communication.md § Channel 2).

## A Read Slice: get_order

The whole slice, one file, forever:

```python
# features/orders/get_order/router.py — the whole slice
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from src.database import DbSession
from src.domain.order import OrderStatus
from src.exceptions import NotFound
from src.models import Order, OrderLine

router = APIRouter()

class OrderView(BaseModel):
    id: int
    status: OrderStatus
    total: int
    line_count: int

@router.get("/orders/{order_id}", response_model=OrderView)
async def get_order(order_id: int, db: DbSession):
    row = (await db.execute(
        select(Order.id, Order.status, Order.total, func.count(OrderLine.id).label("line_count"))
        .join(OrderLine, isouter=True).where(Order.id == order_id)
        .group_by(Order.id))).one_or_none()
    if row is None:
        raise NotFound("order")
    return OrderView(id=row.id, status=row.status, total=row.total, line_count=row.line_count)
```

No domain model loaded — a read has no invariant to enforce; the view type is this slice's read model, never shared with `cancel_order` (Rule 5).

## The Event Consequence: inventory/release_reservation

Cancelling an order needs a reservation released — but `orders` has no business knowing `inventory` has reservations, let alone how one is structured or when it's safe to let go of the parts behind it. `cancel_order`'s handler above does exactly one thing on that front: transition the order and emit `OrderCancelled`. What happens to reserved inventory afterward is entirely `inventory`'s call, on `inventory`'s own schedule — the rule "parts are released when an order is cancelled" is knowledge `inventory` owns, not knowledge `orders` should be trusted to enforce on `inventory`'s behalf. That ownership is exactly why the family has no `router.py`: the subscriber, the handler, and the idempotency shape (`reservation.released = True` landing identically whether a redelivery runs it once or five times) are worked in full in references/cross-feature-communication.md § Subscriber Slice Anatomy — this project's `release_reservation` is that code, unmodified.

## The Canonical Slice Test

`cancel_order`'s test, using the `client` and `db_session` fixtures from references/slice-testing.md, carries all three of that file's required assertions in one function — the response, the persisted state read in a fresh scope, and the emitted outbox row:

```python
# features/orders/cancel_order/test_cancel_order.py
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.order import OrderStatus
from src.models import Order, OutboxMessage

async def test_cancels_a_paid_order(client: AsyncClient, db_session: AsyncSession):
    order = Order(status=OrderStatus.PAID, total=5000)
    db_session.add(order)
    await db_session.commit()  # setup: its own committed unit of work

    resp = await client.post(f"/orders/{order.id}/cancellation", json={"reason": "changed mind"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"                      # 1. the response
    fresh = await db_session.get(Order, order.id)
    await db_session.refresh(fresh)
    assert fresh.status == OrderStatus.CANCELLED                     # 2. persisted state
    outbox = (await db_session.execute(select(OutboxMessage))).scalars().all()
    assert any(m.event_type == "OrderCancelled" for m in outbox)     # 3. the emitted event
```

The domain-failure case belongs to a different slice — `ship_order`, rejecting a shipment attempt against an order that never got paid. This is references/slice-testing.md's second required case per slice (one test per `DomainError` subclass the handler's `domain/` call can raise): `transition()` raises `InvalidTransition`, the global handler maps it to `409`, and the order's `status` column is left untouched.

```python
# features/fulfillment/ship_order/test_ship_order.py — the domain-failure case
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.order import OrderStatus
from src.models import Order

async def test_rejects_shipping_an_unpaid_order(
    client: AsyncClient, db_session: AsyncSession
):
    order = Order(status=OrderStatus.PENDING, total=5000)
    db_session.add(order)
    await db_session.commit()

    resp = await client.post(f"/orders/{order.id}/shipment")

    assert resp.status_code == 409  # InvalidTransition -> 409 via the global handler
    fresh = await db_session.get(Order, order.id)
    await db_session.refresh(fresh)
    assert fresh.status == OrderStatus.PENDING  # no state change
```

## Push-Down in This Project

`create_order` is the one slice here that needs an `Address` — a customer's shipping address, parsed and validated from the request body before an `Order` row is written. It calls `Address.parse(raw)` from `domain/address.py`, the value object references/shared-code.md builds in its § The Wrong Fix, Beside the Right One worked example — the RIGHT half of that comparison, pushing address validation down into a value object instead of pulling it up into an `AddressService`. Nothing about the rule differs by being deployed in this project instead of that file's illustration; restating `Address.parse()`'s body here would be the second copy Rule 7 exists to prevent, so `create_order/router.py` calls it exactly as references/shared-code.md's RIGHT block defines it, and no more.
