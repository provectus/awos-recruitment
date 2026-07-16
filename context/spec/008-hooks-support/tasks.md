# Tasks: Claude Code Hooks Support

---

## Slice 1: Hooks are discoverable — seed hook loads and appears in semantic search

After this slice, `registry/hooks/protect-env-files/` exists, the server loads it with `type="hook"`, and `search_capabilities` returns it (including with the `type="hook"` filter). Bundling and validation come later; the server remains fully functional.

- [x] **Sub-task 1.1:** Create the seed hook `registry/hooks/protect-env-files/`: `HOOK.md` (frontmatter: `name`, `description`, `hooks: [{event: PreToolUse, matcher: Edit|Write, timeout: 10}]`; body: what it does + manual injection instructions with the exact `settings.json` fragment) and executable `protect-env-files.sh` (reads tool-call JSON from stdin, exits 2 to block when the target path matches `.env` patterns). **[Agent: python-expert]**
- [x] **Sub-task 1.2:** Create `models/hook_metadata.py` with `HookEntry` (event `Literal` of the nine names, `matcher`, `timeout`, `extra="forbid"`) and `HookMetadata` (`name` kebab-case pattern, `description` min_length=1, `hooks` min_length=1, `extra="forbid"`); export from `models/__init__.py`; expand `RegistryCapability.type` literal in `models/capability.py` to include `"hook"`. **[Agent: python-expert]**
- [x] **Sub-task 1.3:** Add `_load_hooks(root)` to `registry.py` (mirror `_load_skills`: scan `hooks/*/HOOK.md`, skip on missing/blank name/description, emit `type="hook"`), wire into `load_registry()`, update its docstring. **[Agent: python-expert]**
- [x] **Sub-task 1.4:** Add `"hook"` to `VALID_TYPES` in `tools/search.py`; update the tool docstring prose (lines 25, 34), the stale `search_index.py` docstring (line 74), the FastMCP `instructions` string in `server.py`, and the package docstring in `__init__.py`. **[Agent: python-expert]**
- [x] **Sub-task 1.5:** Add tests: `HookMetadata`/`HookEntry` model cases in `test_validate.py` (valid, missing name, invalid event, empty hooks list, negative timeout, extra fields); `_write_hook` helper + loader cases in `test_registry.py` (parsing, skip-without-description, mixed-types extended, real-registry smoke includes `"hook"`); `type="hook"` sample + filter tests in `test_search_index.py` and `test_search_tool.py` (real-registry search returns `protect-env-files`). **[Agent: python-expert]**
- [x] **Sub-task 1.6:** Run `just test -v`. Then start the server (`just serve`) and verify via an MCP client call that `search_capabilities("block edits to env files", type="hook")` returns `protect-env-files`. **[Agent: qa-tester]**
- [x] **Sub-task 1.7:** Git commit. **[Agent: general-purpose]**

---

## Slice 2: Hooks are validated — `just validate-registry` enforces the hook schema and layout

After this slice, CI blocks invalid hook definitions: bad frontmatter, name mismatch, empty body, missing/non-executable entrypoint, unexpected files, bad `scripts/` extensions.

- [x] **Sub-task 2.1:** Add hook layout constants to `validate/__init__.py` (`_ALLOWED_HOOK_DIRS = {"scripts"}`; allowed root files: `HOOK.md`, `README.md`, `<name>.sh`) and implement `validate_hooks(registry_path)` mirroring `validate_skills`: frontmatter → `HookMetadata`, dir-name match, non-empty body, entrypoint exists **and carries the executable bit** (`mode & 0o111`), layout allowlist reusing `_ALLOWED_SCRIPT_EXTENSIONS` for `scripts/`. Wire into `validate_registry()`. **[Agent: python-expert]**
- [x] **Sub-task 2.2:** Add `validate_hooks` tests in `test_validate.py` (`_make_hook_dir` helper; valid passes, dir-name mismatch, empty body, missing entrypoint, non-executable entrypoint, unexpected root file, bad `scripts/` extension) and update count assertions (`validate_registry` 3→4 validators, JSON summary totals). **[Agent: python-expert]**
- [x] **Sub-task 2.3:** Run `just test -v` and `just validate-registry` (human + `--format json`). Verify the real seed hook passes and a deliberately broken temp hook fails. **[Agent: qa-tester]**
- [x] **Sub-task 2.4:** Git commit. **[Agent: general-purpose]**

---

## Slice 3: Hooks are downloadable — `POST /bundle/hooks` serves tar.gz bundles with telemetry

After this slice, the server ships hook directories (exec bit intact) and emits `capability_installed` events with `type="hook"`.

- [x] **Sub-task 3.1:** Add `resolve_hook_paths(names, registry_path)` to `registry.py` (mirror `resolve_skill_paths`, directory check). **[Agent: python-expert]**
- [x] **Sub-task 3.2:** Add the `POST /bundle/hooks` route to `server.py` mirroring `/bundle/skills`: `BundleRequest` validation (400 on failure), dedupe, resolve, `track_install(name, "hook")` per found hook, archive `<name>/HOOK.md` + `<name>/<name>.sh` + `scripts/` files filtered by `_ALLOWED_SCRIPT_EXTENSIONS`, return `application/gzip`. Update the `track_install` docstring in `telemetry.py`. **[Agent: python-expert]**
- [x] **Sub-task 3.3:** Add tests: `/bundle/hooks` cases in `test_bundle.py` (archive contents incl. **entry mode carries exec bit**, partial/not-found, 400 on >20 or invalid names); telemetry assertions in `test_bundle_telemetry.py` and `test_telemetry.py` (`track_install(name, "hook")`). **[Agent: python-expert]**
- [x] **Sub-task 3.4:** Run `just test -v`. Then start the server and `curl -X POST /bundle/hooks` with `protect-env-files`; extract the tar.gz and verify file layout and `ls -l` shows the entrypoint executable. **[Agent: qa-tester]**
- [x] **Sub-task 3.5:** Git commit. **[Agent: general-purpose]**

---

## Slice 4: Hooks install locally — CLI `hook` command places files into `.claude/hooks/`

After this slice, `npx @provectusinc/awos-recruitment hook protect-env-files` downloads and installs the hook directory (silent skip on existing, exit 1 only on not-found). Settings injection lands in Slice 5.

- [x] **Sub-task 4.1:** Register the `hook` subcommand in `cli/src/cli.ts` (USAGE line, unknown-command guard, `case "hook"`); add `HookDefinition`/`HookFrontmatter` to `lib/types.ts`. **[Agent: typescript-expert]**
- [x] **Sub-task 4.2:** Create `cli/src/commands/hook.ts` with Phase 1 of `installHooks(names)`: `downloadBundle(.../bundle/hooks)`, per-name not-found / skipped (existing dir, silent) / installed (`fs.cpSync` recursive), summary print, exit 1 only on not-found (the `agent.ts` rule). **[Agent: typescript-expert]**
- [x] **Sub-task 4.3:** Add Phase-1 tests in `commands/__tests__/hook.test.ts` (vitest conventions: mocked `downloadBundle`, real temp dirs, cwd spy): install, silent skip exit 0, not-found exit 1, `.claude/hooks/` creation, and the **exec-bit round-trip regression test** (tar entry mode `0o755` → extract → copy → `mode & 0o111`). **[Agent: typescript-expert]**
- [x] **Sub-task 4.4:** Run `just test-cli` and `just build-cli`. Then with the server running locally, run the built CLI (`AWOS_SERVER_URL=http://localhost:8000`) in a temp project and verify `.claude/hooks/protect-env-files/` contents and executable entrypoint; re-run to confirm silent skip. **[Agent: qa-tester]**
- [x] **Sub-task 4.5:** Git commit. **[Agent: general-purpose]**

---

## Slice 5: Hooks activate — CLI injects derived entries into `.claude/settings.json`

After this slice, the full flow works: install → inject → hook is live in Claude Code. Both phases idempotent; repair re-injects settings for skipped hooks.

- [x] **Sub-task 5.1:** Create `cli/src/lib/settings-merge.ts`: read/create `settings.json` (`ENOENT` → `{}`; malformed → `CliError`, never overwrite), structure guards, append-new-group merge with global dedupe (same event + same matcher incl. both-absent + same command → skip), write `JSON.stringify(parsed, null, 2) + "\n"`. **[Agent: typescript-expert]**
- [x] **Sub-task 5.2:** Add Phase 2 to `commands/hook.ts`: for installed **and** skipped hooks, parse `HOOK.md` frontmatter, build groups with the derived command `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>/<name>.sh` (omit unset `matcher`/`timeout`), merge per event, count added/skipped entries; graceful warning on unparseable frontmatter; extend the summary. **[Agent: typescript-expert]**
- [x] **Sub-task 5.3:** Add tests: `lib/__tests__/settings-merge.test.ts` (fresh file, append vs dedupe matrix, malformed JSON, structure guards, formatting) and Phase-2 cases in `hook.test.ts` (creates settings.json, preserves unrelated keys/hooks, repair injection, byte-identical idempotency, matcher-less events, timeout propagation, frontmatter warning). **[Agent: typescript-expert]**
- [x] **Sub-task 5.4:** Run `just test-cli` and `just build-cli`. End-to-end in a temp project against the local server: fresh install (settings.json created), re-run (all skipped, file unchanged), delete the settings entry and re-run (repaired), pre-seed an unrelated hook in settings.json (preserved). Optionally verify the live hook blocks an `.env` edit in a Claude Code session. **[Agent: qa-tester]**
- [x] **Sub-task 5.5:** Git commit. **[Agent: general-purpose]**

---

## Slice 6: Hooks are documented — contributor guide and user-facing docs

After this slice, contributors know how to author hooks and users see the `hook` command.

- [ ] **Sub-task 6.1:** Add a hook authoring section to `docs/CONTRIBUTING.md`: directory layout, frontmatter schema, entrypoint convention (derived command, `hook_event_name` branching for multi-event hooks), injection-instructions requirement, POSIX-shell note. **[Agent: general-purpose]**
- [ ] **Sub-task 6.2:** Update the root `README.md` CLI command table with `hook <names...>` and an example. **[Agent: general-purpose]**
- [ ] **Sub-task 6.3:** Full regression pass: `just test -v`, `just test-cli`, `just validate-registry`. **[Agent: qa-tester]**
- [ ] **Sub-task 6.4:** Git commit. **[Agent: general-purpose]**
