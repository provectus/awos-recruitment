# React Feature-Sliced Design

Claude Code skill for organizing React/TypeScript frontends with [Feature-Sliced Design](https://feature-sliced.design/) — six layers, strict dependency rules, one structure for every slice.

## What it teaches the agent

```
app → pages → widgets → features → entities → shared
```

- Where to place new code (layer decision guide)
- How to structure a slice (`ui/`, `model/`, `api/`, `lib/`, `config.ts`, `index.ts`)
- Import rules: down only, same-layer ban, public API only
- When to create each layer type
- Cross-entity communication (`@x` cross-imports)
- How to write a short `CLAUDE.md` per slice

## Install

```bash
npx @provectusinc/awos-recruitment skill react-feature-sliced-design
```

## Files

| File | What |
|------|------|
| `SKILL.md` | Entry point — rules, tables, decision guide |
| `references/layers.md` | Layer descriptions, decision tree, `@x` cross-imports |
| `references/segments.md` | Segment rules (ui, model, api, lib, config, index) |
| `references/claude-md-template.md` | CLAUDE.md template for slices |
| `references/slice-examples.md` | Generic slice example — structure and public API |
