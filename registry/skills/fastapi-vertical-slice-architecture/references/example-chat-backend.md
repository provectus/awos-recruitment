# Example: Chat Backend

**Contents:** Project Tree · Participant Rules · The Emitting Slice: send_message · The Third Transport: stream_messages · Fan-Out: One Event, Two Subscriber Families · Testing This Project

A second full realization of SKILL.md's Form 2 — a chat backend, nothing e-commerce about it. Where references/example-orders-backend.md proves the template for a state-machine-heavy request/response domain, this project exercises what that one can't: three transports (HTTP, a `@router.websocket` stream, subscribers), one event fanning out to two subscriber families, and a family — `notifications` — that is nothing but a consequence of another family's write. The outbox and the test fixtures (`client`, `db_session`, `ws_client`, `patch_subscriber_session`) are defined once in references/cross-feature-communication.md and references/slice-testing.md and only *used* here. Every Python block below is the code a reader would find in the slice named in its header comment.

## Project Tree

```text
src/
├── features/
│   ├── conversations/
│   │   ├── create_conversation/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # handler inline — one readable function
│   │   │   ├── schemas.py
│   │   │   └── test_create_conversation.py
│   │   ├── add_participant/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # handler inline — emits ParticipantAdded, no subscriber yet
│   │   │   ├── schemas.py
│   │   │   └── test_add_participant.py
│   │   ├── get_conversation/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # five lines, forever — calls may_read
│   │   │   ├── schemas.py
│   │   │   └── test_get_conversation.py
│   │   └── router.py                    # three include_router lines
│   ├── messages/
│   │   ├── send_message/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # thin entry point — calls the handler
│   │   │   ├── handler.py               # earned: load participants, may_post, insert, emit
│   │   │   ├── schemas.py
│   │   │   └── test_send_message.py
│   │   ├── stream_messages/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # the third transport — @router.websocket
│   │   │   └── test_stream_messages.py  # drives frames through src.realtime.registry directly — plumbing import
│   │   ├── deliver_message/
│   │   │   ├── __init__.py
│   │   │   ├── subscriber.py            # entry point is MessageSent, not a route
│   │   │   ├── handler.py
│   │   │   └── test_deliver_message.py  # imports only its own handler — the fan-out proof
│   │   └── router.py                    # two include_router lines — deliver_message has none
│   └── notifications/
│       └── notify_new_message/          # no family router — this family has no HTTP surface
│           ├── __init__.py
│           ├── subscriber.py            # entry point is MessageSent, not a route
│           ├── handler.py
│           └── test_notify_new_message.py   # no schemas.py — the event is the contract
├── domain/
│   ├── conversation.py                  # may_post, may_read — nothing else
│   ├── errors.py                        # DomainError base — subclassed by exceptions.py's NotFound, Forbidden
│   └── events.py                        # MessageSent, ParticipantAdded — nothing else
├── models.py                            # Conversation, Participant, Message, NotificationDelivery, OutboxMessage
├── database.py                          # engine, session factory, get_db, DbSession
├── realtime.py                          # ConnectionRegistry, registry — plumbing beside database.py
├── outbox.py                            # emit, subscribe, relay — references/cross-feature-communication.md
├── notifications_client.py              # thin push/email client — the sanctioned stub seam
├── config.py                            # BaseSettings
├── exceptions.py                        # NotFound, Forbidden + global handlers — DomainError from domain/errors.py
└── main.py                              # app init, family routers, subscribers, outbox relay
```

Two families carry an HTTP surface (`conversations`, `messages`); `notifications` doesn't — the same asymmetry `inventory` shows in the orders project: `notify_new_message`'s only entry point is an event, so there is nothing for a family `router.py` to aggregate. `messages` is the more interesting shape: two routed slices and a subscriber slice side by side — a family's HTTP surface and its event surface aren't mutually exclusive, and a subscriber slice belongs wherever the capability lives. `domain/` holds three modules: `conversation.py`, this project's one rule; `errors.py`, the `DomainError` base that `exceptions.py`'s `NotFound` and `Forbidden` subclass, in `domain/` for the same reason as in the orders project (references/shared-code.md); and `events.py`, two events and no more. `create_conversation` and `get_conversation` hold the same one-file shape `get_order` holds in the orders project, so their code isn't repeated below; the sections that follow cover the slices that carry this project's argument.

## Participant Rules: domain/conversation.py

```python
# domain/conversation.py — pure; called by send_message, get_conversation, stream_messages
def may_post(participant_ids: frozenset[int], user_id: int) -> bool:
    return user_id in participant_ids

def may_read(participant_ids: frozenset[int], user_id: int) -> bool:
    return user_id in participant_ids
```

Today these are the same membership check twice, and neither has a second call site — push-down's default timing would leave them inline. They sit in `domain/` on first sight under shared-code.md's invariant exception: who may read or post a conversation is access control, where one wrong inline copy is already a bug, not a duplication risk waiting to happen. When the two rules diverge — muted participants, join-date cutoffs — each grows its clause here, edited once.

## The Emitting Slice: send_message

```python
# domain/events.py — frozen dataclasses; names are the wire format
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class MessageSent:
    conversation_id: int
    message_id: int
    sender_id: int

@dataclass(frozen=True, slots=True)
class ParticipantAdded:
    conversation_id: int
    user_id: int
```

`send_message` is the only place `MessageSent` is built. `ParticipantAdded` is `add_participant`'s emission, the same shape one level up — this project just has nothing subscribing to it yet, the same way `PaymentDeclined` has no subscriber in the orders project; a fact gets recorded because the owning family knows it matters, whether or not anything downstream cares this month. A thin `router.py` — the same three-line shape as `cancel_order`'s in the orders project: import the handler, call it with a `DbSession`-injected session — exposes the handler below as `POST /conversations/{conversation_id}/messages`, returning `201 Created`:

```python
# features/messages/send_message/handler.py — earned: load participants, enforce may_post, insert, emit
from sqlalchemy import select

from src.database import AsyncSession
from src.domain.conversation import may_post
from src.domain.events import MessageSent
from src.exceptions import Forbidden, NotFound
from src.models import Conversation, Message, Participant
from src.outbox import emit

from .schemas import SendMessageRequest, SendMessageResponse

async def send_message(
    db: AsyncSession, conversation_id: int, body: SendMessageRequest
) -> SendMessageResponse:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise NotFound("conversation")
    participant_ids = frozenset((await db.execute(
        select(Participant.user_id).where(Participant.conversation_id == conversation_id)
    )).scalars().all())
    if not may_post(participant_ids, body.sender_id):  # sender_id stands in for authenticated identity — see note below
        raise Forbidden("not a participant")
    message = Message(conversation_id=conversation_id, sender_id=body.sender_id, text=body.text)
    db.add(message)
    await db.flush()  # populate message.id before it names the event
    await emit(db, MessageSent(conversation_id=conversation_id, message_id=message.id, sender_id=body.sender_id))
    return SendMessageResponse(message_id=message.id, conversation_id=conversation_id)
```

`schemas.py` holds only `SendMessageRequest(sender_id: int, text: str)` and `SendMessageResponse(message_id: int, conversation_id: int)` — too small to earn its own block here. No `repository.py` either: both queries above run once each in this slice, Rule 6's threshold never met. `Forbidden` is `exceptions.py`'s second `DomainError` subclass, mapped to `403` as `NotFound` maps to `404` — a rule `domain/` owns, never re-checked with a bare `HTTPException`. The note the code comment points at: this minimal design has no auth dependency, so `sender_id` rides in the body — in production it comes from the identity the pipeline injects, never from a client-supplied field.

## The Third Transport: stream_messages

```python
# features/messages/stream_messages/router.py — WebSocket entry point; same role as any route
from fastapi import APIRouter, WebSocket

from src.realtime import registry

router = APIRouter()

@router.websocket("/conversations/{conversation_id}/stream")
async def stream_messages(ws: WebSocket, conversation_id: int) -> None:
    await ws.accept()
    registry.register(conversation_id, ws)
    try:
        while True:
            await ws.receive_text()  # inbound frames: keepalive only in this design
    finally:
        registry.unregister(conversation_id, ws)
```

```python
# src/realtime.py — plumbing, beside database.py: in-process connection registry
from collections import defaultdict
from fastapi import WebSocket

class ConnectionRegistry:
    def __init__(self) -> None:
        self._by_conversation: dict[int, set[WebSocket]] = defaultdict(set)

    def register(self, conversation_id: int, ws: WebSocket) -> None:
        self._by_conversation[conversation_id].add(ws)

    def unregister(self, conversation_id: int, ws: WebSocket) -> None:
        self._by_conversation[conversation_id].discard(ws)

    async def send_to_conversation(self, conversation_id: int, payload: dict) -> None:
        for ws in list(self._by_conversation[conversation_id]):
            await ws.send_json(payload)

registry = ConnectionRegistry()
```

`stream_messages` is a `router.py` doing exactly what any entry point does — decorator, wiring, nothing else — over a socket instead of a request/response pair; `registry` is module-level singleton plumbing, the WebSocket-era equivalent of the session factory `database.py` exports, which is why it lives beside `database.py` and not inside any slice. The router never calls `may_read`, though `domain/conversation.py` lists `stream_messages` among its callers: enforcing it needs identity at the handshake, which this design doesn't carry yet — the check lands here the day it does, the same cut as `send_message`'s auth gap. Each half of the socket path proves itself in `## Testing This Project`: `stream_messages`' test drives a frame through `src.realtime.registry` directly (a plumbing import, not a sibling import), and `deliver_message`'s test proves the fan-out path reaches the same socket through the real `MessageSent` event.

## Fan-Out: One Event, Two Subscriber Families

```python
# features/messages/deliver_message/subscriber.py — entry point
from src.domain.events import MessageSent
from src.outbox import subscribe

from .handler import deliver_message

def register() -> None:
    subscribe(MessageSent, deliver_message)
```

```python
# features/messages/deliver_message/handler.py
from src.domain.events import MessageSent
from src.realtime import registry

async def deliver_message(event: MessageSent) -> None:
    await registry.send_to_conversation(event.conversation_id, {
        "type": "message",
        "message_id": event.message_id,
        "sender_id": event.sender_id,
    })
```

```python
# features/notifications/notify_new_message/subscriber.py — entry point
from src.domain.events import MessageSent
from src.outbox import subscribe

from .handler import notify_new_message

def register() -> None:
    subscribe(MessageSent, notify_new_message)
```

```python
# features/notifications/notify_new_message/handler.py
from sqlalchemy import select

from src.database import session_factory
from src.domain.events import MessageSent
from src.models import NotificationDelivery, Participant
from src.notifications_client import send_push  # thin client — the sanctioned stub seam

async def notify_new_message(event: MessageSent) -> None:
    async with session_factory() as db:
        recipients = (await db.execute(
            select(Participant.user_id)
            .where(Participant.conversation_id == event.conversation_id)
            .where(Participant.user_id != event.sender_id)
        )).scalars().all()
        already_pushed = set((await db.execute(
            select(NotificationDelivery.user_id)
            .where(NotificationDelivery.message_id == event.message_id)
        )).scalars().all())
        for user_id in recipients:
            if user_id in already_pushed:
                continue  # redelivered event — this push already went out
            await send_push(user_id, event.message_id)
            db.add(NotificationDelivery(message_id=event.message_id, user_id=user_id))
        await db.commit()
```

`send_message` knows neither of these two folders exists: it loads a conversation, checks `may_post`, inserts a row, and emits one fact — `MessageSent` — into the same commit; what happens after that is entirely the subscribers' business, on their own schedule, exactly as `inventory/release_reservation` is `orders/cancel_order`'s business in the sibling project. A third consequence tomorrow adds a third folder and a third `subscribe(MessageSent, ...)` call, nothing else. (`notify_new_message` pushes to every participant but the sender because `ConnectionRegistry` tracks sockets per conversation, not per user — there is no presence signal to consult in this model set.)

The two handlers carry the two idempotency shapes references/cross-feature-communication.md names. `deliver_message` is at-least-once by design: a redelivered `MessageSent` repeats the socket frame, and the frame's `message_id` is what lets a client drop the duplicate — a persisted delivery log for an ephemeral push to a live socket would outlive the thing it guards. `notify_new_message` is the other shape: a push that leaves the process gets a `NotificationDelivery` row keyed `(message_id, user_id)`, checked before sending — keyed on the business fact, not an event id, because `relay()` hands the handler the reconstructed event, never the `OutboxMessage` row's own id.

## Testing This Project

```python
# features/messages/send_message/test_send_message.py
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Conversation, Message, OutboxMessage, Participant

async def test_sends_a_message_from_a_participant(
    client: AsyncClient, db_session: AsyncSession
):
    conversation = Conversation()
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(Participant(conversation_id=conversation.id, user_id=1))
    await db_session.commit()  # setup: its own committed unit of work

    resp = await client.post(
        f"/conversations/{conversation.id}/messages", json={"sender_id": 1, "text": "hi"}
    )

    assert resp.status_code == 201                                     # 1. the response
    message = (await db_session.execute(
        select(Message).where(Message.conversation_id == conversation.id)
    )).scalar_one()
    assert message.sender_id == 1 and message.text == "hi"             # 2. persisted state
    outbox = (await db_session.execute(select(OutboxMessage))).scalars().all()
    assert any(m.event_type == "MessageSent" for m in outbox)          # 3. the emitted event
```

```python
# features/messages/stream_messages/test_stream_messages.py
from httpx import AsyncClient
from httpx_ws import aconnect_ws

from src.realtime import registry

async def test_receives_a_frame_pushed_through_the_registry(ws_client: AsyncClient):
    async with aconnect_ws("/conversations/1/stream", ws_client) as ws:
        await registry.send_to_conversation(1, {"type": "message", "text": "hi"})
        frame = await ws.receive_json()
        assert frame == {"type": "message", "text": "hi"}

    assert registry._by_conversation[1] == set()  # unregister ran in the router's finally block
    await registry.send_to_conversation(1, {"type": "message", "text": "gone"})  # empty set: nothing to send to, nothing raised
```

`stream_messages`' own test proves only what the slice owns: connect, register, receive, unregister. It imports `registry` from `src.realtime` — plumbing, not a sibling import, so Rule 4 doesn't apply — and drives the frame through `send_to_conversation` directly, because this test has no business knowing an event contract exists. Leaving the `async with` block closes the connection, driving the router's `receive_text()` to raise and its `finally: registry.unregister(...)` to run — the empty `_by_conversation[1]` set is the proof, and the second `send_to_conversation` against it shows an empty conversation is a no-op, not an error.

```python
# features/messages/deliver_message/test_deliver_message.py
from httpx import AsyncClient
from httpx_ws import aconnect_ws

from src.domain.events import MessageSent

from .handler import deliver_message

async def test_delivers_a_sent_message_to_the_open_stream(ws_client: AsyncClient):
    async with aconnect_ws("/conversations/1/stream", ws_client) as ws:
        await deliver_message(MessageSent(conversation_id=1, message_id=9, sender_id=3))
        frame = await ws.receive_json()

    assert frame == {"type": "message", "message_id": 9, "sender_id": 3}
```

This test lives in `deliver_message`'s own slice folder and imports only its own `handler.py` — Rule 4 intact. It connects to `stream_messages`' route over `ws_client` as setup, then delivers through the real event instead of the raw registry call — the fan-out proof. No outbox, no `relay()`: the event is constructed and the handler called directly, as every subscriber test does, so the frame `ws.receive_json()` returns is the object the handler pushed into `registry`.

```python
# features/notifications/notify_new_message/test_notify_new_message.py
from collections.abc import Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events import MessageSent
from src.features.notifications.notify_new_message import handler as notify_new_message_module
from src.models import Conversation, Participant

async def test_notifies_every_participant_but_the_sender(
    db_session: AsyncSession,
    patch_subscriber_session: Callable[[str], None],
    monkeypatch: pytest.MonkeyPatch,
):
    patch_subscriber_session("src.features.notifications.notify_new_message.handler.session_factory")
    conversation = Conversation()
    db_session.add(conversation)
    await db_session.flush()
    db_session.add_all([
        Participant(conversation_id=conversation.id, user_id=1),
        Participant(conversation_id=conversation.id, user_id=2),
    ])
    await db_session.commit()

    sent: list[tuple[int, int]] = []
    async def fake_send_push(user_id: int, message_id: int) -> None:
        sent.append((user_id, message_id))
    monkeypatch.setattr(notify_new_message_module, "send_push", fake_send_push)

    await notify_new_message_module.notify_new_message(
        MessageSent(conversation_id=conversation.id, message_id=7, sender_id=1)
    )
    await notify_new_message_module.notify_new_message(
        MessageSent(conversation_id=conversation.id, message_id=7, sender_id=1)
    )  # redelivery — the NotificationDelivery log makes the second call a no-op

    assert sent == [(2, 7)]  # sender excluded, duplicate suppressed; every other collaborator here is real
```

`send_push` is the only *stub* in this file: a thin client wrapping a third-party process is the one seam references/slice-testing.md's doctrine allows a test to substitute; everything else — including the session `patch_subscriber_session` redirects — stays a real collaborator against a real database. Both patches target the handler's own module (`notify_new_message_module.send_push`, never `src.notifications_client.send_push`) for the reason slice-testing.md § The Fixture Recipe works through: patching the importer, not the source, is what actually reaches the code under test.
