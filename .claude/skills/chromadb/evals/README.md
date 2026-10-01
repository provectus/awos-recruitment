# chromadb skill evaluations

Three prompts that exercise the parts of the ChromaDB API most likely to drift
between releases: filter-operator placement and result shape, `add` vs `upsert`
semantics, and embedding-function persistence across processes.

They exist because the skill's API claims went stale without anyone noticing —
the September 2026 audit found six factual errors that any one of these runs
would have surfaced.

## When to run them

Whenever `server/uv.lock` bumps `chromadb`. A patch release is enough: the
behaviours these prompts probe (silent duplicate-ID drops, which operators a
`where` clause accepts, which embedding-function configs round-trip) are not
covered by the library's public changelog.

## How to run them

The prompts are in `evals.json`. For each one, run an agent with this skill
loaded, then run the code it produces against the pinned library — reviewing
the code is not enough, since the failures here are silent at author time and
only show up on execution:

```bash
cd server && uv sync
uv run python -c "import chromadb; print(chromadb.__version__)"
uv run python /path/to/generated_script.py
```

Use `chromadb.EphemeralClient()` for scratch checks so nothing is written to a
real store, and a `tempfile.mkdtemp()` path when a prompt needs a
`PersistentClient`. Reopening in a genuinely separate process matters for
eval 3 — a second `PersistentClient` in the same process shares cached state
and will pass even when a fresh process would fail.

## Grading

Each eval in `evals.json` carries an `assertions` list. Each assertion has a
`text` (what to check) and a `rationale` (the library behaviour that makes it
matter). They are written to be checkable by reading the generated code plus
running it; none of them depend on style judgements.

When an assertion fails, fix the skill rather than the assertion — unless the
library changed, in which case update the affected section of `SKILL.md` or
`references/`, and the rationale here along with it.
