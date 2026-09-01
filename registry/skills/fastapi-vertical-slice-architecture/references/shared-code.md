# Shared Code

**Contents:** The Three Destinations · Push-Down · The Wrong Fix, Beside the Right One · What `domain/` Purity Means · When `shared/` or `utils.py` Appears Anyway

What leaves a slice, and where it lands. SKILL.md states the rules — Rule 6 (slice-internal decomposition is free), Rule 7 (push-down on a rule's second appearance), Rule 8 (domain purity). This file is the judgment calls underneath them: when code stops being one slice's business, which of three destinations it goes to, and why the wrong destination looks so tempting.

## The Three Destinations

Every candidate for "shared" resolves to exactly one of three places — there is no fourth.

**A business rule → `domain/`.** A calculation, a validation, a state transition that more than one slice must agree on becomes a pure function or value object in `domain/`. It takes primitives and enums in, returns primitives and enums out, and answers to nothing outside itself.

**Mechanics → the pipeline.** Cross-cutting technical concerns — auth, request logging, pagination, a DB session — are not business knowledge and don't belong in `domain/` either. They're middleware or a `Depends()` dependency, wired once and registered in `main.py`, and every slice picks them up by being on the pipeline.

**Anything else → duplicate deliberately.** A query shape, a small mapping, a formatting helper that only resembles another slice's version — write it again. Two call sites with independent futures is cheaper than one call site two teams are afraid to change. The moment two copies must agree — an edit to one is a bug until it reaches the other — the thing was a rule all along, and Rule 7 moves it to `domain/`.

## Push-Down

The trigger is a rule's *second* appearance: the same policy, written independently in two places, where one policy change would require editing both sites. That's Rule 7. First appearance stays put — inline in the slice that needs it. Second appearance moves to `domain/`. The exception is a genuine invariant — money rounding, a legal rule — which goes to `domain/` on first sight, because a single wrong instance is already a bug, not a duplication risk waiting to happen.

Lead case: an order's legal status, checked inline in two unrelated handlers.

```python
# BEFORE — the same policy inline in two handlers (Rule 7 trigger)
# features/orders/cancel_order/router.py
if order.status not in (OrderStatus.PENDING, OrderStatus.PAID):
    raise HTTPException(409, "cannot cancel")
# features/billing/process_payment/handler.py
if order.status is not OrderStatus.PENDING:
    raise HTTPException(409, "cannot pay")
```

```python
# AFTER — the machine, declared once in domain/order.py
from enum import StrEnum

from .errors import DomainError

class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    DECLINED = "declined"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.PAID, OrderStatus.DECLINED, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DECLINED: frozenset(),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

class InvalidTransition(DomainError):
    def __init__(self, current: OrderStatus, to: OrderStatus) -> None:
        super().__init__(f"cannot go {current} -> {to}")

def transition(current: OrderStatus, to: OrderStatus) -> OrderStatus:
    """Return the new status if the move is legal; raise InvalidTransition otherwise."""
    if to not in _TRANSITIONS[current]:
        raise InvalidTransition(current, to)
    return to
```

Three things live at different addresses, and collapsing them is how the machine stops being pure. The **machine** — the states and the `_TRANSITIONS` table — is domain knowledge, declared once. The **triggers** — which use case calls `transition()` and when — are per-slice knowledge, distributed across `cancel_order`, `process_payment`, and anywhere else an order moves. The **consequences** — an event fired after a successful transition — are the calling slice's job, emitted after `transition()` returns, never inside it: `transition()` only ever answers "is this move legal," and never sends anything, writes anything besides its own return value, or knows an outbox exists. Outbox delivery mechanics: references/cross-feature-communication.md. No state-machine library earns its keep here — this is twenty lines of plain data and one guard function; a project already committed to one keeps its own idiom (Precedence 2).

`DomainError` is the project's base exception, defined once in `domain/errors.py` — `InvalidTransition` above subclasses it, and so does `InvalidAddress` below. Rule 8 is what puts it there: a rule declared in `domain/order.py` raises it, so a `DomainError` living in `src/exceptions.py` would force `domain/` to import from `src` — the one import the rule exists to catch. `domain/order.py` reaches it with a relative `from .errors import DomainError`; an absolute `from src.domain.errors import ...` would trip Rule 8's own grep for `from src.` while breaking nothing, so inside `domain/` the relative form is the one to write. The HTTP mapping stays outside `domain/`: `src/exceptions.py` keeps `NotFound` and the global handlers, importing `DomainError` from `domain/errors.py` to translate each subclass to a status — `InvalidTransition` maps to 409. That import runs in the sanctioned direction, the same one `models.py` already takes for `OrderStatus`. Slices raise `DomainError` subclasses; they never construct an `HTTPException` for a rule `domain/` already owns.

## The Wrong Fix, Beside the Right One

Both diagnose the same symptom — address validation duplicated across two slices — and only one of them is a push-down.

```python
# WRONG — pull the procedure up into a horizontal layer
class AddressService:
    def validate_and_normalize(self, raw: dict) -> dict: ...
# every slice now couples to a bag of procedures

# RIGHT — push the rule down into a value object: domain/address.py
from dataclasses import dataclass
from typing import Self

@dataclass(frozen=True, slots=True)
class Address:
    country: str
    postal_code: str
    city: str

    @classmethod
    def parse(cls, raw: "AddressIn") -> Self:
        if raw.country not in COUNTRY_CODES:
            raise InvalidAddress("country")
        if not ZIP_SHAPES[raw.country].match(raw.postal_code):
            raise InvalidAddress("postal_code")
        return cls(raw.country, raw.postal_code, raw.city.strip().title())
```

`AddressIn` is the calling slice's request schema, named only by forward reference — `domain/` never imports a slice's `schemas.py`, which is why the annotation is a string. `InvalidAddress` is a `DomainError` subclass, mapped to HTTP the same way `InvalidTransition` is. Neither name has to exist in this file for the block to parse or the point to land.

The tell is what each fix asks slices to depend on. `AddressService` is a procedure bag — calling it couples a slice to a class with a lifecycle, a constructor, and every other method riding along for the next feature someone bolts on. `Address.parse()` is a concept both slices already depend on — an address, valid or not — expressed as a value with no service wrapped around it. Down is a concept both slices already depend on; up is a procedure bag every slice newly couples to. When a "push-down" produces a class with `Service` in the name, it went up instead.

## What `domain/` Purity Means

Rule 8: `domain/` imports nothing from `src` — no session, no models, no features. `HTTPException` is a separate line, held for a separate reason: it comes from `fastapi`, not `src`, so no import rule catches it — `domain/` still never raises one, because a rule it owns answers in a `DomainError` subclass and the pipeline maps that to a status (above). In practice:

- Every parameter and return value is a primitive, a stdlib type, an enum, or another `domain/` value object — never a SQLAlchemy model, a Pydantic schema, or a slice's own type.
- Every function is exhaustively unit-testable with no fixtures — no DB, no app, no `TestClient`. `transition(OrderStatus.PENDING, OrderStatus.PAID)` runs standalone in a bare `pytest` process.
- The direction is one-way. `models.py` **may** import from `domain/` — `Mapped[OrderStatus]` backing a column is exactly what the enum is for — and `src/exceptions.py` takes that same direction when it imports `DomainError` to map its subclasses to statuses. `domain/` never imports back from `models.py` or `exceptions.py`, and never will; that import is the one this rule exists to catch.

`domain/order.py`, `domain/address.py`, `domain/errors.py`, and `domain/events.py` hold this line for every concept the project accumulates. A module that fails any of the three is not a `domain/` resident yet, whatever folder it currently sits in.

## When `shared/` or `utils.py` Appears Anyway

A `shared/` folder or a `utils.py` is always a routing failure, not a fourth destination — every symbol inside it already belongs somewhere. Refile it:

| Found inside | Belongs in |
| --- | --- |
| A rule used by two or more slices | `domain/` — this is Rule 7 firing late |
| Cross-cutting technical mechanics | The pipeline — middleware or a `Depends()` in `main.py` |
| Code with exactly one consumer | Inline into that slice — Rule 6 territory, not a shared file |
| None of the above | Delete it — nothing references it for a reason |

The single-consumer row is the one teams resist: a helper sitting in `shared/` because it *might* serve a second slice someday is still Rule 6's problem, not this table's. Slice-internal decomposition is free — move it into the slice, as `handler.py` or `repository.py` if it earns the split, and let the next real second consumer be the one that triggers push-down.
