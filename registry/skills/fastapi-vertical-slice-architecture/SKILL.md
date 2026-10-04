---
name: fastapi-vertical-slice-architecture
description: >-
  Use when deciding where new code lives in a FastAPI project, adding an
  endpoint or feature, scaffolding a slice, reviewing FastAPI structure, or
  migrating a layered or domain-module FastAPI codebase to vertical slices.
  Triggers on: where should this endpoint go, where does this SQLAlchemy model
  or schema go, add a feature, create an endpoint, vertical slice, VSA, feature
  folders, slice boundaries, cross-slice imports, cross-feature effects, router
  organization, service layer, god router.
version: 0.2.0
---

# FastAPI Vertical Slice Architecture

Organize a FastAPI backend by business use case — one folder per operation — over shared SQLAlchemy models and pure domain rules. One law governs every placement decision:

> **Minimize coupling between slices, and maximize coupling in a slice.** — Jimmy Bogard

Slices share the database, the ORM models, and the domain rules **by design**. That sharing is not the coupling the law forbids; it is the substrate the law assumes. What slices never share is **use-case code** — no slice imports another slice's handler, repository, or schemas. *Maximize* binds only the inside of a slice: its parts may depend on each other freely.

## Precedence

1. These rules bind **structure**, not idiom. Naming, framework usage, and Python style stay with the project's standards — FastAPI mechanics belong to `fastapi-best-practices`. Where structure and idiom genuinely conflict, raise the conflict; don't silently override either.
2. A deviation the team documented, or applied consistently across the codebase before the work in front of you, is their call. A pattern the change under review is itself establishing is not.
3. Every finding cites one numbered rule; findings are ordered by reach — how much code already depends on the mistake.

## Slice Roles

| Role | File | Owns |
| --- | --- | --- |
| Entry point (router handler) | `router.py` (HTTP, incl. `@router.websocket`); `subscriber.py` (events) | Transport only: decorator, wiring, `status_code`, `response_model`, `Annotated` dependencies; calls the feature handler |
| Feature handler | `handler.py`, or inline in `router.py` while small | The use case: load state, apply `domain/` rules, persist, emit outbox events, return result |
| Slice repository | `repository.py` (optional) | This slice's queries — concrete async functions taking `AsyncSession` |
| Contracts | `schemas.py` | Request/response models, per slice, never reused |
| Public surface | `__init__.py` | Exports `router` (or subscriber registration) — nothing else |

**Earned, not scaffolded.** File count is an outcome, never a template:

- Start with the feature handler inline in `router.py` — one readable function is the correct form for most slices.
- Split `handler.py` when the body outgrows transport concerns (~a screen), or when the orchestration deserves reading independently of the HTTP wiring.
- Split `repository.py` when a query serves multiple code paths within the slice, or when queries crowd the handler.
- Split a `tests/` folder inside the slice (own `conftest.py` allowed) when a second test file is earned or an arrangement fixture serves multiple files — placement mechanics in references/slice-testing.md.
- A five-line read slice stays one file forever. Asymmetry between slices is correct; forcing symmetry is not compliance.

**Guardrails** — what keeps split files VSA rather than layers in a folder:

- **Slice-local only** — nothing outside the slice imports its `handler.py` or `repository.py`.
- **Concrete and direct** — no Protocol, ABC, or injected abstraction with a single implementation. A test double is not a second implementation.
- **No pass-throughs** — a repository function forwarding one call and adding nothing is one unit of work split across two files. Inline it.
- **No template scaffolding** — the endpoint/service/repository trio stamped into every new slice folder is the anti-pattern, whatever the three files are named. A file appears when its threshold is met, never at creation.

The canonical name is `handler.py`. A project consistently using `service.py` for slice-local use-case functions keeps its idiom under Precedence 2.

## Structure

**Form 1 — the template (the invariant):**

```text
src/
├── features/
│   ├── {family}/                   # business capability, never a technical role
│   │   ├── {verb_noun}/            # one use case
│   │   │   ├── __init__.py         # public surface — exports router only
│   │   │   ├── router.py           # entry point (HTTP) — subscriber.py for event slices
│   │   │   ├── handler.py          # feature handler — only when earned
│   │   │   ├── repository.py       # slice queries — only when earned
│   │   │   ├── schemas.py          # this slice's contracts, never reused
│   │   │   └── test_{verb_noun}.py # subcutaneous — real app, real Postgres
│   │   └── router.py               # family router: include_router lines only
│   └── {family}/...
├── domain/
│   ├── {concept}.py                # pure rules, value objects — zero src imports
│   ├── errors.py                   # DomainError base — domain rules raise its subclasses
│   └── events.py                   # domain event types
├── models.py                       # all SQLAlchemy models — single metadata
├── database.py                     # engine, session factory, get_db, DbSession
├── outbox.py                       # emit/subscribe/relay — see references/cross-feature-communication.md
├── config.py                       # BaseSettings
├── exceptions.py                   # NotFound + global handlers — imports DomainError from domain/
└── main.py                         # app init, family routers, subscribers, outbox relay
```

**Form 2 — one realization (an orders backend), deliberately asymmetric:**

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
│   │   │   ├── router.py
│   │   │   ├── handler.py               # earned: load, transition, OrderCancelled emit — past a screen
│   │   │   ├── schemas.py
│   │   │   └── test_cancel_order.py
│   │   ├── get_order/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                # five lines, forever — asymmetry is correct
│   │   │   └── test_get_order.py
│   │   └── router.py                    # three include_router lines
│   ├── billing/
│   │   ├── process_payment/             # router + earned handler + schemas + test
│   │   └── router.py
│   ├── inventory/
│   │   └── release_reservation/         # no family router — this family has no HTTP surface
│   │       ├── __init__.py
│   │       ├── subscriber.py            # entry point is OrderCancelled, not a route
│   │       ├── handler.py
│   │       └── test_release_reservation.py   # no schemas.py — the event is the contract
│   └── fulfillment/
│       ├── ship_order/                  # router (handler inline) + schemas + test
│       └── router.py
├── domain/
│   ├── order.py                         # OrderStatus, transitions table, transition()
│   ├── address.py                       # Address.parse() value object
│   ├── errors.py                        # DomainError base — subclassed in order.py, address.py
│   └── events.py                        # OrderCancelled, PaymentDeclined
├── models.py
├── database.py
├── outbox.py
├── payments_client.py                   # thin PSP client — the sanctioned stub seam
├── config.py
├── exceptions.py
└── main.py
```

Form 2's elided families are spelled out in references/example-orders-backend.md, which works this same project in full. Chat-shaped projects add `realtime.py` (the WebSocket connection registry) beside `database.py` — plumbing, not a feature. A second realization — a dedicated chat backend — is worked in full in references/example-chat-backend.md.

## Placement Decisions

### Import Directions (CRITICAL)

Imports flow **inward** — toward `domain/` — and never sideways between slices. Each row is the file doing the importing.

| From | May import | Must never import |
| --- | --- | --- |
| Slice files (`features/{family}/{slice}/*`) | Own files (relative); `domain/`; `models`; `database`; `outbox`; `exceptions`; `config`; thin clients (`payments_client`) | Any sibling slice, any other family (Rule 4); `main` |
| Family `router.py` | Its own slices' public surfaces (`__init__.py`) — `include_router` lines, a shared prefix and tags, nothing else | Slice internals; other families; `domain/`; `models` — it aggregates, it never computes |
| Slice `test_*.py` | Its own slice; `models`; `domain/`; conftest fixtures | Sibling slices' internals — drive them over the wire instead |
| `domain/*` | Stdlib; itself (relative imports) | **Anything under `src`** — no session, no models, no features, no exceptions (Rule 8) |
| `models.py` | `domain/` (enums and value types backing columns, e.g. `Mapped[OrderStatus]`) | `features/`; `database`; `outbox` |
| `database.py` | `config` | `features/`; `models`; `domain/` |
| `outbox.py` | `models` (`OutboxMessage`); `database` (session types) | `features/` — subscribers register themselves via `subscribe()`; `domain/` — event classes arrive through that same registry |
| `exceptions.py` | `domain/` (`DomainError`, for the global handler mapping it to HTTP) | `features/`; `models` |
| `main.py` | Family routers and subscriber `register()`s — public surfaces only; `database`; `outbox`; `config`; `exceptions` | Slice internals past `__init__.py` (Rule 3) |

The matrix's two load-bearing rows — slice independence (Rule 4) and domain purity (Rule 8) — are CI-enforceable. Ship these import-linter contracts:

```toml
[tool.importlinter]
root_package = "src"

[[tool.importlinter.contracts]]
name = "Slices are independent"
type = "independence"
modules = ["src.features.*.*"]
ignore_imports = ["src.features.*.router -> src.features.**"]

[[tool.importlinter.contracts]]
name = "Domain is pure"
type = "forbidden"
source_modules = ["src.domain"]
forbidden_modules = ["src.features", "src.models", "src.database", "src.exceptions"]
```

Wildcards in `modules` and `ignore_imports` need import-linter >= 2.1. The `ignore_imports` line legalizes the mandated two-level aggregation — a family `router.py` is itself one of the `src.features.*.*` modules, so its `include_router` imports of its own slices would otherwise fail the contract (`**` in the target position, because a single `*` matches one segment). Sibling imports between slices still fail, which is the point. Until a family router exists to match the pattern, set `unmatched_ignore_imports_alerting = "warn"` on the contract.

### Where Does This Code Go?

| The code in hand | Destination |
| --- | --- |
| A new operation — endpoint, subscription, schedule | New slice: `features/{family}/{verb_noun}/` |
| Request/response shape for one operation | That slice's `schemas.py` — never shared (Rule 5) |
| A business rule only one slice uses | Inline in that slice's handler |
| A business rule appearing in a second slice — calculation, validation, transition | `domain/{concept}.py`, pure function or value object (Rule 7) |
| A lifecycle / state machine | `domain/{concept}.py` — the archetypal resident; canonical shape in references/shared-code.md |
| A domain event type | `domain/events.py` |
| An error a domain rule raises | `DomainError` subclass beside the rule; `domain/errors.py` holds the base |
| A SQLAlchemy model | `models.py` — one file, one `Base.metadata` |
| Auth, transactions, validation execution, telemetry | The pipeline: middleware + dependencies registered in `main.py` |
| A client for an external service | Thin module beside `database.py` (`payments_client.py`) — transport only |
| A "utility" with no owner above | Duplicate it. No `shared/`, no `utils.py`, top-level or family-local — that is where service layers regrow |

**Notes.**

- **Router aggregation is two-level.** Slice `router.py` → family `router.py` → `main.py`; adding a slice touches exactly one shared line. `main.py` also registers subscribers and starts the outbox relay.
- **Models stay anemic** — columns, relationships, constraints, no business methods — so `alembic/env.py` keeps a single import point. This is a deliberate side of a real argument: rules live in `domain/` as pure functions, unit-testable without a session, at the price of entities never owning behavior — a team practicing rich domain models consistently is a Precedence 2 deviation, not a breach. Growth path once `models.py` is long: a `models/` package of per-concept modules re-exported from `models/__init__.py`, metadata still single.
- **Dependencies are pipeline, not seams.** An entry-point signature full of `Annotated` dependencies is correct and not a finding. Slice-specific validation dependencies live in that slice's `router.py`. Chaining dependencies across families (`valid_creator_id` → `valid_profile_id`) is a breach: issue the lookup yourself, or move the check into `domain/`.

## The Rules

**Reach** — how much code already depends on the mistake, and the order findings are reported in: *no unit* (the slice the other rules bind to doesn't exist), *crosses* (the coupling already exists), *will cross* (placement that will produce it), *contained* (waste inside one slice, coupling nothing outside it).

| # | Rule | Reach | Find a breach by |
| --- | --- | --- | --- |
| 1 | `src/features/` top level names business capabilities only — no `services/`, `controllers/`, `repositories/`, `utils/` anywhere under it | no unit | `ls src/features/` |
| 2 | A slice holds its whole use case: entry point + contracts + test in one folder | crosses | grep the slice's route path / schema names outside its folder |
| 3 | `__init__.py` exports `router` (or subscriber registration) and nothing else | crosses | read it; grep imports naming slice-internal files |
| 4 | No slice imports a sibling slice | crosses | `grep -r "from src.features"` filtered by own package; import-linter contract |
| 5 | Schemas are per-slice, never reused | crosses | grep each schema class name for a second slice referencing it |
| 6 | Slice-internal decomposition is free (`handler.py`, `repository.py`). Forbidden: single-implementation seams (Protocol/ABC/injected abstraction); pure pass-throughs; role-named files outside a slice folder (family/features level) | contained | grep `Protocol`/ABC in slices + count implementors; `find src/features -maxdepth 2` for family-level role files; read repository functions for one-line forwards |
| 7 | A business rule appearing in a second slice moves to `domain/` as a pure function or value object | will cross | read handler bodies for a calculation/validation/transition standing in two slices |
| 8 | `domain/` imports nothing from `src` — no session, no models, no features. (`models.py` importing from `domain/` is legal.) | crosses | grep `domain/` for `from src.` |
| 9 | Cross-feature effects use only the three channels (§ Cross-Feature Effects) | crosses | Rule 4 grep + grep for self-HTTP calls and `BackgroundTasks` carrying business logic |
| 10 | Every slice has a subcutaneous test — real app, real Postgres | will cross | list slice folder for `test_*.py` or `tests/`; read for `ASGITransport` + absence of mocked sessions |

Rules 4 and 8 are enforced in CI by the import-linter contracts in § Placement Decisions.

## Cross-Feature Effects

Three channels, and only three: a same-transaction write through shared models, an own query on shared models, and an outbox event. The fourth row is not a channel — it is what to do instead of reaching for one.

| Need | Channel | Example |
| --- | --- | --- |
| Change another family's entity state | Shared models + `domain/` transition rule, same transaction | billing sets order → PAID |
| Read another family's data | Own query on shared models — duplicate the query | shipping reads order address |
| Trigger a consequence another family owns | Outbox event; owning family subscribes | payment declined → release reservation |
| Use a sibling slice's logic | Rule → push down to `domain/`; query/mapping → duplicate | both validate addresses |

Never, each one greppable or lintable:

- **Sibling-slice imports** — the slice stops being deletable, and the law's first half is broken directly (Rule 4).
- **Self-HTTP calls from a handler** — a network hop, a second transaction, and a retry story bought to reach code in the same process.
- **Reusing a sibling's `schemas.py` types** — contracts diverge on different schedules, so the shared type couples two releases (Rule 5).
- **`BackgroundTasks` for business consequences** — the process dies and the consequence is silently lost; fire-and-forget mechanics only.
- **Events as orchestration** — a use case spanning families (checkout) is one slice, one transaction, in the family owning the capability. Events carry consequences, not control flow.

Full machinery, code, and anti-pattern gallery: references/cross-feature-communication.md.

## Adding a Slice

1. Name the folder verb-noun after the use case: `features/{family}/{verb_noun}/`
2. Write `schemas.py` — this slice's request/response only
3. Write the feature handler inline in `router.py`: load via session, call `domain/` rules, persist, emit outbox events, build response inline. Promote to `handler.py` / `repository.py` only when a threshold is met. Event slices: `subscriber.py` entry point + `handler.py`
4. Write `__init__.py` exporting `router`
5. Add one `include_router` line to the family router (new family → one line in `main.py`)
6. Write the subcutaneous test
7. Verify: rules 4/6/8 greps; no schema imports from siblings; duplicated rules met the push-down trigger

## Teaching Posture

| Situation | Response |
| --- | --- |
| Writing code | State the placement reasoning in one sentence — which family, which slice, and why the rule lives where it landed |
| Violation spotted | Cite the rule number, show the fix |
| Consistent, deliberate project deviation | Ask before flagging — project consistency beats strict compliance |

## Going Deeper

| Need | Read |
| --- | --- |
| Writing or judging a slice's test — placement, conftest discovery, fixtures, per-entry-point recipes | references/slice-testing.md |
| Where shared code goes; push-down timing; `domain/` purity; refiling a `shared/` or `utils.py` | references/shared-code.md |
| Outbox machinery, subscriber anatomy, idempotency, the anti-pattern gallery | references/cross-feature-communication.md |
| A full HTTP-and-events project in real code — one state machine, three families firing transitions | references/example-orders-backend.md |
| A full WebSocket-and-fan-out project in real code | references/example-chat-backend.md |
| Migrating a layered or domain-module codebase to slices | references/migrating.md |
