# Functional Specification: Claude Code Hooks Support

- **Roadmap Item:** Support Claude Code hooks in the registry and installer — index and serve hook definitions with structured metadata, install discovered hooks into the project, and inject their configuration into `.claude/settings.json`.
- **Status:** Approved
- **Author:** Andrey Nenashev

---

## 1. Overview and Rationale (The "Why")

The AWOS Recruitment system enables teams to centrally manage and distribute **skills**, **MCP server definitions**, and **agents** through a full pipeline: a Git-managed registry, semantic search, server-side bundling, and CLI installation. However, **Claude Code hooks** — event-driven commands that run automatically at lifecycle points (before/after tool use, on session start, etc.) — are not yet part of this pipeline.

Hooks are the primary mechanism for enforcing team-wide guardrails and automations (e.g., "block edits to `.env` files", "run the linter after every edit", "notify on session end"). Without registry support, each developer must hand-craft hook scripts and manually edit `.claude/settings.json` — an error-prone process that leads to inconsistent guardrails across a team, exactly the problem AWOS Recruitment exists to solve.

Hooks differ from existing capability types in one important way: installation is not just a file drop. A hook consists of (a) optional script files placed in the project and (b) a configuration entry that must be **merged into `.claude/settings.json`** so Claude Code activates it. Each hook must therefore carry its own injection documentation, and the installer must perform the settings merge deterministically.

**Success looks like:** A developer (or the `awos:hire` flow) searches for a guardrail (e.g., "protect env files"), discovers a hook in the registry, installs it with a single CLI command, and the hook is immediately active — script files in place, `.claude/settings.json` updated, zero manual file or JSON editing.

---

## 2. Functional Requirements (The "What")

### 2.1. Hook Registry & Indexing

- The Git-managed registry must support a new `registry/hooks/` directory containing hook definitions.
- Each hook is a **directory** at `registry/hooks/<name>/` (mirroring the skill convention) containing:
  - `HOOK.md` (required) — metadata frontmatter plus documentation body.
  - `<name>.sh` (required) — the executable **entrypoint script**. The command injected into `.claude/settings.json` is always the derived path `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>/<name>.sh`; hooks never declare free-form command strings. Multi-event hooks branch inside the entrypoint on the `hook_event_name` field Claude Code passes via stdin JSON.
  - `scripts/` (optional) — helper files used by the entrypoint.
- `HOOK.md` frontmatter fields:
  - `name` (required): kebab-case identifier, 1–64 characters, must match the directory name.
  - `description` (required): non-empty string describing what the hook does and when it fires.
  - `hooks` (required): a non-empty list of hook entries, each with:
    - `event` (required): a valid Claude Code hook event (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Notification`, `Stop`, `SubagentStop`, `PreCompact`, `SessionStart`, `SessionEnd`).
    - `matcher` (optional): tool-name matcher string (e.g., `Edit|Write`).
    - `timeout` (optional): per-command timeout in seconds.
- The `HOOK.md` body must document:
  - What the hook does and why a team would want it.
  - **Injection instructions:** how to add this hook's configuration to `.claude/settings.json` manually — the exact JSON fragment and where it goes. This serves as human-readable documentation and as a fallback for AI-driven or manual injection when the CLI is not used.
- The registry loader must scan `registry/hooks/` and produce capabilities with `type="hook"`.
- Hooks must be embedded and indexed in the search index alongside skills, MCP servers, and agents.
- The existing `search_capabilities` MCP tool must return hooks in search results using the **same result shape** as other capability types (name, description, score), and must accept `type="hook"` as a filter value.

  **Acceptance Criteria:**
  - [ ] A hook directory placed in `registry/hooks/` with a valid `HOOK.md` is loaded by the registry loader with `type="hook"`.
  - [ ] Hooks appear in semantic search results when a relevant natural language query is submitted (e.g., "block edits to env files" returns `protect-env-files`).
  - [ ] Filtering by `type="hook"` returns only hook results.
  - [ ] Hooks without a description are silently skipped during loading (consistent with skills).

### 2.2. Hook Metadata Validation

- A hook metadata schema must be defined and enforced by the registry validation CLI and CI.
- Validation must fail for: missing/malformed `name`, name–directory mismatch, empty `description`, missing or empty `hooks` list, or an entry with an unknown `event`.
- The entrypoint script `<name>.sh` must exist in the hook's registry directory and be executable; validation fails otherwise.
- Validation behavior must be consistent with the existing skill, MCP, and agent validation pipeline (same CLI, same CI workflow, same output formats).

  **Acceptance Criteria:**
  - [ ] A valid hook (correct frontmatter, valid events, existing executable entrypoint) passes `just validate-registry`.
  - [ ] A hook with an unknown `event` value fails validation.
  - [ ] A hook whose entrypoint script `<name>.sh` is missing or not executable fails validation.
  - [ ] A hook with an empty `hooks` list fails validation.
  - [ ] CI blocks merges that introduce invalid hook definitions.

### 2.3. Hook Bundling

- The server must expose a new endpoint `POST /bundle/hooks` that accepts a list of hook names and returns a tar.gz archive containing the corresponding hook directories (including `HOOK.md` and all script files).
- The request body must follow the same validation rules as existing bundle endpoints (1–20 names, kebab-case pattern).
- If a requested hook is not found in the registry, it is excluded from the archive (not an error), and the CLI handles reporting.

  **Acceptance Criteria:**
  - [ ] `POST /bundle/hooks` with valid hook names returns a tar.gz archive containing the requested hook directories with all their files.
  - [ ] Requesting a non-existent hook name does not cause a server error; the name is simply absent from the archive.
  - [ ] The request is rejected if it contains more than 20 names or names with invalid format.

### 2.4. Hook Installation via CLI

- The CLI must support a new command: `npx @provectusinc/awos-recruitment hook <name1> [name2] ...`.
- The command performs two steps per hook:
  1. **File installation:** download the hook bundle and install the hook directory to `.claude/hooks/<name>/` (creating parent directories as needed). If the directory already exists, it is **skipped silently** — files are left untouched.
  2. **Settings injection:** merge each of the hook's entries into `.claude/settings.json` under `hooks.<Event>`, constructing the entry from the frontmatter (`matcher`, `timeout`) with the command derived as `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>/<name>.sh`. The merge must:
     - Create `.claude/settings.json` if it does not exist.
     - Preserve all existing content of the file (other settings keys, other hooks, formatting as valid JSON).
     - **Skip silently** any entry already present — an entry is considered present when an existing entry under the same event has the same `matcher` and `command`.
- Settings injection is performed even when file installation was skipped (so a hook whose files exist but whose settings entry was removed can be repaired), and file installation is performed even if all settings entries already exist. Both steps are independently idempotent.
- The CLI must print a summary showing:
  - Hooks installed (files).
  - Hooks skipped (files already exist).
  - Settings entries added.
  - Settings entries skipped (already present).
  - Hooks not found in the registry.

  **Acceptance Criteria:**
  - [ ] Running `npx @provectusinc/awos-recruitment hook protect-env-files` installs the directory to `.claude/hooks/protect-env-files/` and adds the corresponding entries under `hooks.PreToolUse` in `.claude/settings.json`.
  - [ ] If `.claude/settings.json` does not exist, it is created containing only the injected hook configuration.
  - [ ] If `.claude/settings.json` exists with unrelated settings and hooks, those are preserved unchanged after injection.
  - [ ] Re-running the same install command changes nothing and reports all items as skipped (idempotent).
  - [ ] If the hook files exist but the settings entry is missing, re-running the command re-injects the settings entry.
  - [ ] If a requested hook name does not exist in the registry, it is reported as "not found" in the summary.
  - [ ] Installed scripts retain executable permissions.

### 2.5. Usage Telemetry

- Hook capabilities must participate in the existing telemetry pipeline (spec 007) consistently with other types:
  - Search events involving hooks are captured as they are today (no special handling required beyond the new type value).
  - Hook installations via `POST /bundle/hooks` emit install events with `type="hook"`.

  **Acceptance Criteria:**
  - [ ] A `POST /bundle/hooks` request emits an install telemetry event per requested hook, consistent with the existing bundle telemetry behavior.

---

## 3. Scope and Boundaries

### In-Scope

- Hook catalog structure in the Git-managed registry (`registry/hooks/<name>/` directories).
- Hook metadata schema definition and CI validation, including entrypoint existence and executability checks.
- Registry loader extension to scan and index hooks.
- Semantic search indexing and retrieval for hooks (`type="hook"` filter).
- Server-side bundle endpoint for hooks (`POST /bundle/hooks`).
- CLI `hook` command: file installation into `.claude/hooks/` plus deterministic merge into `.claude/settings.json`.
- Per-hook injection documentation in `HOOK.md` (manual/AI-driven fallback path).
- Install telemetry for hooks.
- At least one real hook published in the registry to validate the end-to-end flow.

### Out-of-Scope

- **`awos:hire` command changes** — `awos:hire` lives in the separate [provectus/awos](https://github.com/provectus/awos) repository. Once hooks are searchable and installable here, `awos:hire` picks them up in that repo's own change (this spec is a dependency of that work, not a container for it).
- Injection into `.claude/settings.local.json` or user-level (`~/.claude`) settings — the target is the shared project `.claude/settings.json` only.
- A hook uninstall/removal command (removing settings entries and files).
- Hook versioning or upgrade-in-place mechanisms (installs never overwrite existing files).
- Security scanning or sandboxing of hook scripts (registry curation via PR review is the control).
- Hook authoring, publishing, or update workflows (capabilities are managed directly in Git).
- A web UI or dashboard for browsing hooks.
- Support for plugin-style hooks (`hooks/hooks.json` in Claude Code plugins) — only project-settings hooks are covered.
