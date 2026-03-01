# docs-that-work

A skill that teaches agents how to write project documentation that serves both humans and AI agents.

## Install

```bash
claude skill add --from awos-recruitment docs-that-work
```

## What This Skill Teaches

- **The discoverability rule** — never document what code already reveals
- **CLAUDE.md discipline** — non-obvious context only, target <30 lines
- **README.md structure** — executable setup steps, not prose
- **Grey box documentation** — describe interfaces, not internals
- **Document separation** — each file has one job, no duplication
- **When docs ARE needed** — "why" decisions, cross-service contracts, environment gotchas

## Files

| File | Content |
|---|---|
| `SKILL.md` | Core guidelines and rules |
| `references/claude-md-guide.md` | Templates for CLAUDE.md and README.md, decision tables |
| `references/anti-patterns.md` | Bloat examples, discoverable content catalog, three-question test |
