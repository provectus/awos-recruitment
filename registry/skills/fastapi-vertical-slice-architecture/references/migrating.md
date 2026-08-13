# Migrating

How an existing FastAPI codebase — layered or domain-module — gets to slices without a stop-the-world rewrite. SKILL.md states the target structure and the rules the destination must satisfy: Rule 1 (`src/features/` holds business capabilities only, no role-named folders), Rule 4 (no sibling-slice imports), Rule 6 (slice-internal decomposition is free; single-implementation seams are not), Rule 7 (push-down on a rule's second appearance), Rule 10 (every slice carries a subcutaneous test). This file is the path from where a project already is to that destination, one endpoint at a time.

## Two Starting Points

Every codebase migrating to slices starts from one of two shapes, and the shape decides how much of the work is structural versus how much is defactoring.

**(a) Classic layered.** `routers/`, `services/`, `crud/` (or `dao/`, `repositories/`) — one folder per technical role, cutting across every feature. A single use case's code is smeared across three or four files, each shaped by what kind of code it is rather than what it does; the top-level names themselves are the Rule 1 breach the destination forbids. Reaching Form 1's `src/features/{family}/{verb_noun}/` from here means inventing the family boundary itself — deciding which routes belong to which business capability — before any defactoring can start.

**(b) Domain modules.** `src/auth/` with `router.py` + `service.py` + `schemas.py`, repeated per domain — `src/users/`, `src/posts/`, and so on. This starting point is closer to the destination than (a): a domain package is already a family, so the family boundary survives the migration untouched — no invention step, no renegotiating which routes belong together. The moves are smaller than from (a), but they're the same three moves: dissolve the per-domain `service.py` into per-use-case handlers, split the god `router.py` into one `router.py` per use case, and give each use case its own `schemas.py` instead of the domain's single shared one (Rule 5).

## Symptoms That Justify Migration

The strangler path below is worth starting only once the layered or domain-module shape is visibly costing something. Four symptoms to check against the current codebase:

| Symptom | Looks like |
| --- | --- |
| Wide-blast feature changes | Every feature change touches 5+ files across `routers/`/`services/`/`crud/` |
| Shared-file contention | Merge conflicts pile up in a shared `service.py` or `router.py` |
| Single-caller service methods | A service method is called from exactly one route |
| Refactor-fragile tests | Mock-heavy tests break on refactors that don't change behavior |

Two or more of these → migrate. One → fix it locally; a single symptom is a local defactoring problem, not evidence the whole structure is wrong. Zero → don't restructure — the layered code isn't broken, and a migration without a symptom behind it is churn.

## The Strangler Path

Seven steps, run per endpoint and repeated until the codebase stops offering candidates:

1. Create the `src/features/` skeleton. Leave `models.py` and `database.py` exactly where they are — the migration changes where use-case code lives, not the shared substrate underneath it.

2. Pick one low-risk endpoint. Write its subcutaneous test before the move — references/slice-testing.md's fixture recipe, run against the endpoint's current, still-layered implementation — then move the endpoint end-to-end into `features/{family}/{verb_noun}/`, and re-run the same test unchanged. A test that passes before and after the move proves the move preserved behavior; a test written after the move only proves the new code satisfies itself. A read-only endpoint with no domain rule and no cross-feature effect is the canonical first pick — Form 2's `get_order` is what it looks like once moved.

3. Defactor. Inline the service methods and single-use `crud`/repository calls this endpoint depended on directly into its handler, and delete any single-implementation interface (`Protocol`/ABC) that existed only to satisfy the old layering — Rule 6 forbids exactly that seam inside a slice. A folder rename that leaves the service-and-repository internals in place is not this step; it's the failure mode below. Done, the moved endpoint satisfies Rule 2 on its own: its whole use case, entry point through contracts through test, in one folder — nothing about it still reaches into the layered code it left behind.

4. Repeat by activity, not by inventory sweep — prioritize endpoints under active development, since a slice migrated the day before someone needed to touch it anyway costs nothing extra.

5. Forbid new code in retired folders. Once a layered folder (`services/`, `crud/`) holds nothing but leftovers, stop it from regrowing — a review rule, or an import-linter `forbidden` contract barring `src.features` (and the moved slices) from importing it, the same contract type SKILL.md's "The Rules" section already ships for domain purity.

6. Push rules down as they surface. The same policy showing up in two moved slices is Rule 7's second-appearance trigger — move it to `domain/` then, not before.

7. Stop when the family count is the only thing still growing. Once every active endpoint lives in a slice, further change is adding families and use cases, which the flat structure already handles — there is no further migration step to run.

Steps 2 through 6 repeat, one endpoint at a time; step 7 is the exit condition the loop runs toward, not an action performed on its own.

## What NOT to Change

Four things the migration must not touch, regardless of how far along it is:

- **DB schema and entities.** The migration moves use-case code, not the data model; `models.py` keeps every table exactly as declared.

- **External API routes and response shapes.** The restructure is invisible to clients — same paths, same request/response bodies, even mid-migration with layered and sliced endpoints served side by side.

- **Alembic history.** `alembic/env.py`'s single `Base.metadata` import point has to keep resolving at every step of the migration, not just at the end — moving code around `models.py` without ever splitting `Base.metadata` is what keeps autogenerate working the whole way through.

- **Working middleware.** It IS the pipeline, per SKILL.md's "Dependencies are pipeline, not seams" — reuse it as the moved slice's `Depends()`, never rebuild it.

## Failure Modes

The path above is easy to abandon halfway without noticing. Four ways that happens:

| Failure Mode | Why it fails |
| --- | --- |
| A folder rename that keeps `service.py`/repository internals | Defactoring IS the migration — a slice still calling through a service class hasn't moved, it's been renamed |
| Copying a shared service into every slice | Shared rules go DOWN to `domain/` (Rule 7); duplication is for slice-local code, not for a class every slice keeps calling |
| A dedicated migration sprint | Migrate only what you touch — a sprint migrates code nobody's changing, risking regressions for zero behavior change |
| Old layers quietly growing | Step 5's retired-folder enforcement exists for exactly this — without it, new code keeps landing in `services/` because it's still there and still easy |
