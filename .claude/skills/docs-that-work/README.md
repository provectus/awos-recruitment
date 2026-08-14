# docs-that-work

A skill that teaches agents how to write project documentation that serves both humans and AI agents.

## Install

```bash
npx @provectusinc/awos-recruitment skill docs-that-work
```

## What This Skill Teaches

- **Two filters, not one** — a line earns its place only if the code does not already reveal it *and* it changes what the agent does versus its default; "write clean code" fails the second even though it passes the first
- **Cache only expensive lookups** — restating `package.json` is bloat; the CI-gating command that no single file states is not
- **Split budgets** — root `CLAUDE.md` loads every turn (~25 lines), a package one loads on demand (~35 plus ~10–15 of Design Intent, 70 ceiling)
- **Write the target, not the ban** — a prohibition makes the forbidden behavior more available, not less
- **Design Intent sections** — document the intended shape of a package so agents stop multiplying leaked anti-patterns; intent outranks existing code
- **An audit procedure with a completion bar** — every line of every in-scope doc gets a verdict; "looks fine" is not one
- **README.md structure** — executable setup steps, not prose
- **Grey box documentation** — describe interfaces, not internals
- **Document separation** — each file has one job, no duplication

## Files

| File | Content |
| --- | --- |
| `SKILL.md` | Core guidelines and rules |
| `references/audit-procedure.md` | Ordered process for refreshing existing docs, with completion criteria |
| `references/claude-md-guide.md` | Templates for CLAUDE.md and README.md, budgets, decision tables |
| `references/anti-patterns.md` | Bloat examples, discoverable content catalog, three-question test, no-op catalog |
| `references/design-intent.md` | Design Intent format, authoring protocol, maintenance rules |

## Credits

The no-op test, the expensive-lookup exception, the split context budgets, and the "state the target, not the ban" rule are adapted from [`writing-for-agents`](https://github.com/mattpocock/skills/tree/main/skills/productivity/writing-for-agents) by Matt Pocock (MIT).

## Pairs With

The `docs-that-work-gate` hook blocks a commit whose changed files have a `CLAUDE.md` or `README.md` that was not refreshed, and points the agent at this skill:

```bash
npx @provectusinc/awos-recruitment hook docs-that-work-gate
```
