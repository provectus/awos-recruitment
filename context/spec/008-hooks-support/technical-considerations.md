# Technical Specification: Claude Code Hooks Support

- **Functional Specification:** `context/spec/008-hooks-support/functional-spec.md`
- **Status:** Completed
- **Author(s):** Andrey Nenashev

---

## 1. High-Level Technical Approach

This feature extends the capability pipeline to support **hooks** as a fourth capability type alongside skills, MCP servers, and agents. It follows the established patterns in both codebases, with one genuinely new piece of machinery: deterministic injection into `.claude/settings.json`.

**Server (Python):** Hooks are directory-based, so they mirror **skills** everywhere directory semantics matter: a new `registry/hooks/<name>/` catalog loaded by a `_load_hooks()` loader, resolved by `resolve_hook_paths()`, bundled as full directories via a new `POST /bundle/hooks` route, and validated with a layout allowlist. The search index and telemetry need no new code — capabilities flow through generically once `type="hook"` is permitted.

**Convention (the key simplification):** every hook ships a **required entrypoint script `<name>.sh`** next to `HOOK.md`, with optional helpers under `scripts/`. The injected settings command is always derived as `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>/<name>.sh` — never stored in frontmatter. Frontmatter entries carry only `event`, `matcher?`, `timeout?`. Multi-event hooks branch inside the entrypoint on the `hook_event_name` field Claude Code passes via stdin JSON. This removes free-form command strings from the schema, making validation trivial and injection fully deterministic.

**CLI (TypeScript):** A new `hook` subcommand follows the two-phase structure of `agent.ts`: Phase 1 extracts hook directories into `.claude/hooks/<name>/` (silent skip on existing); Phase 2 parses each hook's `HOOK.md` frontmatter and merges derived entries into `.claude/settings.json` via a new `lib/settings-merge.ts` module. Both phases are independently idempotent.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. Registry Catalog Structure

```
registry/
├── skills/<name>/SKILL.md          (existing)
├── mcp/<name>.yaml                 (existing)
├── agents/<name>.md                (existing)
└── hooks/<name>/                   (new)
    ├── HOOK.md                     (required — metadata + injection docs)
    ├── <name>.sh                   (required — executable entrypoint)
    └── scripts/                    (optional — helper files)
```

`HOOK.md` frontmatter:

| Field | Required | Type | Constraints |
|-------|----------|------|-------------|
| `name` | Yes | string | Kebab-case, 1–64 chars (`^[a-z0-9-]{1,64}$`), must equal directory name |
| `description` | Yes | string | Non-empty (min_length=1) |
| `hooks` | Yes | list[HookEntry] | Non-empty |

`HookEntry`:

| Field | Required | Type | Constraints |
|-------|----------|------|-------------|
| `event` | Yes | string | One of: `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Notification`, `Stop`, `SubagentStop`, `PreCompact`, `SessionStart`, `SessionEnd` |
| `matcher` | No | string | Tool-name matcher (e.g. `Edit\|Write`); omitted for events that don't use matchers |
| `timeout` | No | int | Seconds, > 0 |

There is **no `command` field** — the command is always the derived entrypoint path. The markdown body documents what the hook does and the manual injection instructions (exact JSON fragment) as the human/AI fallback path.

### 2.2. Server: Data Model

**New file:** `server/src/awos_recruitment_mcp/models/hook_metadata.py`

- `HookEntry` (BaseModel, `extra="forbid"`): `event` as a `Literal` of the nine event names, `matcher: str | None`, `timeout: int | None` (gt=0).
- `HookMetadata` (BaseModel, `extra="forbid"`, consistent with `SkillMetadata`/`AgentMetadata`): `name` (standard kebab-case pattern), `description` (min_length=1), `hooks: list[HookEntry]` (min_length=1).

**Modified files:**
- `models/capability.py` — expand `RegistryCapability.type` literal to `Literal["skill", "tool", "agent", "hook"]` (line 36).
- `models/__init__.py` — export `HookMetadata` / `HookEntry`.
- `models/bundle.py` — no change; `BundleRequest` is reused as-is.

### 2.3. Server: Registry Loader

**Modified file:** `server/src/awos_recruitment_mcp/registry.py`

- **New `_load_hooks(root)`:** near-verbatim mirror of `_load_skills` (lines 158–197) — iterate sorted `hooks/` subdirectories, require `HOOK.md`, parse with `frontmatter.load()`, extract `name`/`description`, skip silently on missing/blank values, emit `RegistryCapability(type="hook")`. The `hooks:` list is not read at load time (not needed for indexing).
- **New `resolve_hook_paths(names, registry_path)`:** mirror of `resolve_skill_paths` (directory existence check on `hooks/<name>/`).
- **Modified `load_registry()`:** add `capabilities.extend(_load_hooks(root))`; update docstring.

### 2.4. Server: Bundle Endpoint

**Modified file:** `server/src/awos_recruitment_mcp/server.py`

**New route `POST /bundle/hooks`** mirroring `/bundle/skills` (lines 69–122):
1. `BundleRequest.model_validate()`; 400 with `{"error", "detail"}` on failure.
2. Deduplicate names, resolve via `resolve_hook_paths()`.
3. Telemetry: `track_install(hook_dir.name, "hook")` per found hook.
4. Archive per hook: `<name>/HOOK.md`, `<name>/<name>.sh`, and flat files under `<name>/scripts/` filtered by the existing `_ALLOWED_SCRIPT_EXTENSIONS`, skipping dotfiles. `tarfile` preserves file modes from disk, so the entrypoint's executable bit travels in the archive (git tracks the exec bit in the registry).
5. Return `application/gzip` response.

### 2.5. Server: Validation

**Modified file:** `server/src/awos_recruitment_mcp/validate/__init__.py`

- **New layout constants** alongside lines 21–23: `_ALLOWED_HOOK_DIRS = {"scripts"}`; root files allowed: `HOOK.md`, `README.md`, and the entrypoint `<name>.sh`.
- **New `validate_hooks(registry_path)`** mirroring `validate_skills` (the layout-enforcing validator):
  1. Iterate `hooks/` subdirectories; require `HOOK.md`.
  2. Parse frontmatter; validate against `HookMetadata`; unpack pydantic errors into `ValidationError` dataclasses.
  3. Directory-name vs `name` field match ("does not match" message convention).
  4. Non-empty markdown body (injection docs are mandatory content).
  5. **Entrypoint checks:** `<name>.sh` must exist and carry the executable bit (`mode & 0o111`).
  6. Layout allowlist: no unexpected files/dirs at root; `scripts/` files must match `_ALLOWED_SCRIPT_EXTENSIONS`; dotfiles skipped. This keeps validator and bundler layout definitions in the same shared constants (the drift-prevention pattern noted at `validate/__init__.py:153–159`).
- **Modified `validate_registry()`:** add `results.extend(validate_hooks(registry_path))`.
- `validate/__main__.py` needs no change (formats generically).

### 2.6. Server: Search

- `search_index.py` — **no code changes**; `type` metadata is written generically from `cap.type`. Update the stale docstring at line 74 enumerating types.
- `tools/search.py` — add `"hook"` to `VALID_TYPES` (line 16); update the tool docstring prose (lines 25, 34) so MCP clients see `hook` as a valid filter value.

### 2.7. Server: Prose/Telemetry Consistency

- `server.py:54–58` — FastMCP `instructions` string: advertise hooks ("skills, agents, tools, and hooks").
- `telemetry.py:91` — `track_install` docstring: add `"hook"` to the enumerated types. No code change; the telemetry `capability_type` string is `"hook"` (matching the registry type, unlike the legacy `"tool"`/`"mcp_server"` mismatch).
- `__init__.py:3` package docstring prose.

### 2.8. CLI: Command Registration

**Modified file:** `cli/src/cli.ts` — the three hardcoded spots:
- `USAGE` string (lines 6–11): add `hook <names...>` line.
- Unknown-command guard (line 23): add `hook`.
- `switch` dispatch: add `case "hook": await installHooks(names)`.

### 2.9. CLI: Types

**Modified file:** `cli/src/lib/types.ts`

- `HookDefinition`: `{ event: string; matcher?: string; timeout?: number }`.
- `HookFrontmatter`: `{ name: string; description: string; hooks: HookDefinition[] }`.
- `InstallResult` is reused unchanged — the existing `"skipped"` status covers silent skips.

### 2.10. CLI: Hook Install Command

**New file:** `cli/src/commands/hook.ts` — `installHooks(names)`, modeled on `agent.ts`'s two-phase structure:

**Phase 1 — Install hook directories:**
1. `downloadBundle(serverUrl + "/bundle/hooks", names)` → temp dir with `<name>/` directories.
2. Per requested name: not in archive → `"not-found"`; `.claude/hooks/<name>/` exists → `"skipped"` (silent, files untouched); else `fs.cpSync(recursive)` → `"installed"`. `fs.cpSync` and `tar.extract` both preserve mode bits, so entrypoints stay executable end-to-end.

**Phase 2 — Settings injection (runs for both `"installed"` and `"skipped"` hooks, per the repair requirement):**
1. Read `.claude/hooks/<name>/HOOK.md`, `parseFrontmatter()` (existing util — nested lists already supported) → `HookFrontmatter`.
2. Per entry, construct the settings group: `{ matcher?, hooks: [{ type: "command", command: "$CLAUDE_PROJECT_DIR/.claude/hooks/<name>/<name>.sh", timeout? }] }` — `matcher`/`timeout` keys omitted when unset; `$CLAUDE_PROJECT_DIR` is a literal string Claude Code expands at runtime.
3. Call `mergeHookEntries(settingsPath, event, groups)` from the new merge module (§2.11); count added vs skipped entries.
4. Unparseable/invalid frontmatter → graceful degradation: files stay installed, a warning appears in the summary, no settings change (mirrors `agent.ts` null-frontmatter handling).

**Summary output:** hooks installed / skipped (files exist) / settings entries added / settings entries skipped (already present) / not found. **Exit code:** `1` only when some hook is `"not-found"` (the `agent.ts` rule) — skips are success, unlike `skill.ts`'s conflict-is-failure behavior.

### 2.11. CLI: Settings Merge Module

**New file:** `cli/src/lib/settings-merge.ts` — modeled on `json-merge.ts` but with nested, dedupe-not-throw semantics:

- **Read/create:** parse `.claude/settings.json`; `ENOENT` → start from `{}`; malformed JSON → `throw CliError("Error: .claude/settings.json contains malformed JSON.")` (never overwrite a file we can't parse).
- **Structure guard:** ensure `parsed.hooks` and `parsed.hooks[<Event>]` are the expected object/array shapes before touching them; all other top-level keys pass through untouched (whole object round-tripped).
- **Dedupe rule (append-new-group, global dedupe):** an entry is *present* when any existing group under the same event has the same `matcher` (both-absent counts as equal) and its inner `hooks` array contains a command equal to the derived entrypoint path. Present → skip; otherwise **append a fresh group** — user-authored groups are never mutated.
- **Write:** `JSON.stringify(parsed, null, 2) + "\n"` (same normalization as `.mcp.json`; content preserved, whitespace normalized).

### 2.12. Registry Seed: `docs-that-work-gate`

One real hook validates the pipeline end-to-end and satisfies the real-registry smoke tests:

- `registry/hooks/docs-that-work-gate/HOOK.md` — frontmatter (`event: PreToolUse`, `matcher: Bash`), body with description, the gating rules, and manual injection instructions.
- `registry/hooks/docs-that-work-gate/docs-that-work-gate.sh` — executable, pure POSIX sh + git; gates `git commit` commands on documentation freshness. Pending changes (`git status --porcelain`: staged + unstaged + untracked) are mapped to their owning docs — the nearest ancestor directory containing `CLAUDE.md`/`README.md` (repo root only owns root-level files). If an owning doc has no pending changes of its own, the hook exits 2 with instructions for Claude to refresh it via the `docs-that-work` skill (`registry/skills/docs-that-work/`) and retry. Loop prevention: updated docs count as fresh; a checksum marker in `.git/docs-that-work-gate.ok` lets an unchanged retry pass ("docs already accurate"); doc-only change sets are never gated. Behavior is covered by `server/tests/test_docs_that_work_gate_hook.py`, which executes the script in scratch git repositories.

---

## 3. Impact and Risk Analysis

### System Dependencies

- **Search index / telemetry / validate CLI:** no code changes — all generic once the type literal is expanded.
- **`awos:hire` (provectus/awos repo):** downstream consumer; picks hooks up via search + CLI once this ships. No coupling in this repo.
- **Functional spec amendment:** the entrypoint convention drops the `command` frontmatter field from the approved functional spec; `functional-spec.md` is updated in the same change.

### Potential Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Executable bit lost anywhere in the chain (git → tar → extract → copy) leaves hooks silently broken | Validator enforces the exec bit at the source; `tarfile` writes modes from disk; node-tar extraction and `fs.cpSync` preserve modes. Add an explicit CLI regression test asserting `mode & 0o111` round-trips (nothing currently exercises non-`.md` bundle content). |
| Bundle/validator/CLI disagree on directory layout → files silently dropped from archives | Single derived-command convention plus shared layout constants (`_ALLOWED_HOOK_DIRS`, entrypoint name rule) used by both `server.py` and `validate/__init__.py` — same drift-prevention pattern as skills. |
| Corrupting a user's `settings.json` | Never write when parse fails (hard error); whole-object round-trip preserves unknown keys; append-only merge never mutates existing groups; idempotency covered by tests. Formatting is normalized to 2-space JSON — same accepted behavior as `.mcp.json`. |
| Locally edited/broken `HOOK.md` breaks Phase 2 on repair runs | Graceful degradation: unparseable frontmatter → warning + no settings change, files untouched. |
| Windows: `.sh` entrypoints assume a POSIX shell | Accepted for v1 (Claude Code hooks run via shell; Git Bash covers most Windows setups). Documented per-hook; revisit if demand appears. |
| Multi-event hooks share one entrypoint | By design — entrypoint branches on `hook_event_name` from stdin JSON. Documented in `HOOK.md` authoring guidance (`docs/CONTRIBUTING.md`). |

---

## 4. Testing Strategy

### Server (Python — pytest)

| Area | Test File | Tests |
|------|-----------|-------|
| `HookMetadata`/`HookEntry` models | `test_validate.py` | Valid metadata; missing name; invalid event literal; empty hooks list; negative timeout; extra fields rejected |
| `_load_hooks()` | `test_registry.py` | New `_write_hook` helper; correct parsing; skip without description; `type="hook"`; mixed-types test extended; real-registry smoke test includes `"hook"` |
| `validate_hooks()` | `test_validate.py` | Valid hook passes; dir-name mismatch; empty body; **missing entrypoint fails; non-executable entrypoint fails**; unexpected root file fails; bad `scripts/` extension fails; `validate_registry` count assertions updated 3→4 |
| `POST /bundle/hooks` | `test_bundle.py` | tar.gz contains `<name>/HOOK.md` + entrypoint (+ scripts); **entry mode carries exec bit**; partial/not-found; 400 on >20 or bad names |
| Search | `test_search_index.py`, `test_search_tool.py` | `type="hook"` sample + filter test; real-registry search returns `docs-that-work-gate` |
| Telemetry | `test_bundle_telemetry.py`, `test_telemetry.py` | `track_install(name, "hook")` called per bundled hook |

### CLI (TypeScript — vitest)

| Area | Test File | Tests |
|------|-----------|-------|
| Hook install Phase 1 | `commands/__tests__/hook.test.ts` | Install to `.claude/hooks/<name>/`; silent skip on existing dir (exit 0); not-found (exit 1); dir creation; **exec-bit round-trip** |
| Settings injection Phase 2 | `commands/__tests__/hook.test.ts` | Creates `settings.json` when missing; preserves unrelated keys/hooks; injects on repair (files skipped, entry missing); full idempotency (re-run → all skipped, file byte-identical); matcher-less events; timeout propagation; unparseable frontmatter warning |
| Merge module | `lib/__tests__/settings-merge.test.ts` | Fresh file; append vs dedupe (same/different matcher, same/different command, both-absent matcher); malformed JSON error; structure-guard on weird existing shapes; formatting |
| Router | existing conventions | `hook` in usage/guard/dispatch |

---

## Files Changed Summary

| File | Action |
|------|--------|
| `registry/hooks/docs-that-work-gate/` | **Create** (HOOK.md + executable entrypoint) |
| `server/src/awos_recruitment_mcp/models/hook_metadata.py` | **Create** |
| `server/src/awos_recruitment_mcp/models/capability.py`, `models/__init__.py` | Modify — type literal, exports |
| `server/src/awos_recruitment_mcp/registry.py` | Modify — `_load_hooks()`, `resolve_hook_paths()` |
| `server/src/awos_recruitment_mcp/validate/__init__.py` | Modify — `validate_hooks()`, hook layout constants |
| `server/src/awos_recruitment_mcp/server.py` | Modify — `/bundle/hooks` route, instructions prose |
| `server/src/awos_recruitment_mcp/tools/search.py` | Modify — `VALID_TYPES`, docstring |
| `server/src/awos_recruitment_mcp/telemetry.py`, `search_index.py`, `__init__.py` | Modify — docstrings only |
| `cli/src/cli.ts` | Modify — usage, guard, dispatch |
| `cli/src/commands/hook.ts` | **Create** |
| `cli/src/lib/settings-merge.ts` | **Create** |
| `cli/src/lib/types.ts` | Modify — `HookFrontmatter`, `HookDefinition` |
| `docs/CONTRIBUTING.md` | Modify — hook authoring guide |
| `context/spec/008-hooks-support/functional-spec.md` | Modify — entrypoint convention amendment |
| Server tests (7 files) | Modify — hook cases |
| CLI tests (2 new, 1 modified) | **Create** / Modify |
