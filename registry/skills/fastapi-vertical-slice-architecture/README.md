# FastAPI Vertical Slice Architecture

Code structure and placement for FastAPI backends — one folder per business use case, over shared SQLAlchemy models and pure domain rules. The skill answers one question, *where does this code go*, with ten numbered rules (each carrying the grep or lint that finds a breach), two fully worked projects, and one law from Jimmy Bogard: **minimize coupling between slices, and maximize coupling in a slice**.

It replaces the tech-agnostic Vertical Slice Architecture skill this registry used to ship. That skill stated the pattern in framework-neutral terms and left the translation from role (entry point, feature handler, contracts) to artifact (`router.py`, `handler.py`, `schemas.py`) to happen at generation time, unverified — sound rules, guessed FastAPI code. Here the translation is made once, in advance, against real FastAPI, SQLAlchemy, and pytest code, and every structural claim is anchored to a file a reader could open in a running project.

## Sources

- **Jimmy Bogard** — the law and organize-by-feature ([Vertical Slice Architecture](https://www.jimmybogard.com/vertical-slice-architecture/)); the slice test fixture pattern that `references/slice-testing.md` follows — real composition root, real database, setup and verification in separate committed scopes ([Vertical Slice Test Fixtures](https://lostechies.com/jimmybogard/2016/10/24/vertical-slice-test-fixtures-for-mediatr-and-asp-net-core/)).
- **Milan Jovanović** — push-down: shared business rules go *down* into the domain model, never *up* into a service layer ([Vertical Slice Architecture](https://www.milanjovanovic.tech/blog/vertical-slice-architecture)). Rule 7 and `references/shared-code.md` are this idea, made FastAPI-shaped.
- **Oskar Dudycz** and **Derek Comartin** — minimize is not eliminate: slices share the database, the ORM models, and the domain rules by design, and the myths that say otherwise are what turn feature folders back into layers ([How to slice the codebase effectively?](https://event-driven.io/en/how_to_slice_the_codebase_effectively/), [My thoughts on Vertical Slices and CQRS](https://www.architecture-weekly.com/p/my-thoughts-on-vertical-slices-cqrs)). Comartin also supplies the migration posture — defactoring, not renaming folders — behind `references/migrating.md` ([Restructuring to a Vertical Slice Architecture](https://codeopinion.com/restructuring-to-a-vertical-slice-architecture/)).
- **Steve "Ardalis" Smith** — [REPR](https://deviq.com/design-patterns/repr-design-pattern) (Request–Endpoint–Response): every use case is an input contract, one entry point, an output contract. That is the Slice Roles table, with `subscriber.py` added as the non-HTTP entry point.
- **[zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)** — the mechanics conventions this skill composes with (and the source the companion `fastapi-best-practices` skill is based on). Its per-domain-module layout is acknowledged structural inspiration and a deliberate departure: this skill slices per use case rather than per domain package, and dissolves the per-domain `service.py` into feature handlers.

## Install

```bash
npx @provectusinc/awos-recruitment skill fastapi-vertical-slice-architecture
```

## Scope & Boundaries

Placement and boundaries — where a file lives, what a slice may import, how features affect each other, and what a slice's test must prove. Everything else belongs to a companion skill, and the skill raises the conflict rather than silently overriding either side:

| Concern | Owner |
|---|---|
| Placement, slice boundaries, cross-feature effects | This skill |
| Slice-test doctrine — what a slice's test proves, subcutaneous wiring | This skill |
| FastAPI mechanics — async routes, `Depends`, Pydantic, DB conventions | `fastapi-best-practices` |
| General pytest idioms — parametrization, markers, mocking | `pytest-best-practices` |
| Python idioms — naming, type hints, error handling, packaging | `modern-python-development` |

## Files

| File | Content |
|---|---|
| `SKILL.md` | The law, Slice Roles, Form 1/Form 2 trees, placement decisions, the 10 rules with their import-linter contracts, the three cross-feature channels, the add-a-slice workflow |
| `references/shared-code.md` | The three destinations for shared code, push-down timing, the wrong fix beside the right one, `domain/` purity, refiling a `shared/` or `utils.py` |
| `references/cross-feature-communication.md` | The three channels in code, outbox machinery (`emit`/`subscribe`/`relay`), subscriber slice anatomy, idempotency, the anti-pattern gallery |
| `references/slice-testing.md` | Subcutaneous doctrine, test placement and conftest discovery, the fixture recipe, the three assertions, per-entry-point recipes (HTTP, WebSocket, subscribers), case coverage per slice |
| `references/example-orders-backend.md` | A worked HTTP-and-events project — one state machine, three families firing transitions, the canonical slice test |
| `references/example-chat-backend.md` | A worked WebSocket-and-fan-out project — three transports, one event with two subscriber families, a family with no HTTP surface |
| `references/migrating.md` | The strangler path from layered or domain-module codebases — symptoms that justify migrating, seven steps, what not to change, failure modes |

## Usage

Once installed, the skill activates automatically when Claude Code detects placement work in a FastAPI project — deciding where a new endpoint or feature goes, scaffolding a slice, reviewing structure and cross-slice imports, or migrating a layered or domain-module codebase to slices.
