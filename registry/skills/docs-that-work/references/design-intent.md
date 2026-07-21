# Design Intent Authoring Guide

How to write, confirm, and maintain Design Intent sections in package-level CLAUDE.md files.

## Why Design Intent Exists

Agents treat existing code as the strongest signal for how new code should look. Code shows the **actual** shape of a package, not the **intended** one. Once an anti-pattern leaks in, agents replicate and multiply it — nothing in the code says which pattern is canonical and which is drift. Where actual and intended diverge, the divergence is undiscoverable from code. That divergence is exactly what CLAUDE.md exists to capture.

## The Canonical Format

Every Design Intent section has three parts: the conflict preamble, a golden example pointer, and 2–4 do/don't rules.

```markdown
# Design Intent

If existing code contradicts this section, follow this section
and flag the file as drift.

Reference: `handlers/create-order.ts` is the canonical handler — copy its structure.

- Do: validate input via schema at the top, one service call, return envelope
- Don't: raw SQL in handlers (leaked into `legacy-report.ts` — do not replicate)
```

Budget: ~35 lines. Combined with the non-obvious constraints (~35 lines), the whole CLAUDE.md stays under 70.

### The conflict preamble

Always include the first two lines verbatim:

> If existing code contradicts this section, follow this section
> and flag the file as drift.

This makes the section self-enforcing. Any Claude Code session reads CLAUDE.md; only skill users read this skill. The preamble carries the conflict rule into repos where the skill is not installed.

### The golden example

Point at ONE canonical file per pattern — the file new code should imitate. The example lives in code; only the pointer is documentation, so it costs almost nothing to maintain. Pick the file that best embodies the intended shape today, not the oldest or largest one.

### Drift callouts

A drift callout is a known, located anti-pattern — not a vague warning:

- Name the specific file(s) where the pattern leaked
- State it as a Don't rule ending with "— do not replicate"
- One callout per anti-pattern; if the same leak is in many files, name the worst offender and say "and others"

## Shapes of Design Intent

Design Intent is language-agnostic: the format — preamble + golden example + rules — is identical in any ecosystem. What varies is the shape being pinned down. Common shapes:

| Shape | What it pins down | Example rule |
| --- | --- | --- |
| Layering | Which layers may talk to which | Handlers call services, never the DB driver (TypeScript API) |
| Error handling | How failures propagate | All failures raise `DomainError` subclasses — no bare `throw` or exit (Python) |
| State ownership | Where state is allowed to live | Cart state lives in the Zustand store, never in component state (React) |
| Dependency direction | Which modules may import which | `core/` never imports from `api/` or `cli/` — dependencies point inward (Go) |
| Extension points | How new variants plug in | New exporters implement `Exporter` and register in the registry — never switch on type (Java) |
| Concurrency | Who may spawn and synchronize | All writes go through the repository actor — no direct coroutine launches in handlers (Kotlin) |

One CLAUDE.md usually combines shapes — pick the 2–4 rules where drift would hurt most, not one rule per shape.

### Worked example: Go worker package

```markdown
# Design Intent

If existing code contradicts this section, follow this section
and flag the file as drift.

Reference: `worker/resize.go` is the canonical job worker — copy its structure.

- Do: implement the `Job` interface, register in `worker/registry.go`, respect `ctx` cancellation
- Don't: spawn goroutines inside jobs (leaked into `worker/transcode.go` — do not replicate; the pool owns concurrency)
- Don't: switch on job type anywhere — extension happens via the registry
```

### Worked example: Python data pipeline package

```markdown
# Design Intent

If existing code contradicts this section, follow this section
and flag the file as drift.

Reference: `pipelines/normalize.py` is the canonical pipeline step — copy its structure.

- Do: one pure function per step (frame in, frame out), raise `PipelineError` naming the step on failure
- Don't: read config or env vars inside steps (leaked into `pipelines/enrich.py` — do not replicate; the runner injects config)
- Don't: import from `pipelines/` inside `core/` — dependencies point from pipelines to core, never back
```

## Authoring Protocol: Propose, Then Confirm

Intent cannot be inferred from drifted code. If the anti-pattern IS the majority pattern, inferring intent from the majority enshrines the drift — the exact failure Design Intent exists to prevent. So:

1. **Scan the package.** Identify the dominant pattern and the best-shaped file.
2. **Draft the section.** Candidate golden example, 2–4 do/don't rules, suspected drift files.
3. **Present the draft as a proposal.** Ask the human to confirm or correct — especially the golden example choice and the drift callouts.
4. **Only confirmed content lands.** If no human is available, mark the section heading `# Design Intent (unconfirmed proposal)` — never present inferred intent as confirmed.

## Maintenance

- **Drift fixed** (anti-pattern refactored away) → delete its callout.
- **Golden example refactored or renamed** → re-point the reference.
- **A rule stops being true** → remove it. Stale intent causes worse decisions than no intent — the same principle as the rest of this skill.
