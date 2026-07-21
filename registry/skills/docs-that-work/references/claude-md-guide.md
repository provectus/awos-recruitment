# CLAUDE.md & README Templates

Concrete templates and decision guides for project documentation.

## Root CLAUDE.md Template

```markdown
# Purpose

[1-2 sentences: what this project does and why it exists]

# Conventions

- [Convention that cannot be discovered from config files]
- [Gotcha that has bitten people before]
- [Non-obvious constraint on how modules interact]
```

### Example: Backend API Service

```markdown
# Purpose

Order processing API for the warehouse system. Receives orders from the storefront, validates inventory, and dispatches to fulfillment.

# Conventions

- All API responses wrap payload in `{"data": ...}` envelope — no bare objects
- Never import from `internal/` packages outside their parent module
- Migration files are manually numbered (not auto-generated) — check latest before creating
- `just dev` requires local Postgres running first (`just db-up`)
```

Commands like `just dev`, `just test`, `just lint` are discoverable from the justfile — only the non-obvious prerequisite gotcha is documented.

## Service-Level CLAUDE.md Template

```markdown
# Purpose

[1 sentence: what this service/module does within the larger system]

# Non-Obvious Context

- [Constraint specific to this module]
- [Gotcha that only applies here]

# Design Intent

If existing code contradicts this section, follow this section
and flag the file as drift.

Reference: `[canonical file]` — copy its structure.

- Do: [pattern rule new code must follow]
- Don't: [anti-pattern] (leaked into `[file]` — do not replicate)
```

### Example: Payment Module

```markdown
# Purpose

Handles payment processing via Stripe — wraps the Stripe SDK and enforces idempotency.

# Non-Obvious Context

- All Stripe calls must include an idempotency key — the helper in `utils.py` generates one from order ID
- Webhook signature verification uses a different API key than charge creation (see env vars)

# Design Intent

If existing code contradicts this section, follow this section
and flag the file as drift.

Reference: `stripe/charge.py` is the canonical Stripe wrapper — copy its structure.

- Do: one Stripe call per function, idempotency key from `utils.py`, raise `PaymentError` on failure
- Don't: retry loops inside wrappers (leaked into `stripe/refund.py` — do not replicate; retries belong to the caller)
```

Rule: never repeat root-level content. If it applies project-wide, it goes in root `CLAUDE.md`.

See `design-intent.md` in this directory for Design Intent authoring and maintenance rules.

## README.md Template

Structure: title, description, prerequisites, setup, run, test, contribute. Every section should contain commands that copy-paste and work.

```markdown
# Warehouse API

Order processing API for the warehouse fulfillment system.

## Prerequisites

- Python >= 3.12
- Docker (for local Postgres)

## Setup

\`\`\`bash
just install
just db-up
\`\`\`

## Run / Test

\`\`\`bash
just dev # start dev server
just test # run pytest
\`\`\`

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).
```

## Root vs Service-Level Decision

| If the content... | Put it in... |
| --- | --- |
| Applies to >1 service or the whole repo | Root `CLAUDE.md` |
| Is specific to one service/module | Service-level `CLAUDE.md` |
| Contradicts or narrows a root convention | Service-level `CLAUDE.md` (with explicit note) |
| Describes the intended shape of code in one package | Service-level `CLAUDE.md` (Design Intent section) |

When unsure, put it in root. Easier to push down later than to discover missing context scattered across services.

## What Belongs Where

| Content Type | CLAUDE.md | README | Architecture Doc | Neither (Discoverable) |
| --- | --- | --- | --- | --- |
| Project purpose | 1-2 sentences | Full description | - | - |
| Setup / run / test commands | - | Yes | - | Discoverable from task runner |
| Non-obvious gotchas | Yes | - | - | - |
| Design Intent (intended code shape) | Package-level CLAUDE.md only | - | - | - |
| Naming conventions | Only if not in linter | - | - | If in linter config |
| Architecture / API contracts | - | - | Yes | - |
| Dir trees, types, deps, env names | - | - | - | Always discoverable |
